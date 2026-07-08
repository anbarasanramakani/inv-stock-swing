@echo off
title NSE Pulse Terminal Launcher
cd /d "%~dp0"

echo ==================================================
echo              ⚡ NSE PULSE TERMINAL ⚡
echo ==================================================
echo.

:: Step 1: Launch Microsoft Edge pointing to the local port
echo [1/2] Launching Microsoft Edge...
start msedge http://localhost:8501

:: Step 2: Start the Streamlit application in the current window
echo [2/2] Starting Streamlit Server...
python -m streamlit run app.py --server.port 8501 --server.headless true

echo.
echo Server stopped.
pause
