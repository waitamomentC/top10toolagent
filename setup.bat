@echo off
chcp 65001 >nul
echo === top10tool 一键安装 ===
echo.

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 未安装，请先安装 Python 3.10+
    echo         下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python 已检测到
echo.

REM 安装依赖
echo [1/2] 安装 Python 依赖...
pip install -r "%~dp0requirements.txt" -q
if %errorlevel% neq 0 (
    echo [ERROR] 依赖安装失败，请检查网络后重试
    pause
    exit /b 1
)
echo       依赖安装完成
echo.

REM 创建 top10tool.bat 启动脚本
echo [2/2] 创建 top10tool 命令...
set "AGENT_DIR=%~dp0"
set "BAT_FILE=%AGENT_DIR%top10tool.bat"

> "%BAT_FILE%" echo @echo off
>> "%BAT_FILE%" echo cd /d "%AGENT_DIR%"
>> "%BAT_FILE%" echo python cli.py %%*

REM 将 agent 目录加入用户 PATH
set "AGENT_DIR_NO_SLASH=%AGENT_DIR:~0,-1%"
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "OLD_PATH=%%b"
echo %OLD_PATH% | findstr /i /c:"%AGENT_DIR_NO_SLASH%" >nul
if %errorlevel% neq 0 (
    if "%OLD_PATH%"=="" (
        setx PATH "%AGENT_DIR_NO_SLASH%" >nul
    ) else (
        setx PATH "%OLD_PATH%;%AGENT_DIR_NO_SLASH%" >nul
    )
    echo       已添加到系统 PATH
) else (
    echo       路径已存在于 PATH 中，跳过
)

echo.
echo === 安装完成! ===
echo.
echo 现在重新打开任意终端，输入 top10tool 即可启动。
echo 首次运行会引导你配置 LLM（API 地址、Key、模型）。
echo.
pause
