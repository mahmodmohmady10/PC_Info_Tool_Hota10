@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title PC Info Tool 2.0 - EXE Builder

echo ==========================================
echo       PC Info Tool 2.0 - EXE Builder
echo ==========================================
echo.
echo Project folder: %CD%
echo Build log: %CD%\build_log.txt
echo.

set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PY_CMD=py"
if not defined PY_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo [ERROR] Python was not found.
    echo Install Python 3.10+ 64-bit and enable "Add Python to PATH".
    goto :failed
)

echo [INFO] Checking Python version...
%PY_CMD% -c "import sys; print(sys.version); raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo [ERROR] Python 3.10 or newer is required.
    goto :failed
)

echo.
echo [1/4] Checking pip...
%PY_CMD% -m pip --version
if errorlevel 1 (
    echo [ERROR] pip is unavailable.
    goto :failed
)

echo.
echo [2/4] Installing project requirements...
%PY_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo [3/4] Installing PyInstaller...
%PY_CMD% -m pip install pyinstaller
if errorlevel 1 goto :failed

echo.
echo [4/4] Building the application...
%PY_CMD% -m PyInstaller --noconfirm --clean --windowed --onedir --name PCInfoTool2 --icon "assets\pc_info_tool.ico" --version-file "version_info.txt" --add-data "assets;assets" --collect-all customtkinter --collect-all darkdetect main.py
if errorlevel 1 goto :failed

echo.
echo ==========================================
echo BUILD SUCCESSFUL
echo ==========================================
echo EXE:
echo %CD%\dist\PCInfoTool2\PCInfoTool2.exe
echo.
echo IMPORTANT: distribute the ENTIRE folder:
echo dist\PCInfoTool2
echo.
goto :done

:failed
echo.
echo ==========================================
echo BUILD FAILED
echo ==========================================
echo Keep this window open and send build_log.txt.
echo The log path is: %CD%\build_log.txt

:done
echo.
echo Press any key to close this window...
pause >nul
exit /b
