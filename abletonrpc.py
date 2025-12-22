import os
import time
from pypresence import Presence  # type: ignore
import psutil  # type: ignore
import threading

# --- CONFIGURATION ---
temp_file_path = "/Volumes/Charidrive/rpctemp/CurrentProjectLog.txt" # Replace with a desired path on your own machine
client_id = "CLIENT_ID_HERE" # Replace with your own Discord Application Client ID

# --- CONNECT RPC ---
RPC = Presence(client_id)
try:
    RPC.connect()
    print("RPC Connected.")
except Exception as e:
    print(f"RPC Connection Error: {e}")

# --- STRICT PROCESS CHECK ---
def is_ableton_running():
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name']:
                # macOS strict match
                if proc.info['name'] == 'Live':
                    return True
                # Windows strict match
                if proc.info['name'].startswith('Ableton Live'):
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

def clear_log_file():
    try:
        with open(temp_file_path, "w", encoding="utf-8") as file:
            file.write("Current Project Name: \n")
        print("Log file cleared (New session detected).")
    except Exception as e:
        print(f"Error clearing log: {e}")

# --- INITIALIZATION FIX ---
# Check status immediately so we don't wipe data if Ableton is already open
ableton_was_running = is_ableton_running()

if ableton_was_running:
    print("Ableton is ALREADY running. preserving existing log file.")
else:
    print("Ableton is NOT running. Clearing log file.")
    clear_log_file()

# Variable defaults
last_modified_time = 0
last_project_name = None
start_time = int(time.time())
broadcasting = True 

# --- THREADING ---
def toggle_broadcast():
    global broadcasting
    while True:
        user_input = input()
        if user_input.lower() == 'toggle':
            broadcasting = not broadcasting
            state = "enabled" if broadcasting else "disabled"
            print(f"Rich Presence {state}.")
            if not broadcasting:
                RPC.clear()

threading.Thread(target=toggle_broadcast, daemon=True).start()

print("Monitoring loop started...")

# --- MAIN LOOP ---
while True:
    try:
        currently_running = is_ableton_running()
        
        # 1. HANDLE STATE CHANGES
        if currently_running and not ableton_was_running:
            # Ableton JUST started (Transition Off -> On)
            print("Ableton launch detected.")
            # We clear the file here because it's a fresh boot, previous data is stale
            clear_log_file()
            last_project_name = None
            start_time = int(time.time())
            ableton_was_running = True

        elif not currently_running and ableton_was_running:
            # Ableton JUST closed (Transition On -> Off)
            print("Ableton closed.")
            RPC.clear()
            ableton_was_running = False
            time.sleep(5)
            continue
        
        # If Ableton is not running at all, just wait
        if not currently_running:
            time.sleep(5)
            continue

        # 2. READ FILE
        if not os.path.exists(temp_file_path):
            time.sleep(1)
            continue

        try:
            file_mtime = os.path.getmtime(temp_file_path)
        except OSError:
            continue

        # Check if file updated OR if we just started the script (initial read)
        # We add 'last_project_name is None' to force a read on script startup
        if file_mtime != last_modified_time or last_project_name is None:
            last_modified_time = file_mtime
            time.sleep(0.1) # Debounce write

            try:
                with open(temp_file_path, "r", encoding="utf-8") as file:
                    content = file.read().strip()
            except Exception:
                continue

            # Extract Name
            new_project_name = ""
            if "Current Project Name:" in content:
                parts = content.split("Current Project Name:")
                if len(parts) > 1:
                    new_project_name = parts[1].strip()

            print(f"Read from file: '{new_project_name}'")

            # Update RPC if Changed
            if new_project_name != last_project_name:
                last_project_name = new_project_name
                
                # Only reset timer if the name actually changed to something valid
                if new_project_name:
                    start_time = int(time.time())

                if broadcasting:
                    if new_project_name:
                        RPC.update(
                            state="Working on a project",
                            details=new_project_name,
                            large_image="ableton_image",
                            large_text="Ableton Live",
                            start=start_time
                        )
                    else:
                        RPC.update(
                            state="Not working on a project",
                            details="Cooking up new music",
                            large_image="ableton_image",
                            large_text="Ableton Live"
                        )
        
        time.sleep(1)

    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f"Loop Error: {e}")
        time.sleep(5)