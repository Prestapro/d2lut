#!/bin/bash
set -e

echo "Building D2R Loot Filter Generator..."

# Ensure we're in the d2lut project root
cd "$(dirname "$0")/.."

# Check if pyinstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "Error: pyinstaller is not installed."
    echo "Run: pip install pyinstaller"
    exit 1
fi

# Clean previous builds
rm -rf build/ dist/ D2R_Loot_Filter_Builder.spec

# Compile using PyInstaller
# --onefile: Bundles everything into a single executable
# --clean: Cleans PyInstaller cache and removes temporary files
# --name: Specific output file name
# --distpath: Put the output executable locally
# --workpath: Use safe temporary directory for the build process
PYTHONPATH=src pyinstaller \
    --name "D2R_Loot_Filter_Builder" \
    --onefile \
    --clean \
    --hidden-import "yaml" \
    --distpath "dist" \
    --workpath "build" \
    scripts/build_d2r_filter.py

echo "Build complete."
echo "You can find your executable at: dist/D2R_Loot_Filter_Builder"

# Create a zip structure that imitates end-user deployment
mkdir -p dist/D2R_Filter_Generator/data/cache
mkdir -p dist/D2R_Filter_Generator/data/templates
mkdir -p dist/D2R_Filter_Generator/config
mkdir -p dist/D2R_Filter_Generator/output

cp dist/D2R_Loot_Filter_Builder dist/D2R_Filter_Generator/
cp data/templates/item-names.json dist/D2R_Filter_Generator/data/templates/
if [ -d "config" ]; then
    cp config/*.yml dist/D2R_Filter_Generator/config/ 2>/dev/null || true
    cp config/*.yaml dist/D2R_Filter_Generator/config/ 2>/dev/null || true
fi
if [ -f "data/cache/d2lut.db" ]; then
    cp data/cache/d2lut.db dist/D2R_Filter_Generator/data/cache/
else
    echo "Warning: d2lut.db not found. Using static prices instead."
    python3 scripts/generate_static_item_names.py
    cp data/templates/item-names.json dist/D2R_Filter_Generator/data/templates/
fi

echo "Created deployment folder at: dist/D2R_Filter_Generator"
echo "To test run: cd dist/D2R_Filter_Generator && ./D2R_Loot_Filter_Builder"
