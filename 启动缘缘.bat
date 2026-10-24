@echo off
rem 缘缘桌宠启动器：双击即用（无黑窗口）；崩溃退出时 3 秒后自动重启，正常退出则不再拉起
cd /d "%~dp0"
:loop
start /wait "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py" --pack "%~dp0pets\yuanyuan"
if errorlevel 1 (
  timeout /t 3 /nobreak >nul
  goto loop
)
