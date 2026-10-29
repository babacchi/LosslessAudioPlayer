"""Album detail view with full tracklist, Hi-Res info and play controls."""
import os
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFrame
)
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QFont
from PySide6.QtCore import Qt, Signal

from app.core.models import Album, Track


class AlbumDetailView(QWidget):
    back_requested = Signal()
    play_track_requested = Signal(object, list)  # (Track, List[Track] queue)
    play_album_requested = Signal(object)        # Album

    def __init__(self, parent=None):
        super().__init__(parent)
        self.album: Optional[Album] = None
        self.tracks: List[Track] = []
        self.current_playing_track_id: Optional[int] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(18)

        # Back Navigation button
        top_nav = QHBoxLayout()
        self.back_btn = QPushButton("← アルバム一覧に戻る")
        self.back_btn.setObjectName("ActionBtn")
        self.back_btn.clicked.connect(self.back_requested.emit)
        top_nav.addWidget(self.back_btn)
        top_nav.addStretch()
        layout.addLayout(top_nav)

        # Album Header Info
        header_frame = QFrame()
        header_frame.setObjectName("AlbumHeaderFrame")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setSpacing(24)

        # Large Artwork
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(200, 200)
        self.cover_label.setStyleSheet("border-radius: 10px; background-color: #1a1e2b;")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.cover_label)

        # Metadata Details
        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(6)

        # Hi-Res Badge & Format
        badge_row = QHBoxLayout()
        self.hires_badge = QLabel("Hi-Res AUDIO")
        self.hires_badge.setObjectName("HiResBadge")
        badge_row.addWidget(self.hires_badge)

        self.format_badge = QLabel("FLAC 96kHz / 24bit")
        self.format_badge.setObjectName("FormatBadge")
        badge_row.addWidget(self.format_badge)
        badge_row.addStretch()
        meta_layout.addLayout(badge_row)

        self.title_label = QLabel("Album Title")
        self.title_label.setStyleSheet("font-size: 24px; font-weight: 700; color: #ffffff;")
        meta_layout.addWidget(self.title_label)

        self.artist_label = QLabel("Artist Name")
        self.artist_label.setStyleSheet("font-size: 16px; font-weight: 500; color: #e5a93b;")
        meta_layout.addWidget(self.artist_label)

        self.info_label = QLabel("Year • Genre • Tracks • Duration")
        self.info_label.setStyleSheet("font-size: 13px; color: #9ca3af;")
        meta_layout.addWidget(self.info_label)

        meta_layout.addSpacing(10)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.play_all_btn = QPushButton("▶ アルバムを再生")
        self.play_all_btn.setObjectName("PrimaryBtn")
        self.play_all_btn.clicked.connect(self._on_play_all)
        btn_row.addWidget(self.play_all_btn)
        btn_row.addStretch()
        meta_layout.addLayout(btn_row)

        header_layout.addLayout(meta_layout)
        layout.addWidget(header_frame)

        # Track List Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["#", "タイトル", "アーティスト", "音質 / フォーマット", "時間"])
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
        self.table.cellDoubleClicked.connect(self._on_track_double_clicked)
        layout.addWidget(self.table)

    def set_album(self, album: Album, tracks: List[Track]):
        self.album = album
        self.tracks = tracks

        self.title_label.setText(album.title)
        self.artist_label.setText(album.artist)

        meta_parts = []
        if album.year:
            meta_parts.append(str(album.year))
        if album.genre:
            meta_parts.append(album.genre)
        meta_parts.append(f"{len(tracks)} 曲")
        meta_parts.append(album.duration_formatted)
        self.info_label.setText(" • ".join(meta_parts))

        # Hi-Res Badge
        self.hires_badge.setVisible(album.is_hires)
        sr_khz = f"{album.sample_rate / 1000:g}kHz"
        is_lossless = album.format.upper() in ["FLAC", "WAV", "AIFF", "ALAC"]
        lossless_str = " Lossless" if is_lossless else ""
        self.format_badge.setText(f"{album.format} {sr_khz} / {album.bit_depth}bit{lossless_str}")

        # Cover
        if album.cover_path and os.path.exists(album.cover_path):
            pixmap = QPixmap(album.cover_path).scaled(
                200, 200,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self.cover_label.setPixmap(pixmap)
        else:
            self._load_fallback_cover()

        # Populate Table
        self.table.setRowCount(len(tracks))
        for row, t in enumerate(tracks):
            is_playing = (self.current_playing_track_id is not None and t.id == self.current_playing_track_id)
            # Track Number or Playing Note
            num_text = "♪" if is_playing else f"{t.track_number:02d}"
            num_item = QTableWidgetItem(num_text)
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            num_item.setData(Qt.ItemDataRole.UserRole, t)
            if is_playing:
                num_item.setForeground(QColor("#e5a93b"))
                num_item.setFont(QFont("sans-serif", 14, QFont.Weight.Bold))
            else:
                num_item.setForeground(QColor("#9ca3af"))
            self.table.setItem(row, 0, num_item)

            # Title
            title_text = t.title
            if t.is_hires:
                title_text = f"★ {title_text}"
            title_item = QTableWidgetItem(title_text)
            title_item.setFont(QFont("sans-serif", 13, QFont.Weight.Medium))
            if is_playing:
                title_item.setForeground(QColor("#e5a93b"))
            self.table.setItem(row, 1, title_item)

            # Artist
            artist_item = QTableWidgetItem(t.artist)
            artist_item.setForeground(QColor("#9ca3af"))
            self.table.setItem(row, 2, artist_item)

            # Format
            format_item = QTableWidgetItem(t.audio_quality_label)
            if t.is_hires:
                format_item.setForeground(QColor("#e5a93b"))
            else:
                format_item.setForeground(QColor("#38bdf8"))
            self.table.setItem(row, 3, format_item)

            # Duration
            dur_item = QTableWidgetItem(t.duration_formatted)
            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            dur_item.setForeground(QColor("#9ca3af"))
            self.table.setItem(row, 4, dur_item)

    def _load_fallback_cover(self):
        img = QImage(200, 200, QImage.Format.Format_RGB32)
        img.fill(QColor("#1b1f2b"))
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor("#2c3447"))
        p.setBrush(QColor("#131620"))
        p.drawEllipse(20, 20, 160, 160)
        p.setBrush(QColor("#e5a93b"))
        p.drawEllipse(85, 85, 30, 30)
        p.end()
        self.cover_label.setPixmap(QPixmap.fromImage(img))

    def _on_play_all(self):
        if self.album and self.tracks:
            self.play_track_requested.emit(self.tracks[0], self.tracks)

    def _on_track_double_clicked(self, row: int, col: int):
        if 0 <= row < len(self.tracks):
            selected_track = self.tracks[row]
            # Play starting from selected track with remaining as queue
            self.play_track_requested.emit(selected_track, self.tracks)

    def set_current_playing_track(self, track: Optional[Track]):
        self.current_playing_track_id = track.id if track else None
        for row in range(self.table.rowCount()):
            num_item = self.table.item(row, 0)
            title_item = self.table.item(row, 1)
            if not num_item:
                continue
            t = num_item.data(Qt.ItemDataRole.UserRole)
            if not t:
                continue

            is_playing = (self.current_playing_track_id is not None and t.id == self.current_playing_track_id)
            if is_playing:
                num_item.setText("♪")
                num_item.setForeground(QColor("#e5a93b"))
                num_item.setFont(QFont("sans-serif", 14, QFont.Weight.Bold))
                if title_item:
                    title_item.setForeground(QColor("#e5a93b"))
            else:
                num_item.setText(f"{t.track_number:02d}")
                num_item.setForeground(QColor("#9ca3af"))
                num_item.setFont(QFont("sans-serif", 12, QFont.Weight.Normal))
                if title_item:
                    title_item.setForeground(QColor("#ffffff"))
