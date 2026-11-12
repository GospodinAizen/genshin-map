@echo off
setlocal
cd /d "%~dp0"
echo Updating official HoYoLAB Teyvat data...
"%~dp0hoyolab_updater.exe"
if errorlevel 1 (
  echo.
  echo HoYoLAB update failed. Check your internet connection and try again.
  pause
  exit /b 1
)
echo Starting Genshin Map Overlay...
start "" "%~dp0GenshinMapOverlay\GenshinMapOverlay.exe" --hoyolab-cache "%LOCALAPPDATA%\genshin-map-overlay\hoyolab\teyvat"
exit /b 0
