@echo off
REM Run NSE Pulse scheduled Full Analysis
REM Run this via Windows Task Scheduler at 9:20 IST and 15:30 IST

cd /d "c:\work\inv-stock-swing"
call .venv\Scripts\activate.bat 2>nul || call activate.bat 2>nul

echo [%date% %time%] Starting scheduled NSE Pulse Full Analysis...
python scheduler.py --schedule-check --universe "Nifty 1000" --strategy "All Strategies"

echo [%date% %time%] Scheduled analysis complete.
echo. >> scheduler_log.txt
echo [%date% %time%] Scheduled analysis complete.