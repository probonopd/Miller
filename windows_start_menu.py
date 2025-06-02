#!/usr/bin/env python3

import os, sys, shlex, subprocess

from PyQt6 import QtWidgets, QtGui, QtCore
from pylnk3 import Lnk
import win32com.client
from win32com.shell import shell, shellcon
import ctypes

from styling import Styling

icon_provider = QtWidgets.QFileIconProvider()

def resolve_shortcut(lnk_path):
    try:
        lnk = Lnk(lnk_path)
        return {
            "target": os.path.expandvars(lnk.path),
            "arguments": os.path.expandvars(lnk.arguments.strip()) if getattr(lnk, "arguments", None) else None,
            "icon": lnk.icon_location if getattr(lnk, "icon_location", None) else None
        }
    except Exception as e:
        print(f"Error resolving shortcut {lnk_path}: {e}")
        return {"target": None, "arguments": None, "icon": None}

def load_icon(path, fallback_path=None):
    if path:
        expanded_path = os.path.expandvars(path)
        if os.path.exists(expanded_path):
            if path.endswith(".exe"):
                return icon_provider.icon(QtCore.QFileInfo(path))
            else:
                return QtGui.QIcon(expanded_path)
    if fallback_path:
        expanded_fallback = os.path.expandvars(fallback_path)
        if os.path.exists(expanded_fallback):
            return icon_provider.icon(QtCore.QFileInfo(expanded_fallback))
    return QtGui.QIcon.fromTheme("application-x-executable")

def replace_placeholders(arguments, data):
    if arguments:
        target = data.get("target_path", "")
        arguments = arguments.replace("%1", target).replace("%s", target)
        return os.path.expandvars(arguments)
    return arguments

def launch_target(data):
    target_path = data.get("target_path")
    requires_admin = data.get("requires_admin", False)
    if not target_path or not os.path.exists(target_path):
        QtWidgets.QMessageBox.warning(None, "Launch Error", f"Target not found:\n{target_path}")
        return
    try:
        if requires_admin:
            print(f"[INFO] Launching as admin: {target_path}")
            # Launch with admin privileges using PowerShell
            subprocess.run([
                "powershell", "-Command",
                f'Start-Process "{target_path}" -Verb RunAs'
            ], check=False)
        else:
            print(f"[INFO] Launching normally: {target_path}")
            os.startfile(target_path)
    except Exception as e:
        QtWidgets.QMessageBox.warning(None, "Launch Error", f"Could not launch target:\n{e}")

def launch_folder(folder_path):
    try:
        subprocess.Popen(["explorer", os.path.normpath(folder_path)])
    except Exception as e:
        QtWidgets.QMessageBox.warning(None, "Open Folder Error", f"Could not open folder:\n{e}")

def menu_item_triggered():
    action = QtWidgets.QApplication.instance().sender()
    if action:
        data = action.data()
        if isinstance(data, dict):
            launch_target(data)
        else:
            launch_folder(data)

def folder_menu_hovered():
    menu = QtWidgets.QApplication.instance().sender()
    if menu and hasattr(menu, "path") and QtWidgets.QApplication.keyboardModifiers() != QtCore.Qt.KeyboardModifier.NoModifier:
        launch_folder(menu.path)

def is_shortcut_admin(lnk_path):
    """Detect if a shortcut requests admin privileges using Windows Shell verbs (no pefile)."""
    try:
        shell_app = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell_app.CreateShortcut(str(lnk_path))
        target = shortcut.TargetPath
        if not target or not os.path.exists(target):
            return False
        # Use Shell.Application to check for "run as administrator" verb
        shell_obj = win32com.client.Dispatch("Shell.Application")
        folder = shell_obj.NameSpace(os.path.dirname(target))
        if folder is None:
            return False
        item = folder.ParseName(os.path.basename(target))
        if item is None:
            return False
        verbs = [v.name for v in item.Verbs()]
        if any("run as administrator" in v.lower() for v in verbs):
            return True
    except Exception:
        pass
    return False

def is_exe_admin(exe_path):
    """Detect if an exe can be run as admin by checking for the 'run as administrator' verb."""
    try:
        shell_obj = win32com.client.Dispatch("Shell.Application")
        folder = shell_obj.NameSpace(os.path.dirname(exe_path))
        if folder is None:
            return False
        item = folder.ParseName(os.path.basename(exe_path))
        if item is None:
            return False
        verbs = [v.name for v in item.Verbs()]
        if any("run as administrator" in v.lower() for v in verbs):
            return True
    except Exception:
        pass
    return False

def add_items_from_directory(menu, directory, clear_first=True, recursive=True, add_folders=True):
    """
    Populates a menu with items from a directory.
    
    If add_folders is True, folder submenus are created.
    If add_folders is False, folders are not added to the menu as submenus, 
    only non-folder items (like .lnk and .exe files) are added.
    
    For submenus (clear_first=True), the menu is cleared each time it’s about to show,
    preventing duplicate entries.
    
    For the top-level menu (clear_first=False), items from multiple directories are accumulated.
    """
    if add_folders == False:
        exclude = ["folder", "install", "help", "uninstall", "manual", "readme", "license", "support", "sample", "example", ".txt", ".pdf"]
    else:
        exclude = []

    if not os.path.isdir(directory):
        return
    if clear_first:
        menu.clear()  # Only clear if we're dynamically repopulating a submenu.
    for entry in sorted(os.listdir(directory), key=str.lower):
        full_path = os.path.join(directory, entry)
        name, ext = os.path.splitext(entry)
        # If we encounter a folder and recursion is True...
        if os.path.isdir(full_path) and recursive:
            if add_folders:
                # Create a submenu for the folder
                submenu = menu.addMenu(name)
                submenu.setIcon(QtGui.QIcon.fromTheme("folder"))
                submenu.path = full_path
                submenu.installEventFilter(menu)  # Install event filter on submenu
                # Connect aboutToShow to repopulate the submenu dynamically.
                submenu.aboutToShow.connect(lambda m=submenu: add_items_from_directory(m, m.path, True, recursive, add_folders))
                submenu.hovered.connect(folder_menu_hovered)
            else:
                # Do not add a submenu for the folder; instead, merge its non-folder items into the current menu
                if not any(keyword in name.lower() for keyword in exclude):
                    print(full_path)
                    add_items_from_directory(menu, full_path, False, recursive, add_folders)
        elif entry.lower().endswith(".lnk"):
            shortcut_data = resolve_shortcut(full_path)
            if not any(keyword in name.lower() for keyword in exclude) and shortcut_data.get("target"):
                # Use admin detection from shortcut manifest/verbs
                requires_admin = is_shortcut_admin(full_path)
                action = QtGui.QAction(name, menu)
                action.setIcon(load_icon(shortcut_data.get("icon"), shortcut_data.get("target")))
                action.setData({
                    "target_path": shortcut_data.get("target"),
                    "arguments": shortcut_data.get("arguments"),
                    "requires_admin": requires_admin
                })
                action.triggered.connect(menu_item_triggered)
                menu.addAction(action)
        elif entry.lower().endswith(".exe"):
            if not any(keyword in name.lower() for keyword in exclude):
                # Use admin detection from exe manifest
                requires_admin = is_exe_admin(full_path)
                action = QtGui.QAction(name, menu)
                action.setIcon(load_icon(full_path))
                action.setData({
                    "target_path": full_path,
                    "arguments": None,
                    "requires_admin": requires_admin
                })
                action.triggered.connect(menu_item_triggered)
                menu.addAction(action)

class StartMenu(QtWidgets.QMenu):
    def __init__(self, parent=None, add_folders=True):
        super().__init__(parent)
        self.setIcon(load_icon(None, "application-x-executable"))
        if sys.platform == "win32":
            self.setIcon(QtGui.QIcon.fromTheme("ms-windows"))
        if self.icon().isNull():
            self.setIcon(QtGui.QIcon.fromTheme("folder"))

        self.aboutToShow.connect(self.populate_start_menu)
        self.add_folders = add_folders
        self.start_menu_dirs = [
            os.path.join(os.getenv("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs"),
            os.path.join(os.getenv("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
        ]
        
        self.key_sequence = ""
        self.key_timer = QtCore.QTimer()
        self.key_timer.setInterval(1000)  # 1 second to reset the key sequence
        self.key_timer.timeout.connect(self.reset_key_sequence)
        self.installEventFilter(self)

    def populate_start_menu(self):
        self.clear()  # Clear the entire menu on each opening

        # Add the .exe files in C:\Windows but not its subdirectories.
        # Create a submenu for the folder
        submenu = self.addMenu("Windows")
        submenu.setIcon(QtGui.QIcon.fromTheme("folder"))
        submenu.path = self, os.getenv("SystemRoot", "")
        submenu.installEventFilter(self)  # Install event filter on submenu
        # Connect aboutToShow to repopulate the submenu dynamically.
        submenu.aboutToShow.connect(lambda m=submenu: add_items_from_directory(submenu, os.getenv("SystemRoot", ""), clear_first=True, recursive=False, add_folders=self.add_folders))
        submenu.hovered.connect(folder_menu_hovered)
        
        # For the main (merged) start menu, accumulate items from each directory.
        for dir_path in filter(os.path.isdir, self.start_menu_dirs):
            add_items_from_directory(self, dir_path, clear_first=False, recursive=True, add_folders=self.add_folders)
        # Sort the menu items alphabetically (ignoring case)
        self.addActions(sorted(self.actions(), key=lambda a: a.text().lower()))
        # If a menu has no actions, disable it so it doesn't show up as an empty submenu.
        if not self.actions():
            self.setEnabled(False)

        # "Add or Remove Programs" (Control Panel)
        self.addSeparator()
        appwizaction = QtGui.QAction("Add or Remove Programs", self)
        # When selected, execute appwiz.cpl
        appwizaction.triggered.connect(lambda: os.startfile("appwiz.cpl"))
        self.addAction(appwizaction)
        self.addSeparator()

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.KeyPress:
            key = event.text().lower()
            if key.isalpha():
                self.key_sequence += key
                self.key_timer.start()  # Restart the timer on each key press
                self.select_menu_item()
                return True
        return super().eventFilter(obj, event)

    def reset_key_sequence(self):
        self.key_sequence = ""
        self.key_timer.stop()

    def select_menu_item(self):
        for action in self.actions():
            if action.text().lower().startswith(self.key_sequence):
                self.setActiveAction(action)
                break

class StartMenuWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Custom Merged Start Menu")
        self.resize(600, 400)
        menubar = self.menuBar()
        # Change the add_folders flag here (False will merge non-folder items recursively)
        self.start_menu = StartMenu(self, add_folders=True)
        menubar.addMenu(self.start_menu)
        menubar.setVisible(True)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    s = Styling(app)
    window = StartMenuWindow()
    window.show()
    sys.exit(app.exec())