""" Commands.py

This module defines the command routing logic for Sentinel, allowing it to interpret and execute built-in commands without needing to involve the AI.
It includes functionality to launch applications based on voice commands, as well as handle system-level commands like shutdown, restart, sleep, and lock. 
The module also maintains a dictionary of known applications for faster access and can scan common directories to find executables when a command is issued.

Key components:
- launch_app_from_command: The main function that takes a command string, parses it,
and executes the appropriate action (launching an app or performing a system command). 
It also provides feedback through voice responses and updates the known applications dictionary for future use.


"""

import logging

from voice.voice import voice_of_ai
import subprocess
import os
import sys
import json
from voice.ears import listen
import time

DATA_FILE = "known_apps.json"

def load_known_apps():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)


def save_known_apps(apps):
    with open(DATA_FILE, 'w') as f:
        json.dump(apps, f, indent=4)



# Configuration
START_DIRS = [
    r"C:\Program Files",
    r"C:\Users\mskri\OneDrive\Desktop\Everything",
    r"C:\Program Files (x86)",
    r"C:\Users\%USERNAME%\AppData\Local",
    r"C:\Users\%USERNAME%\AppData\Roaming",
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
    r"C:\Users\%USERNAME%\AppData\Roaming\Microsoft\Windows\Start Menu\Programs" # Start Menu Programs
]

# Dictionary of known apps (Optional, for faster lookup without searching)
KNOWN_APPS = load_known_apps()

def launch_url_shortcut(path):
    with open(path, "r") as f:
        for line in f:
            if line.startswith("URL="):
                url = line.replace("URL=", "").strip()
                subprocess.Popen(f'start "" "{url}"', shell=True)
                return True

def find_and_open_app(app_name_or_path):
    """
    Tries to find and open an application.
    1. Checks dictionary.
    2. Checks PATH via where.exe.
    3. Scans Start Menu and Program Files.
    """
    
    # 1. Check Dictionary first (if it matches a known key or full path)
    if app_name_or_path in KNOWN_APPS:
        exe_path = KNOWN_APPS[app_name_or_path]
        if os.path.exists(exe_path):
            print(f"Found in Known Apps: {exe_path}")
            logging.info(f"Found in Known Apps: {exe_path}")
            return subprocess.Popen([exe_path], shell=True)
    
    # 2. Check if it looks like a full path already
    if os.path.exists(app_name_or_path):
        print(f"Found direct path: {app_name_or_path}")
        logging.info(f"Found direct path: {app_name_or_path}")
        return subprocess.Popen([app_name_or_path], shell=True)

    # 3. Try 'where.exe' (Windows only)
    if sys.platform.startswith("win"):
        try:
            result = subprocess.Popen(
                ["where.exe", app_name_or_path], 
                capture_output=True, 
                text=True, 
                check=False
            )
            if result.stdout.strip():
                # where.exe returns one path per line
                path = result.stdout.strip().split('\n')[0]
                if os.path.exists(path):
                    print(f"Found via where.exe: {path}")
                    logging.info(f"Found via where.exe: {path}")
                    return subprocess.Popen([path], shell=True)
        except Exception:
            pass

    # 4. Scan Directories (Start Menu, Program Files, etc.)
    # We search for the executable name (without .exe) or the full name
    search_name = app_name_or_path.lower().replace(".exe", "")
    search_name = search_name.replace(" ", "") # Remove spaces for filename matching

    print(f"Scanning directories for '{search_name}'...")
    logging.info(f"Scanning directories for '{search_name}'...")
    
    for base_dir in START_DIRS:
        # Expand %USERNAME%
        full_dir = os.path.expandvars(base_dir)
        if not os.path.exists(full_dir):
            continue

        for root, dirs, files in os.walk(full_dir):
            # Optimization: check filenames only, not deep inside subfolders unless necessary
            # But to be thorough, we check files in the immediate directory
            for file in files:
                file_lower = file.lower()

                if not (file_lower.endswith(".exe") or file_lower.endswith(".lnk") or file_lower.endswith(".url")):
                    continue

                name = file_lower.replace(".exe","").replace(".lnk","").replace(".url","")
                name = name.replace(" ", "")

                if search_name in name:
                    full_path = os.path.join(root, file)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):

                        print(f"Found via scan: {full_path}")
                        logging.info(f"[commands] Found via scan: {full_path}")\
                    
                        # --- UPDATED LOGIC: Add to dictionary and SAVE ---
                        clean_key = os.path.basename(full_path).lower().replace(".exe", "")
                        
                        # Only add if not already in the dict
                        if clean_key not in KNOWN_APPS:
                            KNOWN_APPS[clean_key] = full_path
                            print(f"  -> Added '{clean_key}' to known apps dictionary.")
                            # Save immediately to disk
                            save_known_apps(KNOWN_APPS)
                            print(f"  -> Saved to {DATA_FILE}")
                            
                        
                        if full_path.endswith(".url"):
                            launch_url_shortcut(full_path)
                        else:
                            subprocess.Popen(full_path, shell=True)
                        print(f"  -> Launched: {full_path}")
                        return True
    # 5. If still not found
    print("❌ Application not found.")
    return None

if __name__ == "__main__":
    app_name = input("Enter application name (e.g., chrome, notepad) or full path: ").strip()
    
    result = find_and_open_app(app_name)
    
    if result is None:
        print("\n❌ Application not found. Please provide the full directory path manually.")
        print("Example: C:\\Users\\YourName\\Downloads\\my_app.exe")
    else:
        print("\n✅ Application launched successfully.")

#COMMAND: open_chrome


def launch_app_from_command(command, emitter,bridge=None):

    command = command.replace("COMMAND:", "").strip().lower()

    # Normalize multi-word power commands BEFORE splitting
    command = command.replace("shut down", "shutdown")
    command = command.replace("put to sleep", "sleep")
    command = command.replace("suspend", "sleep")
    command = command.replace("hibernate", "sleep")

    parts = command.split()

    if len(parts) == 0:
        print("❌ Invalid command format")
        logging.warning("Invalid command format: empty command")
        return None

    action = parts[0]
    app_name = " ".join(parts[1:])

    if action == "open" or action == "launch" or action == "start":
        voice_of_ai(f"Opening {app_name}", emitter, bridge)
        print(f"🔍 Launching: {app_name}")
        return find_and_open_app(app_name)

    if action == "shutdown":
        voice_of_ai("Shutting down the system", emitter, bridge)
        subprocess.run(["shutdown", "/s", "/t", "5"])
        return True

    if action == "restart":
        voice_of_ai("Restarting the system", emitter, bridge)
        subprocess.run(["shutdown", "/r", "/t", "5"])
        return True

    if action == "sleep":
        voice_of_ai("Putting the system to sleep", emitter, bridge)
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        return True

    if action == "lock":
        voice_of_ai("Locking the computer", emitter, bridge)
        subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
        return True

    print("❌ Unsupported command:", action)
    logging.warning(f"Unsupported command: {action}")
    return None
    