"""Data models for Jukebox music player."""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Track:
    file_path: str
    title: str = "Unknown Title"
    artist: str = "Unknown Artist"
    album: str = "Unknown Album"
    album_artist: str = ""
    composer: str = ""
    track_number: int = 1
    disc_number: int = 1
    year: Optional[int] = None
    genre: str = ""
    duration: float = 0.0  # seconds
    sample_rate: int = 44100  # Hz
    bit_depth: int = 16  # bits
    channels: int = 2
    format: str = "FLAC"  # FLAC, WAV, AIFF, etc.
    bitrate: Optional[int] = None
    file_size: int = 0
    id: Optional[int] = None
    album_id: Optional[int] = None
    cover_path: Optional[str] = None

    @property
    def is_hires(self) -> bool:
        """Audiophile Hi-Res criteria: >= 24-bit or >= 88.2 kHz."""
        return self.bit_depth >= 24 or self.sample_rate >= 88200

    @property
    def duration_formatted(self) -> str:
        mins = int(self.duration // 60)
        secs = int(self.duration % 60)
        return f"{mins:02d}:{secs:02d}"

    @property
    def audio_quality_label(self) -> str:
        sr_khz = f"{self.sample_rate / 1000:g}kHz"
        return f"{self.format} • {sr_khz} / {self.bit_depth}bit"


@dataclass
class Album:
    title: str
    artist: str
    year: Optional[int] = None
    genre: str = ""
    cover_path: Optional[str] = None
    track_count: int = 0
    total_duration: float = 0.0
    is_hires: bool = False
    sample_rate: int = 44100
    bit_depth: int = 16
    format: str = "FLAC"
    id: Optional[int] = None
    tracks: List[Track] = field(default_factory=list)

    @property
    def duration_formatted(self) -> str:
        mins = int(self.total_duration // 60)
        if mins >= 60:
            hrs = mins // 60
            remaining_mins = mins % 60
            return f"{hrs}h {remaining_mins:02d}m"
        secs = int(self.total_duration % 60)
        return f"{mins:02d}:{secs:02d}"

    @property
    def quality_badge(self) -> str:
        sr_khz = f"{self.sample_rate / 1000:g}kHz"
        return f"{self.format} {sr_khz}/{self.bit_depth}bit"


@dataclass
class Artist:
    name: str
    album_count: int = 0
    track_count: int = 0
    total_duration: float = 0.0
    is_hires: bool = False
    sample_rate: int = 44100
    bit_depth: int = 16
    cover_path: Optional[str] = None
    albums: List[Album] = field(default_factory=list)
    tracks: List[Track] = field(default_factory=list)

    @property
    def duration_formatted(self) -> str:
        mins = int(self.total_duration // 60)
        if mins >= 60:
            hrs = mins // 60
            remaining_mins = mins % 60
            return f"{hrs}時間 {remaining_mins:02d}分"
        secs = int(self.total_duration % 60)
        return f"{mins:02d}:{secs:02d}"


@dataclass
class AudioDevice:
    index: int
    name: str
    hostapi_name: str
    max_output_channels: int
    default_samplerate: float
    is_default: bool = False

    @property
    def display_name(self) -> str:
        suffix = " (System Default)" if self.is_default else ""
        return f"{self.name} [{self.hostapi_name}]{suffix}"
