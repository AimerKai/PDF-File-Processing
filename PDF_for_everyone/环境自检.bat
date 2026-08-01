@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ============================================
echo   PDF Toolkit - Environment Check
echo ============================================
echo.

set "HERE=%~dp0"
set "INT=%HERE%_internal"
set "EXE=%HERE%PDF_for_everyone.exe"
set "OK=1"

echo [1/4] Check main exe...
if exist "%EXE%" (
    echo     OK: PDF_for_everyone.exe
) else (
    echo     FAIL: PDF_for_everyone.exe not found
    set "OK=0"
)

echo [2/4] Check _internal folder...
if exist "%INT%" (
    echo     OK: _internal exists
) else (
    echo     FAIL: _internal folder not found
    set "OK=0"
)

echo [3/4] Check Qt platforms plugin (qwindows.dll)...
set "PLUGIN="
if exist "%INT%\PyQt5\Qt5\plugins\platforms\qwindows.dll" set "PLUGIN=%INT%\PyQt5\Qt5\plugins\platforms\qwindows.dll"
if exist "%INT%\platforms\qwindows.dll" set "PLUGIN=%INT%\platforms\qwindows.dll"
if defined PLUGIN (
    echo     OK: qwindows.dll found
    if not exist "%INT%\platforms\qwindows.dll" (
        echo     Fixing: copying platforms to _internal root...
        if not exist "%INT%\platforms" mkdir "%INT%\platforms" >nul 2>&1
        copy /y "%PLUGIN%" "%INT%\platforms\" >nul
    )
) else (
    echo     FAIL: qwindows.dll not found
    set "OK=0"
)

echo [4/4] Check PyMuPDF core library...
set "FITZ=0"
for /r "%INT%" %%f in (fitz*.pyd _fitz*.pyd fitz*.dll _fitz*.dll) do (
    if exist "%%f" set "FITZ=1"
)
if "!FITZ!"=="1" (
    echo     OK: PyMuPDF core found
) else (
    echo     WARN: PyMuPDF pyd not found (may be packed, normal)
)

echo.
if "%OK%"=="1" (
    echo ===== ALL CHECKS PASSED =====
    echo.
    echo You can now run:
    echo   - Double-click PDF_for_everyone.exe
    echo   - Or double-click start.bat
    echo.
    echo If you see error "no Qt platform plugin could be initialized",
    echo copy the _internal\PyQt5\Qt5\plugins\platforms folder
    echo to the same folder as PDF_for_everyone.exe
    echo.
) else (
    echo ===== SOME CHECKS FAILED =====
    echo Please re-extract this folder. Do not delete any files in _internal.
)
echo.
pause
endlocal
