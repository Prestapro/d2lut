@echo off
setlocal enabledelayedexpansion
echo ============================================================
echo    D2R Magic Item Pricer - Overlay Server Builder
echo ============================================================
echo.

:: Navigate to the d2lut project root
cd /d "%~dp0\.."

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python 3.11+ from https://www.python.org/
    pause
    exit /b 1
)

:: Check/Install PyInstaller
echo Checking PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

:: Install dependencies
echo Installing dependencies...
pip install pyyaml pillow opencv-python pytesseract websockets

:: Clean previous builds
echo Cleaning previous builds...
if exist "build_overlay" rmdir /s /q "build_overlay"
if exist "dist\D2R_Overlay_Server" rmdir /s /q "dist\D2R_Overlay_Server"

:: Set PYTHONPATH
set PYTHONPATH=src

:: Build with PyInstaller
echo.
echo Building executable...
pyinstaller ^
    --name "D2R_Overlay_Server" ^
    --onefile ^
    --clean ^
    --distpath "dist" ^
    --workpath "build_overlay" ^
    --add-data "config;config" ^
    --add-data "data/d2data_json;data/d2data_json" ^
    --hidden-import "PIL" ^
    --hidden-import "cv2" ^
    --hidden-import "websockets" ^
    --collect-all "websockets" ^
    scripts\run_remote_overlay_server.py

if errorlevel 1 (
    echo Build failed!
    pause
    exit /b %errorlevel%
)

:: Create deployment folder
echo.
echo Creating deployment package...
mkdir "dist\D2R_Overlay_Server_Package" 2>nul
copy /y "dist\D2R_Overlay_Server.exe" "dist\D2R_Overlay_Server_Package\" >nul

:: Copy config files
xcopy /E /I /Y "config" "dist\D2R_Overlay_Server_Package\config" >nul 2>&1

:: Copy data files
xcopy /E /I /Y "data\d2data_json" "dist\D2R_Overlay_Server_Package\data\d2data_json" >nul 2>&1

:: Create README
echo Creating README...
(
echo D2R Magic Item Pricer - Overlay Server
echo ======================================
echo.
echo HOW TO RUN:
echo 1. Double-click D2R_Overlay_Server.exe
echo 2. Server will start on port 8765
echo 3. Find your PC IP: open CMD, type 'ipconfig'
echo 4. On dashboard device: enter IP in Connection Settings
echo.
echo FOR REAL GAME DETECTION:
echo - Install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
echo - Run with: D2R_Overlay_Server.exe --no-demo
echo.
echo OPTIONS:
echo --port PORT     Change port ^(default: 8765^)
echo --no-demo       Disable demo mode ^(requires Tesseract^)
echo --help          Show all options
echo.
) > "dist\D2R_Overlay_Server_Package\README.txt"

:: Create start batch file
(
echo @echo off
echo echo Starting D2R Overlay Server...
echo echo.
echo echo Find your IP: open new CMD and type 'ipconfig'
echo echo Then connect from dashboard device
echo echo.
echo D2R_Overlay_Server.exe --demo
echo pause
) > "dist\D2R_Overlay_Server_Package\START_SERVER.bat"

echo.
echo ============================================================
echo    BUILD COMPLETE!
echo ============================================================
echo.
echo Executable: dist\D2R_Overlay_Server_Package\D2R_Overlay_Server.exe
echo.
echo To run: Double-click START_SERVER.bat
echo Or run: D2R_Overlay_Server.exe --demo
echo.
pause
