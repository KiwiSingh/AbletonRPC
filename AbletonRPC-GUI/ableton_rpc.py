import os
import sys
import time
import psutil # type: ignore
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from pypresence import Presence # type: ignore
import subprocess
import shutil

# --- GLOBAL SETTINGS ---
DEFAULT_CLIENT_ID = "1283406074824753203" 
HOME = os.environ.get("HOME", str(Path.home()))
CONFIG_DIR = Path(HOME) / ".config" / "ableton-discord-rpc"
CONFIG_FILE = CONFIG_DIR / "config.txt"
PLIST_PATH = Path(HOME) / "Library" / "LaunchAgents" / "com.user.ableton-rpc.plist"

class AbletonRPCApp:
    def __init__(self, client_id="", log_path="", ableton_path=""):
        self.client_id = client_id or DEFAULT_CLIENT_ID
        self.temp_file_path = log_path
        self.ableton_path = ableton_path
        self.rpc = None
        self.last_modified_time = 0
        self.last_project_name = None
        self.start_time = int(time.time())
        self.ableton_was_running = False

    def patch_ableton_midi_script(self):
        """Standardizes the FauxMIDI install logic and avoids overwriting existing setups."""
        if not self.ableton_path or not self.temp_file_path:
            return False
        
        base_path = Path(self.ableton_path) / "Contents" / "App-Resources" / "MIDI Remote Scripts"
        faux_midi_dir = base_path / "FauxMIDI"
        
        if faux_midi_dir.exists():
            return True

        init_py_content = f"""import Live # type: ignore
import os

def create_instance(c_instance):
    return FauxMIDI(c_instance)

class FauxMIDI:
    def __init__(self, c_instance):
        self.c_instance = c_instance
        try:
            self.song = Live.Application.get_application().get_document()
            self.log_project_name()
            if not self.song.name_has_listener(self.log_project_name):
                self.song.add_name_listener(self.log_project_name)
        except Exception: pass

    def log_project_name(self):
        try:
            raw_name = self.song.name
            final_name = raw_name[:-4] if raw_name and raw_name.endswith('.als') else (raw_name or "Unsaved Project")
            log_file_path = "{self.temp_file_path}"
            with open(log_file_path, "w") as log_file:
                log_file.write(f"Current Project Name: {{final_name}}")
                log_file.flush()
                os.fsync(log_file.fileno())
        except Exception: pass

    def disconnect(self):
        try:
            if self.song and self.song.name_has_listener(self.log_project_name):
                self.song.remove_name_listener(self.log_project_name)
        except: pass
"""
        try:
            faux_midi_dir.mkdir(parents=True, exist_ok=True)
            with open(faux_midi_dir / "__init__.py", "w") as f:
                f.write(init_py_content)
            return True
        except Exception: return False

    def install_launch_agent(self):
        """Forces the Launch Agent identity and bootstraps it automatically."""
        exe_path = sys.executable 
        is_bundle = '.app/Contents/MacOS' in exe_path
        
        if is_bundle:
            app_path = exe_path.split('.app/Contents/MacOS')[0] + '.app'
            target_exe = app_path + '/Contents/MacOS/AbletonRPC'
            # BLESS THE APP: Remove quarantine so launchctl can run it
            subprocess.run(["xattr", "-rd", "com.apple.quarantine", app_path], capture_output=True)
            subprocess.run(["chmod", "+x", target_exe], capture_output=True)
            cmd_args = f"<string>{target_exe}</string><string>--daemon</string>"
        else:
            target_exe = exe_path
            script_path = os.path.abspath(sys.argv[0])
            cmd_args = f"<string>{target_exe}</string><string>{script_path}</string><string>--daemon</string>"

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.user.ableton-rpc</string>
<key>ProgramArguments</key><array>{cmd_args}</array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><false/></dict></plist>"""
        
        try:
            PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(PLIST_PATH, "w") as f: f.write(plist_content)
            
            uid = os.getuid()
            domain = f"gui/{uid}"
            # Force reload the service domain
            subprocess.run(["launchctl", "bootout", domain, str(PLIST_PATH)], capture_output=True)
            subprocess.run(["launchctl", "bootstrap", domain, str(PLIST_PATH)], capture_output=True)
            return True
        except Exception: return False

    def run_monitoring_loop(self):
        """Core Rich Presence monitoring logic."""
        if sys.platform == "darwin":
            subprocess.Popen(["defaults", "write", "com.user.ableton-discord-rpc", "NSAppSleepDisabled", "-bool", "YES"])
        
        try:
            self.rpc = Presence(self.client_id)
            self.rpc.connect()
        except: self.rpc = None
        
        while True:
            try:
                if not self.rpc:
                    try: self.rpc.connect()
                    except: pass
                
                running = any(p.info['name'] == 'Live' or (p.info['name'] and p.info['name'].startswith('Ableton Live')) for p in psutil.process_iter(['name']))
                
                if running and not self.ableton_was_running:
                    self.start_time = int(time.time()); self.ableton_was_running = True
                elif not running and self.ableton_was_running:
                    if self.rpc: self.rpc.clear()
                    self.ableton_was_running = False; time.sleep(5); continue

                if running and os.path.exists(self.temp_file_path):
                    mtime = os.path.getmtime(self.temp_file_path)
                    if mtime != self.last_modified_time:
                        self.last_modified_time = mtime; time.sleep(0.5)
                        with open(self.temp_file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            name = content.split("Current Project Name:")[-1].strip() if "Current Project Name:" in content else ""
                        if name != self.last_project_name and self.rpc:
                            self.last_project_name = name
                            self.rpc.update(state="Working on a project" if name else "Idle", details=name or "Cooking", large_image="ableton_image", start=self.start_time)
                time.sleep(3)
            except: time.sleep(5)

def reset_installation():
    """Wipes settings and unloads background tasks via the GUI button."""
    if messagebox.askyesno("Reset", "This will wipe all settings and stop the service. Proceed?"):
        try:
            uid = os.getuid()
            subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)], capture_output=True)
            if PLIST_PATH.exists(): os.remove(PLIST_PATH)
            if CONFIG_DIR.exists(): shutil.rmtree(CONFIG_DIR)
            os.system(f"pkill -9 AbletonRPC")
            sys.exit(0)
        except Exception as e: messagebox.showerror("Error", str(e))

def run_gui():
    """Builds the setup window with forced macOS focus and modal dialogs."""
    root = tk.Tk()
    root.title("AbletonRPC Setup")
    root.geometry("520x520")
    
    root.lift()
    root.attributes("-topmost", True)
    root.focus_force()

    e_apath, e_lpath = "", ""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            conf = dict(line.strip().split("=", 1) for line in f if "=" in line)
            e_apath, e_lpath = conf.get("ABLETON_PATH", ""), conf.get("LOG_PATH", "")

    tk.Label(root, text="Ableton Discord RPC Setup", font=("Helvetica", 18, "bold")).pack(pady=20)
    
    ap_var = tk.StringVar(value=e_apath)
    tk.Label(root, text="1. Select Ableton Live Application:", font=("Helvetica", 11, "bold")).pack(padx=40, anchor="w")
    tk.Entry(root, textvariable=ap_var, width=45).pack(pady=5)

    def browse_app():
        p = filedialog.askopenfilename(parent=root, initialdir="/Applications", title="Select Ableton Live .app", filetypes=[("macOS Application", "*.app")])
        if p: ap_var.set(p)
        root.lift()

    tk.Button(root, text="Select Bundle...", command=browse_app).pack()
    
    lp_var = tk.StringVar(value=e_lpath)
    tk.Label(root, text="2. Project Log Location:", font=("Helvetica", 11, "bold")).pack(padx=40, anchor="w", pady=(15,0))
    tk.Entry(root, textvariable=lp_var, width=45).pack(pady=5)
    
    def browse_log():
        p = filedialog.asksaveasfilename(parent=root, defaultextension=".txt", initialfile="CurrentProjectLog.txt")
        if p: lp_var.set(p)
        root.lift()

    tk.Button(root, text="Choose Save Location...", command=browse_log).pack()

    def save():
        if not ap_var.get() or not lp_var.get(): return
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            f.write(f"CLIENT_ID={DEFAULT_CLIENT_ID}\nLOG_PATH={lp_var.get()}\nABLETON_PATH={ap_var.get()}\n")
        
        # Kill everything current
        os.system(f"pkill -9 AbletonRPC")
        os.system(f"pkill -9 python")

        # Setup the agent
        app = AbletonRPCApp(DEFAULT_CLIENT_ID, lp_var.get(), ap_var.get())
        app.patch_ableton_midi_script()
        app.install_launch_agent()
        
        # System-managed Kickstart
        uid = os.getuid()
        subprocess.run(["launchctl", "kickstart", "-k", f"gui/{uid}/com.user.ableton-rpc"], capture_output=True)
        
        messagebox.showinfo("Success", "Presence Started! macOS is managing the process.")
        root.destroy()

    tk.Button(root, text="Save & Start Presence", bg="#5865F2", fg="white", font=("Helvetica", 12, "bold"), width=25, height=2, command=save).pack(pady=30)
    tk.Button(root, text="Reset Installation", fg="red", command=reset_installation).pack()
    root.mainloop()

if __name__ == "__main__":
    if "--daemon" in sys.argv:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                conf = dict(line.strip().split("=", 1) for line in f if "=" in line)
            app = AbletonRPCApp(conf.get("CLIENT_ID"), conf.get("LOG_PATH"), conf.get("ABLETON_PATH"))
            app.run_monitoring_loop()
        sys.exit(0)

    run_gui()