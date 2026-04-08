@echo off
setlocal
title Fedda Hub v4 — Update
echo.
echo  ============================================
echo   FEDDA HUB v4 — Update
echo  ============================================
echo.

:: ── 1. Git pull ──────────────────────────────────────────────────────────────
echo [1/3] Pulling latest code from GitHub...
git pull
if errorlevel 1 (
    echo  WARNING: git pull failed — continuing anyway.
)

:: ── 2. Backend deps ──────────────────────────────────────────────────────────
echo.
echo [2/3] Updating backend dependencies...
if not exist "venv\Scripts\activate.bat" (
    echo  No venv found — run install.bat first.
    pause & exit /b 1
)
call venv\Scripts\activate.bat
pip install -r backend\requirements.txt --upgrade --quiet
echo  Backend deps up to date.

:: ── 3. Frontend deps ─────────────────────────────────────────────────────────
echo.
echo [3/3] Updating frontend dependencies...
pushd frontend
npm install --no-audit --no-fund --silent
popd
echo  Frontend deps up to date.

:: ── 4. ComfyUI custom nodes ──────────────────────────────────────────────────
echo.
echo [4/4] Updating ComfyUI custom nodes...
powershell -ExecutionPolicy Bypass -File "%~dp0nodes.ps1" -Update

echo.
echo  Update complete! Run  run.bat  to start.
echo.
pause
