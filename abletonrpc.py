import os
import time
from pypresence import Presence  # type: ignore
import psutil  # type: ignore
import threading  # For handling user input

# Set the path to the temporary file
temp_file_path = "/Volumes/Charidrive/rpctemp/CurrentProjectLog.txt"

# Initialize the Discord RPC client
client_id = "Your Client ID"  # Replace with your actual client ID
RPC = Presence(client_id)
RPC.connect()

# Initialize variables for tracking project name and modification time
last_modified_time = 0
last_project_name = None
start_time = None
broadcasting = True  # Toggle for broadcasting Rich Presence

# Function to check if Ableton Live is running
def is_ableton_running():
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == 'Live':
            return True
    return False

# Function to toggle broadcasting
def toggle_broadcast():
    global broadcasting
    while True:
        user_input = input()  # Wait for user input without a prompt
        if user_input.lower() == 'toggle':
            broadcasting = not broadcasting
            state = "enabled" if broadcasting else "disabled"
            print(f"Rich Presence {state}.")

# Start the input thread for toggling broadcasting
threading.Thread(target=toggle_broadcast, daemon=True).start()

while True:
    try:
        # Wait for Ableton Live to start running
        while not is_ableton_running():
            print("Waiting for Ableton Live to start running...")
            time.sleep(5)

        # Check if the file exists before trying to get its modification time
        if not os.path.exists(temp_file_path):
            print("Log file does not exist.")
            time.sleep(1)
            continue

        # Check the last modification time of the file
        current_modified_time = os.path.getmtime(temp_file_path)

        # If the file has been modified since the last check
        if current_modified_time != last_modified_time:
            last_modified_time = current_modified_time  # Update the last modified time
            print("Log file modified.")

            # Read the project name from the temporary file
            with open(temp_file_path, "r") as file:
                project_name_line = file.read().strip()
                print(f"Read project line: '{project_name_line}'")  # Debug output

                # Check if the project name contains valid text after the placeholder
                if project_name_line.startswith("Current Project Name:"):
                    project_name = project_name_line.split("Current Project Name:")[1].strip()
                else:
                    project_name = ""

                # Check if the project name is empty or just whitespace
                if not project_name or project_name == "":
                    print("No valid project name found.")
                    project_name = None  # Set to None if no valid project name
                else:
                    if project_name != last_project_name:
                        last_project_name = project_name  # Update the last project name
                        start_time = int(time.time())  # Reset the start time

            # Update the Discord Rich Presence if broadcasting is enabled
            if broadcasting:
                try:
                    if project_name:  # If a project is open
                        print(project_name)
                        RPC.update(
                            state="Working on a project",
                            details=project_name,  # Set the project name directly
                            large_image="ableton_image",  # Ensure this key matches your uploaded asset
                            large_text="Ableton Live",
                            start=start_time  # Set the start time for the timer
                        )
                    else:  # If no project is open
                        print("No project open")
                        RPC.update(
                            state="Not working on a project",
                            details="Cooking up new music",  # Default message when no project is open
                            large_image="ableton_image",  # Ensure this key matches your uploaded asset
                            large_text="Ableton Live"
                        )
                except Exception as e:
                    print(f"Error updating Rich Presence: {e}")  # Log the error to Terminal

        # Wait for a short period before checking again
        time.sleep(1)

    except FileNotFoundError:
        # If the file doesn't exist, wait for 1 second and try again
        print("File not found, retrying...")
        time.sleep(1)
    except Exception as e:
        # Handle any other exceptions
        print(f"An error occurred: {e}")
        time.sleep(5)