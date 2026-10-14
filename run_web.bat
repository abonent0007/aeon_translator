@echo off
chcp 65001 >nul 2>&1
title AEON v3.0 — Web Server

echo.
echo ============================================================
echo   🌌 AEON v3.0 — Web Server
echo ============================================================
echo.
echo   Starting server...
echo   Open http://localhost:8080 in your browser
echo   Press Ctrl+C to stop
echo ============================================================
echo.

REM Try venv python first, fall back to system python
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m aeon.web_server
) else (
    python -m aeon.web_server
)

pause
