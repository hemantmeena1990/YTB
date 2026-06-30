@echo off
title YouTube Automation Dashboard
echo ==============================================
echo   YouTube Automation Dashboard
echo ==============================================
echo.

cd /d "%~dp0"

REM ==============================================
REM Check Python
REM ==============================================
echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python 3.8 or higher from https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo.

REM ==============================================
REM Install/Update Required Python Packages
REM ==============================================
echo Installing/Updating required Python packages...
echo.

echo [1/6] Installing Flask and web framework...
pip install --upgrade flask flask-cors

echo [2/6] Installing Selenium and ChromeDriver manager...
pip install --upgrade selenium webdriver-manager

echo [3/6] Installing undetected-chromedriver (anti-detection)...
pip install --upgrade undetected-chromedriver

echo [4/6] Installing utilities and networking...
pip install --upgrade requests psutil yt-dlp

echo [5/6] Installing Playwright...
pip install --upgrade playwright
python -c "from playwright.sync_api import sync_playwright; sync_playwright().start().stop()" 2>nul
if errorlevel 1 (
    echo Installing Playwright Chromium...
    playwright install chromium
)

echo [6/6] Installing additional dependencies...
pip install --upgrade fake-useragent numpy

echo.
echo All packages installed successfully!
echo.

REM ==============================================
REM Check and Start PO Token Server (bgutil)
REM ==============================================
echo ==============================================
echo   PO Token Server Setup
echo ==============================================
echo.

if exist "bgutil-ytdlp-pot-provider\server\build\main.js" (
    echo Starting bgutil PO Token HTTP Server on port 4416...
    start "PO Token Server (bgutil)" /min cmd /c "cd bgutil-ytdlp-pot-provider\server && node build/main.js --port 4416"
    timeout /t 3 /nobreak >nul
    echo [OK] bgutil server started on port 4416.
) else (
    echo [WARNING] bgutil-ytdlp-pot-provider not found.
    echo To install: https://github.com/Brainicism/bgutil-ytdlp-pot-provider
    echo Or use native PO token mode in dashboard.
)

if exist "token_service.js" (
    echo Starting potgen PO Token Server on port 4417...
    start "PO Token Generator (potgen)" /min cmd /c "node token_service.js"
    timeout /t 2 /nobreak >nul
    echo [OK] potgen server started on port 4417.
) else (
    echo [WARNING] token_service.js not found.
    echo This is optional - use bgutil or native mode instead.
)

echo.

REM ==============================================
REM Verify Servers (FIXED - no errors)
REM ==============================================
echo ==============================================
echo   Server Status
echo ==============================================
echo.

REM Check port 4416
netstat -an 2>nul | find "4416" | find "LISTENING" >nul
if errorlevel 1 (
    echo [WARNING] Port 4416 (bgutil) is NOT listening
) else (
    echo [OK] Port 4416 (bgutil) is listening
)

REM Check port 4417
netstat -an 2>nul | find "4417" | find "LISTENING" >nul
if errorlevel 1 (
    echo [WARNING] Port 4417 (potgen) is NOT listening
) else (
    echo [OK] Port 4417 (potgen) is listening
)

echo.

REM ==============================================
REM Ask user to continue (FIXED)
REM ==============================================
echo ==============================================
echo   Ready to Launch Dashboard
echo ==============================================
echo.
echo PO Token Sources Available:
echo   🌿 Native Browser (built-in)
echo   🖥️ bgutil on port 4416
echo   🤖 potgen on port 4417
echo.
echo Proxy Modes Available:
echo   🚫 No Proxy
echo   🌐 Tor Service (port 9050)
echo   🌐 Tor Browser (port 9150)
echo   🔄 Proxy List (Rotating)
echo.
echo ==============================================
echo.
set /p launch_confirm="Launch Dashboard now? (Y/N): "
if /i not "%launch_confirm%"=="Y" (
    echo.
    echo Exiting. Run 'python YTDash.py' manually to start.
    pause
    exit /b 0
)

echo.
echo Starting Dashboard...
echo Dashboard will open at http://127.0.0.1:5000
echo.

python YTDash.py

pause