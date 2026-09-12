@echo off
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "TEMP=%~dp0.cache\tmp"
set "TMP=%TEMP%"
if not exist "%TEMP%" mkdir "%TEMP%"
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo Please run setup.ps1 first.
  pause
  exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" -m fishing_assistant
