@echo off
cd /d "%~dp0"
if exist build_log.txt del build_log.txt
cmd.exe /d /c ""%~dp0build_exe.bat" > "%~dp0build_log.txt" 2>&1"
echo.
echo Builder finished. Log saved to:
echo %~dp0build_log.txt
echo.
echo Opening the log in Notepad...
notepad "%~dp0build_log.txt"
