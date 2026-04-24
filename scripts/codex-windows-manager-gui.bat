@echo off
setlocal
set SCRIPT_DIR=%~dp0
set TARGET=%SCRIPT_DIR%..\codex_windows_manager_gui.py

if not exist "%TARGET%" (
  echo [codex-windows-manager-gui] 找不到脚本：%TARGET%
  exit /b 1
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%TARGET%" %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python "%TARGET%" %*
  exit /b %ERRORLEVEL%
)

echo [codex-windows-manager-gui] 没找到 Python，请先安装 Python 3 并勾选 Add to PATH
exit /b 1
