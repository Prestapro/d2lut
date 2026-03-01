@echo off
setlocal
echo ============================================
echo D2R Loot Filter - Static Price Build
echo ============================================
echo.

:: Navigate to project root
cd /d "%~dp0\.."

:: Step 1: Generate static item-names.json with FG prices
echo [1/2] Generating static item-names.json with FG prices...
python scripts\generate_static_item_names.py
if errorlevel 1 (
    echo Error: Failed to generate item-names.json
    pause
    exit /b 1
)

:: Step 2: Build the executable
echo.
echo [2/2] Building executable...
call scripts\build_exe.bat

echo.
echo ============================================
echo Build complete!
echo ============================================
pause
