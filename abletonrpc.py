import os
import time
import threading
import glob
import tempfile
import psutil  # type: ignore
from pypresence import Presence  # type: ignore
from pypresence.utils import get_ipc_path  # type: ignore

# ---------------------------------------------------------------------------
# Vesktop / alternative Discord client IPC socket hunter
# ---------------------------------------------------------------------------
# pypresence only searches $TMPDIR and /tmp for discord-ipc-{0..9}.
# Vesktop (and WebCord, Legcord, etc.) on macOS places its socket in a
# non-standard location that pypresence misses.  We override get_ipc_path
# inside a thin Presence subclass so the rest of the code is unaffected.

def _find_discord_ipc_socket():
    """
    Return the first usable Discord IPC socket path, checking every location
    that stock Discord, Vesktop, and other alt-clients are known to use on macOS.
    Returns None if nothing is found.
    """
    candidate_dirs = []

    # 1. pypresence's own default logic (handles $TMPDIR / /tmp for stock Discord)
    for i in range(10):
        try:
            p = get_ipc_path(i)
            if p:
                candidate_dirs.append(os.path.dirname(p))
        except Exception:
            pass

    # 2. macOS $TMPDIR (often /var/folders/.../T/)
    tmpdir = os.environ.get("TMPDIR", tempfile.gettempdir())
    candidate_dirs.append(tmpdir)

    # 3. Vesktop on macOS writes its socket into a snap-style subdirectory
    #    inside $TMPDIR, e.g. $TMPDIR/snap.discord/ or $TMPDIR/app.vesktop/
    for pattern in ("snap.discord", "app.vesktop", "vesktop", "discord", "legcord", "webcord"):
        candidate_dirs.append(os.path.join(tmpdir, pattern))

    # 4. XDG_RUNTIME_DIR (Linux / some Vesktop builds)
    xdg = os.environ.get("XDG_RUNTIME_DIR", "")
    if xdg:
        candidate_dirs.append(xdg)
        for pattern in ("snap.discord", "app.vesktop", "vesktop", "discord"):
            candidate_dirs.append(os.path.join(xdg, pattern))

    # Deduplicate while preserving order
    seen = set()
    unique_dirs = []
    for d in candidate_dirs:
        if d not in seen:
            seen.add(d)
            unique_dirs.append(d)

    # Search each directory for discord-ipc-0 ... discord-ipc-9
    for directory in unique_dirs:
        for i in range(10):
            path = os.path.join(directory, f"discord-ipc-{i}")
            if os.path.exists(path):
                return path

    return None


class BroadPresence(Presence):
    """
    Presence subclass that falls back to a broad IPC socket search so it works
    with Vesktop, Legcord, WebCord, and stock Discord on macOS.
    """

    def connect(self):
        # Let pypresence try its normal path first
        try:
            return super().connect()
        except Exception:
            pass

        # Primary failed - try our extended search
        socket_path = _find_discord_ipc_socket()
        if socket_path is None:
            raise ConnectionError(
                "Could not find a Discord IPC socket. "
                "Make sure Discord / Vesktop is running."
            )

        # Monkey-patch the pipe path pypresence will use and retry
        import pypresence.connection as _conn  # type: ignore
        original_get = _conn.get_ipc_path

        def _patched_get(pipe=0):
            return socket_path

        _conn.get_ipc_path = _patched_get
        try:
            return super().connect()
        finally:
            _conn.get_ipc_path = original_get

# --- CONFIGURATION ---
temp_file_path = "/Volumes/Charidrive/rpctemp/CurrentProjectLog.txt"
client_id = "CLIENT_ID_HERE"

# --- CONNECT RPC ---
def connect_rpc():
    try:
        rpc = BroadPresence(client_id)
        rpc.connect()
        print("RPC Connected.")
        return rpc
    except Exception as e:
        print(f"RPC Connection Error: {e}")
        return None

RPC = connect_rpc()

# --- STRICT PROCESS CHECK ---
def is_ableton_running():
    for proc in psutil.process_iter(['name']):
        try:
            name = proc.info['name']
            if not name:
                continue
            if name == 'Live':
                return True
            if name.startswith('Ableton Live'):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def clear_log_file():
    try:
        with open(temp_file_path, "w", encoding="utf-8", buffering=1) as file:
            file.write("")
        print("Log file cleared.")
    except Exception as e:
        print(f"Error clearing log: {e}")


# --- INITIALIZATION ---
ableton_was_running = is_ableton_running()

if ableton_was_running:
    print("Ableton already running — preserving log.")
else:
    print("Ableton not running — clearing log.")
    clear_log_file()

last_modified_time = 0
last_payload = None
start_time = int(time.time())
broadcasting = True


# --- TOGGLE THREAD ---
def toggle_broadcast():
    global broadcasting, RPC
    while True:
        user_input = input()
        if user_input.lower() == "toggle":
            broadcasting = not broadcasting
            state = "enabled" if broadcasting else "disabled"
            print(f"Rich Presence {state}.")
            if not broadcasting and RPC:
                RPC.clear()

threading.Thread(target=toggle_broadcast, daemon=True).start()

print("Monitoring loop started...")


# --- SAFE FILE READ ---
def safe_read_file(path):
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        # File replaced mid-read
        time.sleep(0.2)
        return None


# --- MAIN LOOP ---
while True:
    try:
        if RPC is None:
            RPC = connect_rpc()
            time.sleep(3)
            continue

        currently_running = is_ableton_running()

        # --- STATE TRANSITIONS ---
        if currently_running and not ableton_was_running:
            print("Ableton launch detected.")
            clear_log_file()
            start_time = int(time.time())
            ableton_was_running = True

        elif not currently_running and ableton_was_running:
            print("Ableton closed.")
            if RPC:
                RPC.clear()
            ableton_was_running = False
            time.sleep(5)
            continue

        if not currently_running:
            time.sleep(5)
            continue

        # --- READ FILE SAFELY ---
        try:
            file_mtime = os.path.getmtime(temp_file_path)
        except OSError:
            time.sleep(1)
            continue

        if file_mtime != last_modified_time:
            last_modified_time = file_mtime
            time.sleep(0.2)

            content = safe_read_file(temp_file_path)
            if not content:
                continue

            content = content.strip()

            project = "Unsaved Project"
            tempo = None
            state = None

            # --- Support structured format ---
            lines = content.splitlines()
            data = {}

            for line in lines:
                if ":" in line:
                    k, v = line.split(":", 1)
                    data[k.strip()] = v.strip()

            if "PROJECT" in data:
                project = data.get("PROJECT", project)
                tempo = data.get("TEMPO")
                state = data.get("STATE")
            else:
                # Fallback to old format
                if "Current Project Name:" in content:
                    parts = content.split("Current Project Name:")
                    if len(parts) > 1:
                        project = parts[1].strip()

            payload = (project, tempo, state)

            if payload != last_payload:
                last_payload = payload

                if broadcasting and RPC:
                    try:
                        if tempo and state:
                            RPC.update(
                                state=f"{state} · {tempo} BPM",
                                details=project,
                                large_image="ableton_image",
                                large_text="Ableton Live",
                                start=start_time
                            )
                        else:
                            RPC.update(
                                state="Working on a project",
                                details=project,
                                large_image="ableton_image",
                                large_text="Ableton Live",
                                start=start_time
                            )

                        print(f"Updated Discord → {project}")

                    except Exception as e:
                        print(f"RPC update error: {e}")
                        RPC = None  # Force reconnect

        time.sleep(1)

    except KeyboardInterrupt:
        break

    except Exception as e:
        print(f"Loop error: {e}")
        time.sleep(3)