"""Main application window for Jukebox / Aura Audiophile Music Player."""
import os
from typing import List, Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QStackedWidget, QFileDialog,
    QProgressBar, QFrame, QMessageBox, QButtonGroup
)
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QIcon, QFont

from app.core.models import Track, Album, AudioDevice
from app.core.database import Database
from app.core.audio_engine import AudioEngine
from app.core.scanner import LibraryScannerTask
from app.ui.album_grid import AlbumGridView
from app.ui.album_detail import AlbumDetailView
from app.ui.track_table import TrackTableView
from app.ui.player_bar import PlayerBar
from app.ui.dac_dialog import DacSettingsDialog


class MainWindow(QMainWindow):
    def __init__(self, db: Database, audio_engine: AudioEngine):
        super().__init__()
        self.db = db
        self.audio_engine = audio_engine
        self.thread_pool = QThreadPool.globalInstance()

        self.setWindowTitle("Aura Lossless Audio Player - Audiophile DAC Player")
        self.resize(1200, 800)
        self.setMinimumSize(960, 640)

        # Playback Queue
        self.playback_queue: List[Track] = []
        self.current_queue_index: int = -1
        self.shuffle_enabled: bool = False
        self.repeat_mode: int = 0  # 0: OFF, 1: ALL, 2: ONE
        self.shuffled_indices: List[int] = []
        self.shuffle_pos: int = 0

        # View state
        self.current_search: str = ""
        self.filter_hires_only: bool = False

        self._init_ui()
        self._init_connections()
        self._load_saved_settings()
        self.refresh_library()

    def _init_ui(self):
        root_widget = QWidget()
        self.setCentralWidget(root_widget)

        root_layout = QVBoxLayout(root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Bar
        self.top_bar = self._create_top_bar()
        root_layout.addWidget(self.top_bar)

        # 2. Main Content Area (Sidebar + Content Stack)
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.sidebar = self._create_sidebar()
        content_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.album_grid_view = AlbumGridView()
        self.album_detail_view = AlbumDetailView()
        self.track_table_view = TrackTableView()

        self.stack.addWidget(self.album_grid_view)      # Index 0
        self.stack.addWidget(self.album_detail_view)    # Index 1
        self.stack.addWidget(self.track_table_view)     # Index 2

        content_layout.addWidget(self.stack, stretch=1)
        root_layout.addLayout(content_layout, stretch=1)

        # 3. Bottom Player Bar
        self.player_bar = PlayerBar()
        self.player_bar.set_audio_engine(self.audio_engine)
        root_layout.addWidget(self.player_bar)

    def _create_top_bar(self) -> QFrame:
        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(14)

        # Logo / Title
        logo_label = QLabel("AURA")
        logo_label.setStyleSheet("font-size: 18px; font-weight: 800; color: #ffffff; letter-spacing: 2px;")
        layout.addWidget(logo_label)

        sub_logo = QLabel("LOSSLESS")
        sub_logo.setStyleSheet("font-size: 11px; font-weight: 700; color: #e5a93b; letter-spacing: 1.5px;")
        layout.addWidget(sub_logo)

        layout.addSpacing(20)

        # Search Input
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("🔍 アルバム、アーティスト、楽曲を検索...")
        self.search_input.setFixedWidth(300)
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)

        layout.addStretch()

        # Action Buttons
        self.add_folder_btn = QPushButton("＋ フォルダー追加")
        self.add_folder_btn.setObjectName("ActionBtn")
        self.add_folder_btn.clicked.connect(self._on_add_folder)
        layout.addWidget(self.add_folder_btn)

        self.dac_settings_btn = QPushButton("⚙ DAC / 音質設定")
        self.dac_settings_btn.setObjectName("ActionBtn")
        self.dac_settings_btn.clicked.connect(self._open_dac_settings)
        layout.addWidget(self.dac_settings_btn)

        return top_bar

    def _create_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(230)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 16, 10, 16)
        layout.setSpacing(6)

        section_label = QLabel("ライブラリ")
        section_label.setStyleSheet("color: #6b7280; font-size: 11px; font-weight: 700; padding-left: 10px; margin-bottom: 4px;")
        layout.addWidget(section_label)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        self.btn_nav_albums = QPushButton("💿 アルバム一覧")
        self.btn_nav_albums.setObjectName("NavButton")
        self.btn_nav_albums.setCheckable(True)
        self.btn_nav_albums.setChecked(True)
        self.btn_nav_albums.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.nav_group.addButton(self.btn_nav_albums)
        layout.addWidget(self.btn_nav_albums)

        self.btn_nav_tracks = QPushButton("🎵 曲一覧")
        self.btn_nav_tracks.setObjectName("NavButton")
        self.btn_nav_tracks.setCheckable(True)
        self.btn_nav_tracks.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        self.nav_group.addButton(self.btn_nav_tracks)
        layout.addWidget(self.btn_nav_tracks)

        layout.addSpacing(12)

        filter_label = QLabel("フィルター")
        filter_label.setStyleSheet("color: #6b7280; font-size: 11px; font-weight: 700; padding-left: 10px; margin-bottom: 4px;")
        layout.addWidget(filter_label)

        self.btn_nav_hires = QPushButton("★ ハイレゾのみ")
        self.btn_nav_hires.setObjectName("NavButton")
        self.btn_nav_hires.setCheckable(True)
        self.btn_nav_hires.toggled.connect(self._on_hires_filter_toggled)
        layout.addWidget(self.btn_nav_hires)

        self.btn_nav_compilation = QPushButton("📦 コンピレーション結合")
        self.btn_nav_compilation.setObjectName("NavButton")
        self.btn_nav_compilation.setCheckable(True)
        self.btn_nav_compilation.setChecked(self.db.is_group_by_album_artist())
        self.btn_nav_compilation.setToolTip("ON: Album Artist(Various Artists等)で一括りにする\nOFF: 個別アーティストごとにアルバムを分割する")
        self.btn_nav_compilation.toggled.connect(self._on_compilation_sidebar_toggled)
        layout.addWidget(self.btn_nav_compilation)

        layout.addStretch()

        # Scanning Progress Indicator in Sidebar
        self.scan_progress_widget = QWidget()
        scan_layout = QVBoxLayout(self.scan_progress_widget)
        scan_layout.setContentsMargins(4, 4, 4, 4)
        scan_layout.setSpacing(4)

        self.scan_label = QLabel("ライブラリをスキャン中...")
        self.scan_label.setStyleSheet("font-size: 11px; color: #e5a93b;")
        scan_layout.addWidget(self.scan_label)

        self.scan_bar = QProgressBar()
        self.scan_bar.setFixedHeight(4)
        self.scan_bar.setTextVisible(False)
        self.scan_bar.setStyleSheet("""
            QProgressBar { background: #1c202d; border: none; border-radius: 2px; }
            QProgressBar::chunk { background: #e5a93b; border-radius: 2px; }
        """)
        scan_layout.addWidget(self.scan_bar)

        self.scan_progress_widget.hide()
        layout.addWidget(self.scan_progress_widget)

        return sidebar

    def _init_connections(self):
        # Audio Engine Signals
        self.audio_engine.signals.track_started.connect(self._on_track_started)
        self.audio_engine.signals.playback_state_changed.connect(self._on_playback_state_changed)
        self.audio_engine.signals.position_updated.connect(self.player_bar.update_position)
        self.audio_engine.signals.track_ended.connect(self._on_track_ended)
        self.audio_engine.signals.bit_perfect_changed.connect(self.player_bar.set_bit_perfect_state)
        self.audio_engine.signals.error_occurred.connect(self._on_audio_error)

        # Player Bar Signals
        self.player_bar.play_pause_clicked.connect(self.audio_engine.toggle_play_pause)
        self.player_bar.prev_clicked.connect(self._on_play_prev)
        self.player_bar.next_clicked.connect(self._on_play_next)
        self.player_bar.seek_requested.connect(self.audio_engine.seek)
        self.player_bar.volume_changed.connect(self.audio_engine.set_volume)
        self.player_bar.bit_perfect_toggled.connect(self.audio_engine.set_bit_perfect)
        self.player_bar.dac_selected.connect(self.audio_engine.set_output_device)
        self.player_bar.open_dac_settings_requested.connect(self._open_dac_settings)
        self.player_bar.shuffle_toggled.connect(self._on_shuffle_toggled)
        self.player_bar.repeat_mode_changed.connect(self._on_repeat_mode_changed)

        # Album Grid View Signals
        self.album_grid_view.album_selected.connect(self._on_album_selected)
        self.album_grid_view.play_album_requested.connect(self._on_play_album)
        self.album_grid_view.jacket_size_changed.connect(lambda s: self.db.set_setting("album_jacket_size", str(s)))

        # Album Detail View Signals
        self.album_detail_view.back_requested.connect(lambda: self.stack.setCurrentIndex(0))
        self.album_detail_view.play_track_requested.connect(self._on_play_track_with_queue)

        # Track Table View Signals
        self.track_table_view.track_selected.connect(self._on_play_track_with_queue)

    def _load_saved_settings(self):
        # Restore DAC selection
        devices = self.audio_engine.get_available_devices()
        saved_dac = self.db.get_setting("selected_dac_index")
        dac_index = int(saved_dac) if saved_dac is not None else None
        self.audio_engine.set_output_device(dac_index)
        self.player_bar.set_devices(devices, dac_index)

        # Restore Bit-Perfect mode
        bp_val = self.db.get_setting("bit_perfect", "1")
        is_bp = (bp_val == "1")
        self.audio_engine.set_bit_perfect(is_bp)
        self.player_bar.set_bit_perfect_state(is_bp)

        # Restore Gapless playback mode (default: enabled "1")
        gapless_val = self.db.get_setting("gapless_playback", "1")
        self.audio_engine.set_gapless_enabled(gapless_val == "1")

        # Restore Album Jacket Size
        saved_size = self.db.get_setting("album_jacket_size")
        if saved_size is not None:
            try:
                self.album_grid_view.set_cover_size(int(saved_size))
            except Exception:
                pass

    def refresh_library(self):
        """Fetch albums and tracks from database and update views."""
        albums = self.db.get_albums(self.current_search, sort_by="title")
        if self.filter_hires_only:
            albums = [a for a in albums if a.is_hires]
        self.album_grid_view.set_albums(albums)

        tracks = self.db.get_all_tracks(self.current_search)
        if self.filter_hires_only:
            tracks = [t for t in tracks if t.is_hires]
        self.track_table_view.set_tracks(tracks)
        if self.audio_engine.is_playing and self.audio_engine.current_track:
            self.track_table_view.set_current_playing_track(self.audio_engine.current_track)

    def _on_search_changed(self, text: str):
        self.current_search = text
        self.refresh_library()

    def _on_hires_filter_toggled(self, checked: bool):
        self.filter_hires_only = checked
        self.refresh_library()

    def _on_album_selected(self, album: Album):
        tracks = self.db.get_tracks_for_album(album.id)
        self.album_detail_view.set_album(album, tracks)
        if self.audio_engine.is_playing and self.audio_engine.current_track:
            self.album_detail_view.set_current_playing_track(self.audio_engine.current_track)
        self.stack.setCurrentIndex(1)

    def _on_play_album(self, album: Album):
        tracks = self.db.get_tracks_for_album(album.id)
        if tracks:
            self._on_play_track_with_queue(tracks[0], tracks)

    def _on_play_track_with_queue(self, track: Track, queue: List[Track]):
        self.playback_queue = list(queue)
        try:
            self.current_queue_index = self.playback_queue.index(track)
        except ValueError:
            self.current_queue_index = 0
            self.playback_queue.insert(0, track)

        if self.shuffle_enabled:
            self._build_shuffled_order(start_index=self.current_queue_index)

        self.audio_engine.play_track(track)
        self._prepare_next_track()

    def _peek_next_track(self) -> Optional[Track]:
        """Look ahead to determine the upcoming track in current playback order."""
        if not self.playback_queue:
            return None

        # Repeat one track (🔂)
        if self.repeat_mode == 2:
            if 0 <= self.current_queue_index < len(self.playback_queue):
                return self.playback_queue[self.current_queue_index]
            return None

        # Shuffle mode
        if self.shuffle_enabled and self.shuffled_indices:
            if self.shuffle_pos + 1 < len(self.shuffled_indices):
                next_idx = self.shuffled_indices[self.shuffle_pos + 1]
                if 0 <= next_idx < len(self.playback_queue):
                    return self.playback_queue[next_idx]
            elif self.repeat_mode == 1 and len(self.shuffled_indices) > 0:
                first_idx = self.shuffled_indices[0]
                if 0 <= first_idx < len(self.playback_queue):
                    return self.playback_queue[first_idx]
            return None

        # Sequential mode
        if self.current_queue_index + 1 < len(self.playback_queue):
            return self.playback_queue[self.current_queue_index + 1]
        elif self.repeat_mode == 1 and len(self.playback_queue) > 0:
            return self.playback_queue[0]
        return None

    def _prepare_next_track(self):
        """Pre-buffer next track into audio engine for sample-accurate gapless playback."""
        next_track = self._peek_next_track()
        self.audio_engine.set_next_track(next_track)

    def _build_shuffled_order(self, start_index: int = -1):
        import random
        indices = list(range(len(self.playback_queue)))
        if 0 <= start_index < len(indices):
            indices.remove(start_index)
            random.shuffle(indices)
            self.shuffled_indices = [start_index] + indices
            self.shuffle_pos = 0
        else:
            random.shuffle(indices)
            self.shuffled_indices = indices
            self.shuffle_pos = 0

    def _on_shuffle_toggled(self, enabled: bool):
        self.shuffle_enabled = enabled
        if enabled and self.playback_queue:
            self._build_shuffled_order(start_index=self.current_queue_index)
        self._prepare_next_track()

    def _on_repeat_mode_changed(self, mode: int):
        self.repeat_mode = mode
        self._prepare_next_track()

    def _on_track_started(self, track: Track):
        # Check if this track started seamlessly via gapless transition
        if self.playback_queue:
            if self.shuffle_enabled and self.shuffled_indices:
                if self.shuffle_pos + 1 < len(self.shuffled_indices):
                    next_idx = self.shuffled_indices[self.shuffle_pos + 1]
                    if 0 <= next_idx < len(self.playback_queue) and self.playback_queue[next_idx].id == track.id:
                        self.shuffle_pos += 1
                        self.current_queue_index = next_idx
                elif self.repeat_mode == 1 and len(self.shuffled_indices) > 0:
                    if self.playback_queue[self.shuffled_indices[0]].id == track.id:
                        self._build_shuffled_order(start_index=-1)
                        self.current_queue_index = self.shuffled_indices[0]
            else:
                if self.current_queue_index + 1 < len(self.playback_queue):
                    if self.playback_queue[self.current_queue_index + 1].id == track.id:
                        self.current_queue_index += 1
                elif self.repeat_mode == 1 and len(self.playback_queue) > 0:
                    if self.playback_queue[0].id == track.id:
                        self.current_queue_index = 0

        if not track.cover_path and track.album_id:
            alb = self.db.get_album(track.album_id)
            if alb and alb.cover_path:
                track.cover_path = alb.cover_path
        self.player_bar.set_track(track)
        self.track_table_view.set_current_playing_track(track)
        self.album_detail_view.set_current_playing_track(track)

        # Pre-buffer the next upcoming track for gapless playback
        self._prepare_next_track()

    def _on_playback_state_changed(self, is_playing: bool, is_paused: bool):
        self.player_bar.set_playback_state(is_playing, is_paused)
        if not is_playing:
            self.track_table_view.set_current_playing_track(None)
            self.album_detail_view.set_current_playing_track(None)

    def _on_track_ended(self):
        # 1-track repeat mode (🔂)
        if self.repeat_mode == 2:
            if self.playback_queue and 0 <= self.current_queue_index < len(self.playback_queue):
                track = self.playback_queue[self.current_queue_index]
                self.audio_engine.play_track(track)
                return

        # Auto-advance to next track in queue (with shuffle / all-repeat support)
        self._on_play_next(auto_advance=True)

    def _on_play_prev(self):
        # If past 3 seconds, replay current track from start
        if self.audio_engine.get_current_time() > 3.0:
            self.audio_engine.seek(0)
            return

        if not self.playback_queue:
            return

        if self.shuffle_enabled and self.shuffled_indices:
            if self.shuffle_pos > 0:
                self.shuffle_pos -= 1
                idx = self.shuffled_indices[self.shuffle_pos]
                self.current_queue_index = idx
                self.audio_engine.play_track(self.playback_queue[idx])
            else:
                self.audio_engine.seek(0)
        else:
            if self.current_queue_index > 0:
                self.current_queue_index -= 1
                prev_track = self.playback_queue[self.current_queue_index]
                self.audio_engine.play_track(prev_track)
            elif self.repeat_mode == 1 and len(self.playback_queue) > 0:
                self.current_queue_index = len(self.playback_queue) - 1
                last_track = self.playback_queue[self.current_queue_index]
                self.audio_engine.play_track(last_track)
            else:
                self.audio_engine.seek(0)

    def _on_play_next(self, auto_advance: bool = False):
        if not self.playback_queue:
            self.audio_engine.stop()
            return

        if self.shuffle_enabled and self.shuffled_indices:
            if self.shuffle_pos + 1 < len(self.shuffled_indices):
                self.shuffle_pos += 1
                idx = self.shuffled_indices[self.shuffle_pos]
                self.current_queue_index = idx
                self.audio_engine.play_track(self.playback_queue[idx])
            elif self.repeat_mode == 1:  # All repeat in shuffle
                self._build_shuffled_order(start_index=-1)
                idx = self.shuffled_indices[0]
                self.current_queue_index = idx
                self.audio_engine.play_track(self.playback_queue[idx])
            else:
                self.audio_engine.stop()
        else:
            if self.current_queue_index + 1 < len(self.playback_queue):
                self.current_queue_index += 1
                next_track = self.playback_queue[self.current_queue_index]
                self.audio_engine.play_track(next_track)
            elif self.repeat_mode == 1:  # All repeat
                self.current_queue_index = 0
                first_track = self.playback_queue[0]
                self.audio_engine.play_track(first_track)
            else:
                self.audio_engine.stop()

    def _on_add_folder(self):
        path = QFileDialog.getExistingDirectory(self, "音楽フォルダーを選択")
        if path:
            self.db.add_folder(path)
            self._start_scan([path])

    def _start_scan(self, folders: List[str]):
        self.scan_progress_widget.show()
        self.scan_bar.setValue(0)
        task = LibraryScannerTask(self.db, folders)
        task.signals.progress.connect(self._on_scan_progress)
        task.signals.finished.connect(self._on_scan_finished)
        self.thread_pool.start(task)

    def _on_scan_progress(self, current: int, total: int, filename: str):
        if total > 0:
            pct = int((current / total) * 100)
            self.scan_bar.setValue(pct)
            self.scan_label.setText(f"スキャン中 ({current}/{total}): {filename[:20]}...")

    def _on_scan_finished(self, count: int):
        self.scan_progress_widget.hide()
        self.refresh_library()

    def _open_dac_settings(self):
        dialog = DacSettingsDialog(self.audio_engine, self.db, self)
        dialog.rescan_requested.connect(self._rescan_all)
        dialog.library_regrouped.connect(self._on_library_regrouped)
        dialog.device_selected.connect(lambda idx: self.player_bar.set_devices(
            self.audio_engine.get_available_devices(), idx
        ))
        dialog.bit_perfect_toggled.connect(self.player_bar.set_bit_perfect_state)
        dialog.gapless_toggled.connect(self._on_gapless_toggled)
        dialog.exec()

    def _on_gapless_toggled(self, enabled: bool):
        if enabled:
            self._prepare_next_track()
        else:
            self.audio_engine.set_next_track(None)

    def _on_compilation_sidebar_toggled(self, checked: bool):
        self.db.set_group_by_album_artist(checked)
        self.refresh_library()

    def _on_library_regrouped(self):
        self.btn_nav_compilation.blockSignals(True)
        self.btn_nav_compilation.setChecked(self.db.is_group_by_album_artist())
        self.btn_nav_compilation.blockSignals(False)
        self.refresh_library()

    def _rescan_all(self):
        folders = self.db.get_folders()
        if folders:
            self._start_scan(folders)
        else:
            self.refresh_library()

    def _on_audio_error(self, message: str):
        QMessageBox.warning(self, "オーディオエラー", message)
