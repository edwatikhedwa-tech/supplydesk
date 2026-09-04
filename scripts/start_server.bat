@echo off
REM Double-click entry point for the owner LOCAL_CANONICAL session.
REM All real logic lives in the guarded PowerShell launcher.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_server_and_open.ps1"
echo.
pause
