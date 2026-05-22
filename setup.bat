@echo off
chcp 65001 >nul

echo ================================================
echo    top10tool — 全局安装
echo ================================================
echo.

REM —— 检测 Python ——
set "PYTHON="
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON=python"
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON=py"
    )
)

if "%PYTHON%"=="" (
    echo [ERROR] 未检测到 Python 3.10+
    echo         下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('%PYTHON% --version 2^>^&1') do echo   Python: %%v

echo.
REM —— 保存仓库路径，供自动更新使用 ——
set "REPO_DIR=%~dp0"
set "CONFIG_DIR=%USERPROFILE%\.top10tool"
mkdir "%CONFIG_DIR%" 2>nul
echo %REPO_DIR%>"%CONFIG_DIR%\repo_path"

echo   正在安装 top10tool ...
echo.

%PYTHON% -m pip install "%~dp0." --quiet

if %errorlevel% neq 0 (
    echo [ERROR] 安装失败，请检查网络后重试
    pause
    exit /b 1
)

REM —— 保存已安装版本，供自动更新比对 ——
git -C "%REPO_DIR%" rev-parse origin/master > "%CONFIG_DIR%\installed_commit" 2>nul

echo ================================================
echo    安装完成!
echo ================================================
echo.
echo   top10tool 已全局可用，在任意终端输入即可启动。
echo   首次运行会引导你配置 LLM 连接信息。
echo.
echo   验证:
echo     where top10tool
echo.
pause
