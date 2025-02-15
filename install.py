
#!/usr/bin/env python3

import sys
import os
import subprocess
import venv
import threading
import time

# Configurations
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, "venv")
SIRACUSA_SCRIPT = os.path.join(BASE_DIR, "siracusa.py")
REQUIREMENTS_FILE = (
    os.path.join(BASE_DIR, "requirements-windows.txt")
    if sys.platform == "win32"
    else os.path.join(BASE_DIR, "requirements-linux.txt")
)

# Function to log messages with timestamps
def log(message):
    timestamp = time.strftime("[%H:%M:%S]", time.localtime())
    print(f"{timestamp} {message}")

# Function to create a virtual environment if it doesn't exist
def create_virtual_env():
    if not os.path.exists(VENV_DIR):
        log("Creating virtual environment...")
        venv.create(VENV_DIR, with_pip=True)
        log(f"Virtual environment created at {VENV_DIR}.")
    else:
        log("Virtual environment already exists.")

# Function to install dependencies
def install_dependencies():
    if not os.path.exists(REQUIREMENTS_FILE):
        log(f"Error: The requirements file '{REQUIREMENTS_FILE}' is missing.")
        return False

    create_virtual_env()

    # Path to the pip executable inside the virtual environment
    pip_path = (
        os.path.join(VENV_DIR, "Scripts", "pip.exe")
        if sys.platform == "win32"
        else os.path.join(VENV_DIR, "bin", "pip")
    )

    if not os.path.exists(pip_path):
        log("Error: pip is missing in the virtual environment.")
        return False

    log(f"Installing dependencies from {REQUIREMENTS_FILE}...")
    
    result = subprocess.run(
        [pip_path, "install", "-r", REQUIREMENTS_FILE],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        log("✅ Installation completed successfully!")
        return True
    else:
        log(f"❌ Error: Installation failed. Details:\n{result.stderr}")
        return False

# Function to run siracusa.py inside the virtual environment
def run_siracusa():
    if not os.path.exists(SIRACUSA_SCRIPT):
        log(f"Error: The script '{SIRACUSA_SCRIPT}' is missing.")
        return

    python_executable = (
        os.path.join(VENV_DIR, "Scripts", "python.exe")
        if sys.platform == "win32"
        else os.path.join(VENV_DIR, "bin", "python")
    )

    if not os.path.exists(python_executable):
        log("Error: Python executable not found in virtual environment.")
        return

    log(f"Running '{SIRACUSA_SCRIPT}' inside virtual environment...")
    result = subprocess.run([python_executable, SIRACUSA_SCRIPT], text=True)

    if result.returncode == 0:
        log("✅ 'siracusa.py' executed successfully!")
    else:
        log(f"❌ Error: 'siracusa.py' exited with code {result.returncode}")

# Function to execute installation and run the script
def main():
    log("Starting setup process...")
    
    install_thread = threading.Thread(target=install_dependencies, daemon=True)
    install_thread.start()
    install_thread.join()  # Wait for installation to complete
    
    run_siracusa()  # Run siracusa.py after dependencies are installed

if __name__ == "__main__":
    main()
