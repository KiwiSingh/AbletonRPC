#!/bin/bash

# Convert PNG icon to macOS .icns format
# Usage: ./convert_icon.sh your_icon.png

set -e

if [ $# -eq 0 ]; then
    echo "Usage: ./convert_icon.sh icon.png"
    exit 1
fi

INPUT_FILE="$1"

if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: File '$INPUT_FILE' not found!"
    exit 1
fi

echo "Converting $INPUT_FILE to icon.icns..."

# Create iconset directory
ICONSET="AppIcon.iconset"
rm -rf "$ICONSET"
mkdir "$ICONSET"

# Generate all required sizes
echo "Generating icon sizes..."

# Use sips (built-in macOS tool) to resize
# Important: Create proper PNG files with transparency
sips -z 16 16     "$INPUT_FILE" --out "$ICONSET/icon_16x16.png" >/dev/null 2>&1
sips -z 32 32     "$INPUT_FILE" --out "$ICONSET/icon_16x16@2x.png" >/dev/null 2>&1
sips -z 32 32     "$INPUT_FILE" --out "$ICONSET/icon_32x32.png" >/dev/null 2>&1
sips -z 64 64     "$INPUT_FILE" --out "$ICONSET/icon_32x32@2x.png" >/dev/null 2>&1
sips -z 128 128   "$INPUT_FILE" --out "$ICONSET/icon_128x128.png" >/dev/null 2>&1
sips -z 256 256   "$INPUT_FILE" --out "$ICONSET/icon_128x128@2x.png" >/dev/null 2>&1
sips -z 256 256   "$INPUT_FILE" --out "$ICONSET/icon_256x256.png" >/dev/null 2>&1
sips -z 512 512   "$INPUT_FILE" --out "$ICONSET/icon_256x256@2x.png" >/dev/null 2>&1
sips -z 512 512   "$INPUT_FILE" --out "$ICONSET/icon_512x512.png" >/dev/null 2>&1
sips -z 1024 1024 "$INPUT_FILE" --out "$ICONSET/icon_512x512@2x.png" >/dev/null 2>&1

echo "Converting to .icns format..."

# Remove old icon if exists
rm -f icon.icns

# Convert using iconutil (proper Apple tool)
iconutil -c icns "$ICONSET" -o icon.icns

# Verify the icon was created correctly
if [ ! -f "icon.icns" ]; then
    echo "✗ Error: Failed to create icon.icns"
    rm -rf "$ICONSET"
    exit 1
fi

# Verify it's a valid icon file
if ! file icon.icns | grep -q "Mac OS X icon"; then
    echo "✗ Error: Created icon.icns is not a valid macOS icon format"
    echo "  Your source image might have issues. Try with a different PNG file."
    rm -rf "$ICONSET"
    exit 1
fi

echo "Cleaning up..."
rm -rf "$ICONSET"

echo "✓ Done! Created icon.icns"
echo "  Size: $(ls -lh icon.icns | awk '{print $5}')"
echo "  Type: $(file icon.icns)"
echo ""
echo "The icon is ready to use. Run ./build_app.sh to rebuild with the new icon."