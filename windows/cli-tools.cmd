@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0cli-tools-native.ps1" %*
exit /b %ERRORLEVEL%
