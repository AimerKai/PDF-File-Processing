@echo off
setlocal
chcp 65001 >nul

set "APP=%~dp0PDF_for_everyone.exe"

if not exist "%APP%" (
    echo [Error] PDF_for_everyone.exe not found.
    echo Please keep this file in the same folder as PDF_for_everyone.exe
    pause
    exit /b 1
)

start "" "%APP%"
endlocal
