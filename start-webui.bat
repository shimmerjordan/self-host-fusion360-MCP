@echo off
REM Double-click launcher for the Fusion 360 MCP config dashboard.
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\fusion-mcp.exe" (
  echo [!] Server not installed yet. Run install\windows-install.bat first,
  echo     or: pip install -e .
  echo.
  pause
  exit /b 1
)

echo Starting the Fusion 360 MCP config dashboard...
echo It will open http://127.0.0.1:8088 in your browser.
echo Keep this window open; press Ctrl+C to stop.
echo.
".venv\Scripts\fusion-mcp.exe" webui
pause
