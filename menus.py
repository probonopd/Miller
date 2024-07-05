#!/usr/bin/env python3

"""
Menu creation module for Miller Columns File Manager application.

This module provides functions to create the main application menu bar and add menus,
including File, Edit, Go, and Help menus with respective actions and event connections.
"""

import os
from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QIcon, QAction

def create_menus(window):
    """
    Create the main application menu bar and add menus.
    """
    menubar = window.menuBar()

    # File menu
    file_menu = menubar.addMenu("File")
    close_action = QAction("Close", window)
    close_action.triggered.connect(window.close)
    if os.name == 'nt':
        import windows_integration
        map_drive_action = QAction("Map Network Drive", window)
        map_drive_action.triggered.connect(windows_integration.map_network_drive)
        unmap_drive_action = QAction("Unmap Network Drive", window)
        unmap_drive_action.triggered.connect(windows_integration.unmap_network_drive)
    quit_action = QAction("Quit", window)
    quit_action.triggered.connect(window.quit_application)
    file_menu.addAction(close_action)
    file_menu.addSeparator()
    if os.name == 'nt':
        file_menu.addAction(map_drive_action)
        file_menu.addAction(unmap_drive_action)
        file_menu.addSeparator()
    file_menu.addAction(quit_action)

    # Edit menu
    edit_menu = menubar.addMenu("Edit")
    window.undo_action = QAction("Undo", window)
    window.undo_action.setEnabled(False)
    window.cut_action = QAction("Cut", window)
    window.cut_action.setEnabled(False)
    window.copy_action = QAction("Copy", window)
    window.copy_action.setEnabled(False)
    window.paste_action = QAction("Paste", window)
    window.paste_action.setEnabled(False)
    window.move_to_trash_action = QAction("Move to Trash", window)
    window.move_to_trash_action.setEnabled(False)
    window.delete_action = QAction("Delete", window)
    window.delete_action.setEnabled(False)
    window.empty_trash_action = QAction("Empty Trash", window)
    window.empty_trash_action.setEnabled(False)
    window.empty_trash_action.triggered.connect(window.empty_trash)

    edit_menu.addAction(window.undo_action)
    edit_menu.addSeparator()
    edit_menu.addAction(window.cut_action)
    edit_menu.addAction(window.copy_action)
    edit_menu.addAction(window.paste_action)
    edit_menu.addSeparator()
    edit_menu.addAction(window.move_to_trash_action)
    edit_menu.addAction(window.delete_action)
    edit_menu.addSeparator()
    edit_menu.addAction(window.empty_trash_action)

    # Go menu
    go_menu = menubar.addMenu("Go")
    home_action = QAction("Home", window)
    home_action.triggered.connect(window.go_home)
    trash_action = QAction("Trash", window)
    trash_action.triggered.connect(window.go_trash)
    go_menu.addAction(home_action)
    go_menu.addAction(trash_action)
    go_menu.addSeparator()

    if os.name == 'nt':
        from windows_map_drives import get_drive_letters
        for drive in get_drive_letters():
            drive_action = QAction(drive, window)
            drive_action.triggered.connect(lambda checked, d=drive: window.go_drive(d))
            go_menu.addAction(drive_action)
        go_menu.addSeparator()

    # Help menu
    help_menu = menubar.addMenu("Help")
    about_action = QAction("About", window)
    about_action.triggered.connect(window.show_about)
    help_menu.addAction(about_action)
