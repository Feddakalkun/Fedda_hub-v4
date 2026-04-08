@echo off
setlocal
title Fedda Hub v4
echo.
echo  ============================================
echo   FEDDA HUB v4 — Starting
echo  ============================================
echo.

:: ── Sanity checks ────────────────────────────────────────────────────────────
if not exist "venv\Scripts\activate.bat" (
    echo  ERROR: venv not found. Run install.bat first.
    pause & exit /b 1
)
if not exist "frontend\node_modules" (
    echo  ERROR: frontend\node_modules missing. Run install.bat first.
    pause & exit /b 1
)

:: ── 1. Activate venv ─────────────────────────────────────────────────────────
call venv\Scripts\activate.bat

:: ── 2. Start backend in a new window ─────────────────────────────────────────
echo [1/2] Starting backend (port 8000)...
start "Fedda Backend" cmd /k "call venv\Scripts\activate.bat && python backend\agent.py"

:: Give backend a moment to bind
timeout /t 2 /nobreak >nul

:: ── 3. Start frontend dev server ─────────────────────────────────────────────
echo [2/2] Starting frontend (Vite dev)...
start "Fedda Frontend" cmd /k "cd frontend && npm run dev"

:: Give Vite a moment to start
timeout /t 3 /nobreak >nul

:: ── 4. Open browser ──────────────────────────────────────────────────────────
echo.
echo  Opening http://localhost:5173 ...
start http://localhost:5173

echo.
echo  Both services are running in separate windows.
echo  Close those windows to stop Fedda Hub v4.
echo.
