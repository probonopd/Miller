#!/usr/bin/env python3

"""
status_bar.py

This module defines the status bar functionality for the Miller Columns File Manager application.
"""

from PyQt6.QtWidgets import QLabel

def create_status_bar(window):
    """
    Create and initialize the status bar.
    """
    window.statusBar = window.statusBar()

    window.selected_files_label = QLabel()
    window.statusBar.addWidget(window.selected_files_label)

    window.selected_files_size_label = QLabel()
    window.statusBar.addWidget(window.selected_files_size_label)

    update_status_bar(window)

def update_status_bar(window):
    """
    Update the status bar with current selection information.
    """
    selected_indexes = window.columns[-1].selectionModel().selectedIndexes()
    num_selected_files = len(selected_indexes)
    total_size = sum(window.file_model.size(index) for index in selected_indexes if index.isValid())

    window.selected_files_label.setText(f"Selected files: {num_selected_files}")
    if total_size >= 1024 ** 3:
        total_size = f"{total_size / 1024 ** 3:.2f} GB"
    elif total_size >= 1024 ** 2:
        total_size = f"{total_size / 1024 ** 2:.2f} MB"
    elif total_size >= 1024:
        total_size = f"{total_size / 1024:.2f} KB"
    else:
        total_size = f"{total_size} bytes"
    window.selected_files_size_label.setText(f"Total size: {total_size}")
