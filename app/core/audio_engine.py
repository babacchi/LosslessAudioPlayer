"""Audiophile bit-perfect audio playback engine with direct DAC routing."""
import platform
import threading
import time
from typing import Optional, List
import numpy as np
import sounddevice as sd
import soundfile as sf
from PySide6.QtCore import QObject, Signal, QTimer

from app.core.models import Track, AudioDevice


class AudioEngineSignals(QObject):
    track_started = Signal(object)              # Track
    playback_state_changed = Signal(bool, bool) # is_playing, is_paused
    position_updated = Signal(float, float)     # current_seconds, total_seconds
    track_ended = Signal()
    device_changed = Signal(object)             # AudioDevice
    bit_perfect_changed = Signal(bool)          # is_bit_perfect
    error_occurred = Signal(str)                # error message


class AudioEngine:
    def __init__(self):
        self.signals = AudioEngineSignals()
        self.lock = threading.RLock()

        # Playback state
        self.current_track: Optional[Track] = None
        self.is_playing: bool = False
        self.is_paused: bool = False
        self.is_bit_perfect: bool = True  # Default to Bit-Perfect / Direct Mode
        self.volume: float = 1.0          # 0.0 to 1.0 (Locked to 1.0 in bit-perfect mode)

        # Audio stream state
        self.selected_device_index: Optional[int] = None
        self.stream: Optional[sd.OutputStream] = None
        self.snd_file: Optional[sf.SoundFile] = None
        self.current_frame: int = 0
        self.total_frames: int = 0
        self.sample_rate: int = 44100
        self.channels: int = 2
        self._eof_reached: bool = False

        # Gapless playback state
        self.gapless_enabled: bool = True
        self.next_track: Optional[Track] = None
        self.next_snd_file: Optional[sf.SoundFile] = None
        self._gapless_switched_track: Optional[Track] = None

        # Timer for UI position updates
        self._position_timer = QTimer()
        self._position_timer.setInterval(200)  # 5 times per second
        self._position_timer.timeout.connect(self._emit_position)

    def get_available_devices(self) -> List[AudioDevice]:
        """Query and return all output audio devices (DACs, audio interfaces, speakers)."""
        devices = []
        try:
            device_list = sd.query_devices()
            default_out = sd.default.device[1]

            hostapis = {h["name"]: h["name"] for h in sd.query_hostapis()}

            for idx, dev in enumerate(device_list):
                if dev.get("max_output_channels", 0) > 0:
                    api_name = hostapis.get(sd.query_hostapis(dev["hostapi"])["name"], "Unknown API")
                    is_default = (idx == default_out)
                    devices.append(AudioDevice(
                        index=idx,
                        name=dev["name"],
                        hostapi_name=api_name,
                        max_output_channels=dev["max_output_channels"],
                        default_samplerate=dev["default_samplerate"],
                        is_default=is_default
                    ))
        except Exception as e:
            self.signals.error_occurred.emit(f"Failed to query audio devices: {str(e)}")
        return devices

    def set_output_device(self, device_index: Optional[int]):
        """Select specific hardware DAC / audio output device."""
        with self.lock:
            self.selected_device_index = device_index
            devices = self.get_available_devices()
            selected_dev = next((d for d in devices if d.index == device_index), None)
            if selected_dev:
                self.signals.device_changed.emit(selected_dev)

            # If playing, re-open stream on new device at current position
            if self.is_playing and self.current_track:
                saved_frame = self.current_frame
                self._stop_stream()
                self._start_stream(start_frame=saved_frame)

    def set_bit_perfect(self, enabled: bool):
        """Toggle Bit-Perfect Direct Mode (locks software volume at 0dB unity gain)."""
        with self.lock:
            self.is_bit_perfect = enabled
            if enabled:
                self.volume = 1.0
            self.signals.bit_perfect_changed.emit(enabled)

    def set_volume(self, vol: float):
        """Set software volume (clamped 0.0 - 1.0). In bit-perfect mode, volume is locked to 1.0."""
        with self.lock:
            if self.is_bit_perfect:
                self.volume = 1.0
            else:
                self.volume = max(0.0, min(1.0, vol))

    def set_gapless_enabled(self, enabled: bool):
        """Toggle gapless playback."""
        old_file = None
        with self.lock:
            self.gapless_enabled = enabled
            if not enabled and self.next_snd_file is not None:
                old_file = self.next_snd_file
                self.next_snd_file = None
                self.next_track = None
        if old_file is not None:
            try:
                old_file.close()
            except Exception:
                pass

    def set_next_track(self, track: Optional[Track]):
        """Pre-buffer next track for true sample-accurate gapless playback."""
        old_file = None
        with self.lock:
            if self.next_snd_file is not None:
                old_file = self.next_snd_file
                self.next_snd_file = None
                self.next_track = None
            gapless_on = self.gapless_enabled
            playing = self.is_playing
            current_sr = self.sample_rate
            current_ch = min(self.channels, 2)

        if old_file is not None:
            try:
                old_file.close()
            except Exception:
                pass

        if not gapless_on or track is None or not playing:
            return

        try:
            next_sf = sf.SoundFile(track.file_path, mode="r")
            # Gapless requires matching hardware nominal sample rate & channel count
            if next_sf.samplerate == current_sr and min(next_sf.channels, 2) == current_ch:
                with self.lock:
                    if self.is_playing and self.gapless_enabled:
                        self.next_snd_file = next_sf
                        self.next_track = track
                    else:
                        next_sf.close()
            else:
                next_sf.close()
        except Exception:
            pass

    def play_track(self, track: Track, start_seconds: float = 0.0):
        """Open audio file and start bit-perfect stream output."""
        self._stop_stream()
        with self.lock:
            try:
                self.current_track = track
                self._eof_reached = False
                self.snd_file = sf.SoundFile(track.file_path, mode="r")
                self.sample_rate = self.snd_file.samplerate
                self.channels = self.snd_file.channels

                # Accurate total_frames from track model (mutagen parsed)
                if track.duration > 0:
                    self.total_frames = int(track.duration * self.sample_rate)
                else:
                    self.total_frames = len(self.snd_file)

                start_frame = int(start_seconds * self.sample_rate)
                if start_frame < self.total_frames:
                    self.current_frame = start_frame
                    self.snd_file.seek(start_frame)
                else:
                    self.current_frame = 0

                self._start_stream(start_frame=self.current_frame)
                self.is_playing = True
                self.is_paused = False
                self._position_timer.start()

                self.signals.track_started.emit(track)
                self.signals.playback_state_changed.emit(True, False)
            except Exception as e:
                self.signals.error_occurred.emit(f"Playback error ({track.title}): {str(e)}")
                self.stop()

    def _audio_callback(self, outdata, frames, time_info, status):
        """High-performance real-time audio callback called by PortAudio thread."""
        with self.lock:
            if not self.is_playing or self.is_paused or self.snd_file is None:
                outdata.fill(0)
                return

            try:
                # Read raw PCM blocks (do NOT use fill_value=0.0 which causes phantom silence at EOF)
                data = self.snd_file.read(frames, dtype="float32")
                read_frames = len(data)
                gapless_switched = False

                # If current track reached EOF and gapless playback is enabled with a compatible next track
                if (
                    read_frames < frames
                    and self.gapless_enabled
                    and self.next_snd_file is not None
                    and self.next_track is not None
                ):
                    needed_frames = frames - read_frames
                    next_data = self.next_snd_file.read(needed_frames, dtype="float32")
                    next_read_frames = len(next_data)

                    def _ensure_2d(arr):
                        if arr.ndim == 1:
                            return arr[:, np.newaxis]
                        return arr

                    if read_frames > 0 and next_read_frames > 0:
                        data = np.vstack((_ensure_2d(data), _ensure_2d(next_data)))
                    elif read_frames > 0:
                        data = _ensure_2d(data)
                    else:
                        data = _ensure_2d(next_data)

                    read_frames = len(data)

                    # Seamlessly swap current stream file handle to next track
                    try:
                        self.snd_file.close()
                    except Exception:
                        pass
                    self.snd_file = self.next_snd_file
                    self.next_snd_file = None

                    switched_track = self.next_track
                    self.current_track = switched_track
                    self.next_track = None
                    self.current_frame = next_read_frames
                    if switched_track.duration > 0:
                        self.total_frames = int(switched_track.duration * self.sample_rate)
                    else:
                        self.total_frames = len(self.snd_file)

                    gapless_switched = True
                    self._gapless_switched_track = switched_track

                if read_frames == 0:
                    outdata.fill(0)
                    self._eof_reached = True
                    raise sd.CallbackStop

                # Handle channel mapping (e.g. mono to stereo or multichannel)
                out_channels = outdata.shape[1]
                if data.ndim == 1:
                    data = np.tile(data[:, np.newaxis], (1, out_channels))
                elif data.shape[1] != out_channels:
                    if data.shape[1] == 1:
                        data = np.repeat(data, out_channels, axis=1)
                    elif data.shape[1] > out_channels:
                        data = data[:, :out_channels]
                    else:
                        pad = np.zeros((read_frames, out_channels - data.shape[1]), dtype=np.float32)
                        data = np.hstack((data, pad))

                # Apply volume only if NOT in bit-perfect direct mode
                if not self.is_bit_perfect and self.volume < 1.0:
                    data = data * self.volume

                if read_frames < frames:
                    outdata[:read_frames] = data
                    outdata[read_frames:].fill(0)
                    if not gapless_switched:
                        self.current_frame += read_frames
                    self._eof_reached = True
                    raise sd.CallbackStop
                else:
                    outdata[:] = data
                    if not gapless_switched:
                        self.current_frame += frames

            except sd.CallbackStop:
                raise
            except Exception:
                outdata.fill(0)
                self._eof_reached = True
                raise sd.CallbackStop

    def _sync_macos_dac_sample_rate(self):
        """Automatically switch macOS DAC hardware clock to match source file sample rate."""
        if platform.system() != "Darwin":
            return
        try:
            from app.core.macos_audio import find_coreaudio_device_id, set_device_sample_rate
            dev_info = None
            if self.selected_device_index is not None:
                dev_info = sd.query_devices(self.selected_device_index)
            else:
                default_idx = sd.default.device[1]
                if default_idx is not None and default_idx >= 0:
                    dev_info = sd.query_devices(default_idx)

            if dev_info:
                dev_name = dev_info.get("name", "")
                ca_id = find_coreaudio_device_id(dev_name)
                if ca_id is not None:
                    set_device_sample_rate(ca_id, float(self.sample_rate))
        except Exception:
            pass

    def get_current_hardware_sample_rate(self) -> Optional[float]:
        """Returns the actual hardware clock rate from the DAC."""
        if platform.system() == "Darwin":
            try:
                from app.core.macos_audio import find_coreaudio_device_id, get_device_sample_rate
                dev_info = None
                if self.selected_device_index is not None:
                    dev_info = sd.query_devices(self.selected_device_index)
                else:
                    default_idx = sd.default.device[1]
                    if default_idx is not None and default_idx >= 0:
                        dev_info = sd.query_devices(default_idx)
                if dev_info:
                    ca_id = find_coreaudio_device_id(dev_info.get("name", ""))
                    if ca_id is not None:
                        return get_device_sample_rate(ca_id)
            except Exception:
                pass
        return None

    def _start_stream(self, start_frame: int = 0):
        # 1. On macOS: Hardware Clock switching for Bit-Perfect Direct Mode
        if platform.system() == "Darwin" and self.is_bit_perfect:
            self._sync_macos_dac_sample_rate()

        extra_settings = None
        # 2. On Windows, activate WASAPI Exclusive Mode for Bit-Perfect DAC output
        if platform.system() == "Windows" and hasattr(sd, "WasapiSettings") and self.is_bit_perfect:
            extra_settings = sd.WasapiSettings(exclusive=True)

        # Buffer size: 2048/4096 frames ensures stable glitch-free lossless playback
        blocksize = 4096

        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=min(self.channels, 2),
            device=self.selected_device_index,
            dtype="float32",
            blocksize=blocksize,
            callback=self._audio_callback,
            extra_settings=extra_settings
        )
        self.stream.start()

    def _stop_stream(self):
        self._position_timer.stop()
        stream_to_close = None
        file_to_close = None
        next_file_to_close = None
        with self.lock:
            self.is_playing = False
            self.is_paused = False
            self._eof_reached = False
            self._gapless_switched_track = None
            if self.stream is not None:
                stream_to_close = self.stream
                self.stream = None
            if self.snd_file is not None:
                file_to_close = self.snd_file
                self.snd_file = None
            if self.next_snd_file is not None:
                next_file_to_close = self.next_snd_file
                self.next_snd_file = None
                self.next_track = None

        # Stop and close stream OUTSIDE self.lock!
        # PortAudio Pa_StopStream waits for active audio callback to return,
        # so callback must be free to acquire self.lock and exit.
        if stream_to_close is not None:
            try:
                stream_to_close.stop()
                stream_to_close.close()
            except Exception:
                pass

        if file_to_close is not None:
            try:
                file_to_close.close()
            except Exception:
                pass

        if next_file_to_close is not None:
            try:
                next_file_to_close.close()
            except Exception:
                pass

    def pause(self):
        with self.lock:
            if self.is_playing and not self.is_paused:
                self.is_paused = True
                self.signals.playback_state_changed.emit(True, True)

    def resume(self):
        with self.lock:
            if self.is_playing and self.is_paused:
                self.is_paused = False
                self.signals.playback_state_changed.emit(True, False)

    def toggle_play_pause(self):
        if not self.is_playing and self.current_track:
            self.play_track(self.current_track, start_seconds=self.current_frame / max(1, self.sample_rate))
        elif self.is_paused:
            self.resume()
        elif self.is_playing:
            self.pause()

    def stop(self):
        self._stop_stream()
        with self.lock:
            self.is_playing = False
            self.is_paused = False
            self.current_frame = 0
            total_dur = self.get_total_duration()
        self.signals.playback_state_changed.emit(False, False)
        self.signals.position_updated.emit(0.0, total_dur)

    def seek(self, seconds: float):
        """Seek to specific position in track (seconds)."""
        with self.lock:
            if self.snd_file is None or self.total_frames == 0:
                return
            target_frame = int(seconds * self.sample_rate)
            target_frame = max(0, min(target_frame, self.total_frames - 1))
            self.current_frame = target_frame
            try:
                self.snd_file.seek(target_frame)
            except Exception:
                pass
        self._emit_position()

    def get_current_time(self) -> float:
        if self.sample_rate > 0:
            return self.current_frame / self.sample_rate
        return 0.0

    def get_total_duration(self) -> float:
        if self.total_frames > 0 and self.sample_rate > 0:
            return self.total_frames / self.sample_rate
        if self.current_track:
            return self.current_track.duration
        return 0.0

    def _emit_position(self):
        should_finish = False
        switched_track = None
        curr = 0.0
        total = 0.0
        with self.lock:
            if not self.is_playing:
                return
            if self._gapless_switched_track is not None:
                switched_track = self._gapless_switched_track
                self._gapless_switched_track = None

            curr = self.get_current_time()
            total = self.get_total_duration()
            if self._eof_reached or (total > 0 and curr >= total - 0.05):
                self._eof_reached = False
                should_finish = True

        if switched_track is not None:
            self.signals.track_started.emit(switched_track)

        self.signals.position_updated.emit(curr, total)
        if should_finish:
            self._on_track_finished()

    def _on_track_finished(self):
        with self.lock:
            if not self.is_playing:
                return
            self.is_playing = False
            self.is_paused = False
            self._eof_reached = False
            self.current_frame = 0

        self._stop_stream()
        self.signals.playback_state_changed.emit(False, False)
        self.signals.track_ended.emit()
