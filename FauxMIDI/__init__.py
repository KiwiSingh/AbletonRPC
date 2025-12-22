import Live  # type: ignore
import os

def create_instance(c_instance):
    return FauxMIDI(c_instance)

class FauxMIDI:
    def __init__(self, c_instance):
        self.c_instance = c_instance
        try:
            self.song = Live.Application.get_application().get_document()
            
            # 1. Run logic immediately
            self.log_project_name()

            # 2. Add listener
            if not self.song.name_has_listener(self.log_project_name):
                self.song.add_name_listener(self.log_project_name)
                
        except Exception:
            # If something fails during init, we can't really do anything without debug logging
            pass

    def log_project_name(self):
        try:
            raw_name = self.song.name
            
            # Check if name is None (e.g. during startup race conditions)
            if raw_name is None:
                final_name = "Loading..."
            elif isinstance(raw_name, str):
                if raw_name.endswith('.als'):
                    final_name = raw_name[:-4]
                else:
                    final_name = raw_name
            else:
                final_name = str(raw_name)

            log_file_path = "/Volumes/Charidrive/rpctemp/CurrentProjectLog.txt"
            
            with open(log_file_path, "w") as log_file:
                if final_name and final_name != "Loading...":
                    log_file.write(f"Current Project Name: {final_name}")
                else:
                    log_file.write("Current Project Name: Unsaved Project")
                
                # Force write to disk immediately
                log_file.flush()
                os.fsync(log_file.fileno())
                
        except Exception:
            # Silently fail if writing fails (avoids crashing the MIDI thread)
            pass

    def disconnect(self):
        if self.song and self.song.name_has_listener(self.log_project_name):
            self.song.remove_name_listener(self.log_project_name)