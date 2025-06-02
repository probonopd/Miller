#!/usr/bin/env python3

import sys
import os
import subprocess
import win32com.client
from PyQt6 import QtWidgets, QtGui, QtCore

from styling import Styling

icon_provider = QtWidgets.QFileIconProvider()

def resolve_shortcut(lnk_path):
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(lnk_path))
        return {
            "target": shortcut.TargetPath,
            "arguments": shortcut.Arguments,
            "icon": shortcut.IconLocation if shortcut.IconLocation else shortcut.TargetPath
        }
    except Exception:
        return {"target": None, "arguments": None, "icon": None}

def load_icon(path, fallback_path=None):
    if path:
        expanded_path = os.path.expandvars(path)
        if os.path.exists(expanded_path):
            return icon_provider.icon(QtCore.QFileInfo(expanded_path))
    if fallback_path and os.path.exists(fallback_path):
        return icon_provider.icon(QtCore.QFileInfo(fallback_path))
    return QtGui.QIcon.fromTheme("application-x-executable")

def launch_target(target, arguments=None):
    if not target or not os.path.exists(target):
        QtWidgets.QMessageBox.warning(None, "Launch Error", f"Target not found:\n{target}")
        return
    try:
        if arguments:
            subprocess.Popen([target] + arguments.split())
        else:
            os.startfile(target)
    except Exception as e:
        QtWidgets.QMessageBox.warning(None, "Launch Error", f"Could not launch target:\n{e}")

def launch_folder(folder_path):
    try:
        subprocess.Popen(["explorer", os.path.normpath(folder_path)])
    except Exception as e:
        QtWidgets.QMessageBox.warning(None, "Open Folder Error", f"Could not open folder:\n{e}")

def menu_item_triggered():
    action = QtWidgets.QApplication.instance().sender()
    data = action.data()
    if isinstance(data, dict):
        launch_target(data.get("target"), data.get("arguments"))
    elif isinstance(data, str):
        launch_folder(data)

def sort_menu_actions(menu):
    actions = [a for a in menu.actions() if not a.isSeparator()]
    separators = [a for a in menu.actions() if a.isSeparator()]
    # Sort all actions (submenus and normal actions) together by text
    actions.sort(key=lambda a: a.text().lower())
    for a in menu.actions():
        menu.removeAction(a)
    for a in actions:
        menu.addAction(a)
    for a in separators:
        menu.addAction(a)

def add_items_from_directory(menu, directory, recursive=True):
    if not os.path.isdir(directory):
        return
    for entry in sorted(os.listdir(directory), key=str.lower):
        full_path = os.path.join(directory, entry)
        name, ext = os.path.splitext(entry)
        if os.path.isdir(full_path) and recursive:
            submenu = menu.addMenu(name)
            submenu.setIcon(QtGui.QIcon.fromTheme("folder"))
            submenu.setToolTip(full_path)  # Set tooltip for folder
            add_items_from_directory(submenu, full_path, recursive)
            sort_menu_actions(submenu)
        elif entry.lower().endswith(".lnk"):
            shortcut_data = resolve_shortcut(full_path)
            if shortcut_data.get("target"):
                action = QtGui.QAction(name, menu)
                action.setIcon(load_icon(shortcut_data.get("icon"), shortcut_data.get("target")))
                action.setData({"target": shortcut_data.get("target"), "arguments": shortcut_data.get("arguments")})
                action.setToolTip(shortcut_data.get("target"))  # Tooltip with resolved path
                action.triggered.connect(menu_item_triggered)
                menu.addAction(action)
        elif entry.lower().endswith(".exe"):
            action = QtGui.QAction(name, menu)
            action.setIcon(load_icon(full_path))
            action.setData({"target": full_path, "arguments": None})
            action.setToolTip(full_path)  # Tooltip with exe path
            action.triggered.connect(menu_item_triggered)
            menu.addAction(action)
    sort_menu_actions(menu)

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
        self.key_sequence = ""
        self.key_timer = QtCore.QTimer()
        self.key_timer.setInterval(1000)  # 1 second to reset the key sequence
        self.key_timer.timeout.connect(self.reset_key_sequence)
        # Remove event filter, not needed
        # self.installEventFilter(self)
        self.setToolTipsVisible(True)

    def populate_start_menu(self):
        self.clear()
        for dir_path in filter(os.path.isdir, self.start_menu_dirs):
            add_items_from_directory(self, dir_path, recursive=True)
        sort_menu_actions(self)
        # Add a few builtin items
        self.addSeparator()
        for name, path in [
            ("Control Panel", "control.exe"),
            ("Notepad", "notepad.exe"),
            ("Device Manager", "devmgmt.msc")
        ]:
            action = QtGui.QAction(name, self)
            action.setIcon(load_icon(path))
            action.setData({"target": path, "arguments": None})
            action.setToolTip(path)
            action.triggered.connect(menu_item_triggered)
            self.addAction(action)
        self.addSeparator()
        # --- Always add Windows Terminal (cmd) entries, regardless of wt.exe existence ---
        wt_path = os.path.expandvars(r"wt.exe")
        # Find full path to powershell.exe
        pwsh_path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
        if not os.path.exists(pwsh_path):
            pwsh_path = "powershell.exe"
        action_wt_cmd = QtGui.QAction("Windows Terminal", self)
        action_wt_cmd.setIcon(load_icon(wt_path))
        action_wt_cmd.setData({"target": wt_path, "arguments": "cmd"})
        action_wt_cmd.setToolTip(f"{wt_path} cmd")
        action_wt_cmd.triggered.connect(menu_item_triggered)
        self.addAction(action_wt_cmd)
        action_wt_cmd_admin = QtGui.QAction("Windows Terminal (Admin)", self)
        action_wt_cmd_admin.setIcon(load_icon(wt_path))
        action_wt_cmd_admin.setData({
            "target": pwsh_path,
            "arguments": f'-Command Start-Process \'{wt_path}\' -ArgumentList \'cmd\' -Verb RunAs'
        })
        action_wt_cmd_admin.setToolTip(f"Run as Administrator: {wt_path} cmd")
        action_wt_cmd_admin.triggered.connect(menu_item_triggered)
        self.addAction(action_wt_cmd_admin)
        self.addSeparator()

    # Remove eventFilter, override keyPressEvent instead
    def keyPressEvent(self, event):
        key = event.text().lower()
        if key.isalpha():
            self.key_sequence += key
            self.key_timer.start()
            self.select_menu_item()
            event.accept()
        else:
            super().keyPressEvent(event)

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
        self.setWindowTitle("Custom Hierarchical Start Menu")
        self.resize(600, 400)
        menubar = self.menuBar()
        self.start_menu = StartMenu(self)
        menubar.addMenu(self.start_menu)
        menubar.setVisible(True)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    s = Styling(app)
    window = StartMenuWindow()
    window.show()
    sys.exit(app.exec())
