@echo off
setlocal

set INPUT=%~1
set SHEET=%~2
set DATETAG=%~3

if "%INPUT%"=="" (
  echo Usage: windows_import_ifind_theme.bat ^<input.xlsx/csv^> [sheet] [yyyymmdd]
  exit /b 1
)

powershell -ExecutionPolicy Bypass -File "%~dp0windows_import_ifind_theme.ps1" -InputPath "%INPUT%" -Sheet "%SHEET%" -DateTag "%DATETAG%"
