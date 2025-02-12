#!/usr/bin/env python3

"""
Menu creation module.

This module provides functions to create the main application menu bar and add menus,
including File, Edit, Go, and Help menus with respective actions and event connections.
"""

import os, sys

from PyQt6 import  QtGui, QtCore, QtWidgets

def create_menus(window):
    """
    Create the main application menu bar and add menus.
    """
    menubar = window.menuBar()

    # File menu
    file_menu = menubar.addMenu("File")

    new_folder_action = QtGui.QAction("New Folder", window)
    new_folder_action.setShortcut("Ctrl+Shift+N")
    new_folder_action.triggered.connect(window.new_folder)
    file_menu.addAction(new_folder_action)
    file_menu.addSeparator()

    get_info_action = QtGui.QAction("Get Info...", window)
    get_info_action.setShortcut("Ctrl+I")
    get_info_action.triggered.connect(window.get_info)
    file_menu.addAction(get_info_action)
    file_menu.addSeparator()

    if os.name == 'nt':
        import windows_integration
        map_drive_action = QtGui.QAction("Map Network Drive", window)
        map_drive_action.triggered.connect(windows_integration.map_network_drive)
        unmap_drive_action = QtGui.QAction("Unmap Network Drive", window)
        unmap_drive_action.triggered.connect(windows_integration.unmap_network_drive)

        file_menu.addSeparator()
        file_menu.addAction(map_drive_action)
        file_menu.addAction(unmap_drive_action)
        file_menu.addSeparator()

    close_action = QtGui.QAction("Close", window)
    close_action.setShortcut("Ctrl+W")
    close_action.triggered.connect(window.close)
    file_menu.addAction(close_action)

    # Edit Menu
    edit_menu = menubar.addMenu("Edit")

    undo_action = QtGui.QAction("Undo", window)
    undo_action.setShortcut("Ctrl+Z")
    edit_menu.addAction(undo_action)
    edit_menu.addSeparator()

    cut_action = QtGui.QAction("Cut", window)
    cut_action.setShortcut("Ctrl+X")
    edit_menu.addAction(cut_action)

    copy_action = QtGui.QAction("Copy", window)
    copy_action.setShortcut("Ctrl+C")
    edit_menu.addAction(copy_action)

    window.paste_action = QtGui.QAction("Paste", window)
    window.paste_action.setShortcut("Ctrl+V")
    edit_menu.addAction(window.paste_action)
    edit_menu.addSeparator()

    delete_action = QtGui.QAction("Delete", window)
    delete_action.setShortcut("Delete")
    edit_menu.addAction(delete_action)

    select_all_action = QtGui.QAction("Select All", window)
    select_all_action.setShortcut("Ctrl+A")
    edit_menu.addAction(select_all_action)

    empty_trash_action = QtGui.QAction("Empty Trash", window)
    empty_trash_action.setEnabled(False)
    edit_menu.addAction(empty_trash_action)

    move_to_trash_action = QtGui.QAction("Move to Trash", window)
    move_to_trash_action.setEnabled(False)
    edit_menu.addAction(move_to_trash_action)
    
    if isinstance(window, QtWidgets.QMainWindow) and hasattr(window, 'selectionChanged'):
        copy_action.triggered.connect(window.copy_selected)
        cut_action.triggered.connect(window.cut_selected)
        window.paste_action.triggered.connect(window.paste_items)
        delete_action.triggered.connect(window.delete_selected)
        select_all_action.triggered.connect(window.select_all)
        empty_trash_action.triggered.connect(window.empty_trash)
        move_to_trash_action.triggered.connect(window.move_to_trash)
        
        window.selectionChanged.connect(lambda: cut_action.setEnabled(window.has_selected_items()))
        window.selectionChanged.connect(lambda: copy_action.setEnabled(window.has_selected_items()))
        window.selectionChanged.connect(lambda: delete_action.setEnabled(window.has_selected_items()))
        window.selectionChanged.connect(lambda: empty_trash_action.setEnabled(window.has_trash_items()))
        window.selectionChanged.connect(lambda: move_to_trash_action.setEnabled(window.has_selected_items()))
        
        cut_action.setEnabled(False)
        copy_action.setEnabled(False)
        window.paste_action.setEnabled(False)
        delete_action.setEnabled(False)
        
    # Go menu
    window.go_menu = menubar.addMenu("Go")
    home_action = QtGui.QAction("Home", window)
    home_action.setShortcut("Ctrl+Shift+H")
    home_action.triggered.connect(window.go_home)
    trash_action = QtGui.QAction("Trash", window)
    trash_action.triggered.connect(window.go_trash)
    trash_action.setShortcut("Ctrl+Shift+T")
    window.go_menu.addAction(home_action)
    window.go_menu.addAction(trash_action)
    window.go_menu.addSeparator()

    if sys.platform == "win32":
        run_action = QtGui.QAction("Run...", window)
        run_action.triggered.connect(run_dialog)
        window.go_menu.addAction(run_action)
        run_action.setShortcut("Meta+R")

    window.go_menu.aboutToShow.connect(lambda: populate_volumes(window))

    # View Menu
    view_menu = menubar.addMenu("View")

    if window.__class__.__name__ == "SpatialFilerWindow":
        align_action = QtGui.QAction("Align to Grid")
        align_action.setShortcut("Ctrl+G")
        align_action.triggered.connect(window.align_to_grid)
        view_menu.addAction(align_action)

        sort_menu = QtWidgets.QMenu("Sort", window)
        view_menu.addMenu(sort_menu)
        sort_name = QtGui.QAction("By Name", window)
        sort_name.triggered.connect(lambda: window.sort_items("name"))
        sort_menu.addAction(sort_name)
        sort_date = QtGui.QAction("By Date", window)
        sort_date.triggered.connect(lambda: window.sort_items("date"))
        sort_menu.addAction(sort_date)
        sort_size = QtGui.QAction("By Size", window)
        sort_size.triggered.connect(lambda: window.sort_items("size"))
        sort_menu.addAction(sort_size)
        sort_type = QtGui.QAction("By Type", window)
        sort_type.triggered.connect(lambda: window.sort_items("type"))
        sort_menu.addAction(sort_type)

    # Help menu
    help_menu = menubar.addMenu("Help")
    about_action = QtGui.QAction("About", window)
    about_action.triggered.connect(window.show_about)
    help_menu.addAction(about_action)
    help_menu.addSeparator
    if "log_console" in sys.modules:
        app = QtWidgets.QApplication.instance()
        app.log_console.add_menu_items(help_menu, window)
        
def populate_volumes(window):
    """
    Populate the volumes list with the available drives using QtCore.QStorageInfo.
    Clears old entries before repopulating.
    """
    for action in window.go_menu.actions():
        if hasattr(action, "is_volume") and action.is_volume:
            window.go_menu.removeAction(action)

    drives = QtCore.QStorageInfo.mountedVolumes()
    for drive in drives:
        drive_action = QtGui.QAction(drive.rootPath(), window)
        drive_action.triggered.connect(lambda checked, d=drive.rootPath(): window.go_drive(d))
        drive_action.is_volume = True
        window.go_menu.addAction(drive_action)

def run_dialog():
    """
    Open the Windows Run dialog.
    """
    if sys.platform != "win32":
        return
    from win32com.client import Dispatch
    shell = Dispatch("WScript.Shell")
    shell.Run("rundll32.exe shell32.dll,#61")
