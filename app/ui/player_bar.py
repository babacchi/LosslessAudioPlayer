"""Persistent audiophile playback bar with real-time stream stats and DAC selection."""
import os
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QSlider, QComboBox, QSizePolicy
)
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QFont
from PySide6.QtCore import Qt, Signal

from app.core.models import Track, AudioDevice


class PlayerBar(QFrame):
    play_pause_clicked = Signal()
    prev_clicked = Signal()
    next_clicked = Signal()
    seek_requested = Signal(float)       # target seconds
    volume_changed = Signal(float)       # 0.0 to 1.0
    bit_perfect_toggled = Signal(bool)
    dac_selected = Signal(int)           # device index
    open_dac_settings_requested = Signal()
    shuffle_toggled = Signal(bool)       # is_shuffle
    repeat_mode_changed = Signal(int)    # 0: OFF, 1: ALL, 2: ONE

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PlayerBar")
        self.setFixedHeight(95)

        self.current_track: Optional[Track] = None
        self.total_duration: float = 0.0
        self.is_seeking: bool = False
        self.is_bit_perfect: bool = True
        self.shuffle_enabled: bool = False
        self.repeat_mode: int = 0  # 0: OFF, 1: ALL, 2: ONE

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 8, 16, 8)
        main_layout.setSpacing(16)

        # ==========================================
        # 1. Left Section: Now Playing Cover & Info
        # ==========================================
        left_widget = QWidget()
        left_widget.setFixedWidth(310)
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(54, 54)
        self.cover_label.setStyleSheet("border-radius: 6px; background-color: #1a1e2b;")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_empty_cover()
        left_layout.addWidget(self.cover_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel("再生停止中")
        self.title_label.setObjectName("NowPlayingTitle")
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        info_layout.addWidget(self.title_label)

        self.artist_label = QLabel("楽曲を選択してください")
        self.artist_label.setObjectName("NowPlayingArtist")
        self.artist_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        info_layout.addWidget(self.artist_label)

        # Hi-Res Indicator pill
        self.hires_pill = QLabel("Hi-Res")
        self.hires_pill.setObjectName("HiResBadge")
        self.hires_pill.setVisible(False)
        info_layout.addWidget(self.hires_pill)

        left_layout.addLayout(info_layout)
        main_layout.addWidget(left_widget)

        # ==========================================
        # 2. Center Section: Controls, Seek Bar, Stream Stats
        # ==========================================
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(4)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Transport Controls
        controls_row = QHBoxLayout()
        controls_row.setSpacing(14)
        controls_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Shuffle Button
        self.shuffle_btn = QPushButton("🔀 OFF")
        self.shuffle_btn.setObjectName("ToggleControlBtn")
        self.shuffle_btn.setProperty("active", "false")
        self.shuffle_btn.setToolTip("シャッフル: オフ（クリックしてON）")
        self.shuffle_btn.clicked.connect(self._on_shuffle_clicked)
        controls_row.addWidget(self.shuffle_btn)

        self.prev_btn = QPushButton("⏮")
        self.prev_btn.setObjectName("ControlBtn")
        self.prev_btn.setToolTip("前の曲")
        self.prev_btn.clicked.connect(self.prev_clicked.emit)
        controls_row.addWidget(self.prev_btn)

        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("PlayButton")
        self.play_btn.setToolTip("再生 / 一時停止")
        self.play_btn.clicked.connect(self.play_pause_clicked.emit)
        controls_row.addWidget(self.play_btn)

        self.next_btn = QPushButton("⏭")
        self.next_btn.setObjectName("ControlBtn")
        self.next_btn.setToolTip("次の曲")
        self.next_btn.clicked.connect(self.next_clicked.emit)
        controls_row.addWidget(self.next_btn)

        # Repeat Button
        self.repeat_btn = QPushButton("🔁 OFF")
        self.repeat_btn.setObjectName("ToggleControlBtn")
        self.repeat_btn.setProperty("active", "false")
        self.repeat_btn.setToolTip("リピート: オフ（クリックで全曲リピート）")
        self.repeat_btn.clicked.connect(self._on_repeat_clicked)
        self.repeat_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.repeat_btn.customContextMenuRequested.connect(self._on_repeat_right_clicked)
        controls_row.addWidget(self.repeat_btn)

        center_layout.addLayout(controls_row)

        # Progress / Seek Bar Row
        seek_row = QHBoxLayout()
        seek_row.setSpacing(8)

        self.time_elapsed_label = QLabel("00:00")
        self.time_elapsed_label.setStyleSheet("font-size: 11px; color: #9ca3af; min-width: 38px;")
        seek_row.addWidget(self.time_elapsed_label)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setValue(0)
        self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        seek_row.addWidget(self.seek_slider)

        self.time_total_label = QLabel("00:00")
        self.time_total_label.setStyleSheet("font-size: 11px; color: #9ca3af; min-width: 38px;")
        seek_row.addWidget(self.time_total_label)

        center_layout.addLayout(seek_row)

        # Audiophile Stream Stats text
        self.stream_label = QLabel("DAC出力: 未接続 | サンプルレート: --")
        self.stream_label.setObjectName("StreamInfo")
        self.stream_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.stream_label)

        main_layout.addWidget(center_widget, stretch=1)

        # ==========================================
        # 3. Right Section: DAC / Volume Controls
        # ==========================================
        ctrl_col = QWidget()
        right_layout = QVBoxLayout(ctrl_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # DAC Combo Row
        dac_row = QHBoxLayout()
        dac_row.setSpacing(8)
        dac_label = QLabel("DAC:")
        dac_label.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 600;")
        dac_row.addWidget(dac_label)

        self.dac_combo = QComboBox()
        self.dac_combo.setToolTip("再生DAC / 出力デバイスを選択")
        self.dac_combo.currentIndexChanged.connect(self._on_dac_combo_changed)
        dac_row.addWidget(self.dac_combo)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("ControlBtn")
        self.settings_btn.setToolTip("DAC詳細設定")
        self.settings_btn.clicked.connect(self.open_dac_settings_requested.emit)
        dac_row.addWidget(self.settings_btn)

        right_layout.addLayout(dac_row)

        # Bit-Perfect LED button and Volume Row
        vol_row = QHBoxLayout()
        vol_row.setSpacing(10)

        self.bit_perfect_btn = QPushButton("⚡ BIT-PERFECT")
        self.bit_perfect_btn.setObjectName("BitPerfectBtn")
        self.bit_perfect_btn.setToolTip("ビットパーフェクト直接出力（0dB固定・OSミキサーバイパス）")
        self.bit_perfect_btn.setCheckable(True)
        self.bit_perfect_btn.setChecked(True)
        self.bit_perfect_btn.clicked.connect(self._on_bit_perfect_clicked)
        vol_row.addWidget(self.bit_perfect_btn)

        vol_icon = QLabel("🔊")
        vol_icon.setStyleSheet("color: #9ca3af; font-size: 12px;")
        vol_row.addWidget(vol_icon)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(100)
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.setToolTip("音量 (Bit-Perfect時は100%固定)")
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        self.vol_slider.setEnabled(False)  # Disabled initially because bit-perfect is active
        vol_row.addWidget(self.vol_slider)

        right_layout.addLayout(vol_row)
        main_layout.addWidget(ctrl_col)

        self._update_shuffle_ui()
        self._update_repeat_ui()

    def set_devices(self, devices: List[AudioDevice], selected_index: Optional[int]):
        self.dac_combo.blockSignals(True)
        self.dac_combo.clear()
        selected_row = 0
        for i, dev in enumerate(devices):
            self.dac_combo.addItem(dev.name, dev.index)
            if selected_index is not None and dev.index == selected_index:
                selected_row = i
            elif selected_index is None and dev.is_default:
                selected_row = i
        if devices:
            self.dac_combo.setCurrentIndex(selected_row)
        self.dac_combo.blockSignals(False)
        self._update_stream_info()

    def set_track(self, track: Track):
        self.current_track = track
        self.total_duration = track.duration
        self.title_label.setText(track.title)
        self.title_label.setToolTip(track.title)
        artist_text = f"{track.artist} - {track.album}"
        self.artist_label.setText(artist_text)
        self.artist_label.setToolTip(artist_text)
        self.hires_pill.setVisible(track.is_hires)
        self.time_total_label.setText(track.duration_formatted)
        self.time_elapsed_label.setText("00:00")
        self.seek_slider.setValue(0)
        self._load_cover(track)
        self._update_stream_info()

    def set_playback_state(self, is_playing: bool, is_paused: bool):
        if is_playing and not is_paused:
            self.play_btn.setText("⏸")
        else:
            self.play_btn.setText("▶")

    def update_position(self, current_sec: float, total_sec: float):
        if self.is_seeking:
            return
        self.total_duration = total_sec
        mins = int(current_sec // 60)
        secs = int(current_sec % 60)
        self.time_elapsed_label.setText(f"{mins:02d}:{secs:02d}")

        if total_sec > 0:
            val = int((current_sec / total_sec) * 1000)
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(val)
            self.seek_slider.blockSignals(False)

    def set_bit_perfect_state(self, enabled: bool):
        self.is_bit_perfect = enabled
        self.bit_perfect_btn.setChecked(enabled)
        self.bit_perfect_btn.setProperty("active", "true" if enabled else "false")
        self.bit_perfect_btn.style().unpolish(self.bit_perfect_btn)
        self.bit_perfect_btn.style().polish(self.bit_perfect_btn)

        if enabled:
            self.vol_slider.setEnabled(False)
            self.vol_slider.setValue(100)
        else:
            self.vol_slider.setEnabled(True)
        self._update_stream_info()

    def set_audio_engine(self, audio_engine):
        self.audio_engine = audio_engine

    def _update_stream_info(self):
        dac_name = self.dac_combo.currentText() or "Default DAC"
        if not self.current_track:
            self.stream_label.setText(f"DAC: {dac_name} | スタンバイ")
            return

        t = self.current_track
        sr_khz = f"{t.sample_rate / 1000:g}kHz"

        hw_sr = None
        if hasattr(self, "audio_engine") and self.audio_engine:
            hw_sr = self.audio_engine.get_current_hardware_sample_rate()

        if self.is_bit_perfect:
            if hw_sr and abs(hw_sr - t.sample_rate) < 1.0:
                bp_tag = f" [⚡ BIT-PERFECT: {hw_sr/1000:g}kHz LOCK]"
            elif hw_sr:
                bp_tag = f" [⚡ BIT-PERFECT: {hw_sr/1000:g}kHz]"
            else:
                bp_tag = " [⚡ BIT-PERFECT]"
        else:
            bp_tag = " [DSP Volume]"

        # Format stream string cleanly so it never gets clipped
        short_dac = dac_name[:22] + "..." if len(dac_name) > 22 else dac_name
        self.stream_label.setText(
            f"{t.format} • {sr_khz}/{t.bit_depth}bit • {t.channels}ch{bp_tag} → {short_dac}"
        )
        self.stream_label.setToolTip(
            f"音源フォーマット: {t.format} {sr_khz} / {t.bit_depth}bit ({t.channels}ch)\n"
            f"出力モード: {bp_tag.strip()}\n"
            f"出力DAC: {dac_name}"
        )

    def _update_shuffle_ui(self):
        if self.shuffle_enabled:
            self.shuffle_btn.setText("🔀 ON")
            self.shuffle_btn.setProperty("active", "true")
            self.shuffle_btn.setToolTip("シャッフル: オン（クリックして解除）")
        else:
            self.shuffle_btn.setText("🔀 OFF")
            self.shuffle_btn.setProperty("active", "false")
            self.shuffle_btn.setToolTip("シャッフル: オフ（クリックしてON）")
        self.shuffle_btn.style().unpolish(self.shuffle_btn)
        self.shuffle_btn.style().polish(self.shuffle_btn)

    def _on_shuffle_clicked(self):
        self.shuffle_enabled = not self.shuffle_enabled
        self._update_shuffle_ui()
        self.shuffle_toggled.emit(self.shuffle_enabled)

    def _update_repeat_ui(self):
        if self.repeat_mode == 1:
            self.repeat_btn.setText("🔁 全曲")
            self.repeat_btn.setProperty("active", "true")
            self.repeat_btn.setToolTip("全曲リピート中（クリックで1曲リピート、右クリックで解除）")
        elif self.repeat_mode == 2:
            self.repeat_btn.setText("🔂 1曲")
            self.repeat_btn.setProperty("active", "true")
            self.repeat_btn.setToolTip("1曲リピート中（クリックまたは右クリックで解除）")
        else:
            self.repeat_btn.setText("🔁 OFF")
            self.repeat_btn.setProperty("active", "false")
            self.repeat_btn.setToolTip("リピート: オフ（クリックで全曲リピート）")
        self.repeat_btn.style().unpolish(self.repeat_btn)
        self.repeat_btn.style().polish(self.repeat_btn)

    def _on_repeat_clicked(self):
        # Cycle: 0 (OFF) -> 1 (ALL) -> 2 (ONE) -> 0 (OFF)
        self.repeat_mode = (self.repeat_mode + 1) % 3
        self._update_repeat_ui()
        self.repeat_mode_changed.emit(self.repeat_mode)

    def _on_repeat_right_clicked(self, pos):
        # Right click directly cancels repeat (resets to OFF)
        self.repeat_mode = 0
        self._update_repeat_ui()
        self.repeat_mode_changed.emit(self.repeat_mode)

    def _on_dac_combo_changed(self, index: int):
        dev_index = self.dac_combo.currentData()
        if dev_index is not None:
            self.dac_selected.emit(int(dev_index))
            self._update_stream_info()

    def _on_bit_perfect_clicked(self):
        checked = self.bit_perfect_btn.isChecked()
        self.bit_perfect_toggled.emit(checked)

    def _on_volume_changed(self, val: int):
        self.volume_changed.emit(val / 100.0)

    def _on_seek_pressed(self):
        self.is_seeking = True

    def _on_seek_released(self):
        self.is_seeking = False
        val = self.seek_slider.value()
        if self.total_duration > 0:
            target_sec = (val / 1000.0) * self.total_duration
            self.seek_requested.emit(target_sec)

    def _load_cover(self, track: Track):
        cover_path = getattr(track, "cover_path", None)
        if not cover_path or not os.path.exists(cover_path):
            from app.core.scanner import extract_cover_art
            cover_path = extract_cover_art(track.file_path)
            track.cover_path = cover_path

        if cover_path and os.path.exists(cover_path):
            pixmap = QPixmap(cover_path)
            if not pixmap.isNull():
                # Left thumbnail (54x54)
                pix_left = pixmap.scaled(
                    54, 54,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.cover_label.setPixmap(pix_left)

                return

        self._set_empty_cover()

    def _set_empty_cover(self):
        img = QImage(54, 54, QImage.Format.Format_RGB32)
        img.fill(QColor("#161a24"))
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor("#2c3447"))
        p.setBrush(QColor("#11131a"))
        p.drawEllipse(4, 4, 46, 46)
        p.setBrush(QColor("#e5a93b"))
        p.drawEllipse(22, 22, 10, 10)
        p.end()
        self.cover_label.setPixmap(QPixmap.fromImage(img))
