"""Sony Music Center style album grid view with Hi-Res badges and smooth interaction."""
import os
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QGridLayout, QScrollArea, QPushButton, QSizePolicy, QSlider
)
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QFont, QCursor
from PySide6.QtCore import Qt, Signal, QSize, QEvent

from app.core.models import Album


class AlbumCard(QFrame):
    clicked = Signal(object)      # Album
    play_clicked = Signal(object) # Album

    def __init__(self, album: Album, cover_size: int = 170, parent=None):
        super().__init__(parent)
        self.album = album
        self.cover_size = cover_size
        self.setObjectName("AlbumCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        card_w = self.cover_size + 20
        card_h = self.cover_size + 85
        self.setFixedSize(card_w, card_h)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Cover container with Badges
        self.cover_container = QWidget()
        self.cover_container.setFixedSize(self.cover_size, self.cover_size)
        cover_layout = QVBoxLayout(self.cover_container)
        cover_layout.setContentsMargins(0, 0, 0, 0)

        self.cover_label = QLabel(self.cover_container)
        self.cover_label.setFixedSize(self.cover_size, self.cover_size)
        self.cover_label.setStyleSheet("border-radius: 8px; background-color: #1a1e2b;")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Hi-Res Badge in corner
        if album.is_hires:
            self.hires_label = QLabel("Hi-Res", self.cover_container)
            self.hires_label.setObjectName("HiResBadge")
            self.hires_label.move(8, 8)
            self.hires_label.show()

        # Quality badge in bottom-right corner
        self.qual_badge = QLabel(f"{album.format} {int(album.sample_rate/1000)}k/{album.bit_depth}b", self.cover_container)
        self.qual_badge.setObjectName("FormatBadge")
        self.qual_badge.adjustSize()
        self.qual_badge.move(self.cover_size - self.qual_badge.width() - 8, self.cover_size - self.qual_badge.height() - 8)
        self.qual_badge.show()

        layout.addWidget(self.cover_container)

        # Title
        self.title_label = QLabel(album.title)
        self.title_label.setObjectName("AlbumTitle")
        self.title_label.setToolTip(album.title)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.title_label)

        # Artist
        self.artist_label = QLabel(album.artist)
        self.artist_label.setObjectName("AlbumArtist")
        self.artist_label.setToolTip(album.artist)
        layout.addWidget(self.artist_label)

        # Meta (Year, Tracks)
        meta_parts = []
        if album.year:
            meta_parts.append(str(album.year))
        meta_parts.append(f"{album.track_count}曲")
        self.meta_label = QLabel(" • ".join(meta_parts))
        self.meta_label.setObjectName("AlbumMeta")
        layout.addWidget(self.meta_label)

        layout.addStretch()
        self._load_cover()

    def set_cover_size(self, size: int):
        """Update artwork and card dimensions dynamically."""
        self.cover_size = size
        card_w = size + 20
        card_h = size + 85
        self.setFixedSize(card_w, card_h)
        self.cover_container.setFixedSize(size, size)
        self.cover_label.setFixedSize(size, size)
        if hasattr(self, "qual_badge"):
            self.qual_badge.adjustSize()
            self.qual_badge.move(size - self.qual_badge.width() - 8, size - self.qual_badge.height() - 8)
        self._load_cover()

    def _load_cover(self):
        s = self.cover_size
        if self.album.cover_path and os.path.exists(self.album.cover_path):
            pixmap = QPixmap(self.album.cover_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    s, s,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.cover_label.setPixmap(pixmap)
                return

        # Fallback generated vinyl icon
        img = QImage(s, s, QImage.Format.Format_RGB32)
        img.fill(QColor("#1b1f2b"))
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor("#2c3447"))
        p.setBrush(QColor("#131620"))
        pad = max(4, int(s * 0.08))
        p.drawEllipse(pad, pad, s - 2 * pad, s - 2 * pad)
        p.setBrush(QColor("#e5a93b" if self.album.is_hires else "#4b5563"))
        hole = max(8, int(s * 0.2))
        p.drawEllipse((s - hole) // 2, (s - hole) // 2, hole, hole)
        p.end()
        self.cover_label.setPixmap(QPixmap.fromImage(img))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.album)
        super().mousePressEvent(event)


class AlbumGridView(QWidget):
    album_selected = Signal(object)       # Album
    play_album_requested = Signal(object) # Album
    jacket_size_changed = Signal(int)     # New cover size in pixels

    def __init__(self, parent=None):
        super().__init__(parent)
        self.albums: List[Album] = []
        self.cards: List[AlbumCard] = []
        self.cover_size: int = 170
        self._current_cols: int = 0

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header with count and jacket size slider
        self.header_layout = QHBoxLayout()
        self.count_label = QLabel("0 アルバム")
        self.count_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        self.header_layout.addWidget(self.count_label)
        self.header_layout.addStretch()

        # Jacket size slider controls
        size_container = QWidget()
        size_layout = QHBoxLayout(size_container)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.setSpacing(6)

        size_lbl_min = QLabel("▫")
        size_lbl_min.setStyleSheet("color: #6b7280; font-size: 11px;")
        size_layout.addWidget(size_lbl_min)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(110, 260)
        self.size_slider.setValue(self.cover_size)
        self.size_slider.setFixedWidth(120)
        self.size_slider.setToolTip("アルバムジャケットの表示サイズを調整")
        self.size_slider.valueChanged.connect(self._on_size_slider_changed)
        size_layout.addWidget(self.size_slider)

        size_lbl_max = QLabel("◻")
        size_lbl_max.setStyleSheet("color: #9ca3af; font-size: 16px;")
        size_layout.addWidget(size_lbl_max)

        self.header_layout.addWidget(size_container)
        main_layout.addLayout(self.header_layout)

        # Scroll Area for Grid (auto-wrapping horizontally, scrolling vertically as needed)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.scroll_area.setWidget(self.grid_container)
        main_layout.addWidget(self.scroll_area)

        # Install event filter on scroll_area viewport to reflow instantly on resize
        self.scroll_area.viewport().installEventFilter(self)

        # Empty state widget
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label = QLabel("ライブラリに音楽がありません")
        empty_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #6b7280;")
        empty_sub = QLabel("上部バーの「＋ フォルダー追加」または設定から\n楽曲フォルダーを登録してください。")
        empty_sub.setStyleSheet("font-size: 13px; color: #4b5563; line-height: 1.6;")
        empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_label, alignment=Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_sub, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.empty_widget)

    def eventFilter(self, watched, event):
        if watched == self.scroll_area.viewport() and event.type() == QEvent.Type.Resize:
            self._relayout()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _on_size_slider_changed(self, value: int):
        self.cover_size = value
        for card in self.cards:
            card.set_cover_size(value)
        self._current_cols = 0
        self._relayout()
        self.jacket_size_changed.emit(value)

    def set_cover_size(self, size: int):
        size = max(110, min(260, size))
        self.cover_size = size
        self.size_slider.blockSignals(True)
        self.size_slider.setValue(size)
        self.size_slider.blockSignals(False)
        for card in self.cards:
            card.set_cover_size(size)
        self._current_cols = 0
        self._relayout()

    def _relayout(self):
        """Dynamically calculate columns and wrap cards based on available viewport width and card size."""
        if not self.cards:
            return

        viewport_w = self.scroll_area.viewport().width()
        if viewport_w <= 0:
            viewport_w = self.width() - 40
        if viewport_w <= 0:
            viewport_w = 800

        card_w = self.cover_size + 20
        spacing = 16
        available = max(0, viewport_w - 8)

        # Calculate number of columns that fit horizontally
        cols = max(1, (available + spacing) // (card_w + spacing))

        # Only reposition if the column count has changed or layout is not yet populated
        if cols == self._current_cols and self.grid_layout.count() == len(self.cards):
            return

        self._current_cols = cols

        # Remove cards from existing grid positions without deleting widgets
        while self.grid_layout.count():
            self.grid_layout.takeAt(0)

        # Re-place cards into new (row, col) positions
        for idx, card in enumerate(self.cards):
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

    def set_albums(self, albums: List[Album]):
        self.albums = albums
        hires_count = sum(1 for a in albums if a.is_hires)
        badge_text = f" ({hires_count} Hi-Res)" if hires_count > 0 else ""
        self.count_label.setText(f"{len(albums)} アルバム{badge_text}")

        # Clear existing items and cards
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.cards.clear()
        self._current_cols = 0

        if not albums:
            self.empty_widget.show()
            self.scroll_area.hide()
            return

        self.empty_widget.hide()
        self.scroll_area.show()

        # Build album card widgets using current cover_size
        for album in albums:
            card = AlbumCard(album, cover_size=self.cover_size)
            card.clicked.connect(self.album_selected.emit)
            card.play_clicked.connect(self.play_album_requested.emit)
            self.cards.append(card)

        # Automatically calculate columns and wrap cards
        self._relayout()
