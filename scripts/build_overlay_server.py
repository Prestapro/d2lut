#!/usr/bin/env python3
"""
Build script for D2R Overlay Server.

Creates a standalone executable with all dependencies bundled.

Usage:
    python scripts/build_overlay_server.py

Output:
    dist/D2R_Overlay_Server_Package/  - Ready-to-distribute folder
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command."""
    print(f"  Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=check)


def main():
    """Main build process."""
    print("=" * 60)
    print("   D2R Magic Item Pricer - Overlay Server Builder")
    print("=" * 60)
    print()

    # Get project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    print(f"Project root: {project_root}")

    # Check Python version
    py_version = sys.version_info
    print(f"Python version: {py_version.major}.{py_version.minor}.{py_version.micro}")

    if py_version < (3, 11):
        print("WARNING: Python 3.11+ is recommended")

    # Install build dependencies
    print("\nInstalling build dependencies...")
    deps = ["pyinstaller", "pyyaml", "pillow", "opencv-python", "websockets"]
    run_command([sys.executable, "-m", "pip", "install"] + deps)

    # Clean previous builds
    print("\nCleaning previous builds...")
    dirs_to_clean = ["build_overlay", "dist/D2R_Overlay_Server_Package"]
    for d in dirs_to_clean:
        p = project_root / d
        if p.exists():
            shutil.rmtree(p)
            print(f"  Removed: {d}")

    # Remove old executable
    exe_name = "D2R_Overlay_Server.exe" if platform.system() == "Windows" else "D2R_Overlay_Server"
    exe_path = project_root / "dist" / exe_name
    if exe_path.exists():
        exe_path.unlink()
        print(f"  Removed: dist/{exe_name}")

    # Build with PyInstaller using spec file
    print("\nBuilding executable with PyInstaller...")

    spec_file = project_root / "D2R_Overlay_Server.spec"
    if spec_file.exists():
        run_command([
            sys.executable, "-m", "PyInstaller",
            "--clean",
            "--noconfirm",
            str(spec_file)
        ])
    else:
        # Build without spec file
        sep = ";" if platform.system() == "Windows" else ":"

        run_command([
            sys.executable, "-m", "PyInstaller",
            "--name", "D2R_Overlay_Server",
            "--onefile",
            "--clean",
            "--distpath", "dist",
            "--workpath", "build_overlay",
            "--add-data", f"config{sep}config",
            "--add-data", f"data/d2data_json{sep}data/d2data_json",
            "--hidden-import", "PIL",
            "--hidden-import", "cv2",
            "--hidden-import", "websockets",
            "--collect-all", "websockets",
            "scripts/run_remote_overlay_server.py"
        ])

    # Create deployment package
    print("\nCreating deployment package...")
    package_dir = project_root / "dist" / "D2R_Overlay_Server_Package"
    package_dir.mkdir(parents=True, exist_ok=True)

    # Copy executable
    built_exe = project_root / "dist" / exe_name
    if built_exe.exists():
        shutil.copy(built_exe, package_dir / exe_name)
        print(f"  Copied: {exe_name}")

    # Copy config files
    config_src = project_root / "config"
    config_dst = package_dir / "config"
    if config_src.exists():
        if config_dst.exists():
            shutil.rmtree(config_dst)
        shutil.copytree(config_src, config_dst)
        print("  Copied: config/")

    # Copy data files
    data_src = project_root / "data" / "d2data_json"
    data_dst = package_dir / "data" / "d2data_json"
    if data_src.exists():
        data_dst.mkdir(parents=True, exist_ok=True)
        for f in data_src.glob("*.json"):
            shutil.copy(f, data_dst / f.name)
        print("  Copied: data/d2data_json/")

    # Create README
    readme_path = package_dir / "README.txt"
    readme_content = """D2R Magic Item Pricer - Overlay Server
======================================

HOW TO RUN:
-----------
1. Double-click START_SERVER.bat (Windows) or run ./start_server.sh (Linux/Mac)
2. Server will start on port 8765
3. Find your PC IP address:
   - Windows: Open CMD, type 'ipconfig'
   - Linux/Mac: Open terminal, type 'ip addr show' or 'ifconfig'
4. On dashboard device: open web app, go to Live Dashboard tab
5. Enter the IP address in Connection Settings
6. Click Connect

FOR REAL GAME DETECTION:
------------------------
- Install Tesseract OCR:
  - Windows: https://github.com/UB-Mannheim/tesseract/wiki
  - Linux: sudo apt install tesseract-ocr
  - Mac: brew install tesseract

- Run with --no-demo flag:
  D2R_Overlay_Server.exe --no-demo

COMMAND LINE OPTIONS:
---------------------
  --port PORT     Change WebSocket port (default: 8765)
  --host HOST     Change bind address (default: 0.0.0.0)
  --demo          Run in demo mode with mock items
  --no-demo       Disable demo mode (requires screen capture)
  --help          Show all options

TROUBLESHOOTING:
----------------
- "Connection refused": Check Windows Firewall allows port 8765
  Run as Admin: netsh advfirewall firewall add rule name="D2R Pricer" dir=in action=allow protocol=tcp localport=8765

- No items appearing: Try demo mode first (--demo flag)
  Check server logs for errors

- OCR errors: Install Tesseract OCR and add to PATH

GitHub: https://github.com/Prestapro/d2lut
"""
    readme_path.write_text(readme_content)
    print("  Created: README.txt")

    # Create start scripts
    if platform.system() == "Windows":
        bat_content = """@echo off
echo ============================================================
echo    D2R Overlay Server - Starting...
echo ============================================================
echo.
echo Server will start on port 8765
echo Find your IP: open new CMD and type 'ipconfig'
echo Then connect from dashboard device
echo.
echo Press Ctrl+C to stop the server
echo ============================================================
echo.
D2R_Overlay_Server.exe --demo
pause
"""
        (package_dir / "START_SERVER.bat").write_text(bat_content)
        print("  Created: START_SERVER.bat")
    else:
        sh_content = """#!/bin/bash
echo "============================================================"
echo "   D2R Overlay Server - Starting..."
echo "============================================================"
echo
echo "Server will start on port 8765"
echo "Find your IP: run 'ip addr show' or 'ifconfig'"
echo "Then connect from dashboard device"
echo
echo "Press Ctrl+C to stop the server"
echo "============================================================"
echo
./D2R_Overlay_Server --demo
"""
        sh_path = package_dir / "start_server.sh"
        sh_path.write_text(sh_content)
        sh_path.chmod(0o755)
        print("  Created: start_server.sh")

    # Make executable executable on Unix
    if platform.system() != "Windows":
        (package_dir / exe_name).chmod(0o755)

    print()
    print("=" * 60)
    print("   BUILD COMPLETE!")
    print("=" * 60)
    print()
    print(f"Package location: {package_dir}")
    print()
    print("Contents:")
    for item in sorted(package_dir.iterdir()):
        if item.is_dir():
            count = len(list(item.rglob("*")))
            print(f"  {item.name}/ ({count} files)")
        else:
            size = item.stat().st_size / 1024 / 1024
            print(f"  {item.name} ({size:.1f} MB)")
    print()
    print("To distribute: Zip the D2R_Overlay_Server_Package folder")
    print()


if __name__ == "__main__":
    main()
