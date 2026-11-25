@echo off
setlocal enabledelayedexpansion

set "APP_NAME=Aura Lossless Audio Player"
set "ZIP_NAME=Aura-Lossless-Audio-Player-Windows-x64.zip"

cd /d "%~dp0"

set "PYINSTALLER_BIN=.venv\Scripts\pyinstaller.exe"
if not exist "%PYINSTALLER_BIN%" (
    where pyinstaller >nul 2>nul
    if errorlevel 1 (
        echo Error: PyInstaller not found.
        echo Install it with: .venv\Scripts\pip install pyinstaller
        exit /b 1
    )
    set "PYINSTALLER_BIN=pyinstaller"
)

echo ==^> Cleaning previous build artifacts...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"

echo ==^> Building Windows application with PyInstaller...
"%PYINSTALLER_BIN%" ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --name "%APP_NAME%" ^
    --collect-all _sounddevice_data ^
    --collect-all _soundfile_data ^
    --hidden-import sounddevice ^
    --hidden-import soundfile ^
    --hidden-import mutagen ^
    --hidden-import numpy ^
    --exclude-module tkinter ^
    --exclude-module PySide6.QtWebEngine ^
    --exclude-module PySide6.QtWebEngineCore ^
    --exclude-module PySide6.QtWebEngineWidgets ^
    --exclude-module PySide6.Qt3DCore ^
    --exclude-module PySide6.Qt3DRender ^
    --exclude-module PySide6.QtQml ^
    --exclude-module PySide6.QtQuick ^
    main.py

if errorlevel 1 (
    echo Error: PyInstaller build failed.
    exit /b 1
)

if not exist "dist\%APP_NAME%\%APP_NAME%.exe" (
    echo Error: Expected executable not found at dist\%APP_NAME%\%APP_NAME%.exe
    exit /b 1
)

echo ==^> Creating ZIP archive (%ZIP_NAME%)...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\%APP_NAME%' -DestinationPath 'dist\%ZIP_NAME%' -Force"
if errorlevel 1 (
    echo Error: Failed to create ZIP archive.
    exit /b 1
)

echo.
echo ==^> Release build complete!
echo   Folder: dist\%APP_NAME%\
echo   Archive: dist\%ZIP_NAME%
endlocal

