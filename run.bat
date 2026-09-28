@echo off
title GEOSHIELD - AI Disaster Management System
color 0B
cls
echo.
echo  =============================================================
echo    GEOSHIELD - AI Satellite Disaster Management System
echo  =============================================================
echo.
echo  [*] Starting GEOSHIELD Dashboard...
echo  [*] Please wait, loading data and models...
echo.
echo  Once started, open your browser at:
echo      http://localhost:8501
echo.
echo  Press Ctrl+C to stop the server.
echo  =============================================================
echo.

cd /d "%~dp0"
set PYTHONUTF8=1
streamlit run app/streamlit_app.py --server.port 8501 --server.headless false

pause
