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
            self.song     = Live.Application.get_application().get_document()
            self.app_view = Live.Application.get_application().view
            # Cached state — updated by listeners on main thread, read by background thread
            self._loop_on      = bool(getattr(self.song, "loop", False))
            self._is_session   = False
            self._scene_name   = None
            self._time_sig     = None
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
        # All variants Ableton may return for an unsaved/unnamed project
        UNTITLED = {"Unsaved Project", "Untitled Project", "Untitled", ""}

        def name_monitor():
            while True:
                try:
                    time.sleep(2)
                    current_name = self._get_enhanced_project_name()

                    # Never overwrite a real project name with any untitled variant
                    if (current_name in UNTITLED
                            and self.last_project_name
                            and self.last_project_name not in UNTITLED):
                        continue

                    if current_name != self.last_project_name:
                        self._debug_log(f"Project name changed: '{self.last_project_name}' -> '{current_name}'")
                        self.last_project_name = current_name
                        self.log_state()

                except Exception as e:
                    err = str(e)
                    # self.song C++ object has been invalidated — this instance is dead
                    if "TPyHandle" in err or "did not match C++ signature" in err:
                        self._debug_log("Song reference invalidated — stopping name monitor")
                        return
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

    def _on_loop_changed(self):
        new_val = bool(getattr(self.song, "loop", False))
        if new_val != self._loop_on:
            self._loop_on = new_val
            self._debug_log(f"Loop changed: {self._loop_on}")
            self.log_state()

    def _on_view_changed(self):
        focused = getattr(self.app_view, "focused_document_view", "")
        new_is_session = (focused == "Session")
        if new_is_session != self._is_session:
            self._is_session = new_is_session
            self._debug_log(f"View changed: focused_document_view={repr(focused)} is_session={self._is_session}")
            self._update_scene()
            self.log_state()
        else:
            # Same view — seed _is_session silently on init without spamming log_state
            self._is_session = new_is_session

    def _on_scene_changed(self):
        self._update_scene()
        self.log_state()

    def _on_time_sig_changed(self):
        self._time_sig = self._get_time_sig()
        self.log_state()

    def _update_scene(self):
        try:
            scene = getattr(self.song.view, "selected_scene", None)
            if scene is not None:
                name = getattr(scene, "name", None)
                self._scene_name = name.strip() if name and name.strip() else None
            else:
                self._scene_name = None
        except Exception as e:
            self._debug_log(f"Scene update error: {e}")
            self._scene_name = None

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
            # Key listeners (v3.3+)
            try:
                if hasattr(self.song, "root_note_has_listener") and not self.song.root_note_has_listener(self.log_state):
                    self.song.add_root_note_listener(self.log_state)
                if hasattr(self.song, "scale_name_has_listener") and not self.song.scale_name_has_listener(self.log_state):
                    self.song.add_scale_name_listener(self.log_state)
            except Exception as e:
                self._debug_log(f"Key listeners skipped: {e}")
            # v4.0 — loop, time sig, session record with dedicated callbacks (main thread safe)
            try:
                if hasattr(self.song, "loop_has_listener") and not self.song.loop_has_listener(self._on_loop_changed):
                    self.song.add_loop_listener(self._on_loop_changed)
                if hasattr(self.song, "signature_numerator_has_listener") and not self.song.signature_numerator_has_listener(self._on_time_sig_changed):
                    self.song.add_signature_numerator_listener(self._on_time_sig_changed)
                if hasattr(self.song, "signature_denominator_has_listener") and not self.song.signature_denominator_has_listener(self._on_time_sig_changed):
                    self.song.add_signature_denominator_listener(self._on_time_sig_changed)
                if hasattr(self.song, "session_record_has_listener") and not self.song.session_record_has_listener(self.log_state):
                    self.song.add_session_record_listener(self.log_state)
            except Exception as e:
                self._debug_log(f"v4.0 song listeners skipped: {e}")
            # v4.0 — view, scene, track/device with dedicated callbacks
            try:
                view = self.song.view
                if hasattr(self.app_view, "focused_document_view_has_listener") and not self.app_view.focused_document_view_has_listener(self._on_view_changed):
                    self.app_view.add_focused_document_view_listener(self._on_view_changed)
                if hasattr(view, "selected_scene_has_listener") and not view.selected_scene_has_listener(self._on_scene_changed):
                    view.add_selected_scene_listener(self._on_scene_changed)
                if hasattr(view, "selected_track_has_listener") and not view.selected_track_has_listener(self.log_state):
                    view.add_selected_track_listener(self.log_state)
                if hasattr(view, "selected_device_has_listener") and not view.selected_device_has_listener(self.log_state):
                    view.add_selected_device_listener(self.log_state)
            except Exception as e:
                self._debug_log(f"v4.0 view listeners skipped: {e}")
            # Seed initial cached values on main thread
            self._on_view_changed()
            self._on_time_sig_changed()
        except Exception as e:
            self._debug_log(f"Listener setup error: {e}")

    def _get_key(self):
        """Return a human-readable key string e.g. 'C# Minor', or None if unavailable."""
        NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F",
                      "F#", "G", "G#", "A", "A#", "B"]
        try:
            root = getattr(self.song, "root_note", None)
            scale = getattr(self.song, "scale_name", None)
            if root is None:
                return None
            note = NOTE_NAMES[int(root) % 12]
            if scale:
                return f"{note} {scale}"
            return note
        except Exception as e:
            self._debug_log(f"Key detection error: {e}")
            return None

    def _get_time_sig(self):
        """Return time signature string e.g. '7/8', or None."""
        try:
            num = getattr(self.song, "signature_numerator", None)
            den = getattr(self.song, "signature_denominator", None)
            if num is not None and den is not None:
                return f"{int(num)}/{int(den)}"
            return None
        except Exception as e:
            self._debug_log(f"Time sig error: {e}")
            return None

    def _get_scene_and_view(self):
        """Read from cached instance vars updated by main-thread listeners."""
        return self._scene_name, self._is_session

    def _get_recording_status(self):
        """Return detailed recording status — distinguishes arrangement vs clip recording."""
        try:
            record_mode    = getattr(self.song, "record_mode", False)      # arrangement record
            session_record = getattr(self.song, "session_record", False)   # clip/session record
            is_playing     = getattr(self.song, "is_playing", False)
            if session_record:
                return "Clip Recording"
            if record_mode:
                return "Recording"
            if is_playing:
                return "Playing"
            return "Stopped"
        except Exception as e:
            self._debug_log(f"Recording status error: {e}")
            return "Stopped"

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
            tempo    = int(getattr(self.song, "tempo", 120))
            state    = self._get_recording_status()
            loop_on  = self._loop_on  # cached by _on_loop_changed listener on main thread

            track_name, track_type, device_name = self._get_track_info()
            key       = self._get_key()
            time_sig  = self._time_sig  # cached by _on_time_sig_changed listener on main thread
            scene_name, is_session = self._get_scene_and_view()  # reads cached _scene_name, _is_session

            os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
            with open(self.log_file_path, "w", encoding="utf-8") as f:
                f.write(f"PROJECT:{project}\\n")
                f.write(f"TEMPO:{tempo}\\n")
                f.write(f"STATE:{state}\\n")
                f.write(f"INSTALLATION:{self.installation_name}\\n")
                f.write(f"LOOP:{'1' if loop_on else '0'}\\n")
                f.write(f"VIEW:{'Session' if is_session else 'Arrangement'}\\n")
                if key:
                    f.write(f"KEY:{key}\\n")
                if time_sig:
                    f.write(f"TIME_SIG:{time_sig}\\n")
                if scene_name:
                    f.write(f"SCENE:{scene_name}\\n")
                if track_name:
                    f.write(f"TRACK:{track_name}\\n")
                if track_type:
                    f.write(f"TRACK_TYPE:{track_type}\\n")
                if device_name:
                    f.write(f"DEVICE:{device_name}\\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            self._debug_log(f"log_state error: {e}")

    def _get_track_info(self):
        """Return (track_name, track_type, device_name) for the currently selected track.

        Device selection priority (v3.2.0):
          - 0 devices  → None
          - 1 device   → show it regardless of type
          - 2 devices  → show the LAST one (first is usually the instrument, e.g. Serum)
          - 3+ devices → show the currently focused device (user has explicitly selected something)
        Device type codes: 0=AudioEffect, 1=Instrument, 2=MIDIEffect
        """
        try:
            view  = self.song.view
            track = getattr(view, "selected_track", None)
            if track is None:
                return None, None, None

            track_name = getattr(track, "name", None) or None

            # Determine track type
            track_type = None
            try:
                if getattr(track, "has_midi_input", False):
                    track_type = "MIDI"
                elif getattr(track, "has_audio_input", False):
                    track_type = "Audio"
            except Exception:
                pass

            # Smart device selection
            device_name = None
            try:
                devices = list(getattr(track, "devices", []))
                count   = len(devices)

                if count == 0:
                    chosen = None
                elif count == 1:
                    chosen = devices[0]
                elif count == 2:
                    # First slot is almost always the instrument — show the last one
                    chosen = devices[-1]
                else:
                    # 3+ devices: show whatever the user has focused
                    track_view      = getattr(track, "view", None)
                    selected_device = getattr(track_view, "selected_device", None) if track_view else None
                    if selected_device is None:
                        selected_device = getattr(view, "selected_device", None)
                    # If nothing is explicitly focused, fall back to last non-instrument device
                    if selected_device is None:
                        effects = [d for d in devices if getattr(d, "type", -1) != 1]
                        chosen  = effects[-1] if effects else devices[-1]
                    else:
                        chosen = selected_device

                if chosen is not None:
                    device_name = getattr(chosen, "name", None) or None
            except Exception as e:
                self._debug_log(f"Device selection error: {e}")

            return track_name, track_type, device_name
        except Exception as e:
            self._debug_log(f"Track info error: {e}")
            return None, None, None

    def disconnect(self):
        try:
            self._debug_log("FauxMIDI disconnecting...")
            for attr, cb in [
                ("remove_name_listener", self.log_state),
                ("remove_tempo_listener", self.log_state),
                ("remove_is_playing_listener", self.log_state),
                ("remove_record_mode_listener", self.log_state),
                ("remove_root_note_listener", self.log_state),
                ("remove_scale_name_listener", self.log_state),
                ("remove_loop_listener", self._on_loop_changed),
                ("remove_signature_numerator_listener", self._on_time_sig_changed),
                ("remove_signature_denominator_listener", self._on_time_sig_changed),
                ("remove_session_record_listener", self.log_state),
            ]:
                try:
                    if hasattr(self.song, attr):
                        getattr(self.song, attr)(cb)
                except:
                    pass
            try:
                if hasattr(self.app_view, "remove_focused_document_view_listener"):
                    self.app_view.remove_focused_document_view_listener(self._on_view_changed)
                view = self.song.view
                for attr, cb in [
                    ("remove_selected_track_listener", self.log_state),
                    ("remove_selected_device_listener", self.log_state),
                    ("remove_selected_scene_listener", self._on_scene_changed),
                ]:
                    try:
                        if hasattr(view, attr):
                            getattr(view, attr)(cb)
                    except:
                        pass
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
# Discord presence coordinator
# ---------------------------------------------------------------------------
# Multiple daemons (one per installation) share a single Discord connection
# slot. A JSON lock file decides who owns it:
#   Recording > Playing > Stopped
# Each daemon refreshes the lock every tick while active. If the owner goes
# silent for > LOCK_TTL seconds, any other active daemon can steal it.

LOCK_FILE  = CONFIG_DIR / "discord_owner.json"
LOCK_TTL   = 12   # seconds before a stale lock can be stolen

PRIORITY = {"Recording": 2, "Playing": 1, "Stopped": 0}


def _read_lock():
    try:
        with open(LOCK_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _write_lock(install_hash: str, state: str):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(LOCK_FILE, "w") as f:
            json.dump({
                "owner": install_hash,
                "state": state,
                "ts":    time.time(),
            }, f)
    except Exception:
        pass


def _release_lock(install_hash: str):
    lock = _read_lock()
    if lock.get("owner") == install_hash:
        try:
            LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            pass


def _try_acquire_lock(install_hash: str, state: str) -> bool:
    """Return True if this daemon should own the Discord presence."""
    lock = _read_lock()
    owner     = lock.get("owner")
    own_state = lock.get("state", "Stopped")
    ts        = lock.get("ts", 0)

    if not owner:                                        # nobody owns it
        _write_lock(install_hash, state)
        return True
    if owner == install_hash:                            # we already own it
        _write_lock(install_hash, state)
        return True
    if time.time() - ts > LOCK_TTL:                     # owner went silent
        _write_lock(install_hash, state)
        return True
    if PRIORITY.get(state, 0) > PRIORITY.get(own_state, 0):  # higher priority
        _write_lock(install_hash, state)
        return True
    return False


# ---------------------------------------------------------------------------
# Per-installation monitoring daemon
# ---------------------------------------------------------------------------

class AbletonRPCApp:
    def __init__(self, installation):
        self.installation      = installation
        self.rpc               = None
        self.last_mtime        = 0
        self.last_content_hash = ""
        self.last_payload      = None
        self.start_time        = int(time.time())
        self.was_running       = False
        self.owns_lock         = False

    def run(self):
        print(f"🔍 [{self.installation.name}] Daemon started (PID {os.getpid()})")
        while True:
            try:
                self._tick()
            except Exception as e:
                msg = str(e).lower()
                if "pipe" in msg or "closed" in msg:
                    print(f"🔌 [{self.installation.name}] Pipe closed — reconnecting")
                    self.rpc = None
                    self.owns_lock = False
                else:
                    print(f"⚠️  [{self.installation.name}] Loop error: {e}")
                time.sleep(5)

    def _connect(self):
        try:
            self.rpc = BroadPresence(self.installation.client_id)
            self.rpc.connect()
            print(f"✅ [{self.installation.name}] Connected to Discord")
            return True
        except Exception as e:
            print(f"⚠️  [{self.installation.name}] Discord connect failed: {e}")
            self.rpc = None
            return False

    def _tick(self):
        if not self.rpc:
            if not self._connect():
                time.sleep(10)
                return

        running = self._is_running()

        if running and not self.was_running:
            self.start_time  = int(time.time())
            self.was_running = True
            print(f"🎵 [{self.installation.name}] Detected — monitoring started")

        elif not running and self.was_running:
            self.was_running = False
            if self.owns_lock:
                self.owns_lock = False
                _release_lock(self.installation.install_hash)
                try:
                    self.rpc.clear()
                except Exception:
                    pass
            print(f"🔇 [{self.installation.name}] Closed — presence cleared")
            time.sleep(5)
            return

        if not running:
            time.sleep(3)
            return

        # ── Read log file ──────────────────────────────────────────────────
        log_path = self.installation.log_path
        if not os.path.exists(log_path):
            time.sleep(1)
            return

        try:
            mtime = os.path.getmtime(log_path)
        except OSError:
            time.sleep(1)
            return

        # Read file and hash content — mtime alone has 1s precision on HFS+
        # which causes missed updates when a single listener write happens
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            time.sleep(0.5)
            return

        import hashlib as _hl
        content_hash = _hl.md5(content.encode()).hexdigest()

        if mtime == self.last_mtime and content_hash == self.last_content_hash:
            # No change — refresh lock while active
            if self.owns_lock:
                lock = _read_lock()
                if lock.get("owner") == self.installation.install_hash:
                    _write_lock(self.installation.install_hash,
                                lock.get("state", "Stopped"))
            time.sleep(1)
            return

        self.last_mtime        = mtime
        self.last_content_hash = content_hash

        data = {}
        for line in content.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip()

        project    = data.get("PROJECT", "Unsaved Project")
        tempo      = data.get("TEMPO", "120")
        state      = data.get("STATE", "Stopped")
        inst_name  = data.get("INSTALLATION", self.installation.name)
        key        = data.get("KEY")
        time_sig   = data.get("TIME_SIG")
        scene      = data.get("SCENE")
        track      = data.get("TRACK")
        track_type = data.get("TRACK_TYPE")
        device     = data.get("DEVICE")
        loop_on    = data.get("LOOP") == "1"
        view       = data.get("VIEW", "Arrangement")

        # ── Acquire or check lock ──────────────────────────────────────────
        self.owns_lock = _try_acquire_lock(self.installation.install_hash, state)
        if not self.owns_lock:
            time.sleep(1)
            return

        payload = (project, tempo, state, key, time_sig, scene, track, device, loop_on, view)
        if payload == self.last_payload:
            time.sleep(1)
            return
        self.last_payload = payload

        # ── Build presence strings ─────────────────────────────────────────
        try:
            def smart_truncate(text, limit):
                """Truncate at a word boundary with ellipsis."""
                if len(text) <= limit:
                    return text
                truncated = text[:limit - 1].rsplit(" ", 1)[0]
                return truncated + "…"

            # details line: "My Project — Kick Drum [MIDI]"
            if track:
                type_tag = f" [{track_type}]" if track_type else ""
                details  = f"{project} — {track}{type_tag}"
            else:
                details  = project
            details = smart_truncate(details, 128)

            # state line: "Playing · 120 BPM · C# Minor · Compressor"
            state_str = f"{state} · {tempo} BPM"
            if key:
                state_str += f" · {key}"
            if device:
                state_str += f" · {device}"
            state_str = smart_truncate(state_str, 128)

            # large_text tooltip (hover over album art):
            # "Session View · Verse 2 · 7/8"  or "Arrangement View · 7/8"
            tooltip_parts = [f"{view} View"]
            if scene:
                tooltip_parts.append(scene)
            if time_sig:
                tooltip_parts.append(time_sig)
            large_tooltip = " · ".join(tooltip_parts)

            # small_image: loop indicator (requires loop_on/loop_off assets uploaded to Discord Portal)
            small_img  = "loop_on"  if loop_on else "loop_off"
            small_text = "Loop active" if loop_on else "Loop off"

            update_kwargs = dict(
                state=state_str,
                details=details,
                large_image="ableton_image",
                large_text=large_tooltip,
                small_image=small_img,
                small_text=small_text,
                start=self.start_time,
            )

            try:
                self.rpc.update(**update_kwargs)
            except Exception:
                # small_image asset probably not uploaded yet — retry without it
                update_kwargs.pop("small_image", None)
                update_kwargs.pop("small_text", None)
                self.rpc.update(**update_kwargs)

            key_info    = f" | {key}" if key else ""
            track_info  = f" | {track}" if track else ""
            device_info = f" → {device}" if device else ""
            loop_info   = " 🔁" if loop_on else ""
            scene_info  = f" | {scene}" if scene else ""
            print(f"📡 [{inst_name}] {project}{key_info}{track_info}{device_info}{scene_info}{loop_info} | {state} | {tempo} BPM | {view}")
        except Exception as e:
            print(f"⚠️  [{self.installation.name}] RPC update error: {e}")
            self.rpc      = None
            self.owns_lock = False

        time.sleep(1)

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

def run_daemon(install_hash: str):
    """Run the daemon for a single installation identified by install_hash."""
    import fcntl
    lock_path = CONFIG_DIR / f"daemon-{install_hash}.lock"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # PID-aware locking: if a lockfile exists, check if that PID is still alive.
    # If the process is dead (stale lock), kill it and take over.
    # If it's alive and IS us somehow, proceed. Otherwise exit.
    if lock_path.exists():
        try:
            existing_pid = int(lock_path.read_text().strip())
            if existing_pid != os.getpid():
                try:
                    os.kill(existing_pid, 0)  # Check if process exists
                    # Process is alive — is it actually our script?
                    proc = psutil.Process(existing_pid)
                    cmdline = " ".join(proc.cmdline())
                    if install_hash in cmdline and "ableton_rpc" in cmdline:
                        print(f"⚠️  Daemon for {install_hash} already running (PID {existing_pid}) — exiting")
                        sys.exit(0)
                    else:
                        # Different process somehow got our PID slot — steal it
                        print(f"🔄 Stale lock for {install_hash} (PID {existing_pid} is unrelated) — taking over")
                except (ProcessLookupError, psutil.NoSuchProcess):
                    # Process is dead — stale lock, take over
                    print(f"🔄 Clearing stale lock for {install_hash} (PID {existing_pid} is dead)")
        except (ValueError, OSError):
            pass  # Unreadable lockfile — proceed

    # Acquire the lock
    try:
        lock_fd = open(lock_path, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
    except (IOError, OSError):
        print(f"⚠️  Could not acquire lock for {install_hash} — another instance just started")
        sys.exit(0)

    # Load the specific installation
    installations = load_installations()
    installation  = next((i for i in installations if i.install_hash == install_hash), None)

    if not installation:
        print(f"❌ Installation not found: {install_hash}")
        sys.exit(1)

    app = AbletonRPCApp(installation)
    app.run()   # blocks forever


def main():
    args = sys.argv[1:]

    if not args:
        print("Usage:")
        print("  ableton_rpc.py --daemon <hash>     Run daemon for one installation")
        print("  ableton_rpc.py --install <hash>    Install FauxMIDI")
        print("  ableton_rpc.py --remove  <hash>    Remove FauxMIDI")
        sys.exit(1)

    if args[0] == "--daemon" and len(args) >= 2:
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        run_daemon(args[1])

    elif args[0] == "--install" and len(args) >= 2:
        installs = load_installations()
        match = next((i for i in installs if i.install_hash == args[1]), None)
        if not match:
            print(f"❌ Installation not found: {args[1]}")
            sys.exit(1)
        sys.exit(0 if install_faux_midi(match) else 1)

    elif args[0] == "--remove" and len(args) >= 2:
        installs = load_installations()
        match = next((i for i in installs if i.install_hash == args[1]), None)
        if match:
            remove_faux_midi(match)
        sys.exit(0)

    else:
        print(f"Unknown arguments: {args}")
        sys.exit(1)


if __name__ == "__main__":
    main()
