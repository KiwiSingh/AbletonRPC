#!/bin/bash

# Debug icon issues

echo "=== Icon Debug Information ==="
echo ""

# Check if icon.icns exists
if [ -f "icon.icns" ]; then
    echo "✓ icon.icns exists"
    echo "  Size: $(ls -lh icon.icns | awk '{print $5}')"
    echo "  Type: $(file icon.icns)"
    echo ""
    
    # Check if it's a valid icns file
    if file icon.icns | grep -q "Apple Icon Image"; then
        echo "✓ icon.icns is a valid Apple Icon Image format"
    else
        echo "✗ icon.icns is NOT a valid Apple Icon Image format"
        echo "  This is likely the problem!"
    fi
else
    echo "✗ icon.icns not found in current directory"
fi

echo ""

# Check if the app has the icon
if [ -d "dist/AbletonRPC.app" ]; then
    echo "Checking app bundle icons..."
    echo ""
    
    RESOURCES="dist/AbletonRPC.app/Contents/Resources"
    
    if [ -f "$RESOURCES/icon.icns" ]; then
        echo "✓ Found: $RESOURCES/icon.icns"
        echo "  Size: $(ls -lh "$RESOURCES/icon.icns" | awk '{print $5}')"
    else
        echo "✗ Missing: $RESOURCES/icon.icns"
    fi
    
    if [ -f "$RESOURCES/app.icns" ]; then
        echo "✓ Found: $RESOURCES/app.icns"
        echo "  Size: $(ls -lh "$RESOURCES/app.icns" | awk '{print $5}')"
    else
        echo "✗ Missing: $RESOURCES/app.icns"
    fi
    
    # Check Info.plist for icon file reference
    echo ""
    echo "Info.plist CFBundleIconFile:"
    /usr/libexec/PlistBuddy -c "Print CFBundleIconFile" "dist/AbletonRPC.app/Contents/Info.plist" 2>/dev/null || echo "  (not set)"
    
else
    echo "✗ App not found at dist/AbletonRPC.app"
fi

echo ""
echo "=== Suggested Fixes ==="
echo ""

if [ -f "discord_icon.png" ]; then
    echo "1. Try reconverting your PNG icon:"
    echo "   ./convert_icon.sh discord_icon.png"
    echo ""
fi

echo "2. Rebuild the app:"
echo "   rm -rf build dist"
echo "   ./build_app.sh"
echo ""

echo "3. If icon still doesn't show, try refreshing Finder:"
echo "   touch dist/AbletonRPC.app"
echo "   killall Finder"
echo ""