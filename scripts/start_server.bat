@echo off
REM Double-click entry point for the desktop shortcut. All real logic lives
REM in start_server_and_open.ps1 (workspace-guard protected, same as every
REM other operator script in this folder).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_server_and_open.ps1"
echo.
pause
