#!/bin/bash
# convert_icon.sh — converts discord_icon.png into a macOS .icns file
# Uses only built-in macOS tools: sips + iconutil (no Homebrew required)
#
# Usage: ./convert_icon.sh [source.png]
# Default source: discord_icon.png in the same directory

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

SOURCE="${1:-discord_icon.png}"

if [ ! -f "$SOURCE" ]; then
    echo -e "${RED}✗${NC} Source image not found: $SOURCE"
    echo "   Place discord_icon.png in this directory, or pass a path as argument."
    exit 1
fi

echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  AbletonRPC — Icon Converter             ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# Verify source is a valid image
if ! sips -g pixelWidth "$SOURCE" &>/dev/null; then
    echo -e "${RED}✗${NC} '$SOURCE' is not a valid image file"
    exit 1
fi

W=$(sips -g pixelWidth  "$SOURCE" | awk '/pixelWidth/  {print $2}')
H=$(sips -g pixelHeight "$SOURCE" | awk '/pixelHeight/ {print $2}')
echo -e "${GREEN}✓${NC} Source image: $SOURCE (${W}×${H})"

if [ "$W" -lt 512 ] || [ "$H" -lt 512 ]; then
    echo -e "${YELLOW}⚠${NC}  Source is smaller than 512×512 — icons may appear blurry"
    echo "   Recommended: use a 1024×1024 PNG for best quality"
fi

# ── Create iconset directory ───────────────────────────────────────────────
ICONSET_DIR="AppIcon.iconset"
rm -rf "$ICONSET_DIR"
mkdir "$ICONSET_DIR"
echo -e "${BLUE}→${NC} Generating icon sizes..."

declare -a SIZES=(16 32 64 128 256 512 1024)

for SIZE in "${SIZES[@]}"; do
    # Standard resolution
    if [ "$SIZE" -lt 1024 ]; then
        OUT="$ICONSET_DIR/icon_${SIZE}x${SIZE}.png"
        sips -z "$SIZE" "$SIZE" "$SOURCE" --out "$OUT" &>/dev/null
    fi

    # @2x (retina) — only up to 512@2x=1024
    HALF=$((SIZE / 2))
    if [ "$HALF" -ge 16 ] && [ "$SIZE" -le 1024 ]; then
        OUT2X="$ICONSET_DIR/icon_${HALF}x${HALF}@2x.png"
        sips -z "$SIZE" "$SIZE" "$SOURCE" --out "$OUT2X" &>/dev/null
    fi
done

echo -e "${GREEN}✓${NC} Generated $(ls "$ICONSET_DIR" | wc -l | tr -d ' ') icon sizes"

# ── Convert iconset → .icns ────────────────────────────────────────────────
echo -e "${BLUE}→${NC} Converting to .icns..."
iconutil -c icns "$ICONSET_DIR" -o icon.icns
rm -rf "$ICONSET_DIR"

if [ ! -f "icon.icns" ]; then
    echo -e "${RED}✗${NC} icon.icns was not created"
    exit 1
fi

echo -e "${GREEN}✓${NC} icon.icns created ($(du -sh icon.icns | cut -f1))"
echo ""
echo "Done! icon.icns is ready — build.sh will pick it up automatically."
echo ""
