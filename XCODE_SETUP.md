# AbletonRPC — Xcode Setup Instructions

## Prerequisites
- Xcode installed
- Apple Developer account (free tier is fine for local use)
- Python 3.14 at `/usr/local/bin/python3`

---

## Step 1 — Create the main app target

1. Open Xcode → **File → New → Project**
2. Choose **macOS → App**
3. Fill in:
   - Product Name: `AbletonRPC`
   - Bundle Identifier: `com.kiwi.AbletonRPC`  ← use your own prefix
   - Interface: **SwiftUI**
   - Language: **Swift**
   - Minimum Deployment: **macOS 13**
4. Save the project

---

## Step 2 — Add the helper target

1. **File → New → Target**
2. Choose **macOS → App**
3. Fill in:
   - Product Name: `AbletonRPCHelper`
   - Bundle Identifier: `com.kiwi.AbletonRPC.Helper`  ← MUST be prefixed with main app ID
   - Interface: **SwiftUI**
   - Language: **Swift**
4. Click Finish

---

## Step 3 — Add source files

### Main app target
Copy these files into the `AbletonRPC/` group in Xcode:
- `AbletonRPCApp.swift`
- `ContentView.swift`
- `AddInstallationView.swift`
- `Models.swift`
- `InstallationManager.swift`

Delete the boilerplate `ContentView.swift` Xcode generated first.

### Helper target
Copy into the `AbletonRPCHelper/` group:
- `AbletonRPCHelper/HelperApp.swift`

Delete the boilerplate files Xcode generated.

### Python daemon
1. In Xcode, select the `AbletonRPC` target (main app)
2. Drag `Resources/ableton_rpc.py` into the project navigator
3. In the dialog, make sure **"AbletonRPC" target** is checked (not Helper)
4. Confirm it appears in **Build Phases → Copy Bundle Resources**

---

## Step 4 — Embed the helper in the main app

1. Select the **AbletonRPC** project in the navigator
2. Select the **AbletonRPC** target
3. Go to **Build Phases**
4. Click **+** → **New Copy Files Phase**
5. Set **Destination** to `Wrapper`
6. Set **Subpath** to `Contents/Library/LoginItems`
7. Click **+** in the phase and add `AbletonRPCHelper.app`

This embeds the helper at the path the `HelperApp.swift` code expects.

---

## Step 5 — Configure the helper's Info.plist

Select the **AbletonRPCHelper** target → **Info** tab, add:

| Key | Type | Value |
|-----|------|-------|
| `LSUIElement` | Boolean | YES |
| `LSBackgroundOnly` | Boolean | YES |

This hides the helper from the Dock and App Switcher.

---

## Step 6 — Configure signing

1. Select the project → **Signing & Capabilities**
2. For **both** targets:
   - Check **Automatically manage signing**
   - Select your Team (free account is fine)
3. Make sure both use the **same Team ID**

---

## Step 7 — Add required capabilities

Select **AbletonRPC** (main app) target → **Signing & Capabilities → + Capability**:

Add:
- **App Sandbox** → disable it (needed for reading Ableton's MIDI scripts folder)

Or if you prefer to keep the sandbox, add:
- **App Sandbox** → **File Access** → Downloads: Read/Write
- **App Sandbox** → **File Access** → Music: Read/Write

For simplicity during development, disabling the sandbox is fine.

---

## Step 8 — Build and run

1. Select the **AbletonRPC** scheme
2. **Product → Run** (⌘R)
3. On first launch, macOS will ask for permission to add a Login Item
4. Approve it — the helper will then auto-start at login and launch the Python daemon

Check **System Settings → General → Login Items** to confirm `AbletonRPC Helper` appears.

---

## How it all works together

```
Login
  ↓
macOS starts AbletonRPCHelper (via SMAppService)
  ↓
HelperApp.swift finds ableton_rpc.py in parent bundle
  ↓
Launches: python3 .../AbletonRPC.app/Contents/Resources/ableton_rpc.py --daemon
  ↓
Daemon reads ~/Library/Application Support/AbletonRPC/installations.json
  ↓
One monitoring thread per installation
  ↓
Detects Ableton → reads log file → updates Discord RPC
```

If the daemon crashes, the helper restarts it after 5 seconds.
If the helper crashes, SMAppService restarts it.

---

## Adding an installation (user flow)

1. Open AbletonRPC app
2. Click **Add Installation**
3. Choose the `.app` bundle (NSOpenPanel — no tkinter issues)
4. Choose a log file location
5. Click **Add Installation**
6. App calls `python3 ableton_rpc.py --install <hash>` to install FauxMIDI
7. User restarts Ableton → sets FauxMIDI as Control Surface in MIDI prefs
8. Done — rich presence updates automatically

---

## Bundle identifiers to update

Replace `com.kiwi` with your own prefix throughout:
- `AbletonRPCApp.swift` — `com.kiwi.AbletonRPC.Helper`
- `AbletonRPCHelper/HelperApp.swift` — no changes needed
- Xcode project — set during creation

---

## Notes on free developer account

- SMAppService works fine for local use
- The app won't be notarized, so other Macs will show a Gatekeeper warning
- Users can bypass with right-click → Open
- For proper distribution, a paid account ($99/year) is needed for Developer ID signing + notarization
