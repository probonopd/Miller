#!/usr/bin/env python3

import os, sys, shlex, subprocess

from PyQt6 import QtWidgets, QtGui, QtCore
from pylnk3 import Lnk

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
            return QtGui.QIcon(expanded_path)
    if fallback_path:
        expanded_fallback = os.path.expandvars(fallback_path)
        if os.path.exists(expanded_fallback):
            icon_provider = QtWidgets.QFileIconProvider()
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
    if not target_path or not os.path.exists(target_path):
        QtWidgets.QMessageBox.warning(None, "Launch Error", f"Target not found:\n{target_path}")
        return
    try:
        arguments = replace_placeholders(data.get("arguments"), data)
        subprocess.Popen([target_path] + shlex.split(arguments) if arguments else [target_path])
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

def add_items_from_directory(menu, directory, clear_first=True):
    """
    Populates a menu with items from a directory.
    For submenus (clear_first=True), the menu is cleared each time it’s about to show,
    preventing duplicate entries.
    For the top-level menu (clear_first=False), items from multiple directories are accumulated.
    """
    if not os.path.isdir(directory):
        return
    if clear_first:
        menu.clear()  # Only clear if we're dynamically repopulating a submenu.
    for entry in sorted(os.listdir(directory), key=str.lower):
        full_path = os.path.join(directory, entry)
        name = os.path.splitext(entry)[0]
        if os.path.isdir(full_path):
            submenu = menu.addMenu(name)
            submenu.setIcon(QtGui.QIcon.fromTheme("folder"))
            submenu.path = full_path
            # For dynamic submenus, connect aboutToShow with clear_first=True so that they refresh each time.
            submenu.aboutToShow.connect(lambda m=submenu: add_items_from_directory(m, m.path, True))
            submenu.hovered.connect(folder_menu_hovered)
        elif entry.lower().endswith(".lnk"):
            shortcut_data = resolve_shortcut(full_path)
            action = QtGui.QAction(name, menu)
            action.setIcon(load_icon(shortcut_data.get("icon"), shortcut_data.get("target")))
            action.setData({"target_path": shortcut_data.get("target"), "arguments": shortcut_data.get("arguments")})
            action.triggered.connect(menu_item_triggered)
            menu.addAction(action)
        elif entry.lower().endswith(".exe"):
            action = QtGui.QAction(name, menu)
            action.setIcon(load_icon(full_path))
            action.setData({"target_path": full_path, "arguments": None})
            action.triggered.connect(menu_item_triggered)
            menu.addAction(action)

class StartMenu(QtWidgets.QMenu):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIcon(load_icon(None, "application-x-executable"))
        if sys.platform == "win32":
            self.setIcon(QtGui.QIcon.fromTheme("ms-windows"))
        if self.icon().isNull():
            self.setIcon(QtGui.QIcon.fromTheme("folder"))
        self.aboutToShow.connect(self.populate_start_menu)
        self.start_menu_dirs = [
            os.path.join(os.getenv("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs"),
            os.path.join(os.getenv("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
        ]
    
    def populate_start_menu(self):
        self.clear()  # Clear the entire menu on each opening
        # For the main (merged) start menu, accumulate items from each directory.
        for dir_path in filter(os.path.isdir, self.start_menu_dirs):
            add_items_from_directory(self, dir_path, clear_first=False)
        # Sort the menu items alphabetically (ignoring case)
        self.addActions(sorted(self.actions(), key=lambda a: a.text().lower()))

class StartMenuWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Custom Merged Start Menu")
        self.resize(600, 400)

        menubar = self.menuBar()
        self.start_menu = StartMenu(self)
        menubar.addMenu(self.start_menu)
        menubar.setVisible(True)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = StartMenuWindow()
    window.show()
    sys.exit(app.exec())
