#!/usr/bin/env python3
"""
AbletonRPC Daemon
Managed by AbletonRPCHelper via SMAppService — no launchd plists needed.
"""

import os
import sys
import time
import json
import signal
import hashlib
import tempfile
import threading
from pathlib import Path

import psutil  # type: ignore
from pypresence import Presence  # type: ignore
from pypresence.utils import get_ipc_path  # type: ignore

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HOME       = Path.home()
CONFIG_DIR = HOME / "Library" / "Application Support" / "AbletonRPC"
INSTALLS_CONFIG = CONFIG_DIR / "installations.json"
DEFAULT_CLIENT_ID = "1283406074824753203"

# ---------------------------------------------------------------------------
# Vesktop / alt-client IPC socket hunter
# ---------------------------------------------------------------------------

def _find_discord_ipc_socket():
    candidate_dirs = []

    for i in range(10):
        try:
            p = get_ipc_path(i)
            if p:
                candidate_dirs.append(os.path.dirname(p))
        except Exception:
            pass

    tmpdir = os.environ.get("TMPDIR", tempfile.gettempdir())
    candidate_dirs.append(tmpdir)

    for pattern in ("snap.discord", "app.vesktop", "vesktop", "discord", "legcord", "webcord"):
        candidate_dirs.append(os.path.join(tmpdir, pattern))

    xdg = os.environ.get("XDG_RUNTIME_DIR", "")
    if xdg:
        candidate_dirs.append(xdg)
        for pattern in ("snap.discord", "app.vesktop", "vesktop", "discord"):
            candidate_dirs.append(os.path.join(xdg, pattern))

    seen, unique_dirs = set(), []
    for d in candidate_dirs:
        if d not in seen:
            seen.add(d)
            unique_dirs.append(d)

    for directory in unique_dirs:
        for i in range(10):
            path = os.path.join(directory, f"discord-ipc-{i}")
            if os.path.exists(path):
                return path

    return None


class BroadPresence(Presence):
    def connect(self):
        try:
            return super().connect()
        except Exception:
            pass

        socket_path = _find_discord_ipc_socket()
        if socket_path is None:
            raise ConnectionError(
                "Could not find a Discord IPC socket. "
                "Make sure Discord / Vesktop is running."
            )

        import pypresence.connection as _conn  # type: ignore
        original_get = _conn.get_ipc_path

        def _patched_get(pipe=0):
            return socket_path

        _conn.get_ipc_path = _patched_get
        try:
            return super().connect()
        finally:
            _conn.get_ipc_path = original_get


# ---------------------------------------------------------------------------
# Installation model
# ---------------------------------------------------------------------------

class AbletonInstallation:
    def __init__(self, name, ableton_path, log_path, client_id=None):
        self.name        = name
        self.ableton_path = ableton_path
        self.log_path    = log_path
        self.client_id   = client_id or DEFAULT_CLIENT_ID
        self.install_hash = hashlib.md5(ableton_path.encode()).hexdigest()[:8]

    @classmethod
    def from_dict(cls, data):
        return cls(
            data["name"],
            data["ableton_path"],
            data["log_path"],
            data.get("client_id", DEFAULT_CLIENT_ID),
        )


def load_installations():
    if not INSTALLS_CONFIG.exists():
        return []
    try:
        with open(INSTALLS_CONFIG) as f:
            data = json.load(f)
        return [AbletonInstallation.from_dict(d) for d in data.get("installations", [])]
    except Exception as e:
        print(f"⚠️  Could not load installations: {e}")
        return []


# ---------------------------------------------------------------------------
# FauxMIDI installer  (called via --install <hash>)
# ---------------------------------------------------------------------------

FAUX_MIDI_TEMPLATE = '''import Live
import os
import traceback
import threading
import time
from _Framework.ControlSurface import ControlSurface

def create_instance(c_instance):
    return FauxMIDI(c_instance)

class FauxMIDI(ControlSurface):
    def __init__(self, c_instance):
        super(FauxMIDI, self).__init__(c_instance)
        self.log_file_path = {LOG_PATH}
        self.debug_log_path = self.log_file_path + ".debug"
        self.installation_name = {INSTALL_NAME}
        self.last_project_name = None
        self.name_check_counter = 0

        try:
            self._debug_log(f"FauxMIDI initializing for {self.installation_name}...")
            self.song = Live.Application.get_application().get_document()
            self._setup_listeners()
            self._debug_log("Listeners setup complete")
            self._start_name_monitor()
            self.log_state()
            self._debug_log("Initial state logged successfully")
        except Exception as e:
            self._debug_log(f"Initialization error: {e}")
            self._debug_log(traceback.format_exc())

    def _debug_log(self, message):
        try:
            import datetime
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            os.makedirs(os.path.dirname(self.debug_log_path), exist_ok=True)
            with open(self.debug_log_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] [{self.installation_name}] {message}\\n")
                f.flush()
                os.fsync(f.fileno())
        except:
            pass

    def _start_name_monitor(self):
        def name_monitor():
            while True:
                try:
                    time.sleep(2)
                    current_name = self._get_enhanced_project_name()
                    if (current_name == "Unsaved Project"
                            and self.last_project_name
                            and self.last_project_name != "Unsaved Project"):
                        continue
                    if current_name != self.last_project_name:
                        self._debug_log(f"Project name changed: \'{self.last_project_name}\' -> \'{current_name}\'")
                        self.last_project_name = current_name
                        self.log_state()
                except Exception as e:
                    self._debug_log(f"Name monitor error: {e}")
                    time.sleep(5)

        threading.Thread(target=name_monitor, daemon=True).start()
        self._debug_log("Background name monitor started")

    def _get_enhanced_project_name(self):
        try:
            raw_name = getattr(self.song, "name", None)
            if raw_name and raw_name.strip():
                name = raw_name[:-4] if raw_name.endswith(".als") else raw_name
                if name:
                    return name
            try:
                if hasattr(self.song, "file_path"):
                    fp = getattr(self.song, "file_path", None)
                    if fp:
                        fn = os.path.basename(fp)
                        if fn.endswith(".als"):
                            return fn[:-4]
            except Exception:
                pass
            return "Unsaved Project"
        except Exception as e:
            self._debug_log(f"Enhanced name detection error: {e}")
            return "Unsaved Project"

    def _setup_listeners(self):
        try:
            if hasattr(self.song, "name_has_listener") and not self.song.name_has_listener(self.log_state):
                self.song.add_name_listener(self.log_state)
            if hasattr(self.song, "tempo_has_listener") and not self.song.tempo_has_listener(self.log_state):
                self.song.add_tempo_listener(self.log_state)
            if hasattr(self.song, "is_playing_has_listener") and not self.song.is_playing_has_listener(self.log_state):
                self.song.add_is_playing_listener(self.log_state)
            if hasattr(self.song, "record_mode_has_listener") and not self.song.record_mode_has_listener(self.log_state):
                self.song.add_record_mode_listener(self.log_state)
        except Exception as e:
            self._debug_log(f"Listener setup error: {e}")

    def log_state(self):
        try:
            project = self._get_enhanced_project_name()
            if (project == "Unsaved Project"
                    and self.last_project_name
                    and self.last_project_name != "Unsaved Project"):
                project = self.last_project_name
        except:
            project = self.last_project_name or "Unsaved Project"

        try:
            tempo = int(getattr(self.song, "tempo", 120))
            is_playing = getattr(self.song, "is_playing", False)
            record_mode = getattr(self.song, "record_mode", False)
            state = "Recording" if record_mode else ("Playing" if is_playing else "Stopped")

            os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
            with open(self.log_file_path, "w", encoding="utf-8") as f:
                f.write(f"PROJECT:{project}\\n")
                f.write(f"TEMPO:{tempo}\\n")
                f.write(f"STATE:{state}\\n")
                f.write(f"INSTALLATION:{self.installation_name}\\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            self._debug_log(f"log_state error: {e}")

    def disconnect(self):
        try:
            self._debug_log("FauxMIDI disconnecting...")
            for remove in ["remove_name_listener", "remove_tempo_listener",
                           "remove_is_playing_listener", "remove_record_mode_listener"]:
                try:
                    if hasattr(self.song, remove):
                        getattr(self.song, remove)(self.log_state)
                except:
                    pass
        except Exception as e:
            self._debug_log(f"Disconnect error: {e}")
        super(FauxMIDI, self).disconnect()
'''


def install_faux_midi(installation):
    base_path = (Path(installation.ableton_path) / "Contents" /
                 "App-Resources" / "MIDI Remote Scripts")
    faux_midi_dir = base_path / "FauxMIDI"

    script = FAUX_MIDI_TEMPLATE.replace("{LOG_PATH}", repr(str(installation.log_path)))
    script = script.replace("{INSTALL_NAME}", repr(installation.name))

    try:
        faux_midi_dir.mkdir(parents=True, exist_ok=True)
        with open(faux_midi_dir / "__init__.py", "w", encoding="utf-8") as f:
            f.write(script)
        print(f"✅ FauxMIDI installed for {installation.name}")
        return True
    except Exception as e:
        print(f"❌ FauxMIDI install failed: {e}")
        return False


def remove_faux_midi(installation):
    import shutil
    faux_midi_dir = (Path(installation.ableton_path) / "Contents" /
                     "App-Resources" / "MIDI Remote Scripts" / "FauxMIDI")
    if faux_midi_dir.exists():
        try:
            shutil.rmtree(faux_midi_dir)
            print(f"✅ FauxMIDI removed from {installation.name}")
        except Exception as e:
            print(f"⚠️  Could not remove FauxMIDI: {e}")


# ---------------------------------------------------------------------------
# Per-installation monitoring app
# ---------------------------------------------------------------------------

class AbletonRPCApp:
    def __init__(self, installation):
        self.installation   = installation
        self.rpc            = None
        self.last_mtime     = 0
        self.last_payload   = None
        self.start_time     = int(time.time())
        self.was_running    = False

    def run(self):
        print(f"🔍 Monitoring: {self.installation.name}")
        while True:
            try:
                self._tick()
            except Exception as e:
                msg = str(e).lower()
                if "pipe" in msg or "closed" in msg:
                    print(f"🔌 [{self.installation.name}] Pipe closed — reconnecting")
                    self.rpc = None
                else:
                    print(f"⚠️  [{self.installation.name}] Loop error: {e}")
                time.sleep(5)

    def _tick(self):
        if not self.rpc:
            try:
                self.rpc = BroadPresence(self.installation.client_id)
                self.rpc.connect()
                print(f"✅ [{self.installation.name}] Connected to Discord")
            except Exception as e:
                print(f"⚠️  [{self.installation.name}] Discord connect failed: {e}")
                time.sleep(10)
                return

        running = self._is_running()

        if running and not self.was_running:
            self.start_time = int(time.time())
            self.was_running = True
            print(f"🎵 [{self.installation.name}] Detected — monitoring started")
        elif not running and self.was_running:
            if self.rpc:
                try:
                    self.rpc.clear()
                except Exception:
                    pass
            print(f"🔇 [{self.installation.name}] Closed — presence cleared")
            self.was_running = False
            time.sleep(5)
            return

        if not running:
            time.sleep(3)
            return

        log_path = self.installation.log_path
        if not os.path.exists(log_path):
            time.sleep(1)
            return

        try:
            mtime = os.path.getmtime(log_path)
        except OSError:
            time.sleep(1)
            return

        if mtime != self.last_mtime:
            self.last_mtime = mtime
            time.sleep(0.2)
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                time.sleep(0.5)
                return

            data = {}
            for line in content.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    data[k.strip()] = v.strip()

            project  = data.get("PROJECT", "Unsaved Project")
            tempo    = data.get("TEMPO", "120")
            state    = data.get("STATE", "Stopped")
            inst_name = data.get("INSTALLATION", self.installation.name)

            payload = (project, tempo, state)
            if payload != self.last_payload and self.rpc:
                self.last_payload = payload
                try:
                    self.rpc.update(
                        state=f"{state} · {tempo} BPM",
                        details=f"{inst_name}: {project}",
                        large_image="ableton_image",
                        start=self.start_time,
                    )
                    print(f"📡 [{inst_name}] {project} | {state} | {tempo} BPM")
                except Exception as e:
                    print(f"⚠️  [{self.installation.name}] RPC update error: {e}")
                    self.rpc = None

        time.sleep(3)

    def _is_running(self):
        try:
            for proc in psutil.process_iter(["name", "exe"]):
                try:
                    name = proc.info["name"] or ""
                    exe  = proc.info.get("exe") or ""
                    if (name == "Live" or "Ableton" in name) and ".app/Contents/MacOS" in exe:
                        app_path = exe.split(".app/Contents/MacOS")[0] + ".app"
                        if app_path == self.installation.ableton_path:
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_daemon():
    installations = load_installations()
    if not installations:
        print("⚠️  No installations configured. Add one via the AbletonRPC app.")
        # Keep running — the config file may appear later
        while True:
            time.sleep(30)
            installations = load_installations()
            if installations:
                break

    print(f"🚀 Starting daemon for {len(installations)} installation(s)")

    threads = []
    for install in installations:
        app = AbletonRPCApp(install)
        t = threading.Thread(target=app.run, daemon=True, name=install.name)
        t.start()
        threads.append(t)

    # Block until all threads finish (they shouldn't unless something goes very wrong)
    for t in threads:
        t.join()


def main():
    args = sys.argv[1:]

    if not args:
        print("Usage:")
        print("  ableton_rpc.py --daemon            Run monitoring daemon")
        print("  ableton_rpc.py --install <hash>    Install FauxMIDI for installation")
        print("  ableton_rpc.py --remove  <hash>    Remove FauxMIDI for installation")
        sys.exit(1)

    if args[0] == "--daemon":
        # Graceful shutdown on SIGTERM
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        run_daemon()

    elif args[0] == "--install" and len(args) >= 2:
        install_hash = args[1]
        installs = load_installations()
        match = next((i for i in installs if i.install_hash == install_hash), None)
        if not match:
            print(f"❌ Installation not found: {install_hash}")
            sys.exit(1)
        success = install_faux_midi(match)
        sys.exit(0 if success else 1)

    elif args[0] == "--remove" and len(args) >= 2:
        install_hash = args[1]
        installs = load_installations()
        match = next((i for i in installs if i.install_hash == install_hash), None)
        if match:
            remove_faux_midi(match)
        sys.exit(0)

    else:
        print(f"Unknown argument: {args[0]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
