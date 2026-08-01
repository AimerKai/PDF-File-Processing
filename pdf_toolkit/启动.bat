@echo off
chcp 65001 >nul
setlocal

rem ============================================================
rem  PDF 工具箱启动器 / PDF Toolkit Launcher
rem  自动查找已安装 PyQt5 的 Python 解释器来运行 main.py
rem ============================================================

set "SCRIPT_DIR=%~dp0"
set "MAIN=%SCRIPT_DIR%main.py"

rem 优先使用已知装好依赖的 Python 3.10 路径
set "PY_GOOD=C:\Users\KaiChen\AppData\Local\Programs\Python\Python310\python.exe"

if exist "%PY_GOOD%" (
    set "PY=%PY_GOOD%"
    goto :run
)

rem 回退: 尝试 py 启动器的 3.10
for /f "delims=" %%i in ('py -3.10 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
if defined PY if exist "%PY%" goto :run

rem 回退: 依次尝试常见 Python，找第一个装了 PyQt5 的
for %%P in (
    "py -3",
    "python",
    "C:\Python310\python.exe",
    "C:\Python311\python.exe",
    "C:\Python312\python.exe"
) do (
    for /f "delims=" %%i in ('%%P -c "import PyQt5,fitz;print(1)" 2^>nul') do (
        if "%%i"=="1" (
            for /f "delims=" %%j in ('%%P -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%j"
        )
    )
)

if not defined PY (
    echo [错误] 未找到安装了 PyQt5 和 PyMuPDF 的 Python 解释器。
    echo [Error] No Python interpreter with PyQt5 and PyMuPDF found.
    echo.
    echo 请运行: pip install -r requirements.txt
    pause
    exit /b 1
)

:run
echo 使用 Python: %PY%
echo 正在启动 PDF 工具箱...
"%PY%" "%MAIN%"
if errorlevel 1 pause
endlocal
