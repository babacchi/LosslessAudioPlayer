"""All-tracks list view with sorting and Hi-Res badges."""
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt, Signal

from app.core.models import Track


class NumericTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically based on a numeric sort_key."""
    def __init__(self, display_text: str, sort_key: float):
        super().__init__(display_text)
        self.sort_key = sort_key

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.sort_key < other.sort_key
        return super().__lt__(other)


class TrackTableView(QWidget):
    track_selected = Signal(object, list)  # (Track, List[Track])

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tracks: List[Track] = []
        self.current_playing_track_id: Optional[int] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["#", "タイトル", "アーティスト", "アルバム", "フォーマット", "時間"])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

    def set_tracks(self, tracks: List[Track]):
        self.tracks = tracks
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(tracks))

        for row, t in enumerate(tracks):
            is_playing = (self.current_playing_track_id is not None and t.id == self.current_playing_track_id)

            # Index / Playing ♪
            idx_text = "♪" if is_playing else f"{row + 1:02d}"
            idx_item = NumericTableWidgetItem(idx_text, float(row + 1))
            idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            idx_item.setData(Qt.ItemDataRole.UserRole, t)
            idx_item.setData(Qt.ItemDataRole.UserRole + 1, row + 1)
            if is_playing:
                idx_item.setForeground(QColor("#e5a93b"))
                idx_item.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
            else:
                idx_item.setForeground(QColor("#9ca3af"))
            self.table.setItem(row, 0, idx_item)

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
            artist_item.setForeground(QColor("#d1d5db"))
            self.table.setItem(row, 2, artist_item)

            # Album
            album_item = QTableWidgetItem(t.album)
            album_item.setForeground(QColor("#9ca3af"))
            self.table.setItem(row, 3, album_item)

            # Format
            format_sort_key = float(t.sample_rate * 100 + t.bit_depth)
            format_item = NumericTableWidgetItem(t.audio_quality_label, format_sort_key)
            if t.is_hires:
                format_item.setForeground(QColor("#e5a93b"))
            else:
                format_item.setForeground(QColor("#38bdf8"))
            self.table.setItem(row, 4, format_item)

            # Duration
            dur_item = NumericTableWidgetItem(t.duration_formatted, float(t.duration))
            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            dur_item.setForeground(QColor("#9ca3af"))
            self.table.setItem(row, 5, dur_item)

        self.table.setSortingEnabled(True)

    def set_current_playing_track(self, track: Optional[Track]):
        self.current_playing_track_id = track.id if track else None

        for row in range(self.table.rowCount()):
            idx_item = self.table.item(row, 0)
            title_item = self.table.item(row, 1)
            if not idx_item:
                continue

            t = idx_item.data(Qt.ItemDataRole.UserRole)
            orig_idx = idx_item.data(Qt.ItemDataRole.UserRole + 1) or (row + 1)
            if not t:
                continue

            is_playing = (self.current_playing_track_id is not None and t.id == self.current_playing_track_id)
            if is_playing:
                idx_item.setText("♪")
                idx_item.setForeground(QColor("#e5a93b"))
                idx_item.setFont(QFont("sans-serif", 14, QFont.Weight.Bold))
                if title_item:
                    title_item.setForeground(QColor("#e5a93b"))
            else:
                idx_item.setText(f"{orig_idx:02d}")
                idx_item.setForeground(QColor("#9ca3af"))
                idx_item.setFont(QFont("sans-serif", 12, QFont.Weight.Normal))
                if title_item:
                    title_item.setForeground(QColor("#ffffff"))

    def _on_row_double_clicked(self, row: int, col: int):
        item = self.table.item(row, 0)
        if not item:
            return
        track = item.data(Qt.ItemDataRole.UserRole)
        if not track:
            return

        # Queue contains tracks in current visible (sorted) order
        queue = []
        for r in range(self.table.rowCount()):
            row_item = self.table.item(r, 0)
            if row_item:
                t = row_item.data(Qt.ItemDataRole.UserRole)
                if t:
                    queue.append(t)

        self.track_selected.emit(track, queue)
