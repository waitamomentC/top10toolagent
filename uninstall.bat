@echo off
chcp 65001 >nul
echo === top10tool 一键卸载 ===
echo.

set "AGENT_DIR=%~dp0"
set "AGENT_DIR_NO_SLASH=%AGENT_DIR:~0,-1%"

REM 1. 删除 top10tool.bat
if exist "%AGENT_DIR%top10tool.bat" (
    del "%AGENT_DIR%top10tool.bat"
    echo [OK] 已删除 top10tool.bat
) else (
    echo [--] top10tool.bat 不存在，跳过
)

REM 2. 从 PATH 中移除 agent 目录
echo [..] 清理 PATH...
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "OLD_PATH=%%b"
if defined OLD_PATH (
    set "NEW_PATH="
    set "FOUND=0"
    for %%p in ("%OLD_PATH:;=" "%") do (
        set "SEG=%%~p"
        setlocal enabledelayedexpansion
        if /i not "!SEG!"=="%AGENT_DIR_NO_SLASH%" (
            if "!NEW_PATH!"=="" (
                endlocal & set "NEW_PATH=!SEG!"
            ) else (
                endlocal & set "NEW_PATH=!NEW_PATH!;!SEG!"
            )
        ) else (
            endlocal & set "FOUND=1"
        )
    )
    setlocal enabledelayedexpansion
    if "!FOUND!"=="1" (
        setx PATH "!NEW_PATH!" >nul
        echo [OK] 已从 PATH 中移除
    ) else (
        echo [--] PATH 中未找到，跳过
    )
    endlocal
) else (
    echo [--] 用户 PATH 为空，跳过
)

REM 3. 删除配置文件
set "CONFIG_DIR=%USERPROFILE%\.top10tool"
if exist "%CONFIG_DIR%" (
    rmdir /s /q "%CONFIG_DIR%"
    echo [OK] 已删除配置文件 %CONFIG_DIR%
) else (
    echo [--] 配置文件不存在，跳过
)

echo.
echo === 卸载完成 ===
echo 项目文件保留在 %AGENT_DIR_NO_SLASH%
echo 如需删除项目，手动执行: rmdir /s /q "%AGENT_DIR_NO_SLASH%"
echo.
pause
