@echo off
chcp 65001 >nul
echo === top10tool 卸载 ===
echo.

REM —— 检测 Python ——
set "PYTHON=python"
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% equ 0 set "PYTHON=py"
)

REM 1. 卸载 pip 包
echo [1/2] 卸载 top10tool ...
%PYTHON% -m pip uninstall top10tool -y 2>nul
if %errorlevel% equ 0 (
    echo [OK] 已卸载 top10tool
) else (
    echo [--] top10tool 未安装或已卸载
)

REM 2. 删除配置文件
echo [2/2] 清理配置文件 ...
set "CONFIG_DIR=%USERPROFILE%\.top10tool"
if exist "%CONFIG_DIR%" (
    rmdir /s /q "%CONFIG_DIR%"
    echo [OK] 已删除 %CONFIG_DIR%
) else (
    echo [--] 配置文件不存在，跳过
)

echo.
echo === 卸载完成 ===
pause
