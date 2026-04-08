@echo off
setlocal
title Fedda Hub v4 — Install
echo.
echo  ============================================
echo   FEDDA HUB v4 — Install
echo  ============================================
echo.

:: ── 1. Python venv ───────────────────────────────────────────────────────────
echo [1/3] Setting up Python virtual environment...
if not exist "venv" (
    python -m venv venv
    if errorlevel 1 (
        echo  ERROR: Python not found. Install Python 3.11+ and try again.
        pause & exit /b 1
    )
    echo  Created venv\
) else (
    echo  venv already exists, skipping.
)

echo [1/3] Installing backend dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip --quiet
pip install -r backend\requirements.txt --quiet
if errorlevel 1 (
    echo  ERROR: Failed to install backend requirements.
    pause & exit /b 1
)
echo  Backend deps installed.

:: ── 2. Node / npm ────────────────────────────────────────────────────────────
echo.
echo [2/3] Installing frontend dependencies...
where npm >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Node.js / npm not found. Install from https://nodejs.org and try again.
    pause & exit /b 1
)
pushd frontend
npm install --no-audit --no-fund --silent
if errorlevel 1 (
    echo  ERROR: npm install failed.
    popd & pause & exit /b 1
)
popd
echo  Frontend deps installed.

:: ── 3. ComfyUI custom nodes ──────────────────────────────────────────────────
echo.
echo [3/3] Installing ComfyUI custom nodes...
powershell -ExecutionPolicy Bypass -File "%~dp0nodes.ps1"

:: ── 4. Done ──────────────────────────────────────────────────────────────────
echo.
echo [4/4] All done!
echo.
echo  Run  run.bat  to start Fedda Hub v4.
echo.
pause
