#!/bin/bash
set -e

echo "============================================================"
echo "   D2R Magic Item Pricer - Overlay Server Builder"
echo "============================================================"
echo

# Navigate to the d2lut project root
cd "$(dirname "$0")/.."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed."
    echo "Please install Python 3.11+"
    exit 1
fi

# Check/Install PyInstaller
echo "Checking PyInstaller..."
if ! pip show pyinstaller &> /dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# Install dependencies
echo "Installing dependencies..."
pip install pyyaml pillow opencv-python pytesseract websockets

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build_overlay/ dist/D2R_Overlay_Server dist/D2R_Overlay_Server_Package

# Set PYTHONPATH
export PYTHONPATH=src

# Build with PyInstaller
echo
echo "Building executable..."
pyinstaller \
    --name "D2R_Overlay_Server" \
    --onefile \
    --clean \
    --distpath "dist" \
    --workpath "build_overlay" \
    --add-data "config:config" \
    --add-data "data/d2data_json:data/d2data_json" \
    --hidden-import "PIL" \
    --hidden-import "cv2" \
    --hidden-import "websockets" \
    --collect-all "websockets" \
    scripts/run_remote_overlay_server.py

# Create deployment folder
echo
echo "Creating deployment package..."
mkdir -p dist/D2R_Overlay_Server_Package
cp dist/D2R_Overlay_Server dist/D2R_Overlay_Server_Package/

# Copy config files
cp -r config dist/D2R_Overlay_Server_Package/ 2>/dev/null || true

# Copy data files
mkdir -p dist/D2R_Overlay_Server_Package/data/d2data_json
cp -r data/d2data_json/*.json dist/D2R_Overlay_Server_Package/data/d2data_json/ 2>/dev/null || true

# Create README
echo "Creating README..."
cat > dist/D2R_Overlay_Server_Package/README.txt << 'EOF'
D2R Magic Item Pricer - Overlay Server
======================================

HOW TO RUN:
1. Run: ./D2R_Overlay_Server --demo
2. Server will start on port 8765
3. Find your PC IP: run 'ip addr show' or 'ifconfig'
4. On dashboard device: enter IP in Connection Settings

FOR REAL GAME DETECTION:
- Install Tesseract OCR: sudo apt install tesseract-ocr (Linux) or brew install tesseract (Mac)
- Run with: ./D2R_Overlay_Server --no-demo

OPTIONS:
--port PORT     Change port (default: 8765)
--no-demo       Disable demo mode (requires Tesseract)
--help          Show all options
EOF

# Create start script
cat > dist/D2R_Overlay_Server_Package/start_server.sh << 'EOF'
#!/bin/bash
echo "Starting D2R Overlay Server..."
echo
echo "Find your IP: open terminal and run 'ip addr show' or 'ifconfig'"
echo "Then connect from dashboard device"
echo
./D2R_Overlay_Server --demo
EOF
chmod +x dist/D2R_Overlay_Server_Package/start_server.sh
chmod +x dist/D2R_Overlay_Server_Package/D2R_Overlay_Server

echo
echo "============================================================"
echo "   BUILD COMPLETE!"
echo "============================================================"
echo
echo "Executable: dist/D2R_Overlay_Server_Package/D2R_Overlay_Server"
echo
echo "To run: ./dist/D2R_Overlay_Server_Package/start_server.sh"
echo "Or run: ./dist/D2R_Overlay_Server_Package/D2R_Overlay_Server --demo"
echo
