#!/usr/bin/env python3

"""
Script for interacting with Windows context menus using PyQt6 and win32com.

This script provides a function to show a context menu for a given file or folder path.
The context menu is constructed in Qt and is populated with the available verbs.
When a verb is selected, it is executed using the win32com library.
"""

import os
from pathlib import Path
from typing import Sequence

from PyQt6.QtGui import QAction, QIcon, QCursor
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox

import win32com.client


def _safe_path_parse(file_path) -> Path:
    """Safely parse a file path to a Path object."""
    return Path(file_path)


def show_context_menu(paths):
    """
    Show the appropriate context menu.

    Args:
        paths (Sequence[os.PathLike | str]): The paths for which to show the context menu.
    """
    if isinstance(paths, (str, os.PathLike)):
        paths = [_safe_path_parse(paths)]
    elif isinstance(paths, list):
        paths = [_safe_path_parse(p) for p in paths]
    else:
        return
    
    if not paths:
        print("No usable paths provided.")
        return

    menu = QMenu()

    shell = win32com.client.Dispatch("Shell.Application")
    items = [shell.NameSpace(str(p.parent)).ParseName(p.name) for p in paths]

    print(f"Paths: {paths}")

    # Populate context menu with verbs
    # FIXME: Handle multiple items; currently only the first item is used. This might mean that we need to get the Verbs in a different way?
    # TODO: Check if https://github.com/NickHugi/PyKotor/blob/master/Libraries/Utility/src/utility/system/windows_context_menu.py handles multiple items better
    # May need to take a look at SHMultiFileProperties and https://stackoverflow.com/a/34551988/1839209.
    if items[0] is None:
        print("Could not retrieve context menu items.")
        return
    verbs = items[0].Verbs()
    if verbs is not None:
        for verb in verbs:
            if verb.Name:
                app = QApplication.instance()
                action = QAction(verb.Name, app)
                # Copying the path does not work using the default context menu action,
                # hence we override it
                # FIXME: Find a way that works independently of the language
                if "path" in verb.Name or "Pfad" in verb.Name:
                    # Copy path to clipboard
                    action.triggered.connect(lambda _, p=paths[0]: copy_path_to_clipboard(p))
                else:
                    action.triggered.connect(lambda _, v=verb: execute_verb(v))
                menu.addAction(action)
            else:
                menu.addSeparator()

    menu.exec(QCursor.pos())

def copy_path_to_clipboard(path):
    """
    Copy the specified path to the clipboard.
    """
    print(f"Copying path to clipboard: {path}")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.clipboard().setText(str(path))


def execute_verb(verb):
    """
    Execute the specified verb.

    Args:
        verb: The verb to execute.
    """
    print(f"Executing verb: {verb.Name}")
    try:
        verb.DoIt()
    except Exception as e:
        show_error_message(f"An error occurred while executing the action: {e}")

def show_error_message(message):
    """
    Display an error message.

    Args:
        message (str): The error message to display.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Critical)
    msg_box.setText("An error occurred.")
    msg_box.setInformativeText(message)
    msg_box.setWindowTitle("Error")
    msg_box.exec()


if __name__ == "__main__":
    app = QApplication([])

    # Example with multiple file paths
    multiple_files = [
        r"C:\Windows\System32\notepad.exe",
        r"C:\Windows\System32\calc.exe",
    ]
    show_context_menu(multiple_files)
   
    # Example with a folder path
    folderpath = r"C:\Windows\System32"
    show_context_menu(folderpath)

    # Example with a file path
    filepath = r"C:\Windows\System32\notepad.exe"
    show_context_menu(filepath)