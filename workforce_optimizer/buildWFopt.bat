@echo off
setlocal EnableDelayedExpansion


:: ==================================================================
:: Workforce Optimizer - One-Click Build Script (2026 Edition)
:: Double-click this file → WorkforceOptimizer.exe in dist\WorkforceOptimizer\
:: ==================================================================

python -m pytest tests/ -v || exit /b

echo.
echo  ====================================================
echo    Workforce Optimizer - Building Distributable EXE
echo  ====================================================
echo.

:: --- Config -------------------------------------------------------
set "INSTALLER_FILE_NAME=WorkforceOptimizer_Setup"
set "APP_NAME=WorkforceOptimizer"
set "MAIN_SCRIPT=main.py"
set "ICON=icons\teamwork.ico"
set "DIST_DIR=dist"
set "BUILD_DIR=build"
set "OUTPUT_DIR=output"
set "SPEC_FILE=%APP_NAME%.spec"
set "INSTALLER_SCRIPT=workforce_optimizer.iss"

:: --- Clean old builds -------------------------------------
echo [1/6] Cleaning old builds...
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%BUILD_DIR%"  rmdir /s /q "%BUILD_DIR%"

:: --- Step Run PyInstaller ---------
echo [2/6] Running PyInstaller...
pyinstaller main.spec --clean || exit /b

:: --- Build installer -----------------------------------
echo [3/6] Build installer...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" .\%INSTALLER_SCRIPT% || exit /b

:: --- Digitally sign executable -----------------------------------
echo [4/6] Digitally sign executable...
set "PWD="
set /p PWD="Enter code-signing password: "
"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe" sign /f "C:\sign\WorkforceOptimizer.pfx" /p %PWD% /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "%DIST_DIR%\%APP_NAME%.exe" || exit /b

:: --- Digitally sign the installer -----------------------
echo [5/6] Digitally sign installer...
set "PWD="
set /p PWD="Enter code-signing password: "
"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe" sign /f "C:\sign\WorkforceOptimizer.pfx" /p %PWD% /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "%OUTPUT_DIR%\%INSTALLER_FILE_NAME%.exe" || exit /b


:: --- Done! -------------------------------------------------
echo.
echo [6/6] BUILD COMPLETE!
echo.
echo   Your executable is ready:
echo   "%OUTPUT_DIR%\%INSTALLER_FILE_NAME%.exe"
echo.
echo   You can now distribute this single file!
echo.

endlocal