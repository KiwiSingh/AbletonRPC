import os
import sys
import time
import psutil  # type: ignore
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from pypresence import Presence  # type: ignore
import subprocess

# --- CONFIGURATION PATHS ---
CONFIG_DIR = Path.home() / ".config" / "ableton-discord-rpc"
CONFIG_FILE = CONFIG_DIR / "config.txt"

class AbletonRPCApp:
    def __init__(self, client_id="", log_path=""):
        self.client_id = client_id
        self.temp_file_path = log_path
        self.rpc = None
        self.last_modified_time = 0
        self.last_project_name = None
        self.start_time = int(time.time())
        self.ableton_was_running = False

    def install_launch_agent(self):
        """Standard macOS background registration."""
        exe_path = os.path.abspath(sys.argv[0])
        if '.app/Contents/MacOS' in exe_path:
            exe_path = exe_path.split('.app/Contents/MacOS')[0] + '.app/Contents/MacOS/AbletonRPC'
        
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.user.ableton-discord-rpc</string>
    <key>ProgramArguments</key><array><string>{exe_path}</string></array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><false/>
</dict>
</plist>"""
        plist_path = Path.home() / "Library/LaunchAgents/com.user.ableton-discord-rpc.plist"
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(plist_path, "w") as f: f.write(plist_content)
        
        # Trigger macOS background registration
        res = subprocess.run(["launchctl", "load", "-w", str(plist_path)], capture_output=True)
        
        # FAIL-SAFE: If launchctl fails, open System Settings for the user
        if res.returncode != 0:
            print("Registration failed. Opening System Settings...")
            subprocess.run(["open", "x-apple.systempreferences:com.apple.LoginItems-Settings.extension"])

    def run_monitoring_loop(self):
        """The actual background work."""
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

                # Check for Ableton
                running = any(p.info['name'] in ['Live', 'Ableton Live'] for p in psutil.process_iter(['name']))

                if running and not self.ableton_was_running:
                    self.start_time = int(time.time())
                    self.ableton_was_running = True
                    if os.path.exists(self.temp_file_path):
                        with open(self.temp_file_path, "w") as f: f.write("Current Project Name: \n")

                elif not running and self.ableton_was_running:
                    if self.rpc: self.rpc.clear()
                    self.ableton_was_running = False
                    time.sleep(5)
                    continue

                if running and os.path.exists(self.temp_file_path):
                    mtime = os.path.getmtime(self.temp_file_path)
                    if mtime != self.last_modified_time:
                        self.last_modified_time = mtime
                        time.sleep(0.5)
                        with open(self.temp_file_path, "r") as f:
                            content = f.read()
                            name = content.split("Current Project Name:")[-1].strip() if "Current Project Name:" in content else ""
                        
                        if name != self.last_project_name and self.rpc:
                            self.last_project_name = name
                            state = "Working on a project" if name else "Idle"
                            self.rpc.update(state=state, details=name if name else "Cooking", large_image="ableton_image", start=self.start_time)
                
                time.sleep(3)
            except:
                time.sleep(5)

def run_gui():
    root = tk.Tk()
    root.title("AbletonRPC Setup")
    root.geometry("480x350")
    root.attributes("-topmost", True)
    
    tk.Label(root, text="Ableton Discord RPC Setup", font=("Arial", 16, "bold")).pack(pady=20)
    
    tk.Label(root, text="Discord Client ID:").pack(padx=40, anchor="w")
    cid_ent = tk.Entry(root, width=40)
    cid_ent.pack(pady=5)
    
    tk.Label(root, text="Log File Path:").pack(padx=40, anchor="w")
    path_var = tk.StringVar()
    tk.Entry(root, textvariable=path_var, width=40, state="readonly").pack(pady=5)

    def browse():
        p = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="CurrentProjectLog.txt")
        if p: path_var.set(p)
    tk.Button(root, text="Browse...", command=browse).pack()

    def save_and_exit():
        cid, lpath = cid_ent.get().strip(), path_var.get().strip()
        if not cid or not lpath:
            messagebox.showerror("Error", "Required fields missing!")
            return
        
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            f.write(f"CLIENT_ID={cid}\nLOG_PATH={lpath}\n")
        
        root.destroy()

    tk.Button(root, text="Save & Start", bg="#5865F2", fg="white", width=20, height=2, command=save_and_exit).pack(pady=30)
    root.mainloop()

if __name__ == "__main__":
    if not CONFIG_FILE.exists():
        run_gui()
        # Spawn detached and exit immediately
        subprocess.Popen([sys.executable, os.path.abspath(__file__)], start_new_session=True)
        sys.exit(0)

    # Background process starts here
    with open(CONFIG_FILE, "r") as f:
        conf = dict(line.strip().split("=", 1) for line in f if "=" in line)
    
    app = AbletonRPCApp(client_id=conf.get("CLIENT_ID"), log_path=conf.get("LOG_PATH"))
    
    # Register background task and start loop
    app.install_launch_agent()
    app.run_monitoring_loop()