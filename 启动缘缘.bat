@echo off
rem 缘缘桌宠启动器：双击即用，无黑窗口
cd /d "%~dp0"
start "yuanyuan" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
