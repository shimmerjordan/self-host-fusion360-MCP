@echo off
REM Double-click entry point for the Windows installer.
REM Sets the console to UTF-8 so Chinese / special characters render correctly.
chcp 65001 >nul
echo Starting self-host-fusion360-mcp installer...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows-install.ps1" %*
echo.
pause
