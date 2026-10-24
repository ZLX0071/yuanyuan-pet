@echo off
rem 便携包构建（T5.4）：输出 dist\YuanyuanPet\，可用 zip 打包分发
set ROOT=%~dp0..
cd /d "%ROOT%"
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --name YuanyuanPet ^
  --paths "%ROOT%\src" ^
  --add-data "%ROOT%\pets;pets" ^
  --exclude-module rembg --exclude-module onnxruntime --exclude-module cv2 ^
  --exclude-module torch --exclude-module matplotlib --exclude-module tkinter --exclude-module PyQt5 ^
  --distpath "%ROOT%\dist" --workpath "%ROOT%\build" --specpath "%ROOT%\build" "%ROOT%\main.py"
