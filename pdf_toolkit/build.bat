@echo off
chcp 65001 >nul
setlocal

rem ============================================================
rem  PDF 工具箱打包脚本 / PDF Toolkit Build Script
rem  使用 PyInstaller 打包成独立 exe，无需安装 Python 即可运行
rem ============================================================

set "PY=C:\Users\KaiChen\AppData\Local\Programs\Python\Python310\python.exe"
if not exist "%PY%" set "PY=python"

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo ============================================
echo  Building PDF_for_everyone...
echo  Python: %PY%
echo ============================================
echo.

rem 清理旧产物 / Clean old build
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist PDF_for_everyone.spec del /q PDF_for_everyone.spec

rem 打包 / Package
rem   --onedir        目录模式 (启动更快)
rem   --windowed      GUI 程序无控制台
rem   --name          输出名
rem   --exclude-module 排除不必要的大依赖(torch/matplotlib等)，缩小体积
"%PY%" -m PyInstaller ^
    --onedir ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --name "PDF_for_everyone" ^
    --exclude-module torch ^
    --exclude-module matplotlib ^
    --exclude-module sympy ^
    --exclude-module numpy ^
    --exclude-module scipy ^
    --exclude-module pandas ^
    --exclude-module IPython ^
    --exclude-module notebook ^
    --exclude-module tkinter ^
    --exclude-module pytest ^
    --exclude-module django ^
    --exclude-module flask ^
    main.py

if errorlevel 1 (
    echo.
    echo [错误] 打包失败 / Build FAILED
    pause
    exit /b 1
)

echo.
echo ============================================
echo  打包成功 / Build SUCCESS
echo  输出: %SCRIPT_DIR%dist\PDF_for_everyone\
echo ============================================
echo  可将该文件夹拷贝到任意 Windows 电脑直接运行。
pause
endlocal
