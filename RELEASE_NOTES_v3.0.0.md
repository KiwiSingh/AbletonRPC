# AbletonRPC v3.0.0 — Brand New Day

This is a ground-up rewrite. v3.0.0 replaces the Python/Tkinter app with a native Swift frontend and a properly managed background daemon, fixing the reliability and dark mode issues that plagued earlier versions.

---

## What's new

### Native Swift app
The GUI is now written in SwiftUI. No more Tkinter dark mode rendering bugs, no more invisible widgets, no more "damaged or incomplete" app warnings. The app looks and behaves like a proper macOS application.

### Bundled Python runtime
Python is now shipped inside the app bundle. Users no longer need to install Python separately — just download, open, and go.

### Reliable background daemon
The daemon is now managed by a native Swift helper app (`AbletonRPCHelper`) registered as a LaunchAgent. The helper explicitly sets up the correct user environment (`HOME`, `TMPDIR`, `PATH`) before launching the Python daemon, fixing the `TMPDIR` mismatch and exit code 78 issues that caused the daemon to silently fail in previous versions.

### Vesktop and alt-client support
`BroadPresence` — a custom `pypresence` subclass — now searches all known Discord IPC socket locations used by Vesktop, Legcord, WebCord, and other alternative clients, in addition to the standard locations used by the official Discord client.

### Native macOS file picker
The `.app` bundle picker now uses `NSOpenPanel` instead of tkinter's broken `filedialog`, which couldn't select `.app` bundles at all on Tk 8.6.

### Clean uninstall
The Remove button now fully uninstalls FauxMIDI from the Ableton bundle in addition to stopping the service and removing the LaunchAgent plist. A restart prompt is shown to complete the cleanup.

### FauxMIDI stability fix for Live 12.4
The background name monitor in the FauxMIDI MIDI script no longer overwrites a known project name with a failed detection result. In Ableton Live 12.4, the Live Python API occasionally throws C++ signature mismatches when `song.name` is called from a background thread — the monitor now holds the last known good name instead of falling back to "Unsaved Project".

---

## Upgrading from v2.x

v3.0.0 is not a drop-in upgrade. A clean reinstall is required:

```bash
# Stop everything and wipe the old install
pkill -f "AbletonRPCHelper" 2>/dev/null
pkill -f "ableton_rpc.py" 2>/dev/null
rm -f ~/Library/LaunchAgents/com.kiwi.AbletonRPC*.plist
rm -f ~/Library/LaunchAgents/com.user.ableton-rpc.*.plist
rm -rf /Applications/AbletonRPC.app
rm -rf ~/Library/Application\ Support/AbletonRPC

# Remove FauxMIDI from your Ableton installs
rm -rf "/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/MIDI Remote Scripts/FauxMIDI"
rm -rf "/Applications/Ableton Live 12 Beta.app/Contents/App-Resources/MIDI Remote Scripts/FauxMIDI"
```

Then install v3.0.0, open the app, and add your installations again.

---

## Building from source

```bash
git clone https://github.com/KiwiSingh/AbletonRPC
cd AbletonRPC/AbletonRPC-GUI
./build.sh --install
```

Requires Xcode (not just Command Line Tools) and Homebrew. `build.sh` handles everything else including `xcodegen`, icon conversion, Python bundling, and Dock registration.

---

## Known limitations

- Requires a paid Apple Developer account for proper notarization. Builds from source will trigger a Gatekeeper warning on other Macs — right-click → Open to bypass, or run `xattr -rd com.apple.quarantine AbletonRPC.app` after downloading.
- Tested on macOS 26 Tahoe with Ableton Live 12.4 Suite and 12.4 Beta. Earlier macOS versions (13–15) should work but have not been tested on this release.
