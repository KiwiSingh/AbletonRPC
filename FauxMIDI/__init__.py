import Live #type: ignore
import os
import traceback
import threading
import time

def create_instance(c_instance):
    return FauxMIDI(c_instance)

class FauxMIDI:
    def __init__(self, c_instance):
        self.c_instance = c_instance
        self.last_project_name = None
        self.name_check_counter = 0
        self.log_file_path = "/Volumes/Charidrive/rpctemp/CurrentProjectLog.txt"
        self.debug_log_path = self.log_file_path + ".debug"
        
        try:
            self._debug_log("Enhanced FauxMIDI initializing...")
            self.song = Live.Application.get_application().get_document()
            self._setup_listeners()
            self._debug_log("Listeners setup complete")
            self._start_name_monitor()
            self.log_project_name()
            self._debug_log("Initial project name logged")
        except Exception as e:
            self._debug_log(f"Initialization error: {e}")
            self._debug_log(traceback.format_exc())

    def _debug_log(self, message):
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            os.makedirs(os.path.dirname(self.debug_log_path), exist_ok=True)
            with open(self.debug_log_path, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
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
                        self.log_project_name()
                except Exception as e:
                    self._debug_log(f"Name monitor error: {e}")
                    time.sleep(5)
        
        monitor_thread = threading.Thread(target=name_monitor, daemon=True)
        monitor_thread.start()
        self._debug_log("Background name monitor started")

    def _get_enhanced_project_name(self):
        try:
            raw_name = getattr(self.song, 'name', None)
            if raw_name and raw_name.strip():
                name = raw_name[:-4] if raw_name.endswith('.als') else raw_name
                if name and name != "":
                    self._debug_log(f"Method 1 (song.name): '{name}'")
                    return name
            
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
                                self._debug_log(f"Method 2 (canonical_parent): '{name}'")
                                return name
            except Exception as e:
                self._debug_log(f"Method 2 failed: {e}")
            
            try:
                if hasattr(self.song, 'file_path'):
                    file_path = getattr(self.song, 'file_path', None)
                    if file_path:
                        filename = os.path.basename(file_path)
                        if filename.endswith('.als'):
                            name = filename[:-4]
                            self._debug_log(f"Method 3 (file_path): '{name}'")
                            return name
            except Exception as e:
                self._debug_log(f"Method 3 failed: {e}")
            
            self.name_check_counter += 1
            if self.name_check_counter % 5 == 0:
                raw_name_delayed = getattr(self.song, 'name', None)
                if raw_name_delayed and raw_name_delayed.strip() and raw_name_delayed != raw_name:
                    name = raw_name_delayed[:-4] if raw_name_delayed.endswith('.als') else raw_name_delayed
                    self._debug_log(f"Method 4 (delayed check): '{name}'")
                    return name
            
            if raw_name is None:
                self._debug_log("All methods failed - raw_name is None (Loading...)")
                return "Loading..."
            
            self._debug_log(f"All methods failed. raw_name='{raw_name}', counter={self.name_check_counter}")
            return "Unsaved Project"
            
        except Exception as e:
            self._debug_log(f"Enhanced name detection error: {e}")
            return "Unsaved Project"

    def _setup_listeners(self):
        try:
            if hasattr(self.song, 'name_has_listener') and not self.song.name_has_listener(self.log_project_name):
                self.song.add_name_listener(self.log_project_name)
                self._debug_log("Added name listener")
            
            if hasattr(self.song, 'tempo_has_listener') and not self.song.tempo_has_listener(self.log_project_name):
                self.song.add_tempo_listener(self.log_project_name)
                self._debug_log("Added tempo listener")
            
            if hasattr(self.song, 'is_playing_has_listener') and not self.song.is_playing_has_listener(self.log_project_name):
                self.song.add_is_playing_listener(self.log_project_name)
                self._debug_log("Added playing listener")
            
            if hasattr(self.song, 'record_mode_has_listener') and not self.song.record_mode_has_listener(self.log_project_name):
                self.song.add_record_mode_listener(self.log_project_name)
                self._debug_log("Added record listener")
                
            try:
                app = Live.Application.get_application()
                if hasattr(app, 'add_document_listener'):
                    app.add_document_listener(self.log_project_name)
                    self._debug_log("Added document listener")
            except Exception as e:
                self._debug_log(f"Could not add document listener: {e}")
                
        except Exception as e:
            self._debug_log(f"Listener setup error: {e}")
            self._debug_log(traceback.format_exc())

    def log_project_name(self):
        try:
            self._debug_log("log_project_name called")
            final_name = self._get_enhanced_project_name()
            self._debug_log(f"Final project name: '{final_name}'")
            os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
            
            with open(self.log_file_path, "w", encoding="utf-8") as log_file:
                if final_name and final_name not in ["Loading...", "Unsaved Project"]:
                    log_file.write(f"Current Project Name: {final_name}")
                    self._debug_log(f"Wrote project name: '{final_name}'")
                else:
                    log_file.write("Current Project Name: Unsaved Project")
                    self._debug_log("Wrote: Unsaved Project")
                
                log_file.flush()
                os.fsync(log_file.fileno())
                
            self._debug_log(f"Successfully wrote to {self.log_file_path}")
                
        except Exception as e:
            self._debug_log(f"log_project_name error: {e}")
            self._debug_log(traceback.format_exc())
            
            try:
                os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
                with open(self.log_file_path, "w", encoding="utf-8") as log_file:
                    log_file.write(f"Current Project Name: Error - {str(e)}")
                    log_file.flush()
                self._debug_log("Wrote error state to main log")
            except Exception as fallback_error:
                self._debug_log(f"Fallback logging also failed: {fallback_error}")

    def disconnect(self):
        try:
            self._debug_log("FauxMIDI disconnecting...")
            if hasattr(self, 'song') and self.song:
                try:
                    if hasattr(self.song, 'remove_name_listener'):
                        self.song.remove_name_listener(self.log_project_name)
                        self._debug_log("Removed name listener")
                except: 
                    pass
                
                try:
                    if hasattr(self.song, 'remove_tempo_listener'):
                        self.song.remove_tempo_listener(self.log_project_name)
                        self._debug_log("Removed tempo listener")
                except: 
                    pass
                
                try:
                    if hasattr(self.song, 'remove_is_playing_listener'):
                        self.song.remove_is_playing_listener(self.log_project_name)
                        self._debug_log("Removed playing listener")
                except: 
                    pass
                
                try:
                    if hasattr(self.song, 'remove_record_mode_listener'):
                        self.song.remove_record_mode_listener(self.log_project_name)
                        self._debug_log("Removed record listener")
                except: 
                    pass
                
                try:
                    app = Live.Application.get_application()
                    if hasattr(app, 'remove_document_listener'):
                        app.remove_document_listener(self.log_project_name)
                        self._debug_log("Removed document listener")
                except: 
                    pass
                
            self._debug_log("All listeners removed successfully")
        except Exception as e:
            self._debug_log(f"Disconnect error: {e}")