@echo off
title NSE Pulse Terminal Launcher
cd /d "%~dp0"

echo ==================================================
echo              ⚡ NSE PULSE TERMINAL ⚡
echo ==================================================
echo.

:: Step 1: Start FastAPI backend (main.py) in a separate background window
echo [1/3] Starting FastAPI Backend (port 8000)...
start "NSE Pulse API" cmd /k "python main.py"

:: Wait 3 seconds for the API server to initialise before opening the browser
timeout /t 3 /nobreak >nul

:: Step 2: Launch Microsoft Edge pointing to the Streamlit port
echo [2/3] Launching Microsoft Edge...
start msedge http://localhost:8501

:: Step 3: Start the Streamlit application in the current window
echo [3/3] Starting Streamlit Server (port 8501)...
python -m streamlit run app.py --server.port 8501 --server.headless true

echo.
echo Servers stopped.
pause
