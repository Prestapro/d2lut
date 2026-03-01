@echo off
setlocal
echo ============================================
echo D2R Loot Filter - Quick Static Build
echo ============================================
echo.

:: Navigate to project root
cd /d "%~dp0\.."

:: Configuration
set OUTPUT_DIR=output
set GAME_DIR=D:\Diablo II Resurrected
set MOD_DIR=%GAME_DIR%\mods\d2lut\d2lut.mpq\data\local\lng\strings

:: Step 1: Generate static item-names.json
echo [1/3] Generating item-names.json with FG prices...
python scripts\generate_static_item_names.py
if errorlevel 1 (
    echo Error: Failed to generate item-names.json
    pause
    exit /b 1
)

:: Step 2: Create output directory
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

:: Step 3: Copy to game directory (if exists)
echo [2/3] Copying to output directory...
copy /y "data\templates\item-names.json" "%OUTPUT_DIR%\" >nul
echo Copied to: %OUTPUT_DIR%\item-names.json

if exist "%GAME_DIR%" (
    echo [3/3] Installing to game directory...
    if not exist "%MOD_DIR%" mkdir "%MOD_DIR%"
    copy /y "data\templates\item-names.json" "%MOD_DIR%\" >nul
    echo Installed to: %MOD_DIR%\item-names.json
) else (
    echo [3/3] Game directory not found at %GAME_DIR%
    echo Skipping game installation.
)

echo.
echo ============================================
echo Done! Generated item-names.json with FG prices
echo ============================================
echo.
echo Next steps:
echo 1. Copy item-names.json to your D2R mod folder
echo 2. Restart D2R to apply the loot filter
echo.
pause
