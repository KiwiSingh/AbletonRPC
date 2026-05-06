#!/bin/bash
# AbletonRPC — Full build script
# No paid Apple Developer account required — uses ad-hoc signing.
# Usage: ./build.sh [--install]   (--install also copies .app to /Applications)

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${BLUE}→${NC} $*"; }
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
fail() { echo -e "${RED}✗${NC} $*"; exit 1; }

echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  AbletonRPC — Build Script               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── Xcode CLT ─────────────────────────────────────────────────────────────
log "Checking Xcode Command Line Tools..."
if ! xcode-select -p &>/dev/null; then
    fail "Xcode Command Line Tools not installed. Run: xcode-select --install"
fi
ok "Xcode CLT: $(xcode-select -p)"

# ── Homebrew ──────────────────────────────────────────────────────────────
log "Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    warn "Homebrew not found — installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    [[ $(uname -m) == 'arm64' ]] && eval "$(/opt/homebrew/bin/brew shellenv)" \
                                  || eval "$(/usr/local/bin/brew shellenv)"
fi
ok "Homebrew ready"

# ── xcodegen ─────────────────────────────────────────────────────────────
log "Checking xcodegen..."
if ! command -v xcodegen &>/dev/null; then
    log "Installing xcodegen..."
    brew install xcodegen
fi
ok "xcodegen $(xcodegen --version 2>/dev/null | head -1)"

# ── Python dependencies ───────────────────────────────────────────────────
log "Checking Python dependencies..."
PYTHON3="/usr/local/bin/python3"
if ! command -v "$PYTHON3" &>/dev/null; then
    PYTHON3="python3"
fi

MISSING=()
while IFS='>=' read -r pkg _; do
    [[ -z "$pkg" || "$pkg" == \#* ]] && continue
    "$PYTHON3" -c "import $pkg" 2>/dev/null || MISSING+=("$pkg")
done < requirements.txt

if [ ${#MISSING[@]} -gt 0 ]; then
    warn "Missing Python packages: ${MISSING[*]}"
    log "Installing via pip..."
    "$PYTHON3" -m pip install -r requirements.txt --quiet
    ok "Python dependencies installed"
else
    ok "Python dependencies present"
fi
log "Checking for icon..."
if [ -f "discord_icon.png" ]; then
    if [ ! -f "icon.icns" ] || [ "discord_icon.png" -nt "icon.icns" ]; then
        log "Converting discord_icon.png → icon.icns..."
        bash convert_icon.sh discord_icon.png
    else
        ok "icon.icns is up to date"
    fi
elif [ -f "icon.icns" ]; then
    ok "icon.icns found"
else
    warn "No icon found — app will use default macOS icon"
fi

# ── Generate .xcodeproj ───────────────────────────────────────────────────
log "Generating Xcode project from project.yml..."
xcodegen generate --spec project.yml
ok "AbletonRPC.xcodeproj generated"

# ── Write Info.plist files ────────────────────────────────────────────────
# xcodegen defines them in project.yml but doesn't always write them to disk.
# Write them explicitly so xcodebuild can find them.
log "Writing Info.plist files..."

mkdir -p AbletonRPC AbletonRPCHelper

cat > AbletonRPC/Info.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>AbletonRPC</string>
<key>CFBundleDisplayName</key><string>AbletonRPC</string>
<key>CFBundleIdentifier</key><string>com.kiwi.AbletonRPC</string>
<key>CFBundleVersion</key><string>3.1.0</string>
<key>CFBundleShortVersionString</key><string>3.1.0</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleExecutable</key><string>$(EXECUTABLE_NAME)</string>
<key>CFBundleIconFile</key><string>icon</string>
<key>NSPrincipalClass</key><string>NSApplication</string>
<key>NSHighResolutionCapable</key><true/>
<key>LSMinimumSystemVersion</key><string>13.0</string>
</dict></plist>
PLIST

cat > AbletonRPCHelper/Info.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>AbletonRPCHelper</string>
<key>CFBundleDisplayName</key><string>AbletonRPC Helper</string>
<key>CFBundleIdentifier</key><string>com.kiwi.AbletonRPC.Helper</string>
<key>CFBundleVersion</key><string>3.1.0</string>
<key>CFBundleShortVersionString</key><string>3.1.0</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleExecutable</key><string>$(EXECUTABLE_NAME)</string>
<key>NSPrincipalClass</key><string>NSApplication</string>
<key>LSUIElement</key><true/>
<key>LSBackgroundOnly</key><true/>
<key>LSMinimumSystemVersion</key><string>13.0</string>
</dict></plist>
PLIST

ok "Info.plist files written"

# ── Build ─────────────────────────────────────────────────────────────────
BUILD_DIR="build/Release"
log "Building AbletonRPC.app (ad-hoc signed)..."

xcodebuild \
    -project AbletonRPC.xcodeproj \
    -scheme AbletonRPC \
    -configuration Release \
    -derivedDataPath build/DerivedData \
    CONFIGURATION_BUILD_DIR="$(pwd)/$BUILD_DIR" \
    CODE_SIGN_IDENTITY="-" \
    CODE_SIGNING_REQUIRED=YES \
    CODE_SIGN_STYLE=Manual \
    DEVELOPMENT_TEAM="" \
    clean build \
    2>&1 | grep -E "error:|warning:|Build succeeded|Build FAILED|Compiling|Linking|note:" \
    || true

APP_PATH="$BUILD_DIR/AbletonRPC.app"

if [ ! -d "$APP_PATH" ]; then
    fail "Build failed — AbletonRPC.app not found. Check output above for errors."
fi
ok "Build succeeded: $APP_PATH ($(du -sh "$APP_PATH" | cut -f1))"

# ── Bundle Python framework ───────────────────────────────────────────────
log "Bundling Python runtime into app..."

# Find the python.org Python framework
PYTHON_BIN=$(command -v /usr/local/bin/python3.14 || \
             command -v /usr/local/bin/python3 || \
             echo "")

if [ -z "$PYTHON_BIN" ]; then
    warn "Could not find Python 3 — skipping bundling. Users will need Python installed."
else
    # Resolve the real executable (may be a symlink)
    PYTHON_REAL=$(python3 -c "import sys; print(sys.executable)" 2>/dev/null || "$PYTHON_BIN" -c "import sys; print(sys.executable)")
    PYTHON_VERSION=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

    # Find the Python.framework root
    FRAMEWORK_ROOT=$(echo "$PYTHON_REAL" | grep -o '.*/Python.framework' || true)

    if [ -n "$FRAMEWORK_ROOT" ] && [ -d "$FRAMEWORK_ROOT" ]; then
        BUNDLE_PYTHON_DIR="$APP_PATH/Contents/Resources/python"
        mkdir -p "$BUNDLE_PYTHON_DIR"

        log "Copying Python $PYTHON_VERSION framework (this may take a moment)..."

        # Copy just the versioned framework — not the whole thing
        VERSIONED="$FRAMEWORK_ROOT/Versions/$PYTHON_VERSION"
        if [ -d "$VERSIONED" ]; then
            # Copy bin, lib, include — skip .pyc caches and test suites to keep size down
            rsync -a --quiet \
                --exclude "*.pyc" \
                --exclude "__pycache__" \
                --exclude "test/" \
                --exclude "tests/" \
                --exclude "idle_test/" \
                --exclude "*/test/*.py" \
                --exclude "ensurepip/" \
                --exclude "tkinter/" \
                --exclude "turtledemo/" \
                "$VERSIONED/bin/"     "$BUNDLE_PYTHON_DIR/bin/"
            rsync -a --quiet \
                --exclude "*.pyc" \
                --exclude "__pycache__" \
                --exclude "test/" \
                --exclude "tests/" \
                --exclude "config-*/" \
                "$VERSIONED/lib/python${PYTHON_VERSION}/" \
                "$BUNDLE_PYTHON_DIR/lib/python${PYTHON_VERSION}/"

            # Copy the Python shared library itself
            cp -f "$VERSIONED/Python" "$BUNDLE_PYTHON_DIR/" 2>/dev/null || \
            cp -f "$VERSIONED/lib/libpython${PYTHON_VERSION}.dylib" "$BUNDLE_PYTHON_DIR/" 2>/dev/null || true

            # Install required packages into the bundled Python's site-packages
            BUNDLED_PIP="$BUNDLE_PYTHON_DIR/bin/pip3"
            BUNDLED_SITE="$BUNDLE_PYTHON_DIR/lib/python${PYTHON_VERSION}/site-packages"
            mkdir -p "$BUNDLED_SITE"

            if [ -f "$BUNDLED_PIP" ]; then
                log "Installing pypresence and psutil into bundled Python..."
                "$BUNDLE_PYTHON_DIR/bin/python3" -m pip install \
                    pypresence psutil \
                    --target "$BUNDLED_SITE" \
                    --quiet --no-warn-script-location 2>/dev/null || \
                "$PYTHON_BIN" -m pip install \
                    pypresence psutil \
                    --target "$BUNDLED_SITE" \
                    --quiet 2>/dev/null || true
            else
                # pip not in bundle — install packages directly to target
                "$PYTHON_BIN" -m pip install \
                    pypresence psutil \
                    --target "$BUNDLED_SITE" \
                    --quiet 2>/dev/null || true
            fi

            ok "Python $PYTHON_VERSION bundled ($(du -sh "$BUNDLE_PYTHON_DIR" | cut -f1))"
        else
            warn "Could not find versioned framework at $VERSIONED — skipping"
        fi
    else
        # No framework found (e.g. Homebrew Python) — copy just the binary + packages
        warn "Python.framework not found — bundling binary + packages only"
        BUNDLE_PYTHON_DIR="$APP_PATH/Contents/Resources/python"
        mkdir -p "$BUNDLE_PYTHON_DIR/bin" "$BUNDLE_PYTHON_DIR/lib/site-packages"
        cp -f "$PYTHON_REAL" "$BUNDLE_PYTHON_DIR/bin/python3"
        "$PYTHON_BIN" -m pip install \
            pypresence psutil \
            --target "$BUNDLE_PYTHON_DIR/lib/site-packages" \
            --quiet 2>/dev/null || true
        ok "Python binary + packages bundled"
    fi
fi
log "Running post-build fixups..."

# 1. Move helper from Resources/ to Library/LoginItems/ where it belongs
HELPER_IN_RESOURCES="$APP_PATH/Contents/Resources/AbletonRPCHelper.app"
HELPER_DEST="$APP_PATH/Contents/Library/LoginItems"
if [ -d "$HELPER_IN_RESOURCES" ]; then
    mkdir -p "$HELPER_DEST"
    mv "$HELPER_IN_RESOURCES" "$HELPER_DEST/"
    ok "Moved helper to Library/LoginItems/"
elif [ -d "$APP_PATH/Contents/Library/LoginItems/AbletonRPCHelper.app" ]; then
    ok "Helper already in correct location"
else
    warn "Helper not found anywhere in bundle — registration will fail"
fi

# 2. Copy Python daemon script into Resources/
if [ ! -f "$APP_PATH/Contents/Resources/ableton_rpc.py" ]; then
    cp Resources/ableton_rpc.py "$APP_PATH/Contents/Resources/"
    ok "Copied ableton_rpc.py to bundle Resources"
fi

# 3. Copy icon into Resources/ if present
if [ -f "icon.icns" ]; then
    cp icon.icns "$APP_PATH/Contents/Resources/icon.icns"
    ok "Copied icon.icns to bundle Resources"
fi

# Re-sign after modifications
log "Re-signing bundle after fixups..."
codesign --force --deep --sign - "$APP_PATH" 2>/dev/null || true
ok "Bundle re-signed"

# ── Remove quarantine ─────────────────────────────────────────────────────
log "Removing quarantine flags..."
xattr -rd com.apple.quarantine "$APP_PATH" 2>/dev/null || true
ok "Quarantine cleared"

# ── Install to /Applications ──────────────────────────────────────────────
if [[ "$1" == "--install" ]]; then
    log "Installing to /Applications..."
    if [ -d "/Applications/AbletonRPC.app" ]; then
        # Unload any existing LaunchAgent before replacing the app
        PLIST="$HOME/Library/LaunchAgents/com.kiwi.AbletonRPC.Helper.plist"
        if [ -f "$PLIST" ]; then
            launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
        fi
        rm -rf "/Applications/AbletonRPC.app"
    fi
    cp -R "$APP_PATH" "/Applications/"
    xattr -rd com.apple.quarantine "/Applications/AbletonRPC.app" 2>/dev/null || true
    ok "Installed to /Applications/AbletonRPC.app"

    # Refresh Launch Services and Dock so the icon shows correctly
    log "Refreshing Dock icon cache..."
    /System/Library/Frameworks/CoreServices.framework/Versions/Current/Frameworks/LaunchServices.framework/Versions/Current/Support/lsregister \
        -f /Applications/AbletonRPC.app 2>/dev/null || true
    killall Dock 2>/dev/null || true
    ok "Dock refreshed"
    echo ""
    echo "Launch AbletonRPC from Applications."
    echo "The helper will register its LaunchAgent automatically on first launch."
else
    echo ""
    echo "App built at: $BUILD_DIR/AbletonRPC.app"
    echo ""
    echo "To install:   ./build.sh --install"
    echo "To run now:   open $BUILD_DIR/AbletonRPC.app"
    echo ""
    echo -e "${YELLOW}Note for GitHub users:${NC}"
    echo "  After downloading, run: xattr -rd com.apple.quarantine AbletonRPC.app"
    echo "  Or right-click → Open on first launch to bypass Gatekeeper."
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Build Complete!                         ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
