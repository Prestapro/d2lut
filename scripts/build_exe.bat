@echo off
setlocal
echo Building D2R Loot Filter Generator (Windows)...

:: Navigate to the d2lut project root
cd /d "%~dp0\.."

:: Check if pyinstaller is installed
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo Error: pyinstaller is not installed.
    echo Run: pip install pyinstaller
    exit /b 1
)

:: Clean previous builds
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "D2R_Loot_Filter_Builder.spec" del /q "D2R_Loot_Filter_Builder.spec"

:: Set PYTHONPATH so relative imports in src/ work
set PYTHONPATH=src

:: Compile using PyInstaller
echo Running PyInstaller...
pyinstaller ^
    --name "D2R_Loot_Filter_Builder" ^
    --onefile ^
    --clean ^
    --hidden-import "yaml" ^
    --distpath "dist" ^
    --workpath "build" ^
    scripts\build_d2r_filter.py

if errorlevel 1 (
    echo Build failed.
    exit /b %errorlevel%
)

echo Build complete.
echo You can find your executable at: dist\D2R_Loot_Filter_Builder.exe

:: Create a zip structure that imitates end-user deployment
echo Creating deployment folder structure...
mkdir "dist\D2R_Filter_Generator\data\cache" 2>nul
mkdir "dist\D2R_Filter_Generator\data\templates" 2>nul
mkdir "dist\D2R_Filter_Generator\config" 2>nul
mkdir "dist\D2R_Filter_Generator\output" 2>nul

copy /y "dist\D2R_Loot_Filter_Builder.exe" "dist\D2R_Filter_Generator\" >nul
copy /y "data\templates\item-names.json" "dist\D2R_Filter_Generator\data\templates\" >nul
if exist "config" (
    copy /y "config\*.yml" "dist\D2R_Filter_Generator\config\" >nul
    copy /y "config\*.yaml" "dist\D2R_Filter_Generator\config\" >nul
)

if exist "data\cache\d2lut.db" (
    copy /y "data\cache\d2lut.db" "dist\D2R_Filter_Generator\data\cache\" >nul
) else (
    echo Warning: data\cache\d2lut.db not found. Using static prices instead.
    echo Running static price generator...
    python scripts\generate_static_item_names.py
    copy /y "data\templates\item-names.json" "dist\D2R_Filter_Generator\data\templates\" >nul
)

echo Created deployment folder at: dist\D2R_Filter_Generator
echo To test run: cd dist\D2R_Filter_Generator ^& D2R_Loot_Filter_Builder.exe
pause
