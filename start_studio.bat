@echo off
title Quran Studio Launcher
cd /d "%~dp0"
echo Starting Quran Studio server...
set QURAN_BAT_OPEN=1
start "Quran Studio Server" python main.py
echo Waiting until the Studio is TRULY ready (first start can take a minute)...
powershell -NoProfile -Command "for ($i=0;$i -lt 45;$i++){ try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:5000/' -TimeoutSec 3; if ($r.StatusCode -eq 200) { break } } catch { }; Start-Sleep -Seconds 2 }"
echo Opening Studio in your browser...
start http://127.0.0.1:5000
echo.
echo Studio is running in the OTHER black window (keep it open).
echo To STOP later: red button in UI, or CTRL+C in that window.
exit
