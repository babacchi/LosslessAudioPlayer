"""Artist detail view with albums grid/carousel, full tracklist, and playback controls."""
import os
import random
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QFont, QBrush, QPen
from PySide6.QtCore import Qt, Signal

from app.core.models import Artist, Album, Track
from app.ui.album_grid import AlbumCard


class ArtistDetailView(QWidget):
    back_requested = Signal()
    album_selected = Signal(object)              # Album
    play_album_requested = Signal(object)        # Album
    play_track_requested = Signal(object, list)  # (Track, List[Track] queue)
    play_artist_requested = Signal(object)       # Artist

    def __init__(self, parent=None):
        super().__init__(parent)
        self.artist: Optional[Artist] = None
        self.albums: List[Album] = []
        self.tracks: List[Track] = []
        self.current_playing_track_id: Optional[int] = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Top Navigation Button
        top_nav = QHBoxLayout()
        self.back_btn = QPushButton("← アーティスト一覧に戻る")
        self.back_btn.setObjectName("ActionBtn")
        self.back_btn.clicked.connect(self.back_requested.emit)
        top_nav.addWidget(self.back_btn)
        top_nav.addStretch()
        main_layout.addLayout(top_nav)

        # Scroll area for entire artist detail view
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(20)

        # Artist Header Info
        header_frame = QFrame()
        header_frame.setObjectName("ArtistHeaderFrame")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 20, 20, 20)
        header_layout.setSpacing(24)

        # Large Circular Avatar
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(160, 160)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.avatar_label)

        # Metadata Details
        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(6)

        # Badges row
        badge_row = QHBoxLayout()
        self.hires_badge = QLabel("Hi-Res AUDIO")
        self.hires_badge.setObjectName("HiResBadge")
        badge_row.addWidget(self.hires_badge)

        self.format_badge = QLabel("Lossless Audio")
        self.format_badge.setObjectName("FormatBadge")
        badge_row.addWidget(self.format_badge)
        badge_row.addStretch()
        meta_layout.addLayout(badge_row)

        self.name_label = QLabel("Artist Name")
        self.name_label.setStyleSheet("font-size: 26px; font-weight: 700; color: #ffffff;")
        meta_layout.addWidget(self.name_label)

        self.info_label = QLabel("0枚のアルバム • 0曲")
        self.info_label.setStyleSheet("font-size: 13px; color: #9ca3af;")
        meta_layout.addWidget(self.info_label)

        meta_layout.addSpacing(10)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.play_all_btn = QPushButton("▶ 全曲を再生")
        self.play_all_btn.setObjectName("PrimaryBtn")
        self.play_all_btn.clicked.connect(self._on_play_all)
        btn_row.addWidget(self.play_all_btn)

        self.shuffle_btn = QPushButton("🔀 シャッフル再生")
        self.shuffle_btn.setObjectName("ActionBtn")
        self.shuffle_btn.clicked.connect(self._on_shuffle_play)
        btn_row.addWidget(self.shuffle_btn)
        btn_row.addStretch()
        meta_layout.addLayout(btn_row)

        header_layout.addLayout(meta_layout)
        content_layout.addWidget(header_frame)

        # Section 1: Albums
        self.albums_section = QWidget()
        albums_section_layout = QVBoxLayout(self.albums_section)
        albums_section_layout.setContentsMargins(0, 0, 0, 0)
        albums_section_layout.setSpacing(10)

        self.albums_header = QLabel("💿 アルバム")
        self.albums_header.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        albums_section_layout.addWidget(self.albums_header)

        self.albums_scroll = QScrollArea()
        self.albums_scroll.setWidgetResizable(True)
        self.albums_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.albums_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.albums_scroll.setFixedHeight(260)
        self.albums_scroll.setStyleSheet("background: transparent; border: none;")

        self.albums_container = QWidget()
        self.albums_container.setStyleSheet("background: transparent;")
        self.albums_layout = QHBoxLayout(self.albums_container)
        self.albums_layout.setContentsMargins(0, 0, 0, 0)
        self.albums_layout.setSpacing(14)
        self.albums_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.albums_scroll.setWidget(self.albums_container)
        albums_section_layout.addWidget(self.albums_scroll)
        content_layout.addWidget(self.albums_section)

        # Section 2: Tracks Table
        tracks_section = QWidget()
        tracks_section_layout = QVBoxLayout(tracks_section)
        tracks_section_layout.setContentsMargins(0, 0, 0, 0)
        tracks_section_layout.setSpacing(10)

        self.tracks_header = QLabel("🎵 楽曲一覧")
        self.tracks_header.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        tracks_section_layout.addWidget(self.tracks_header)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["#", "タイトル", "アルバム", "音質 / フォーマット", "時間"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(300)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.cellDoubleClicked.connect(self._on_track_double_clicked)
        tracks_section_layout.addWidget(self.table)

        content_layout.addWidget(tracks_section)
        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)

    def set_artist(self, artist: Artist, albums: List[Album], tracks: List[Track]):
        self.artist = artist
        self.albums = albums
        self.tracks = tracks

        self.name_label.setText(artist.name)

        # Info string
        alb_text = f"{len(albums)}枚のアルバム"
        trk_text = f"{len(tracks)}曲"
        dur_text = artist.duration_formatted
        self.info_label.setText(f"{alb_text} • {trk_text} • 再生時間: {dur_text}")
        self.albums_header.setText(f"💿 アルバム ({len(albums)})")
        self.tracks_header.setText(f"🎵 楽曲一覧 ({len(tracks)})")

        # Badges
        self.hires_badge.setVisible(artist.is_hires)
        if artist.is_hires:
            sr_khz = f"{artist.sample_rate / 1000:g}kHz"
            self.format_badge.setText(f"Hi-Res {sr_khz} / {artist.bit_depth}bit")
        else:
            self.format_badge.setText("Lossless Audio")

        # Avatar
        self._load_avatar()

        # Populate Albums
        while self.albums_layout.count():
            item = self.albums_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if albums:
            self.albums_section.show()
            for alb in albums:
                card = AlbumCard(alb, cover_size=130)
                card.clicked.connect(self.album_selected.emit)
                card.play_clicked.connect(self.play_album_requested.emit)
                self.albums_layout.addWidget(card)
        else:
            self.albums_section.hide()

        # Populate Tracks Table
        self._populate_tracks_table()

    def _load_avatar(self):
        s = 160
        img = QImage(s, s, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        has_image = False
        if self.artist and self.artist.cover_path and os.path.exists(self.artist.cover_path):
            pixmap = QPixmap(self.artist.cover_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    s, s,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                if scaled.width() > s or scaled.height() > s:
                    x = (scaled.width() - s) // 2
                    y = (scaled.height() - s) // 2
                    scaled = scaled.copy(x, y, s, s)

                brush = QBrush(scaled)
                p.setBrush(brush)
                border_color = QColor("#e5a93b" if self.artist.is_hires else "#2c3447")
                p.setPen(QPen(border_color, 3))
                p.drawEllipse(3, 3, s - 6, s - 6)
                has_image = True

        if not has_image:
            p.setBrush(QBrush(QColor("#1b1f2b")))
            border_color = QColor("#e5a93b" if (self.artist and self.artist.is_hires) else "#2c3447")
            p.setPen(QPen(border_color, 3))
            p.drawEllipse(3, 3, s - 6, s - 6)

            p.setPen(QColor("#e5a93b" if (self.artist and self.artist.is_hires) else "#9ca3af"))
            font = QFont("Helvetica Neue")
            font.setPointSize(48)
            font.setBold(True)
            p.setFont(font)
            initial = (self.artist.name[0] if (self.artist and self.artist.name) else "A").upper()
            p.drawText(0, 0, s, s, Qt.AlignmentFlag.AlignCenter, initial)

        p.end()
        self.avatar_label.setPixmap(QPixmap.fromImage(img))

    def _populate_tracks_table(self):
        self.table.setRowCount(len(self.tracks))
        for row, t in enumerate(self.tracks):
            is_playing = (self.current_playing_track_id is not None and t.id == self.current_playing_track_id)

            # Row Number or Note
            num_text = "♪" if is_playing else f"{row + 1:02d}"
            num_item = QTableWidgetItem(num_text)
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            num_item.setData(Qt.ItemDataRole.UserRole, t)
            if is_playing:
                num_item.setForeground(QColor("#e5a93b"))
                num_item.setFont(QFont("Helvetica Neue", 13, QFont.Weight.Bold))
            else:
                num_item.setForeground(QColor("#9ca3af"))
            self.table.setItem(row, 0, num_item)

            # Title
            title_text = t.title
            if t.is_hires:
                title_text = f"★ {title_text}"
            title_item = QTableWidgetItem(title_text)
            title_item.setFont(QFont("Helvetica Neue", 13, QFont.Weight.Medium))
            if is_playing:
                title_item.setForeground(QColor("#e5a93b"))
            self.table.setItem(row, 1, title_item)

            # Album
            album_item = QTableWidgetItem(t.album)
            album_item.setForeground(QColor("#9ca3af"))
            self.table.setItem(row, 2, album_item)

            # Format
            format_item = QTableWidgetItem(t.audio_quality_label)
            if t.is_hires:
                format_item.setForeground(QColor("#e5a93b"))
            else:
                format_item.setForeground(QColor("#9ca3af"))
            self.table.setItem(row, 3, format_item)

            # Duration
            dur_item = QTableWidgetItem(t.duration_formatted)
            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            dur_item.setForeground(QColor("#9ca3af"))
            self.table.setItem(row, 4, dur_item)

    def set_current_playing_track(self, track: Optional[Track]):
        self.current_playing_track_id = track.id if track else None
        for row in range(self.table.rowCount()):
            num_item = self.table.item(row, 0)
            title_item = self.table.item(row, 1)
            if not num_item or not title_item:
                continue

            t = num_item.data(Qt.ItemDataRole.UserRole)
            is_active = (track is not None and t and t.id == track.id)

            if is_active:
                num_item.setText("♪")
                num_item.setForeground(QColor("#e5a93b"))
                num_item.setFont(QFont("Helvetica Neue", 13, QFont.Weight.Bold))
                title_item.setForeground(QColor("#e5a93b"))
            else:
                num_item.setText(f"{row + 1:02d}")
                num_item.setForeground(QColor("#9ca3af"))
                num_item.setFont(QFont("Helvetica Neue", 13, QFont.Weight.Normal))
                title_item.setForeground(QColor("#e5e7eb"))

    def _on_track_double_clicked(self, row: int, col: int):
        num_item = self.table.item(row, 0)
        if num_item:
            track = num_item.data(Qt.ItemDataRole.UserRole)
            if track:
                self.play_track_requested.emit(track, self.tracks)

    def _on_play_all(self):
        if self.tracks:
            self.play_track_requested.emit(self.tracks[0], self.tracks)

    def _on_shuffle_play(self):
        if self.tracks:
            shuffled = list(self.tracks)
            random.shuffle(shuffled)
            self.play_track_requested.emit(shuffled[0], shuffled)

