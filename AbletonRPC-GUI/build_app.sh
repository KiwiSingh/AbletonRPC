#!/bin/bash

# Ableton Discord RPC - Complete Build Script
# This script builds the macOS application bundle

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  AbletonRPC - Build Script               ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗${NC} Python 3 is not installed!"
    echo "   Please install Python 3 from https://www.python.org/"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python 3 found: $(python3 --version)"

# Check if required files exist
if [ ! -f "ableton_rpc.py" ]; then
    echo -e "${RED}✗${NC} ableton_rpc.py not found!"
    exit 1
fi
echo -e "${GREEN}✓${NC} Found ableton_rpc.py"

if [ ! -f "setup.py" ]; then
    echo -e "${RED}✗${NC} setup.py not found!"
    exit 1
fi
echo -e "${GREEN}✓${NC} Found setup.py"

# Install dependencies
echo ""
echo -e "${BLUE}→${NC} Checking dependencies..."

DEPS=(pypresence psutil py2app)
MISSING_DEPS=()

for dep in "${DEPS[@]}"; do
    if ! python3 -c "import $dep" 2>/dev/null; then
        MISSING_DEPS+=($dep)
    fi
done

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠${NC}  Missing dependencies: ${MISSING_DEPS[*]}"
    echo -e "${BLUE}→${NC} Installing missing dependencies..."
    pip3 install "${MISSING_DEPS[@]}"
    echo -e "${GREEN}✓${NC} Dependencies installed"
else
    echo -e "${GREEN}✓${NC} All dependencies present"
fi

# Clean previous builds
echo ""
echo -e "${BLUE}→${NC} Cleaning previous builds..."
rm -rf build dist
echo -e "${GREEN}✓${NC} Build directories cleaned"

# Build the application
echo ""
echo -e "${BLUE}→${NC} Building application bundle..."
python3 setup.py py2app

if [ ! -d "dist/AbletonRPC.app" ]; then
    echo -e "${RED}✗${NC} Build failed! Application not created."
    exit 1
fi

echo -e "${GREEN}✓${NC} Application built successfully!"

# Check if icon file exists and offer to add it
if [ -f "icon.icns" ]; then
    echo -e "${BLUE}→${NC} Adding custom icon..."
    # Copy to Resources folder with the app's icon name
    cp icon.icns dist/AbletonRPC.app/Contents/Resources/
    # Also rename to match the CFBundleIconFile if needed
    cp icon.icns dist/AbletonRPC.app/Contents/Resources/app.icns
    echo -e "${GREEN}✓${NC} Custom icon added"
else
    echo -e "${YELLOW}⚠${NC}  No icon.icns found - app will use default icon"
    echo "   Run ./convert_icon.sh your_icon.png to create one"
fi

touch dist/AbletonRPC.app
# Display build info
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Build Complete!                          ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo ""
echo "Application: dist/AbletonRPC.app"
echo "Size: $(du -sh dist/AbletonRPC.app | cut -f1)"
echo ""
echo "Next steps:"
echo "  1. Test the app: open dist/AbletonRPC.app"
echo "  2. Move to Applications: mv dist/AbletonRPC.app ~/Applications/"
echo "  3. Run installer: ./install.sh"
echo ""
echo "Or create a DMG for distribution."
echo ""