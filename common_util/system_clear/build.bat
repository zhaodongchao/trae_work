@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================
echo Windows 系统垃圾清理工具 - 打包脚本
echo ==========================================

set "PYTHON="
where py >nul 2>nul && set "PYTHON=py -3"
if not defined PYTHON (
    where python >nul 2>nul && set "PYTHON=python"
)

if not defined PYTHON (
    echo [错误] 未找到 python/py 命令，请从 python.org 安装 Python 并添加到 PATH。
    pause >nul
    exit /b 1
)

%PYTHON% --version >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] %PYTHON% 无法正常运行，请检查 Python 安装。
    pause >nul
    exit /b 1
)

if not exist ".venv" (
    echo 正在创建虚拟环境...
    %PYTHON% -m venv .venv
    if %errorlevel% neq 0 (
        echo [错误] 虚拟环境创建失败。
        pause >nul
        exit /b 1
    )
)

echo 正在安装依赖...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败，请检查网络连接或 pip 报错信息。
    pause >nul
    exit /b 1
)

echo 正在打包...
.venv\Scripts\python.exe build.py
if %errorlevel% neq 0 (
    echo [错误] 打包失败。
    pause >nul
    exit /b 1
)

echo.
echo 打包完成，可执行文件位于 dist/SystemClear.exe
echo 按任意键退出...
pause >nul
