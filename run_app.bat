@echo off
title NSE Pulse Terminal Launcher
cd /d "%~dp0"

echo ==================================================
echo              ⚡ NSE PULSE TERMINAL ⚡
echo ==================================================
echo.

:: Check if .venv exists and use it
set PYTHON_EXE=python
if exist ".venv\Scripts\python.exe" (
    echo [info] Using virtual environment Python...
    set PYTHON_EXE=".venv\Scripts\python.exe"
)

:: Step 1: Start FastAPI backend (main.py) in a separate background window
echo [1/3] Starting FastAPI Backend (port 8000)...
start "NSE Pulse API" cmd /k "%PYTHON_EXE% main.py"

:: Wait 3 seconds for the API server to initialise before opening the browser
timeout /t 3 /nobreak >nul

:: Step 2: Launch Microsoft Edge pointing to the Streamlit port
echo [2/3] Launching Default Browser...
start http://localhost:8501

:: Step 3: Start the Streamlit application in the current window
echo [3/3] Starting Streamlit Server (port 8501)...
%PYTHON_EXE% -m streamlit run app.py --server.port 8501 --server.headless true

echo.
echo Servers stopped.
pause
