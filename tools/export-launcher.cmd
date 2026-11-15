@echo off
setlocal
set "script=%~dp0launcher.ps1"
if not exist "%script%" set "script=%~dp0export-launcher.ps1"
if /i "%~1"=="stop" (
  powershell.exe -NoLogo -NoProfile -Sta -ExecutionPolicy Bypass -File "%script%" -Stop
) else (
  powershell.exe -NoLogo -NoProfile -Sta -ExecutionPolicy Bypass -File "%script%"
)
exit /b %ERRORLEVEL%
