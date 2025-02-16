#!/usr/bin/env python3
import sys, os, subprocess, venv, time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, "venv")
SIRACUSA_SCRIPT = os.path.join(BASE_DIR, "siracusa.py")
REQUIREMENTS_FILE = os.path.join(BASE_DIR, "requirements-windows.txt") if sys.platform == "win32" else os.path.join(BASE_DIR, "requirements-linux.txt")

def main():
    timestamp = lambda: time.strftime("[%H:%M:%S]", time.localtime())
    print(f"{timestamp()} Starting setup process...")

    # Ensure pip is installed on systems that require a system-level install
    print(f"{timestamp()} Install pip...")
    if os.path.exists("/etc/debian_version"):
        print(f"{timestamp()} Installing pip for Debian/Ubuntu...")
        if os.system("sudo apt update") != 0 or os.system("sudo apt install -y python3-pip python3-requests") != 0:
            print(f"{timestamp()} ❌ Error: Failed to install pip on Debian/Ubuntu.")
            sys.exit(1)
    elif os.path.exists("/etc/redhat-release"):
        print(f"{timestamp()} Installing pip for Fedora/RedHat...")
        if os.system("sudo dnf install -y python3-pip") != 0:
            print(f"{timestamp()} ❌ Error: Failed to install pip on Fedora/RedHat.")
            sys.exit(1)
    elif os.path.exists("/etc/SuSE-release"):
        print(f"{timestamp()} Installing pip for SUSE...")
        if os.system("sudo zypper install -y python3-pip") != 0:
            print(f"{timestamp()} ❌ Error: Failed to install pip on SUSE.")
            sys.exit(1)
    elif os.path.exists("/etc/arch-release"):
        print(f"{timestamp()} Installing pip for Arch/Arch-based...")
        if os.system("sudo pacman -S --noconfirm python-pip") != 0:
            print(f"{timestamp()} ❌ Error: Failed to install pip on Arch.")
            sys.exit(1)
    elif os.path.exists("/etc/gentoo-release"):
        print(f"{timestamp()} Installing pip for Gentoo...")
        if os.system("sudo emerge -av app-admin/python-updater") != 0:
            print(f"{timestamp()} ❌ Error: Failed to install pip on Gentoo.")
            sys.exit(1)
    elif os.path.exists("/etc/alpine-release"):
        print(f"{timestamp()} Installing pip for Alpine...")
        if os.system("sudo apk add py3-pip py3-requests py3-pyqt6") != 0:
            print(f"{timestamp()} ❌ Error: Failed to install pip on Alpine.")
            sys.exit(1)
    # Chimera Linunx
    elif os.path.exists("/etc/chimera-release"):
        print(f"{timestamp()} Installing pip for Chimera...")
        if os.system("apk add git python-pip python-requests python-pyqt6") != 0:
            print(f"{timestamp()} ❌ Error: Failed to install pip on Chimera.")
            sys.exit(1)
    elif sys.platform == "darwin":
        print(f"{timestamp()} Installing pip for MacOS...")
        if os.system("brew install python3") != 0:
            print(f"{timestamp()} ❌ Error: Failed to install pip on MacOS.")
            sys.exit(1)
    
    # Check requirements file
    if not os.path.exists(REQUIREMENTS_FILE):
        print(f"{timestamp()} Error: The requirements file '{REQUIREMENTS_FILE}' is missing.")
        sys.exit(1)
    
    # Create virtual environment if needed
    if not os.path.exists(VENV_DIR):
        print(f"{timestamp()} Creating virtual environment...")
        venv.create(VENV_DIR, with_pip=True, system_site_packages=True)
        print(f"{timestamp()} Virtual environment created at {VENV_DIR}.")
    else:
        print(f"{timestamp()} Virtual environment already exists.")
    
    # Install dependencies
    pip_path = os.path.join(VENV_DIR, "Scripts", "pip.exe") if sys.platform == "win32" else os.path.join(VENV_DIR, "bin", "pip")
    if not os.path.exists(pip_path):
        print(f"{timestamp()} Error: pip is missing in the virtual environment.")
        print(f"{timestamp()} Please delete the 'venv' directory and run the script again.")
        sys.exit(1)
    
    print(f"{timestamp()} Installing dependencies from {REQUIREMENTS_FILE}...")
    result = subprocess.run([pip_path, "install", "-r", REQUIREMENTS_FILE], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"{timestamp()} ❌ Error: Installation failed. Details:\n{result.stderr}")
        sys.exit(1)
    print(f"{timestamp()} ✅ Dependencies installed successfully!")


    if not os.path.exists("icons/elementary-xfce"):
        print(f"{timestamp()} Downloading icons...")
        import requests
        url = "http://archive.ubuntu.com/ubuntu/pool/universe/x/xubuntu-artwork/xubuntu-artwork_16.04.2.tar.xz"
        filename = url.split("/")[-1]
        response = requests.get(url)
        with open(filename, "wb") as f:
            f.write(response.content)
        print(f"{timestamp()} Downloaded 'xubuntu-artwork_16.04.2.tar.xz' from {url}")
        if not os.path.exists("icons"):
            os.makedirs("icons")
        # Unpack but only the subdirectory elementary-xfce to icons/
        print(f"{timestamp()} Extracting icons...")
        import tarfile
        with tarfile.open(filename, "r:xz") as tar:
            # Extract "trunk/usr/share/icons/elementary-xfce" to "icons/elementary-xfce" (need to strip the first directories)
            for member in tar.getmembers():
                if member.name.startswith("trunk/usr/share/icons/elementary-xfce"):
                    member.name = member.name.replace("trunk/usr/share/icons/", "")
                    tar.extract(member, path="icons/")
        print(f"{timestamp()} Extracted 'elementary-xfce' to 'icons/'")
        os.remove(filename)

    # Fonts
    if not sys.platform == "win32":
        if not os.path.exists("fonts/Inter-Regular.ttf") or not os.path.exists("fonts/Inter-Bold.ttf") or not os.path.exists("fonts/Inter-Italic.ttf") or not os.path.exists("fonts/Inter-BoldItalic.ttf"):
            print(f"{timestamp()} Downloading fonts...")
            import requests
            urls = [
                "https://github.com/rdey/rdey-packages/raw/refs/heads/master/design/fonts/Inter-Regular.ttf",
                "https://github.com/rdey/rdey-packages/raw/refs/heads/master/design/fonts/Inter-Bold.ttf",
                "https://github.com/rdey/rdey-packages/raw/refs/heads/master/design/fonts/Inter-Italic.ttf",
                "https://github.com/rdey/rdey-packages/raw/refs/heads/master/design/fonts/Inter-BoldItalic.ttf"
            ]
            if not os.path.exists("fonts"):
                os.makedirs("fonts")
            for url in urls:
                filename = url.split("/")[-1]
                response = requests.get(url)
                with open(os.path.join("fonts", filename), "wb") as f:
                    f.write(response.content)
                print(f"{timestamp()} Downloaded '{filename}' from {url}")
            print(f"{timestamp()} Downloaded fonts to 'fonts/'")
    
    # If we are on Linux, create /usr/share/wayland-sessions/ and create .desktop file that runs start-siracusa.sh
    if not sys.platform == "win32":
        print(f"{timestamp()} Creating desktop entry for Wayland...")
        desktop_entry = """[Desktop Entry]
Name=Spatial
Comment=Spatial Desktop Environment
Exec=/usr/bin/startspatial-wayland
Type=Application
DesktopNames=Spatial
"""

        # Check whether /usr/share/wayland-sessions/ exists or /usr/local/share/wayland-sessions/ exists and create the file there if it does
        if os.path.exists("/usr/share/wayland-sessions/"):
            with open("/usr/share/wayland-sessions/spatial.desktop", "w") as f:
                f.write(desktop_entry)
        elif os.path.exists("/usr/local/share/wayland-sessions/"):
            with open("/usr/local/share/wayland-sessions/spatial.desktop", "w") as f:
                f.write(desktop_entry)
        else:
            print(f"{timestamp()} ❌ Error: Could not find /usr/share/wayland-sessions/ or /usr/local/share/wayland-sessions/")
            sys.exit(1)
        
        start_spatial = """#!/bin/sh

# Set environment variables
export XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=MyWaylandDE

# Start the Wayland compositor in the background
kwin_wayland --xwayland &

# Launch the desktop environment's session manager or panel
@@@PLACEHOLDER@@@
"""
        start_spatial = start_spatial.replace("@@@PLACEHOLDER@@@", os.path.abspath(os.path.join(VENV_DIR, "bin", "python")) + " " +  os.path.abspath(SIRACUSA_SCRIPT))
        with open("/usr/bin/startspatial-wayland", "w") as f:
            f.write(start_spatial)
        os.chmod("/usr/bin/startspatial-wayland", 0o755)
        print(f"{timestamp()} ✅ Desktop session file created successfully!")

    # Run siracusa.py
    if not os.path.exists(SIRACUSA_SCRIPT):
        print(f"{timestamp()} Error: The script '{SIRACUSA_SCRIPT}' is missing.")
        sys.exit(1)
    
    python_executable = os.path.join(VENV_DIR, "Scripts", "python.exe") if sys.platform == "win32" else os.path.join(VENV_DIR, "bin", "python")
    if not os.path.exists(python_executable):
        print(f"{timestamp()} Error: Python executable not found in virtual environment.")
        sys.exit(1)
    
    print(f"{timestamp()} Running '{SIRACUSA_SCRIPT}' inside virtual environment...")
    result = subprocess.run([python_executable, SIRACUSA_SCRIPT], text=True)
    if result.returncode != 0:
        print(f"{timestamp()} ❌ Error: 'siracusa.py' exited with code {result.returncode}")
        sys.exit(1)
    print(f"{timestamp()} ✅ 'siracusa.py' executed successfully!")

if __name__ == "__main__":
    main()
