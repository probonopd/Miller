#!/usr/bin/env python3

import sys

from PyQt6 import QtWidgets, QtCore

class PreferencesDialog(QtWidgets.QDialog):
    _instance = None  # Track the open instance

    def __init__(self, parent=None):
        if PreferencesDialog._instance is not None:
            PreferencesDialog._instance.show()
            PreferencesDialog._instance.raise_()
            PreferencesDialog._instance.activateWindow()
            return

        super().__init__(parent)

        # Get app instance
        app = QtWidgets.QApplication.instance()
        self.preferences = app.preferences

        self.setWindowTitle("Preferences")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)

        self._build_ui()

        PreferencesDialog._instance = self  # Set instance reference
        self.destroyed.connect(lambda: self._on_close())  # Cleanup when closed

        # Print the full path of the preferences file
        print(f"Preferences file: {self.preferences.fileName()}")

        # If the file is not writable, print a warning
        if not self.preferences.isWritable():
            print("Warning: Preferences are not writable")

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Preferences section
        self.options = {
            "hide_file_extensions": QtWidgets.QCheckBox("Hide file extensions"),
            "show_hidden_files": QtWidgets.QCheckBox("Show hidden files"),
        }

        for key, checkbox in self.options.items():
            checkbox.setChecked(self.preferences.value(key, False, type=bool))
            checkbox.stateChanged.connect(lambda state, k=key: self._update_preference(k, state))
            row_layout = QtWidgets.QHBoxLayout()
            row_layout.addWidget(checkbox)
            row_layout.addStretch()
            layout.addLayout(row_layout)

        # Desktop Picture Selection
        if not sys.platform == "win32":
            desktop_layout = QtWidgets.QHBoxLayout()
            self.desktop_picture_label = QtWidgets.QLabel("Desktop Picture:")
            self.desktop_picture_button = QtWidgets.QPushButton("Choose")
            self.desktop_picture_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            self.desktop_picture_button.clicked.connect(self.select_desktop_picture)
            desktop_layout.addWidget(self.desktop_picture_label)
            desktop_layout.addWidget(self.desktop_picture_button)
            layout.addLayout(desktop_layout)
        
        if sys.platform == "win32":
            # Read the value of 

    def _update_preference(self, key, state):
        self.preferences.setValue(key, bool(state))
        self.preferences.sync()
        for window in QtWidgets.QApplication.topLevelWidgets():
            if hasattr(window, "refresh_view"):
                window.refresh_view()

    def select_desktop_picture(self):
        file_dialog = QtWidgets.QFileDialog(self)
        file_dialog.setNameFilters(["Images (*.png *.jpg *.jpeg)"])
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.preferences.setValue("desktop_picture", selected_files[0])
                self.preferences.sync()
                print(f"Selected desktop picture: {selected_files[0]}")

    def _on_close(self):
        PreferencesDialog._instance = None  # Reset instance when dialog is closed

if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    # Create a QSettings instance
    app.preferences = QtCore.QSettings("MyApp", "Preferences")

    if not PreferencesDialog._instance:
        dialog = PreferencesDialog()
        dialog.show()

    app.exec()
