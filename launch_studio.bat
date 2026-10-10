@echo off
title Quran Studio Server
cd /d "%~dp0"
REM كشف بايثون تلقائياً (Python launcher أو python في المسار)
set PYEXE=python
where py >nul 2>&1 && set PYEXE=py
where python3 >nul 2>&1 && set PYEXE=python3
start "" "%PYEXE%" main.py
