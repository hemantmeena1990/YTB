@echo off
setlocal enabledelayedexpansion
title YouTube Automation Dashboard Launcher
echo ==============================================
echo   YouTube Automation Dashboard - Setup & Launch
echo ==============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found:
python --version

REM Check pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip is not available.
    echo Please ensure pip is installed.
    pause
    exit /b 1
)
echo [OK] pip found

echo.
echo Checking required Python packages...

set PACKAGES=flask selenium webdriver-manager psutil requests
set MISSING=

for %%p in (%PACKAGES%) do (
    python -c "import %%p" 2>nul
    if errorlevel 1 (
        echo [MISSING] %%p
        set MISSING=1
    ) else (
        echo [OK] %%p
    )
)

if defined MISSING (
    echo.
    set /p INSTALL="Some packages are missing. Install them now? (y/n): "
    if /i "!INSTALL!"=="y" (
        echo Installing missing packages...
        for %%p in (%PACKAGES%) do (
            python -c "import %%p" 2>nul
            if errorlevel 1 (
                echo Installing %%p...
                pip install %%p
            )
        )
        echo Installation complete.
    ) else (
        echo Please install required packages manually.
        pause
        exit /b 1
    )
)

echo.
echo All prerequisites satisfied.
echo Launching Dashboard in minimized window...

REM Launch YTDash.py minimized (the dashboard will open browser automatically)
start /min python YTDash.py

echo.
echo Dashboard is starting. You can close this window.
echo Dashboard will open automatically in your browser.
timeout /t 2 /nobreak >nul
exit