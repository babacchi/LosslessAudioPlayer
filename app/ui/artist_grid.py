"""Artist grid view with circular avatars, Hi-Res badges, responsive auto-wrapping and size scaling."""
import os
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QGridLayout, QScrollArea, QPushButton, QSizePolicy, QSlider
)
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QFont, QCursor, QBrush, QPen
from PySide6.QtCore import Qt, Signal, QSize, QEvent

from app.core.models import Artist


class ArtistCard(QFrame):
    clicked = Signal(object)       # Artist
    play_clicked = Signal(object)  # Artist

    def __init__(self, artist: Artist, avatar_size: int = 150, parent=None):
        super().__init__(parent)
        self.artist = artist
        self.avatar_size = avatar_size
        self.setObjectName("ArtistCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        card_w = self.avatar_size + 24
        card_h = self.avatar_size + 76
        self.setFixedSize(card_w, card_h)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Avatar Container with Badges
        self.avatar_container = QWidget()
        self.avatar_container.setFixedSize(self.avatar_size, self.avatar_size)
        avatar_layout = QVBoxLayout(self.avatar_container)
        avatar_layout.setContentsMargins(0, 0, 0, 0)

        self.avatar_label = QLabel(self.avatar_container)
        self.avatar_label.setFixedSize(self.avatar_size, self.avatar_size)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_layout.addWidget(self.avatar_label)

        # Hi-Res Badge in corner
        if artist.is_hires:
            self.hires_label = QLabel("Hi-Res", self.avatar_container)
            self.hires_label.setObjectName("HiResBadge")
            self.hires_label.move(self.avatar_size - 48, 4)
            self.hires_label.show()

        layout.addWidget(self.avatar_container, alignment=Qt.AlignmentFlag.AlignCenter)

        # Artist Name
        self.name_label = QLabel(artist.name)
        self.name_label.setObjectName("ArtistCardName")
        self.name_label.setToolTip(artist.name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.name_label)

        # Meta (Albums, Tracks)
        alb_text = f"{artist.album_count} アルバム" if artist.album_count > 0 else ""
        trk_text = f"{artist.track_count}曲"
        meta_parts = [p for p in [alb_text, trk_text] if p]
        self.meta_label = QLabel(" • ".join(meta_parts))
        self.meta_label.setObjectName("ArtistCardMeta")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.meta_label)

        layout.addStretch()
        self._load_avatar()

    def set_avatar_size(self, size: int):
        self.avatar_size = size
        card_w = size + 24
        card_h = size + 76
        self.setFixedSize(card_w, card_h)
        self.avatar_container.setFixedSize(size, size)
        self.avatar_label.setFixedSize(size, size)
        if hasattr(self, "hires_label"):
            self.hires_label.move(size - 48, 4)
        self._load_avatar()

    def _load_avatar(self):
        s = self.avatar_size
        img = QImage(s, s, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        has_image = False
        if self.artist.cover_path and os.path.exists(self.artist.cover_path):
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
                p.setPen(QPen(border_color, 2))
                p.drawEllipse(2, 2, s - 4, s - 4)
                has_image = True

        if not has_image:
            # Fallback artist avatar: circular badge with artist initials
            p.setBrush(QBrush(QColor("#1b1f2b")))
            border_color = QColor("#e5a93b" if self.artist.is_hires else "#2c3447")
            p.setPen(QPen(border_color, 2))
            p.drawEllipse(2, 2, s - 4, s - 4)

            p.setPen(QColor("#e5a93b" if self.artist.is_hires else "#9ca3af"))
            font = QFont()
            font.setPointSize(max(10, int(s * 0.32)))
            font.setBold(True)
            p.setFont(font)
            initial = (self.artist.name[0] if self.artist.name else "A").upper()
            p.drawText(0, 0, s, s, Qt.AlignmentFlag.AlignCenter, initial)

        p.end()
        self.avatar_label.setPixmap(QPixmap.fromImage(img))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.artist)
        super().mousePressEvent(event)


class ArtistGridView(QWidget):
    artist_selected = Signal(object)       # Artist
    play_artist_requested = Signal(object) # Artist
    avatar_size_changed = Signal(int)      # New avatar size in pixels

    def __init__(self, parent=None):
        super().__init__(parent)
        self.artists: List[Artist] = []
        self.cards: List[ArtistCard] = []
        self.avatar_size: int = 150
        self._current_cols: int = 0

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header with count and size slider
        self.header_layout = QHBoxLayout()
        self.count_label = QLabel("0 アーティスト")
        self.count_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        self.header_layout.addWidget(self.count_label)
        self.header_layout.addStretch()

        # Size slider controls
        size_container = QWidget()
        size_layout = QHBoxLayout(size_container)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.setSpacing(6)

        size_lbl_min = QLabel("▫")
        size_lbl_min.setStyleSheet("color: #6b7280; font-size: 11px;")
        size_layout.addWidget(size_lbl_min)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(100, 240)
        self.size_slider.setValue(self.avatar_size)
        self.size_slider.setFixedWidth(120)
        self.size_slider.setToolTip("アーティストアイコンの表示サイズを調整")
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
        empty_label = QLabel("アーティストが見つかりません")
        empty_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #6b7280;")
        empty_sub = QLabel("検索条件を変更するか、上部バーの「＋ フォルダー追加」から\n楽曲フォルダーを登録してください。")
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
        self.avatar_size = value
        for card in self.cards:
            card.set_avatar_size(value)
        self._current_cols = 0
        self._relayout()
        self.avatar_size_changed.emit(value)

    def set_avatar_size(self, size: int):
        size = max(100, min(240, size))
        self.avatar_size = size
        self.size_slider.blockSignals(True)
        self.size_slider.setValue(size)
        self.size_slider.blockSignals(False)
        for card in self.cards:
            card.set_avatar_size(size)
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

        card_w = self.avatar_size + 24
        spacing = 16
        available = max(0, viewport_w - 8)

        cols = max(1, (available + spacing) // (card_w + spacing))

        if cols == self._current_cols and self.grid_layout.count() == len(self.cards):
            return

        self._current_cols = cols

        while self.grid_layout.count():
            self.grid_layout.takeAt(0)

        for idx, card in enumerate(self.cards):
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

    def set_artists(self, artists: List[Artist]):
        self.artists = artists
        hires_count = sum(1 for a in artists if a.is_hires)
        badge_text = f" ({hires_count} Hi-Res)" if hires_count > 0 else ""
        self.count_label.setText(f"{len(artists)} アーティスト{badge_text}")

        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.cards.clear()
        self._current_cols = 0

        if not artists:
            self.empty_widget.show()
            self.scroll_area.hide()
            return

        self.empty_widget.hide()
        self.scroll_area.show()

        for artist in artists:
            card = ArtistCard(artist, avatar_size=self.avatar_size)
            card.clicked.connect(self.artist_selected.emit)
            card.play_clicked.connect(self.play_artist_requested.emit)
            self.cards.append(card)

        self._relayout()

