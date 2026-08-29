@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo 未找到 python 命令，请确认 Python 已安装并添加到 PATH。
    pause >nul
    exit /b 1
)

echo 正在安装依赖...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo 依赖安装失败。
    pause >nul
    exit /b 1
)

echo 正在打包...
python build.py
if %errorlevel% neq 0 (
    echo 打包失败。
    pause >nul
    exit /b 1
)

echo.
echo 打包完成，可执行文件位于 dist/AutoKeyI.exe
echo 按任意键退出...
pause >nul
