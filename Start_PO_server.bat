@echo off
title PO Token Server Manager
echo ==============================================
echo   PO Token Server Manager
echo ==============================================
echo.

REM Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo Working directory: %CD%
echo.

REM Kill existing node processes
echo [1/4] Stopping existing PO token servers...
taskkill /f /im node.exe >nul 2>&1
timeout /t 2 /nobreak >nul
echo [OK] Existing servers stopped

REM ==============================================
REM Start po-token-generator on port 4417
REM ==============================================
echo.
echo [2/4] Starting po-token-generator on port 4417...

if exist "%SCRIPT_DIR%token_service.js" (
    start "PO Token Generator (Port 4417)" /min cmd /c "node "%SCRIPT_DIR%token_service.js""
    echo [OK] po-token-generator starting...
) else (
    echo [WARNING] token_service.js not found at %SCRIPT_DIR%token_service.js
)

timeout /t 2 /nobreak >nul

REM ==============================================
REM Start bgutil PO token server on port 4416
REM ==============================================
echo.
echo [3/4] Starting bgutil PO token server on port 4416...

set "BGUTIL_PATH=%SCRIPT_DIR%bgutil-ytdlp-pot-provider\server\build\main.js"

if exist "%BGUTIL_PATH%" (
    echo Starting bgutil server...
    start "Bgutil PO Token Server (Port 4416)" /min cmd /c "cd /d "%SCRIPT_DIR%bgutil-ytdlp-pot-provider\server" && node build\main.js --port 4416"
    echo [OK] bgutil server starting...
) else (
    echo [ERROR] bgutil server not found at: %BGUTIL_PATH%
)

timeout /t 3 /nobreak >nul

REM ==============================================
REM Verify servers are running
REM ==============================================
echo.
echo [4/4] Verifying PO token servers...

REM Check port 4416
netstat -an | find ":4416" | find "LISTENING" >nul
if errorlevel 1 (
    echo [WARNING] Port 4416 (bgutil) is NOT listening
) else (
    echo [OK] Port 4416 (bgutil) is listening
)

REM Check port 4417
netstat -an | find ":4417" | find "LISTENING" >nul
if errorlevel 1 (
    echo [WARNING] Port 4417 (po-token-generator) is NOT listening
) else (
    echo [OK] Port 4417 (po-token-generator) is listening
)

echo.
echo ==============================================
echo   PO Token Servers Started
echo ==============================================
echo.
echo Port 4416: bgutil PO token server
echo Port 4417: po-token-generator
echo.
echo To stop all servers: taskkill /f /im node.exe
echo ==============================================
pause