

import subprocess
import os
import sys
import json

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
    r"C:\Program Files (x86)",
    r"C:\Users\%USERNAME%\AppData\Local",
    r"C:\Users\%USERNAME%\AppData\Roaming",
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs", # Start Menu Programs
]

# Dictionary of known apps (Optional, for faster lookup without searching)
KNOWN_APPS = load_known_apps()


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
            return subprocess.Popen([exe_path], shell=True)
    
    # 2. Check if it looks like a full path already
    if os.path.exists(app_name_or_path):
        print(f"Found direct path: {app_name_or_path}")
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
                    return subprocess.Popen([path], shell=True)
        except Exception:
            pass

    # 4. Scan Directories (Start Menu, Program Files, etc.)
    # We search for the executable name (without .exe) or the full name
    search_name = app_name_or_path.lower().replace(".exe", "")
    search_name = search_name.replace(" ", "") # Remove spaces for filename matching

    print(f"Scanning directories for '{search_name}'...")
    
    for base_dir in START_DIRS:
        # Expand %USERNAME%
        full_dir = os.path.expandvars(base_dir)
        if not os.path.exists(full_dir):
            continue

        for root, dirs, files in os.walk(full_dir):
            # Optimization: check filenames only, not deep inside subfolders unless necessary
            # But to be thorough, we check files in the immediate directory
            for file in files:
                if file.lower().replace(".exe","") == search_name or file == app_name_or_path:
                    full_path = os.path.join(root, file)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):

                        print(f"Found via scan: {full_path}")
                                
                        # --- UPDATED LOGIC: Add to dictionary and SAVE ---
                        clean_key = os.path.basename(full_path).lower().replace(".exe", "")
                        
                        # Only add if not already in the dict
                        if clean_key not in KNOWN_APPS:
                            KNOWN_APPS[clean_key] = full_path
                            print(f"  -> Added '{clean_key}' to known apps dictionary.")
                            # Save immediately to disk
                            save_known_apps(KNOWN_APPS)
                            print(f"  -> Saved to {DATA_FILE}")
                            
                        
                        subprocess.Popen([full_path], shell=True)
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


def launch_app_from_command(command):
    """
    Extract app name from command string and launch it.
    Example: "sentinal luanch chrome" -> "chrome"
    """
    # Remove command prefix if present
    app_name = command.removeprefix("COMMAND: open_")
  
    
    if not app_name:
        print("❌ No application specified in command.")
        return None
    
    print(f"🔍 Launching: {app_name}")
    return find_and_open_app(app_name)
