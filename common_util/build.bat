@echo off
chcp 65001 >nul
cd /d %~dp0

echo 正在安装依赖...
python -m pip install -r requirements.txt

echo 正在打包...
python build.py

echo.
echo 打包完成，可执行文件位于 dist/AutoKeyI.exe
echo 按任意键退出...
pause >nul
