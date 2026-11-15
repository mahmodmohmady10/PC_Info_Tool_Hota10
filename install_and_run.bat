@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher was not found. Install Python 3.10 or newer first.
  pause
  exit /b 1
)
echo Installing required packages...
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo Package installation failed.
  pause
  exit /b 1
)
echo Starting PC Info Tool 2.0...
py main.py
if errorlevel 1 pause
endlocal
