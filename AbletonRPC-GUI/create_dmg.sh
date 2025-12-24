#!/bin/bash

# Ableton Discord RPC - DMG Creator
# Creates a distributable DMG file from the built app

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  AbletonRPC - DMG Creator                 ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
echo ""

# Configuration
APP_NAME="AbletonRPC"
APP_PATH="dist/${APP_NAME}.app"
DMG_NAME="${APP_NAME}-v1.0.0.dmg"
VERSION="1.0.0"

# Check if app exists
if [ ! -d "$APP_PATH" ]; then
    echo -e "${RED}✗${NC} Error: ${APP_PATH} not found!"
    echo "   Please build the app first with: ./build_app.sh"
    exit 1
fi
echo -e "${GREEN}✓${NC} Found app: ${APP_PATH}"

# Check if icon exists and is valid
echo ""
echo -e "${BLUE}→${NC} Checking icon file..."
USE_ICON=false
if [ -f "icon.icns" ]; then
    if file icon.icns | grep -q "Mac OS X icon"; then
        echo -e "${GREEN}✓${NC} Valid icon.icns found"
        USE_ICON=true
    else
        echo -e "${YELLOW}⚠${NC}  icon.icns exists but is not a valid macOS icon format"
        echo "   DMG will be created without custom volume icon"
        echo "   Run ./convert_icon.sh to fix the icon"
    fi
else
    echo -e "${YELLOW}⚠${NC}  icon.icns not found"
    echo "   DMG will be created without custom volume icon"
fi

# Check if Homebrew is installed
echo ""
echo -e "${BLUE}→${NC} Checking for Homebrew..."
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}⚠${NC}  Homebrew not found. Installing Homebrew..."
    echo ""
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for this session
    if [[ $(uname -m) == 'arm64' ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    else
        eval "$(/usr/local/bin/brew shellenv)"
    fi
    
    echo -e "${GREEN}✓${NC} Homebrew installed"
else
    echo -e "${GREEN}✓${NC} Homebrew is installed"
fi

# Check if create-dmg is installed
echo ""
echo -e "${BLUE}→${NC} Checking for create-dmg..."
if ! brew list create-dmg &> /dev/null; then
    echo -e "${YELLOW}⚠${NC}  create-dmg not found. Installing..."
    brew install create-dmg
    echo -e "${GREEN}✓${NC} create-dmg installed"
else
    echo -e "${GREEN}✓${NC} create-dmg is installed"
fi

# Remove old DMG if it exists
if [ -f "$DMG_NAME" ]; then
    echo ""
    echo -e "${BLUE}→${NC} Removing old DMG..."
    rm "$DMG_NAME"
fi

# Create DMG
echo ""
echo -e "${BLUE}→${NC} Creating DMG..."
echo ""

# Build create-dmg command based on whether we have a valid icon
if [ "$USE_ICON" = true ]; then
    echo "Using custom volume icon..."
    DMG_CMD=(
        create-dmg
        --volname "${APP_NAME}"
        --volicon "icon.icns"
        --window-pos 200 120
        --window-size 600 400
        --icon-size 100
        --icon "${APP_NAME}.app" 175 190
        --hide-extension "${APP_NAME}.app"
        --app-drop-link 425 190
        --no-internet-enable
        --skip-jenkins
        "$DMG_NAME"
        "$APP_PATH"
    )
else
    echo "Creating DMG without custom volume icon..."
    DMG_CMD=(
        create-dmg
        --volname "${APP_NAME}"
        --window-pos 200 120
        --window-size 600 400
        --icon-size 100
        --icon "${APP_NAME}.app" 175 190
        --hide-extension "${APP_NAME}.app"
        --app-drop-link 425 190
        --no-internet-enable
        --skip-jenkins
        "$DMG_NAME"
        "$APP_PATH"
    )
fi

# Try with skip-jenkins flag to avoid AppleScript timeout issues
"${DMG_CMD[@]}" 2>&1 | grep -v "AppleScript" || true

# If that fails, try a simpler approach without fancy positioning
if [ ! -f "$DMG_NAME" ]; then
    echo -e "${YELLOW}⚠${NC}  First attempt had issues, trying simpler DMG creation..."
    
    create-dmg \
      --volname "${APP_NAME}" \
      --window-size 600 400 \
      --app-drop-link 425 190 \
      --skip-jenkins \
      "$DMG_NAME" \
      "$APP_PATH" || {
        echo -e "${YELLOW}⚠${NC}  Fancy DMG creation failed, using basic method..."
        
        # Fallback: Create a simple DMG using hdiutil
        TEMP_DMG="temp_${DMG_NAME}"
        
        # Create temporary directory
        TEMP_DIR=$(mktemp -d)
        cp -R "$APP_PATH" "$TEMP_DIR/"
        ln -s /Applications "$TEMP_DIR/Applications"
        
        # Create DMG
        hdiutil create -volname "${APP_NAME}" -srcfolder "$TEMP_DIR" -ov -format UDZO "$TEMP_DMG"
        mv "$TEMP_DMG" "$DMG_NAME"
        
        # Cleanup
        rm -rf "$TEMP_DIR"
        
        echo -e "${GREEN}✓${NC} Created basic DMG (without custom styling)"
    }
fi

# Check if DMG was created successfully
if [ ! -f "$DMG_NAME" ]; then
    echo -e "${RED}✗${NC} DMG creation failed!"
    exit 1
fi

# Display results
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  DMG Created Successfully!                ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo ""
echo "DMG File: $DMG_NAME"
echo "Size: $(du -sh "$DMG_NAME" | cut -f1)"
echo ""
echo "The DMG is ready for distribution!"
echo ""
echo "Users can:"
echo "  1. Download and open the DMG"
echo "  2. Drag the app to Applications folder"
echo "  3. Run the app - setup GUI appears on first launch"
echo "  4. Done! App installs itself automatically"
echo ""