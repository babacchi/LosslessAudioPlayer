"""Dark audiophile theme inspired by Sony Music Center for PC."""

DARK_THEME_QSS = """
/* Base Window & Widget */
QWidget {
    background-color: #0d0f14;
    color: #e5e7eb;
    font-family: "Helvetica Neue", "Arial";
    font-size: 13px;
    selection-background-color: #e5a93b;
    selection-color: #0d0f14;
}

QMainWindow {
    background-color: #0d0f14;
}

/* Scroll Area & Scrollbars */
QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollBar:vertical {
    border: none;
    background: #11131a;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #282d3b;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #3b4255;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    border: none;
    background: #11131a;
    height: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #282d3b;
    min-width: 30px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #3b4255;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Sidebar Navigation */
QFrame#Sidebar {
    background-color: #12141c;
    border-right: 1px solid #1c202d;
}

QPushButton#NavButton {
    background-color: transparent;
    color: #9ca3af;
    text-align: left;
    padding: 10px 16px;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton#NavButton:hover {
    background-color: #1b1e2a;
    color: #ffffff;
}
QPushButton#NavButton:checked {
    background-color: #212635;
    color: #e5a93b;
    font-weight: 600;
    border-left: 3px solid #e5a93b;
    border-top-left-radius: 0px;
    border-bottom-left-radius: 0px;
}

/* Top Header Bar */
QFrame#TopBar {
    background-color: #12141c;
    border-bottom: 1px solid #1c202d;
    padding: 8px 16px;
}

QLineEdit#SearchInput {
    background-color: #1a1e2b;
    color: #ffffff;
    border: 1px solid #282f42;
    border-radius: 18px;
    padding: 6px 14px;
    font-size: 13px;
}
QLineEdit#SearchInput:focus {
    border: 1px solid #e5a93b;
    background-color: #1f2434;
}

QPushButton#ActionBtn {
    background-color: #1a1e2b;
    color: #e5e7eb;
    border: 1px solid #2a3144;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 500;
}
QPushButton#ActionBtn:hover {
    background-color: #252b3d;
    border-color: #3f4963;
    color: #ffffff;
}

/* Album Detail Header Frame */
QFrame#AlbumHeaderFrame, QFrame#ArtistHeaderFrame {
    background-color: #12151e;
    border: 1px solid #1f2537;
    border-radius: 12px;
}

QPushButton#PrimaryBtn {
    background-color: #e5a93b;
    color: #0b0c10;
    border: none;
    border-radius: 8px;
    padding: 9px 22px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#PrimaryBtn:hover {
    background-color: #f5b746;
    color: #0b0c10;
}
QPushButton#PrimaryBtn:pressed {
    background-color: #cca72f;
    color: #0b0c10;
}

/* DAC Dropdown Selector */
QComboBox {
    background-color: #1a1e2b;
    color: #f3f4f6;
    border: 1px solid #2e3549;
    border-radius: 6px;
    padding: 3px 24px 3px 10px;
    font-size: 11px;
    min-width: 140px;
    max-width: 180px;
    min-height: 24px;
}
QComboBox:hover {
    border-color: #e5a93b;
    background-color: #212637;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #2a3144;
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #9ca3af;
    width: 0px;
    height: 0px;
}
QComboBox::down-arrow:hover {
    border-top-color: #e5a93b;
}
QComboBox QAbstractItemView {
    background-color: #161923;
    border: 1px solid #2e3549;
    selection-background-color: #2b3245;
    selection-color: #e5a93b;
    padding: 4px;
    font-size: 11px;
}

/* Album Card */
QFrame#AlbumCard {
    background-color: #141721;
    border: 1px solid #1f2433;
    border-radius: 10px;
    padding: 10px;
}
QFrame#AlbumCard:hover {
    background-color: #1b202e;
    border: 1px solid #37415a;
}

/* Artist Card */
QFrame#ArtistCard {
    background-color: #141721;
    border: 1px solid #1f2433;
    border-radius: 12px;
    padding: 10px;
}
QFrame#ArtistCard:hover {
    background-color: #1b202e;
    border: 1px solid #e5a93b;
}

QLabel#ArtistCardName {
    color: #ffffff;
    font-size: 13px;
    font-weight: 600;
}
QLabel#ArtistCardMeta {
    color: #9ca3af;
    font-size: 11px;
}

QLabel#AlbumTitle {
    color: #ffffff;
    font-size: 13px;
    font-weight: 600;
}
QLabel#AlbumArtist {
    color: #9ca3af;
    font-size: 12px;
}
QLabel#AlbumMeta {
    color: #6b7280;
    font-size: 11px;
}

/* Hi-Res Badges */
QLabel#HiResBadge {
    background-color: #201a08;
    color: #e5a93b;
    border: 1px solid #e5a93b;
    border-radius: 4px;
    padding: 1px 5px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

QLabel#FormatBadge {
    background-color: #182030;
    color: #38bdf8;
    border: 1px solid #1e3a5f;
    border-radius: 4px;
    padding: 1px 5px;
    font-size: 10px;
    font-weight: 600;
}

/* Player Bar (Bottom) */
QFrame#PlayerBar {
    background-color: #11131a;
    border-top: 1px solid #1e2330;
    padding: 8px 16px;
}

QLabel#NowPlayingTitle {
    color: #ffffff;
    font-size: 14px;
    font-weight: 600;
}
QLabel#NowPlayingArtist {
    color: #9ca3af;
    font-size: 12px;
}
QLabel#StreamInfo {
    color: #e5a93b;
    font-size: 11px;
    font-family: Menlo, Monaco, Consolas, monospace;
}

/* Round Play/Pause Controls */
QPushButton#PlayButton {
    background-color: #e5a93b;
    color: #0b0c10;
    border: none;
    border-radius: 20px;
    width: 40px;
    height: 40px;
    font-size: 16px;
}
QPushButton#PlayButton:hover {
    background-color: #f5b746;
}

QPushButton#ControlBtn {
    background-color: transparent;
    color: #d1d5db;
    border: none;
    border-radius: 16px;
    width: 32px;
    height: 32px;
    font-size: 14px;
}
QPushButton#ControlBtn:hover {
    background-color: #1e2230;
    color: #ffffff;
}

/* Shuffle / Repeat Toggle Control Buttons */
QPushButton#ToggleControlBtn {
    background-color: #161a24;
    color: #9ca3af;
    border: 1px solid #2e3547;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
    min-height: 28px;
    min-width: 64px;
}
QPushButton#ToggleControlBtn:hover {
    background-color: #212738;
    color: #ffffff;
    border-color: #4b5568;
}
QPushButton#ToggleControlBtn[active="true"] {
    background-color: #3d2f14;
    color: #f5b746;
    border: 1.5px solid #e5a93b;
    font-weight: 700;
}
QPushButton#ToggleControlBtn[active="true"]:hover {
    background-color: #4d3a18;
    color: #ffd073;
    border-color: #ffd073;
}

/* Bit-Perfect Mode Toggle Button */
QPushButton#BitPerfectBtn {
    background-color: #13241b;
    color: #10b981;
    border: 1px solid #10b981;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
QPushButton#BitPerfectBtn:hover {
    background-color: #183325;
}
QPushButton#BitPerfectBtn[active="false"] {
    background-color: #1a1e2b;
    color: #6b7280;
    border: 1px solid #2c3345;
}

/* Custom Audiophile Sliders */
QSlider::groove:horizontal {
    height: 4px;
    background: #252b3a;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #e5a93b;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #ffffff;
    border: 2px solid #e5a93b;
    width: 12px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 6px;
}
QSlider::handle:horizontal:hover {
    background: #fef08a;
    border: 2px solid #f59e0b;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}

/* Track Table View */
QTableWidget {
    background-color: transparent;
    border: none;
    gridline-color: transparent;
    selection-background-color: #1d2332;
    selection-color: #ffffff;
}
QTableWidget::item {
    padding: 6px 10px;
    border-bottom: 1px solid #161922;
}
QTableWidget::item:hover {
    background-color: #181d2a;
}
QHeaderView::section {
    background-color: #0f1118;
    color: #9ca3af;
    border: none;
    border-bottom: 1px solid #1f2533;
    padding: 6px 10px;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
}
QHeaderView::section:hover {
    background-color: #1a1e2b;
    color: #e5a93b;
}
QHeaderView::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #e5a93b;
    width: 0px;
    height: 0px;
    margin-left: 4px;
}
QHeaderView::up-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #e5a93b;
    width: 0px;
    height: 0px;
    margin-left: 4px;
}
"""
