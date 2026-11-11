@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Checking Python...
py -3.11 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.11 was not found. Install Python 3.11+ and enable the Python Launcher.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [2/4] Creating virtual environment...
  py -3.11 -m venv .venv
  if errorlevel 1 goto :failed
)

echo [3/4] Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo [4/4] Downloading HoYoLAB map, tiles and marker data...
".venv\Scripts\python.exe" hoyolab_updater.py
if errorlevel 1 goto :failed

echo Starting Genshin Impact overlay...
".venv\Scripts\python.exe" genshin.py --hoyolab-cache "%LOCALAPPDATA%\genshin-map-overlay\hoyolab\teyvat"
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo Test launch failed. Read the error above, then send the full error text.
pause
exit /b 1
