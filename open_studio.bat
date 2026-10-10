@echo off
title Open Quran Studio
echo Opening Quran Studio in your browser...
echo If the site does not open, make sure QuranStudio.exe is running,
echo then type this address manually in Edge/Chrome:
echo    http://127.0.0.1:5000
start http://127.0.0.1:5000
timeout /t 3 /nobreak >nul
exit
