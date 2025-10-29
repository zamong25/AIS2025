@echo off
echo === Delphi Trader Execution Script ===
echo.

cd /d C:\Users\PCW\Desktop\delphi-trader

echo Starting Delphi Trader...
echo Path: %cd%
echo.

:loop
cd legacy\src
..\..\new_venv\Scripts\python.exe main.py
cd ..\..
echo.
echo Waiting 15 minutes for next execution...
timeout /t 900 /nobreak > nul
goto loop