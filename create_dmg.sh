#!/bin/bash
# AbletonRPC — DMG Creator
# Creates a distributable DMG from the built app.
# Run ./build.sh --install first, or just ./build.sh to build without installing.

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

VERSION="4.0.0"
APP_NAME="AbletonRPC"
APP_PATH="build/Release/${APP_NAME}.app"
DMG_NAME="${APP_NAME}-v${VERSION}.dmg"
INSTALLER_SCRIPT="install_helper.applescript"
INSTALLER_APP="Install AbletonRPC.app"

echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  AbletonRPC — DMG Creator                ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── Check app exists ──────────────────────────────────────────────────────
if [ ! -d "$APP_PATH" ]; then
    fail "App not found at $APP_PATH — run ./build.sh first"
fi
ok "Found $APP_PATH ($(du -sh "$APP_PATH" | cut -f1))"

# ── Compile installer app ─────────────────────────────────────────────────
log "Compiling installer app..."
if [ ! -f "$INSTALLER_SCRIPT" ]; then
    fail "install_helper.applescript not found — make sure it's in the project root"
fi
rm -rf "$INSTALLER_APP"
osacompile -o "$INSTALLER_APP" "$INSTALLER_SCRIPT"
if [ -d "$INSTALLER_APP" ]; then
    ok "Installer app compiled: $INSTALLER_APP"
else
    fail "osacompile failed — could not build installer app"
fi

# ── Homebrew ──────────────────────────────────────────────────────────────
log "Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    warn "Homebrew not found — installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    [[ $(uname -m) == 'arm64' ]] && eval "$(/opt/homebrew/bin/brew shellenv)" \
                                  || eval "$(/usr/local/bin/brew shellenv)"
fi
ok "Homebrew ready"

# ── create-dmg ────────────────────────────────────────────────────────────
log "Checking create-dmg..."
if ! command -v create-dmg &>/dev/null; then
    log "Installing create-dmg..."
    brew install create-dmg
fi
ok "create-dmg $(create-dmg --version 2>/dev/null || echo 'ready')"

# ── Remove old DMG ────────────────────────────────────────────────────────
if [ -f "$DMG_NAME" ]; then
    log "Removing existing $DMG_NAME..."
    rm "$DMG_NAME"
fi

# ── Check for icon ────────────────────────────────────────────────────────
USE_ICON=false
if [ -f "icon.icns" ]; then
    if file icon.icns | grep -q "Mac OS X icon"; then
        USE_ICON=true
        ok "icon.icns found and valid"
    else
        warn "icon.icns exists but is not a valid macOS icon — DMG will use default"
    fi
else
    warn "icon.icns not found — DMG will use default volume icon"
    warn "Run ./convert_icon.sh first if you want a custom icon"
fi

# ── Create DMG ────────────────────────────────────────────────────────────
log "Creating $DMG_NAME..."
echo ""

DMG_ARGS=(
    create-dmg
    --volname "$APP_NAME"
    --window-pos 200 120
    --window-size 660 400
    --icon-size 128
    --icon "${APP_NAME}.app" 160 195
    --icon "Install AbletonRPC.app" 480 195
    --hide-extension "${APP_NAME}.app"
    --hide-extension "Install AbletonRPC.app"
    --app-drop-link 320 195
    --no-internet-enable
    --skip-jenkins
)

if [ "$USE_ICON" = true ]; then
    DMG_ARGS+=(--volicon "icon.icns")
fi

# Try with create-dmg — stage both apps in a temp folder
STAGING=$(mktemp -d)
cp -R "$APP_PATH" "$STAGING/"
cp -R "$INSTALLER_APP" "$STAGING/"

if "${DMG_ARGS[@]}" "$DMG_NAME" "$STAGING/" 2>&1 | grep -v "^$"; then
    true
fi

# Fallback to plain hdiutil
if [ ! -f "$DMG_NAME" ]; then
    warn "create-dmg had issues — falling back to hdiutil..."
    ln -s /Applications "$STAGING/Applications"
    hdiutil create \
        -volname "$APP_NAME" \
        -srcfolder "$STAGING" \
        -ov -format UDZO \
        "$DMG_NAME"
    ok "Created DMG via hdiutil fallback"
fi

rm -rf "$STAGING"

[ -f "$DMG_NAME" ] || fail "DMG creation failed"

# ── Add Gatekeeper note inside DMG ────────────────────────────────────────
echo ""
ok "$DMG_NAME created ($(du -sh "$DMG_NAME" | cut -f1))"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  DMG ready for distribution!             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "File: $DMG_NAME"
echo ""
echo "Users: open the DMG and run 'Install AbletonRPC' — it handles"
echo "copying to /Applications and removing the Gatekeeper restriction."
echo ""
echo "Upload $DMG_NAME to your GitHub release."
echo ""
