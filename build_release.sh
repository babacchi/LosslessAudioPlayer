#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Aura Lossless Audio Player"
BUNDLE_ID="com.auraaudio.losslessplayer"
ARCH="$(uname -m)"
DMG_NAME="Aura-Lossless-Audio-Player-macOS-${ARCH}.dmg"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${ROOT_DIR}/.venv/bin/python3"
PYINSTALLER_BIN="${ROOT_DIR}/.venv/bin/pyinstaller"

if [[ ! -x "$PYINSTALLER_BIN" ]]; then
    echo "Error: PyInstaller not found at $PYINSTALLER_BIN"
    echo "Install it with: .venv/bin/pip install pyinstaller"
    exit 1
fi

echo "==> Cleaning previous build artifacts..."
rm -rf build dist "${APP_NAME}.spec"

echo "==> Building macOS .app bundle with PyInstaller..."
"$PYINSTALLER_BIN" \
    --noconfirm \
    --clean \
    --windowed \
    --name "$APP_NAME" \
    --osx-bundle-identifier "$BUNDLE_ID" \
    --collect-all _sounddevice_data \
    --collect-all _soundfile_data \
    --hidden-import sounddevice \
    --hidden-import soundfile \
    --hidden-import mutagen \
    --hidden-import numpy \
    --exclude-module tkinter \
    --exclude-module PySide6.QtWebEngine \
    --exclude-module PySide6.QtWebEngineCore \
    --exclude-module PySide6.QtWebEngineWidgets \
    --exclude-module PySide6.Qt3DCore \
    --exclude-module PySide6.Qt3DRender \
    --exclude-module PySide6.QtQml \
    --exclude-module PySide6.QtQuick \
    main.py

APP_PATH="dist/${APP_NAME}.app"
if [[ ! -d "$APP_PATH" ]]; then
    echo "Error: Expected app bundle not found at $APP_PATH"
    exit 1
fi

echo "==> Ad-hoc code signing ${APP_PATH}..."
codesign --force --deep --sign - "$APP_PATH"

echo "==> Creating DMG installer (${DMG_NAME})..."
DMG_STAGING="build/dmg_staging"
rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"
cp -R "$APP_PATH" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"

hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$DMG_STAGING" \
    -ov \
    -format UDZO \
    "dist/${DMG_NAME}"

rm -rf "$DMG_STAGING"

echo ""
echo "==> Release build complete!"
ls -lh "dist/${DMG_NAME}"
du -sh "$APP_PATH"

