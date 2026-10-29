"""DAC and audiophile audio settings configuration dialog."""
import platform
from typing import List, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QGroupBox, QListWidget, QFileDialog,
    QTabWidget, QWidget, QMessageBox
)
from PySide6.QtCore import Qt, Signal

from app.core.models import AudioDevice
from app.core.database import Database
from app.core.audio_engine import AudioEngine


class DacSettingsDialog(QDialog):
    device_selected = Signal(int)
    bit_perfect_toggled = Signal(bool)
    gapless_toggled = Signal(bool)
    rescan_requested = Signal()
    library_regrouped = Signal()

    def __init__(self, audio_engine: AudioEngine, db: Database, parent=None):
        super().__init__(parent)
        self.audio_engine = audio_engine
        self.db = db

        self.setWindowTitle("DAC & オーディオ設定 (音質設定)")
        self.setFixedSize(600, 630)
        self.setStyleSheet("""
            QDialog { background-color: #12141c; color: #f3f4f6; }
            QTabWidget::pane { border: 1px solid #1f2533; background: #12141c; }
            QTabBar::tab {
                background: #181c26; color: #9ca3af; padding: 10px 18px;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
            }
            QTabBar::tab:selected { background: #222736; color: #e5a93b; font-weight: 600; }
            QGroupBox {
                border: 1px solid #232938; border-radius: 8px; margin-top: 14px; padding-top: 16px;
                font-weight: 600; color: #e5a93b;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Tab 1: Audio Hardware / DAC
        self.tab_audio = QWidget()
        self._init_audio_tab()
        self.tabs.addTab(self.tab_audio, "DAC / 出力デバイス")

        # Tab 2: Library Folders
        self.tab_library = QWidget()
        self._init_library_tab()
        self.tabs.addTab(self.tab_library, "ライブラリ管理")

        # Bottom Close Button
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.close_btn = QPushButton("完了")
        self.close_btn.setObjectName("PrimaryBtn")
        self.close_btn.clicked.connect(self.accept)
        btn_box.addWidget(self.close_btn)
        layout.addLayout(btn_box)

    def _init_audio_tab(self):
        tab_layout = QVBoxLayout(self.tab_audio)
        tab_layout.setContentsMargins(16, 16, 16, 16)
        tab_layout.setSpacing(16)

        # DAC Selection Box
        dac_group = QGroupBox("再生DAC / 出力デバイス")
        dac_layout = QVBoxLayout(dac_group)

        self.device_combo = QComboBox()
        self.devices = self.audio_engine.get_available_devices()
        selected_row = 0
        for i, dev in enumerate(self.devices):
            self.device_combo.addItem(dev.display_name, dev.index)
            if self.audio_engine.selected_device_index is not None:
                if dev.index == self.audio_engine.selected_device_index:
                    selected_row = i
            elif dev.is_default:
                selected_row = i

        if self.devices:
            self.device_combo.setCurrentIndex(selected_row)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        dac_layout.addWidget(self.device_combo)

        self.dev_info_label = QLabel()
        self.dev_info_label.setStyleSheet("color: #9ca3af; font-size: 11px;")
        dac_layout.addWidget(self.dev_info_label)
        self._update_device_info_label(selected_row)
        tab_layout.addWidget(dac_group)

        # Bit-Perfect Mode Box
        bp_group = QGroupBox("ハイレゾ・ビットパーフェクト再生")
        bp_layout = QVBoxLayout(bp_group)

        self.bp_check = QCheckBox("ビットパーフェクト直接出力を有効にする (推奨)")
        self.bp_check.setChecked(self.audio_engine.is_bit_perfect)
        self.bp_check.setStyleSheet("color: #ffffff; font-weight: 600;")
        self.bp_check.toggled.connect(self._on_bit_perfect_toggled)
        bp_layout.addWidget(self.bp_check)

        os_name = "WASAPI排他モード (Windows)" if platform.system() == "Windows" else "Core Audio Direct Output (macOS)"
        desc_text = (
            f"● OSのオーディオミキサーやリサンプラーを完全にバイパスします。\n"
            f"● 音源ファイルのサンプリング周波数（96kHz, 192kHz等）に合わせてDACクロックを自動追従。\n"
            f"● 動作モード: {os_name}\n"
            f"※ ビットパーフェクト時は音量減衰を行わず100%（0dB）でDACに送信されるため、\n"
            f"   音量は外部アンプやDAC本体のボリュームノブで調整してください。"
        )
        desc_label = QLabel(desc_text)
        desc_label.setStyleSheet("color: #9ca3af; font-size: 11px; line-height: 1.5;")
        desc_label.setWordWrap(True)
        bp_layout.addWidget(desc_label)

        tab_layout.addWidget(bp_group)

        # Gapless Playback Box
        gapless_group = QGroupBox("ギャップレス再生 (Gapless Playback)")
        gapless_layout = QVBoxLayout(gapless_group)

        self.gapless_check = QCheckBox("ギャップレス再生を有効にする (推奨)")
        self.gapless_check.setChecked(self.audio_engine.gapless_enabled)
        self.gapless_check.setStyleSheet("color: #ffffff; font-weight: 600;")
        self.gapless_check.toggled.connect(self._on_gapless_toggled)
        gapless_layout.addWidget(self.gapless_check)

        gapless_desc = (
            "● 同一サンプリングレートの楽曲間（ライブ盤、クラシック、メドレー等）で、\n"
            "   出力ストリームを切断・再接続せずPCMバッファを隙間なくシームレスに結合して再生します。\n"
            "● 曲間の無音（ギャップ）やDACの再初期化ラグを完全に解消します。\n"
            "※ サンプリングレートが異なる楽曲へ切り替わる際は、DACハードウェアクロック同期のため\n"
            "   自動的に通常切り替え（DACクロック再同期）が行われます。"
        )
        gapless_label = QLabel(gapless_desc)
        gapless_label.setStyleSheet("color: #9ca3af; font-size: 11px; line-height: 1.5;")
        gapless_label.setWordWrap(True)
        gapless_layout.addWidget(gapless_label)

        tab_layout.addWidget(gapless_group)
        tab_layout.addStretch()

    def _init_library_tab(self):
        tab_layout = QVBoxLayout(self.tab_library)
        tab_layout.setContentsMargins(16, 16, 16, 16)
        tab_layout.setSpacing(12)

        lbl = QLabel("登録済み音楽フォルダー:")
        lbl.setStyleSheet("font-weight: 600; color: #ffffff;")
        tab_layout.addWidget(lbl)

        self.folder_list = QListWidget()
        self.folder_list.setStyleSheet("""
            QListWidget { background: #161a25; border: 1px solid #283042; border-radius: 6px; padding: 6px; }
            QListWidget::item { padding: 6px; }
        """)
        self._refresh_folders()
        tab_layout.addWidget(self.folder_list)

        btn_row = QHBoxLayout()
        self.add_folder_btn = QPushButton("＋ フォルダー追加")
        self.add_folder_btn.setObjectName("ActionBtn")
        self.add_folder_btn.clicked.connect(self._on_add_folder)
        btn_row.addWidget(self.add_folder_btn)

        self.remove_folder_btn = QPushButton("－ 削除")
        self.remove_folder_btn.setObjectName("ActionBtn")
        self.remove_folder_btn.clicked.connect(self._on_remove_folder)
        btn_row.addWidget(self.remove_folder_btn)

        btn_row.addStretch()

        self.rescan_btn = QPushButton("🔄 今すぐ再スキャン")
        self.rescan_btn.setObjectName("PrimaryBtn")
        self.rescan_btn.clicked.connect(self._on_rescan)
        btn_row.addWidget(self.rescan_btn)
        tab_layout.addLayout(btn_row)

        tab_layout.addSpacing(10)

        # Compilation & Album Grouping Box
        group_box = QGroupBox("アルバムのグルーピング設定 (コンピレーション)")
        group_layout = QVBoxLayout(group_box)

        self.compilation_check = QCheckBox("コンピレーションをアルバムアーティストで一括りにする (推奨)")
        self.compilation_check.setChecked(self.db.is_group_by_album_artist())
        self.compilation_check.setStyleSheet("color: #ffffff; font-weight: 600;")
        self.compilation_check.toggled.connect(self._on_compilation_toggled)
        group_layout.addWidget(self.compilation_check)

        comp_desc = (
            "● ON (有効): 「Album Artist（例: Various Artists、サントラ盤など）」が設定されているアルバムは、\n"
            "   曲ごとにアーティストが異なっていても1枚のアルバムとしてまとめて表示します。\n"
            "● OFF (無効): 曲ごとのアーティスト名義でアルバムを厳密に分割して別々に表示します。\n"
            "※ 切り替え時にデータベースを即座に再構成します（音源の再スキャンは不要です）。"
        )
        comp_label = QLabel(comp_desc)
        comp_label.setStyleSheet("color: #9ca3af; font-size: 11px; line-height: 1.5;")
        comp_label.setWordWrap(True)
        group_layout.addWidget(comp_label)

        tab_layout.addWidget(group_box)
        tab_layout.addStretch()

    def _on_compilation_toggled(self, checked: bool):
        self.db.set_group_by_album_artist(checked)
        self.library_regrouped.emit()

    def _refresh_folders(self):
        self.folder_list.clear()
        folders = self.db.get_folders()
        for f in folders:
            self.folder_list.addItem(f)

    def _on_add_folder(self):
        path = QFileDialog.getExistingDirectory(self, "音楽フォルダーを選択")
        if path:
            self.db.add_folder(path)
            self._refresh_folders()
            self.rescan_requested.emit()

    def _on_remove_folder(self):
        item = self.folder_list.currentItem()
        if item:
            path = item.text()
            if QMessageBox.question(
                self, "フォルダーの解除",
                f"このフォルダーの楽曲をライブラリから解除しますか？\n{path}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.Yes:
                self.db.remove_folder(path)
                self._refresh_folders()
                self.rescan_requested.emit()

    def _on_rescan(self):
        self.rescan_requested.emit()
        self.accept()

    def _on_device_changed(self, index: int):
        dev_index = self.device_combo.currentData()
        if dev_index is not None:
            self.audio_engine.set_output_device(int(dev_index))
            self.db.set_setting("selected_dac_index", dev_index)
            self.device_selected.emit(int(dev_index))
            self._update_device_info_label(index)

    def _update_device_info_label(self, row: int):
        if 0 <= row < len(self.devices):
            d = self.devices[row]
            self.dev_info_label.setText(
                f"API: {d.hostapi_name} | 最大出力チャンネル数: {d.max_output_channels}ch | 標準サンプリング周波数: {d.default_samplerate:g}Hz"
            )

    def _on_bit_perfect_toggled(self, checked: bool):
        self.audio_engine.set_bit_perfect(checked)
        self.db.set_setting("bit_perfect", "1" if checked else "0")
        self.bit_perfect_toggled.emit(checked)

    def _on_gapless_toggled(self, checked: bool):
        self.audio_engine.set_gapless_enabled(checked)
        self.db.set_setting("gapless_playback", "1" if checked else "0")
        self.gapless_toggled.emit(checked)
