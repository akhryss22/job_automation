@echo off
title Job Tracker Scraper Run
cd /d "%~dp0"
echo ========================================================
echo         RUNNING AWS RE/START JOB TRACKER SCRAPER
echo ========================================================
echo.
echo Running scraper script...
.venv\Scripts\python.exe main.py
echo.
echo ========================================================
echo              SCRAPER RUN COMPLETE
echo ========================================================
echo.
pause
