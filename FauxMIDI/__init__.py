import Live  # type: ignore

def create_instance(c_instance):
    ' Creates and returns the FauxMIDI script '
    return FauxMIDI(c_instance)

class FauxMIDI:
    def __init__(self, c_instance):
        self.c_instance = c_instance
        self.log_project_name()

    def log_project_name(self):
        # Access the current song
        project_name = Live.Application.get_application().get_document().name

        # Set the path for the log file
        log_file_path = "/Volumes/Charidrive/rpctemp/CurrentProjectLog.txt"

        try:
            # Open the file for writing (this will overwrite the file)
            with open(log_file_path, "w") as log_file:
                # Write the project name to the file
                log_file.write(f"Current Project Name: {project_name}\n")
        except Exception as e:
            # Handle any errors
            print(f"Error writing to log file: {e}")

    def midi_input(self, midi_bytes):
        # This function can be used to handle incoming MIDI messages if needed
        pass

# local variables:
# tab-width: 4