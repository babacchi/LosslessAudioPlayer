#!/usr/bin/env python3
"""Main entry point for Aura Lossless Audio Player."""
import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.core.database import Database
from app.core.audio_engine import AudioEngine
from app.ui.styles import DARK_THEME_QSS
from app.ui.main_window import MainWindow


def main():
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Aura Lossless Audio Player")
    app.setOrganizationName("AuraAudio")

    # Apply Audiophile Dark Theme
    app.setStyleSheet(DARK_THEME_QSS)

    # Initialize Core Subsystems
    db = Database()
    audio_engine = AudioEngine()

    window = MainWindow(db, audio_engine)
    window.show()

    # Clean shutdown hook
    def on_exit():
        audio_engine.stop()

    app.aboutToQuit.connect(on_exit)
    ret = app.exec()

    # Destroy widgets cleanly while QApplication is still alive to avoid
    # PySide6 atexit destructionVisitor crashes in QObject::~QObject.
    import gc
    from PySide6.QtCore import QEvent
    try:
        import shiboken6
        if shiboken6.isValid(window):
            shiboken6.delete(window)
    except Exception:
        window.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()

    del window
    gc.collect()
    app.processEvents()
    del app
    gc.collect()
    sys.exit(ret)


if __name__ == "__main__":
    main()
