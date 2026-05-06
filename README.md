# AbletonRPC

<p align="center">
  <img src="https://i.ibb.co/V9NbLcY/ableton-image-beeg.png" alt="AbletonRPC logo">
</p>

Unofficial Ableton Live Discord rich presence for macOS — now powered by a native Swift app.


### Main GUI

![Main GUI](AbletonRPCGUI.png)

### Setup Flow

![Setup Flow](https://i.ibb.co/5xXj19c/Monosnap-Add-Ableton-Installation-2025-12-25-18-30-21.png)

### MIDI Preferences

![MIDI Preferences](https://i.ibb.co/9pbMpW1/Ableton-MIDIprefs.png)

## Disclaimer

AbletonRPC installs a small MIDI Remote Script (`FauxMIDI`) inside your Ableton Live application bundle. This modification is read-only from Ableton's perspective, does not touch any project files or preferences, and carries no risk of account ban or license revocation. That said, if you are not comfortable with it, stop here. This project is **unofficial** and is not affiliated with Ableton AG in any way.

Do not seek support for AbletonRPC in Ableton's official Discord or support channels.

---

## Requirements

- macOS 13 Ventura or later (tested on macOS 26 Tahoe)
- Ableton Live 11 or later (any edition)
- Discord desktop client (not the web app) — official client or Vesktop both work
- Python 3.10 or later from [python.org](https://www.python.org/downloads/) (not the system Python)

---

## Installation

### Using the pre-built app (recommended)

1. Download the latest release from the [Releases](https://github.com/KiwiSingh/AbletonRPC/releases) page
2. Unzip and move `AbletonRPC.app` to your Applications folder
3. Right-click → Open on first launch to bypass Gatekeeper
4. Click **Add Installation** and follow the setup flow

### Building from source

```bash
git clone https://github.com/KiwiSingh/AbletonRPC
cd AbletonRPC/AbletonRPC-GUI
./build.sh --install
```

`build.sh` handles everything: installs `xcodegen` via Homebrew, generates the Xcode project, builds the app, and copies it to `/Applications`. Xcode must be installed (Command Line Tools alone are not enough).

---

## Setup flow

1. Open AbletonRPC from your Applications folder
2. Click **Add Installation**

   ![Add installation](https://i.ibb.co/N2c18sM2/Monosnap-Ableton-RPC-Multi-Installation-Manager-2025-12-25-18-28-34.png)

3. Give your installation a name, select your Ableton Live `.app` bundle, and choose a location for the log file (can be anywhere — an external drive works fine as long as it's connected when Ableton is running)

   ![Setup flow](https://i.ibb.co/bMvBCbmT/Monosnap-Add-Ableton-Installation-2025-12-25-18-30-21.png)

4. Click **Add Installation** — AbletonRPC installs the FauxMIDI script and registers the background helper automatically
5. Restart Ableton Live, then go to **Preferences → MIDI** and set `FauxMIDI` as a Control Surface

   ![MIDI preferences](https://i.ibb.co/9pbMpW1/Ableton-MIDIprefs.png)

6. Open Discord and start a session in Ableton — your rich presence will update automatically

---

## How it works

```
macOS Login
  ↓
AbletonRPC Helper starts (via LaunchAgent)
  ↓
Helper launches Python daemon with correct environment
  ↓
Daemon reads ~/Library/Application Support/AbletonRPC/installations.json
  ↓
One monitoring thread per Ableton installation
  ↓
FauxMIDI writes project name, tempo, and state to a log file
  ↓
Daemon reads log file → updates Discord Rich Presence via pypresence
```

The helper is a native Swift app that manages the Python daemon's lifecycle — restarting it on crash and ensuring it always runs with the correct environment variables. This replaces the fragile `launchctl` approach used in v1/v2.

---

## Multiple installations

AbletonRPC supports running multiple Ableton versions simultaneously (e.g. Live 11 and Live 12). Each installation gets its own monitoring thread and log file. Discord will always show the version that is actively playing or recording.

---

## CLI usage

For those who prefer running the daemon directly:

```bash
cd AbletonRPC-GUI
pip install pypresence psutil
python3 Resources/ableton_rpc.py --daemon
```

The daemon reads from `~/Library/Application Support/AbletonRPC/installations.json`. Add installations via the GUI first, then run the daemon from the CLI if preferred.

---

## Vesktop / alt-client support

AbletonRPC includes a custom IPC socket hunter (`BroadPresence`) that searches non-standard socket locations used by Vesktop, Legcord, WebCord, and other alternative Discord clients — in addition to the standard locations used by the official client.

---

## Frequently asked questions

**Q. Is this a port of [DAWRPC](https://github.com/Serena1432/DAWRPC)?**

No. Completely independent project built from scratch for macOS.

---

**Q. Will this mess up my Ableton installation?**

No. AbletonRPC only adds a `FauxMIDI` folder to Ableton's MIDI Remote Scripts directory. It does not modify any existing files. Removing the installation via the GUI cleans it up completely.

---

**Q. Will this affect my existing MIDI controllers or mappings?**

No. FauxMIDI is a passive observer — it only reads song state. It does not send or receive MIDI data and does not interfere with Push, MPK Mini, AKAI Fire, or any other controller.

---

**Q. My art assets aren't showing in Discord rich presence.**

Discord takes 10–60 minutes to propagate newly uploaded assets from the Developer Portal. Don't re-upload — just wait.

---

**Q. The presence stopped working after I updated Ableton.**

Ableton updates sometimes replace the MIDI Remote Scripts folder. Open the AbletonRPC GUI, remove the installation, and add it again to reinstall FauxMIDI.

---

**Q. I upgraded Ableton via Rent-to-Own and the presence broke.**

Same fix as above — remove and re-add the installation in the GUI.

---

**Q. What Python version do I need?**

Python 3.10 or later from [python.org](https://www.python.org/downloads/). The system Python (`/usr/bin/python3`) that ships with macOS is too old and has a broken Tk version. AbletonRPC will use `/usr/local/bin/python3` by default.

---

**Q. Is this safe to use with Vesktop?**

Yes. See [Vesktop / alt-client support](#vesktop--alt-client-support) above.

---

**Q. Have you tested this with the latest Ableton version?**

Yes — tested with Ableton Live 12.4 Suite on macOS 26 Tahoe.

---

**Q. Can I use my own Discord application / client ID?**

Yes. When adding an installation, replace the pre-filled Client ID with your own from the [Discord Developer Portal](https://discord.com/developers/applications). Make sure to upload your art assets there too.

---

**Q. Where can I reach you?**

Email: [kiwisingh@proton.me](mailto:kiwisingh@proton.me)  
Discord: `char1ot33r`
