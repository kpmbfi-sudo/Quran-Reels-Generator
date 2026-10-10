@echo off
title Link YouTube Channel - Quran Studio
cd /d "%~dp0"
echo ============================================================
echo  Link your YouTube channel (one-time setup)
echo  Steps in browser:
echo   1. Choose the email that owns your YouTube channel
echo   2. If a warning appears: Advanced - Go to app (unsafe)
echo   3. Click Allow / Continue
echo ============================================================
echo.
python setup_youtube.py
echo.
echo ------------------------------------------------------------
echo  If you see SUCCESS above, your channel is linked.
echo  Reopen the Studio page and check the green badge.
echo ------------------------------------------------------------
echo  Press any key to close...
pause >nul
