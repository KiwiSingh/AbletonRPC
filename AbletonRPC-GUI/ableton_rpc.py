import os
import sys
import time
import psutil # type: ignore
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from pypresence import Presence # type: ignore
import subprocess
import shutil
import json
import hashlib

# --- GLOBAL SETTINGS ---
DEFAULT_CLIENT_ID = "1283406074824753203" 
HOME = os.environ.get("HOME", str(Path.home()))
CONFIG_DIR = Path(HOME) / ".config" / "ableton-discord-rpc"
INSTALLS_CONFIG = CONFIG_DIR / "installations.json"
LAUNCH_AGENTS_DIR = Path(HOME) / "Library" / "LaunchAgents"

class AbletonInstallation:
    def __init__(self, name, ableton_path, log_path, client_id=None):
        self.name = name
        self.ableton_path = ableton_path
        self.log_path = log_path
        self.client_id = client_id or DEFAULT_CLIENT_ID
        
        # Generate unique identifiers
        self.install_hash = hashlib.md5(ableton_path.encode()).hexdigest()[:8]
        self.service_name = f"com.user.ableton-rpc.{self.install_hash}"
        self.plist_path = LAUNCH_AGENTS_DIR / f"{self.service_name}.plist"
    
    def to_dict(self):
        return {
            'name': self.name,
            'ableton_path': self.ableton_path,
            'log_path': self.log_path,
            'client_id': self.client_id,
            'install_hash': self.install_hash,
            'service_name': self.service_name
        }
    
    @classmethod
    def from_dict(cls, data):
        install = cls(data['name'], data['ableton_path'], data['log_path'], data['client_id'])
        install.install_hash = data['install_hash']
        install.service_name = data['service_name']
        install.plist_path = LAUNCH_AGENTS_DIR / f"{install.service_name}.plist"
        return install

class MultiAbletonRPCManager:
    def __init__(self):
        self.installations = {}
        self.load_installations()
    
    def load_installations(self):
        """Load all configured installations"""
        if INSTALLS_CONFIG.exists():
            try:
                with open(INSTALLS_CONFIG, 'r') as f:
                    data = json.load(f)
                    for install_data in data.get('installations', []):
                        install = AbletonInstallation.from_dict(install_data)
                        self.installations[install.install_hash] = install
            except Exception as e:
                print(f"Warning: Could not load installations config: {e}")
    
    def save_installations(self):
        """Save all installations to config"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            'installations': [install.to_dict() for install in self.installations.values()]
        }
        with open(INSTALLS_CONFIG, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_installation(self, name, ableton_path, log_path, client_id=None):
        """Add a new Ableton installation"""
        install = AbletonInstallation(name, ableton_path, log_path, client_id)
        self.installations[install.install_hash] = install
        self.save_installations()
        return install
    
    def remove_installation(self, install_hash):
        """Remove an installation and stop its service"""
        if install_hash in self.installations:
            install = self.installations[install_hash]
            self.stop_service(install)
            if install.plist_path.exists():
                install.plist_path.unlink()
            del self.installations[install_hash]
            self.save_installations()
            return True
        return False
    
    def get_running_ableton_versions(self):
        """Detect which Ableton versions are currently running"""
        running_versions = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    if proc.info['name'] == 'Live' or (proc.info['name'] and 'Ableton' in proc.info['name']):
                        exe_path = proc.info.get('exe', '')
                        if exe_path:
                            # Extract app bundle path
                            if '.app/Contents/MacOS' in exe_path:
                                app_path = exe_path.split('.app/Contents/MacOS')[0] + '.app'
                                running_versions.append({
                                    'pid': proc.info['pid'],
                                    'name': proc.info['name'],
                                    'path': app_path
                                })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error detecting running Ableton versions: {e}")
        return running_versions
    
    def patch_ableton_midi_script(self, installation):
        """Install MIDI script for specific installation"""
        if not installation.ableton_path or not installation.log_path:
            return False
        
        base_path = Path(installation.ableton_path) / "Contents" / "App-Resources" / "MIDI Remote Scripts"
        faux_midi_dir = base_path / "FauxMIDI"
        
        # Enhanced MIDI script template (same as before but with installation-specific logging)
        init_py_template = """import Live
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
        self.log_file_path = {LOG_PATH_PLACEHOLDER}
        self.debug_log_path = self.log_file_path + ".debug"
        self.installation_name = {INSTALL_NAME_PLACEHOLDER}
        self.last_project_name = None
        self.name_check_counter = 0
        
        try:
            self._debug_log(f"FauxMIDI initializing for {self.installation_name}...")
            self.song = Live.Application.get_application().get_document()
            self._setup_listeners()
            self._debug_log("Listeners setup complete")
            
            # Start background name monitoring thread
            self._start_name_monitor()
            
            self.log_state()  # Initial state log
            self._debug_log("Initial state logged successfully")
        except Exception as e:
            self._debug_log(f"Initialization error: {e}")
            self._debug_log(traceback.format_exc())

    def _debug_log(self, message):
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            os.makedirs(os.path.dirname(self.debug_log_path), exist_ok=True)
            with open(self.debug_log_path, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [{self.installation_name}] {message}\\n")
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
                    if current_name != self.last_project_name:
                        self._debug_log(f"Project name changed: '{self.last_project_name}' -> '{current_name}'")
                        self.last_project_name = current_name
                        self.log_state()
                except Exception as e:
                    self._debug_log(f"Name monitor error: {e}")
                    time.sleep(5)
        
        monitor_thread = threading.Thread(target=name_monitor, daemon=True)
        monitor_thread.start()
        self._debug_log("Background name monitor started")

    def _get_enhanced_project_name(self):
        try:
            # Method 1: Direct song.name
            raw_name = getattr(self.song, 'name', None)
            if raw_name and raw_name.strip():
                name = raw_name[:-4] if raw_name.endswith('.als') else raw_name
                if name and name != "":
                    return name
            
            # Method 2: Check canonical_parent
            try:
                app = Live.Application.get_application()
                if hasattr(app, 'get_document') and hasattr(app.get_document(), 'canonical_parent'):
                    doc = app.get_document()
                    if hasattr(doc, 'canonical_parent') and doc.canonical_parent:
                        parent_path = str(doc.canonical_parent)
                        if parent_path and parent_path != "":
                            filename = os.path.basename(parent_path)
                            if filename.endswith('.als'):
                                name = filename[:-4]
                                return name
            except Exception as e:
                self._debug_log(f"Method 2 failed: {e}")
            
            # Method 3: Check file_path
            try:
                if hasattr(self.song, 'file_path'):
                    file_path = getattr(self.song, 'file_path', None)
                    if file_path:
                        filename = os.path.basename(file_path)
                        if filename.endswith('.als'):
                            name = filename[:-4]
                            return name
            except Exception as e:
                self._debug_log(f"Method 3 failed: {e}")
            
            # Method 4: Delayed check
            self.name_check_counter += 1
            if self.name_check_counter % 5 == 0:
                raw_name_delayed = getattr(self.song, 'name', None)
                if raw_name_delayed and raw_name_delayed.strip() and raw_name_delayed != raw_name:
                    name = raw_name_delayed[:-4] if raw_name_delayed.endswith('.als') else raw_name_delayed
                    return name
            
            return "Unsaved Project"
            
        except Exception as e:
            self._debug_log(f"Enhanced name detection error: {e}")
            return "Unsaved Project"

    def _setup_listeners(self):
        try:
            if hasattr(self.song, 'name_has_listener') and not self.song.name_has_listener(self.log_state):
                self.song.add_name_listener(self.log_state)
            if hasattr(self.song, 'tempo_has_listener') and not self.song.tempo_has_listener(self.log_state):
                self.song.add_tempo_listener(self.log_state)
            if hasattr(self.song, 'is_playing_has_listener') and not self.song.is_playing_has_listener(self.log_state):
                self.song.add_is_playing_listener(self.log_state)
            if hasattr(self.song, 'record_mode_has_listener') and not self.song.record_mode_has_listener(self.log_state):
                self.song.add_record_mode_listener(self.log_state)
                
            try:
                app = Live.Application.get_application()
                if hasattr(app, 'add_document_listener'):
                    app.add_document_listener(self.log_state)
            except Exception as e:
                self._debug_log(f"Could not add document listener: {e}")
                
        except Exception as e:
            self._debug_log(f"Listener setup error: {e}")

    def log_state(self):
        try:
            project = self._get_enhanced_project_name()
            tempo = int(getattr(self.song, 'tempo', 120))
            is_playing = getattr(self.song, 'is_playing', False)
            record_mode = getattr(self.song, 'record_mode', False)
            
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
            try:
                os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
                with open(self.log_file_path, "w", encoding="utf-8") as f:
                    f.write(f"PROJECT:Error - {str(e)}\\n")
                    f.write("TEMPO:120\\n")
                    f.write("STATE:Error\\n")
                    f.write(f"INSTALLATION:{self.installation_name}\\n")
                    f.flush()
            except:
                pass

    def disconnect(self):
        try:
            self._debug_log("FauxMIDI disconnecting...")
            if hasattr(self, 'song') and self.song:
                try:
                    if hasattr(self.song, 'remove_name_listener'):
                        self.song.remove_name_listener(self.log_state)
                except: pass
                try:
                    if hasattr(self.song, 'remove_tempo_listener'):
                        self.song.remove_tempo_listener(self.log_state)
                except: pass
                try:
                    if hasattr(self.song, 'remove_is_playing_listener'):
                        self.song.remove_is_playing_listener(self.log_state)
                except: pass
                try:
                    if hasattr(self.song, 'remove_record_mode_listener'):
                        self.song.remove_record_mode_listener(self.log_state)
                except: pass
                
                try:
                    app = Live.Application.get_application()
                    if hasattr(app, 'remove_document_listener'):
                        app.remove_document_listener(self.log_state)
                except: pass
                
        except Exception as e:
            self._debug_log(f"Disconnect error: {e}")
        
        super(FauxMIDI, self).disconnect()
"""
        
        # Replace placeholders with installation-specific values
        final_script = init_py_template.replace("{LOG_PATH_PLACEHOLDER}", repr(str(installation.log_path)))
        final_script = final_script.replace("{INSTALL_NAME_PLACEHOLDER}", repr(installation.name))

        try:
            faux_midi_dir.mkdir(parents=True, exist_ok=True)
            with open(faux_midi_dir / "__init__.py", "w", encoding="utf-8") as f:
                f.write(final_script)
            print(f"✅ MIDI script installed for {installation.name}: {faux_midi_dir}")
            return True
        except Exception as e:
            print(f"❌ Failed to install MIDI script for {installation.name}: {e}")
            return False
    
    def install_launch_agent(self, installation):
        """Install launch agent for specific installation"""
        exe_path = sys.executable 
        is_bundle = '.app/Contents/MacOS' in exe_path
        
        if is_bundle:
            app_path = exe_path.split('.app/Contents/MacOS')[0] + '.app'
            target_exe = app_path + '/Contents/MacOS/AbletonRPC'
            subprocess.run(["xattr", "-rd", "com.apple.quarantine", app_path], capture_output=True)
            subprocess.run(["chmod", "+x", target_exe], capture_output=True)
            cmd_args = f"<string>{target_exe}</string><string>--daemon</string><string>{installation.install_hash}</string>"
        else:
            target_exe = exe_path
            script_path = os.path.abspath(sys.argv[0])
            cmd_args = f"<string>{target_exe}</string><string>{script_path}</string><string>--daemon</string><string>{installation.install_hash}</string>"

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>{installation.service_name}</string>
<key>ProgramArguments</key><array>{cmd_args}</array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><false/>
<key>StandardOutPath</key><string>{installation.log_path}.service.log</string>
<key>StandardErrorPath</key><string>{installation.log_path}.service.error</string>
</dict></plist>"""
        
        try:
            installation.plist_path.parent.mkdir(parents=True, exist_ok=True)
            with open(installation.plist_path, "w") as f: 
                f.write(plist_content)
            
            uid = os.getuid()
            domain = f"gui/{uid}"
            subprocess.run(["launchctl", "bootout", domain, str(installation.plist_path)], capture_output=True)
            subprocess.run(["launchctl", "bootstrap", domain, str(installation.plist_path)], capture_output=True)
            print(f"✅ Launch agent installed for {installation.name}: {installation.service_name}")
            return True
        except Exception as e:
            print(f"❌ Failed to install launch agent for {installation.name}: {e}")
            return False
    
    def start_service(self, installation):
        """Start service for specific installation"""
        try:
            uid = os.getuid()
            domain = f"gui/{uid}"
            result = subprocess.run(["launchctl", "kickstart", "-k", f"{domain}/{installation.service_name}"], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            print(f"❌ Failed to start service for {installation.name}: {e}")
            return False
    
    def stop_service(self, installation):
        """Stop service for specific installation"""
        try:
            uid = os.getuid()
            domain = f"gui/{uid}"
            subprocess.run(["launchctl", "bootout", domain, str(installation.plist_path)], capture_output=True)
            return True
        except Exception as e:
            print(f"❌ Failed to stop service for {installation.name}: {e}")
            return False
    
    def get_service_status(self, installation):
        """Check if service is running for specific installation"""
        try:
            result = subprocess.run(["launchctl", "list", installation.service_name], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False

class AbletonRPCApp:
    def __init__(self, installation):
        self.installation = installation
        self.rpc = None
        self.last_modified_time = 0
        self.last_data_payload = None
        self.start_time = int(time.time())
        self.ableton_was_running = False

    def run_monitoring_loop(self):
        """Monitoring loop for specific installation"""
        print(f"🔍 Starting monitoring for {self.installation.name}")
        print(f"📁 Ableton path: {self.installation.ableton_path}")
        print(f"📝 Log file: {self.installation.log_path}")
        print(f"🔧 Service: {self.installation.service_name}")
        
        try:
            self.rpc = Presence(self.installation.client_id)
            self.rpc.connect()
            print("✅ Connected to Discord RPC")
        except Exception as e:
            print(f"⚠️  Discord RPC connection failed: {e}")
            self.rpc = None
        
        while True:
            try:
                if not self.rpc:
                    try: 
                        self.rpc = Presence(self.installation.client_id)
                        self.rpc.connect()
                        print("✅ Reconnected to Discord RPC")
                    except Exception as e:
                        print(f"⚠️  Discord reconnection failed: {e}")
                        time.sleep(10)
                        continue
                
                # Check if THIS specific Ableton version is running
                running = self._is_this_ableton_running()
                
                if running and not self.ableton_was_running:
                    self.start_time = int(time.time())
                    self.ableton_was_running = True
                    print(f"🎵 {self.installation.name} detected - monitoring started")
                elif not running and self.ableton_was_running:
                    if self.rpc: 
                        self.rpc.clear()
                        print(f"🔇 {self.installation.name} closed - Discord presence cleared")
                    self.ableton_was_running = False
                    time.sleep(5)
                    continue

                if running and os.path.exists(self.installation.log_path):
                    try:
                        mtime = os.path.getmtime(self.installation.log_path)
                        if mtime != self.last_modified_time:
                            self.last_modified_time = mtime
                            time.sleep(0.5)
                            
                            with open(self.installation.log_path, "r", encoding="utf-8") as f:
                                lines = f.read().splitlines()
                                data = {}
                                for line in lines:
                                    if ":" in line:
                                        k, v = line.split(":", 1)
                                        data[k.strip()] = v.strip()
                            
                            project = data.get("PROJECT", "Unsaved Project")
                            tempo = data.get("TEMPO", "120")
                            state = data.get("STATE", "Stopped")
                            installation_name = data.get("INSTALLATION", self.installation.name)
                            
                            current_payload = (project, tempo, state)

                            if current_payload != self.last_data_payload and self.rpc:
                                self.last_data_payload = current_payload
                                self.rpc.update(
                                    state=f"{state} · {tempo} BPM",
                                    details=f"{installation_name}: {project}",
                                    large_image="ableton_image",
                                    start=self.start_time
                                )
                                print(f"📡 Updated Discord: [{installation_name}] {project} | {state} | {tempo} BPM")
                    except Exception as e:
                        print(f"⚠️  Error reading log file: {e}")
                        
                time.sleep(3)
            except Exception as e:
                print(f"⚠️  Monitoring loop error: {e}")
                time.sleep(5)
    
    def _is_this_ableton_running(self):
        """Check if this specific Ableton installation is running"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    if proc.info['name'] == 'Live' or (proc.info['name'] and 'Ableton' in proc.info['name']):
                        exe_path = proc.info.get('exe', '')
                        if exe_path and '.app/Contents/MacOS' in exe_path:
                            app_path = exe_path.split('.app/Contents/MacOS')[0] + '.app'
                            if app_path == self.installation.ableton_path:
                                return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return False

def run_multi_gui():
    """Multi-installation GUI"""
    root = tk.Tk()
    root.title("AbletonRPC - Multi-Installation Manager")
    root.geometry("800x700")
    
    manager = MultiAbletonRPCManager()
    
    # Header
    header_frame = tk.Frame(root)
    header_frame.pack(fill=tk.X, padx=20, pady=10)
    
    tk.Label(header_frame, text="Ableton Discord RPC v1.0.8", font=("Helvetica", 20, "bold")).pack()
    tk.Label(header_frame, text="(Call An Ambulance, But Not For Me)", font=("Helvetica", 12), fg="blue").pack()
    
    # Running versions detection
    detect_frame = tk.Frame(root)
    detect_frame.pack(fill=tk.X, padx=20, pady=10)
    
    tk.Label(detect_frame, text="🔍 Detected Running Ableton Versions:", font=("Helvetica", 12, "bold")).pack(anchor="w")
    
    running_text = tk.Text(detect_frame, height=3, font=("Monaco", 10))
    running_text.pack(fill=tk.X, pady=5)
    
    def refresh_running():
        running_versions = manager.get_running_ableton_versions()
        running_text.delete(1.0, tk.END)
        if running_versions:
            for version in running_versions:
                running_text.insert(tk.END, f"• {version['name']} (PID: {version['pid']}) - {version['path']}\n")
        else:
            running_text.insert(tk.END, "No Ableton Live instances currently running")
        running_text.config(state="disabled")
    
    tk.Button(detect_frame, text="Refresh", command=refresh_running).pack(anchor="e")
    refresh_running()
    
    # Installations list
    list_frame = tk.Frame(root)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    
    tk.Label(list_frame, text="📋 Configured Installations:", font=("Helvetica", 12, "bold")).pack(anchor="w")
    
    # Treeview for installations
    columns = ("Name", "Version", "Status", "Log Path")
    tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
    
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=150)
    
    tree.pack(fill=tk.BOTH, expand=True, pady=5)
    
    # Scrollbar for treeview
    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tree.configure(yscrollcommand=scrollbar.set)
    
    def refresh_installations():
        for item in tree.get_children():
            tree.delete(item)
        
        for install in manager.installations.values():
            status = "🟢 Running" if manager.get_service_status(install) else "🔴 Stopped"
            version = Path(install.ableton_path).name
            tree.insert("", tk.END, values=(install.name, version, status, install.log_path))
    
    # Control buttons
    control_frame = tk.Frame(root)
    control_frame.pack(fill=tk.X, padx=20, pady=10)
    
    def add_installation():
        add_window = tk.Toplevel(root)
        add_window.title("Add Ableton Installation")
        add_window.geometry("500x400")
        add_window.transient(root)
        add_window.grab_set()
        
        tk.Label(add_window, text="Add New Ableton Installation", font=("Helvetica", 16, "bold")).pack(pady=20)
        
        # Name
        tk.Label(add_window, text="Installation Name:", font=("Helvetica", 11, "bold")).pack(anchor="w", padx=40)
        name_var = tk.StringVar()
        tk.Entry(add_window, textvariable=name_var, width=50).pack(pady=5)
        
        # Ableton path
        tk.Label(add_window, text="Ableton Live Application:", font=("Helvetica", 11, "bold")).pack(anchor="w", padx=40, pady=(15,0))
        ableton_var = tk.StringVar()
        tk.Entry(add_window, textvariable=ableton_var, width=50).pack(pady=5)
        tk.Button(add_window, text="Select App...", 
                 command=lambda: ableton_var.set(filedialog.askopenfilename(filetypes=[("macOS Application", "*.app")]))).pack()
        
        # Log path
        tk.Label(add_window, text="Log File Location:", font=("Helvetica", 11, "bold")).pack(anchor="w", padx=40, pady=(15,0))
        log_var = tk.StringVar()
        tk.Entry(add_window, textvariable=log_var, width=50).pack(pady=5)
        tk.Button(add_window, text="Choose Location...", 
                 command=lambda: log_var.set(filedialog.asksaveasfilename(defaultextension=".txt"))).pack()
        
        # Client ID (optional)
        tk.Label(add_window, text="Discord Client ID (optional):", font=("Helvetica", 11, "bold")).pack(anchor="w", padx=40, pady=(15,0))
        client_var = tk.StringVar(value=DEFAULT_CLIENT_ID)
        tk.Entry(add_window, textvariable=client_var, width=50).pack(pady=5)
        
        def save_installation():
            if not all([name_var.get(), ableton_var.get(), log_var.get()]):
                messagebox.showerror("Error", "Please fill in all required fields")
                return
            
            try:
                install = manager.add_installation(
                    name_var.get(), 
                    ableton_var.get(), 
                    log_var.get(), 
                    client_var.get() or DEFAULT_CLIENT_ID
                )
                
                # Install MIDI script and launch agent
                script_success = manager.patch_ableton_midi_script(install)
                agent_success = manager.install_launch_agent(install)
                
                if script_success and agent_success:
                    messagebox.showinfo("Success", 
                        f"✅ Installation '{install.name}' added successfully!\n\n"
                        f"Service: {install.service_name}\n"
                        f"Log: {install.log_path}\n"
                        f"Debug: {install.log_path}.debug\n\n"
                        f"Next steps:\n"
                        f"1. Restart {install.name}\n"
                        f"2. Set Control Surface to 'FauxMIDI' in MIDI preferences")
                    add_window.destroy()
                    refresh_installations()
                else:
                    messagebox.showerror("Error", "Installation failed - check console for details")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add installation: {e}")
        
        tk.Button(add_window, text="Add Installation", bg="#5865F2", fg="white", 
                 font=("Helvetica", 12, "bold"), command=save_installation).pack(pady=20)
    
    def remove_installation():
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an installation to remove")
            return
        
        item = tree.item(selection[0])
        install_name = item['values'][0]
        
        # Find installation by name
        install_to_remove = None
        for install in manager.installations.values():
            if install.name == install_name:
                install_to_remove = install
                break
        
        if install_to_remove and messagebox.askyesno("Confirm", f"Remove installation '{install_name}'?"):
            if manager.remove_installation(install_to_remove.install_hash):
                messagebox.showinfo("Success", f"Installation '{install_name}' removed")
                refresh_installations()
            else:
                messagebox.showerror("Error", "Failed to remove installation")
    
    def start_stop_service():
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an installation")
            return
        
        item = tree.item(selection[0])
        install_name = item['values'][0]
        
        # Find installation by name
        install = None
        for i in manager.installations.values():
            if i.name == install_name:
                install = i
                break
        
        if install:
            if manager.get_service_status(install):
                if manager.stop_service(install):
                    messagebox.showinfo("Success", f"Service stopped for '{install_name}'")
                else:
                    messagebox.showerror("Error", "Failed to stop service")
            else:
                if manager.start_service(install):
                    messagebox.showinfo("Success", f"Service started for '{install_name}'")
                else:
                    messagebox.showerror("Error", "Failed to start service")
            refresh_installations()
    
    # Control buttons
    btn_frame = tk.Frame(control_frame)
    btn_frame.pack()
    
    tk.Button(btn_frame, text="➕ Add Installation", command=add_installation, 
             bg="#28a745", fg="white", font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="🗑️ Remove", command=remove_installation, 
             bg="#dc3545", fg="white", font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="⚡ Start/Stop", command=start_stop_service, 
             bg="#ffc107", fg="black", font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="🔄 Refresh", command=lambda: [refresh_running(), refresh_installations()], 
             bg="#17a2b8", fg="white", font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=5)
    
    refresh_installations()
    
    # Status info
    info_frame = tk.Frame(root)
    info_frame.pack(fill=tk.X, padx=20, pady=10)
    
    info_text = tk.Text(info_frame, height=4, font=("Monaco", 9))
    info_text.pack(fill=tk.X)
    info_text.insert("1.0", 
        "💡 Multi-Installation Features:\n"
        "• Each Ableton version gets its own service and log file\n"
        "• Services run independently - no conflicts between versions\n"
        "• Discord shows which specific Ableton version is active\n"
        "• Debug logs include installation name for easy troubleshooting")
    info_text.config(state="disabled")
    
    root.mainloop()

def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--daemon":
        # Daemon mode with installation hash
        install_hash = sys.argv[2]
        
        manager = MultiAbletonRPCManager()
        if install_hash in manager.installations:
            installation = manager.installations[install_hash]
            app = AbletonRPCApp(installation)
            app.run_monitoring_loop()
        else:
            print(f"❌ Installation not found: {install_hash}")
        sys.exit(0)
    else:
        run_multi_gui()

if __name__ == "__main__":
    main()