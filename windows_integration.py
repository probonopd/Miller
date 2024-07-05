#!/usr/bin/env python3

"""
Windows integration module for Miller Columns File Manager application.

This module contains functions for platform-specific functionalities on Windows,
including displaying context menus and retrieving file properties.
"""

import os
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QModelIndex

import windows_map_drives

def show_context_menu(window, pos, column_view):
    """
    Display a context menu at the given position for the specified column view.
    """
    indexes = column_view.selectedIndexes()

    if not indexes:
        parent_index = column_view.rootIndex()
        if parent_index.isValid():
            file_paths = [window.file_model.filePath(parent_index)]
        else:
            return
    else:
        file_paths = [window.file_model.filePath(index) for index in indexes]

    if os.name == 'nt':
        try:
            import windows_context_menu
            windows_context_menu.show_context_menu(file_paths)
        except Exception as e:
            QMessageBox.critical(window, "Error", f"{e}")
        return
    else:
        QMessageBox.critical(window, "Error", "Context menu not supported on this platform.")

def show_properties(window, index: QModelIndex):
    """
    Show properties for the file or directory specified by the QModelIndex.
    """
    if index.isValid():
        file_path = window.file_model.filePath(index)
        if os.name == 'nt':
            import windows_properties
            windows_properties.get_file_properties(file_path)
        else:
            print("show_properties not implemented for this platform")

def map_network_drive(window):
    """
    Map a network drive.
    """
    if os.name == 'nt':
        network_drive_manager = windows_map_drives.NetworkDriveManager()
        map_dialog = windows_map_drives.MapDriveDialog(network_drive_manager)
        map_dialog.exec()

    else:
        QMessageBox.critical(window, "Error", "Network drive mapping not supported on this platform.")

def unmap_network_drive(window):
    """
    Unmap a network drive.
    """
    if os.name == 'nt':
        network_drive_manager = windows_map_drives.NetworkDriveManager()
        unmap_dialog = windows_map_drives.UnmapDriveDialog(network_drive_manager)
        unmap_dialog.exec()
    else:
        QMessageBox.critical(window, "Error", "Network drive unmapping not supported on this platform.")