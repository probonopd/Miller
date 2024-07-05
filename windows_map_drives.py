#!/usr/bin/env python3

import os
import sys
import string
import subprocess
from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QMessageBox, QComboBox


class NetworkDriveManager:
    """
    Class to handle mapping and unmapping of Windows network drives.
    """
    def __init__(self):
        """
        Initialize the NetworkDriveManager.
        """
        self.drive_letter = ''
        self.network_path = ''

    def map_drive(self, drive_letter, network_path):
        """
        Map a network drive to the specified drive letter.

        :param drive_letter: The drive letter to map (e.g., 'Z:')
        :param network_path: The network path to map to (e.g., '\\\\server\\share')
        """

        # Turn double backslashes into single backslashes
        network_path = network_path.replace('\\\\', '\\')
        # Prepend with one "\"
        network_path = '\\' + network_path

        try:
            subprocess.check_call(['net', 'use', drive_letter + ":", network_path])
            QMessageBox.information(None, "Success", f"Drive {drive_letter} mapped to {network_path}")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(None, "Error", f"Failed to map drive {drive_letter} to {network_path}\n{e}")

    def unmap_drive(self, drive_letter):
        """
        Unmap the specified network drive.

        :param drive_letter: The drive letter to unmap (e.g., 'Z:')
        """
        drive_letter = drive_letter[0] + ":"
        try:
            subprocess.check_call(['net', 'use', '/del', drive_letter])
            QMessageBox.information(None, "Success", f"Drive {drive_letter} unmapped successfully")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(None, "Error", f"Failed to unmap drive {drive_letter}\n{e}")

    def get_available_drive_letters(self):
        """
        Get a list of available drive letters that are not currently in use.

        :return: List of available drive letters
        """
        used_drives = get_drive_letters()
        used_drives = [d[0] for d in used_drives] # Remove all but the first character of the drive letter
        print("Used drives: ", used_drives)
        available_drives = [d for d in string.ascii_uppercase if d not in used_drives]
        return available_drives


class MapDriveDialog(QDialog):
    """
    Dialog to map a network drive.
    """
    def __init__(self, network_drive_manager):
        """
        Initialize the MapDriveDialog.

        :param network_drive_manager: An instance of NetworkDriveManager
        """
        super().__init__()
        self.network_drive_manager = network_drive_manager
        self.setWindowTitle("Map Network Drive")
        self.layout = QVBoxLayout()

        self.drive_letter_combo = QComboBox()
        self.drive_letter_combo.addItems(self.network_drive_manager.get_available_drive_letters())
        self.drive_letter_combo.setPlaceholderText("Select Drive Letter")
        self.layout.addWidget(self.drive_letter_combo)

        self.network_path_edit = QLineEdit()
        self.network_path_edit.setPlaceholderText("Network Path (e.g., \\\\server\\share)")
        self.layout.addWidget(self.network_path_edit)

        button_layout = QHBoxLayout()
        self.map_button = QPushButton("Map Drive")
        self.map_button.setEnabled(False)
        self.map_button.clicked.connect(self.map_drive)
        button_layout.addWidget(self.map_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)
        button_layout.addWidget(self.cancel_button)

        self.layout.addLayout(button_layout)
        self.setLayout(self.layout)

        self.drive_letter_combo.currentTextChanged.connect(self.validate_inputs)
        self.network_path_edit.textChanged.connect(self.validate_inputs)

    def validate_inputs(self):
        """
        Validate inputs and enable/disable the map button.
        """
        drive_letter = self.drive_letter_combo.currentText().strip()
        network_path = self.network_path_edit.text().strip()
        if drive_letter and network_path:
            self.map_button.setEnabled(True)
        else:
            self.map_button.setEnabled(False)

    def map_drive(self):
        """
        Handle the mapping of a network drive.
        """
        drive_letter = self.drive_letter_combo.currentText().strip()
        network_path = self.network_path_edit.text().strip()

        if not drive_letter:
            QMessageBox.warning(self, "Error", "Drive Letter is required.")
            return

        if network_path:
            self.network_drive_manager.map_drive(drive_letter, network_path)
            self.close()
        else:
            QMessageBox.warning(self, "Error", "Network Path is required.")


class UnmapDriveDialog(QDialog):
    """
    Dialog to unmap a network drive.
    """
    def __init__(self, network_drive_manager):
        """
        Initialize the UnmapDriveDialog.

        :param network_drive_manager: An instance of NetworkDriveManager
        """
        super().__init__()
        self.network_drive_manager = network_drive_manager
        self.setWindowTitle("Unmap Network Drive")
        self.layout = QVBoxLayout()

        self.drive_letter_combo = QComboBox()
        mapped_drives = get_drive_letters()
        self.drive_letter_combo.addItems([drive[0] for drive in mapped_drives])
        self.drive_letter_combo.setPlaceholderText("Select Drive Letter")
        self.layout.addWidget(self.drive_letter_combo)

        button_layout = QHBoxLayout()
        self.unmap_button = QPushButton("Unmap Drive")
        self.unmap_button.setEnabled(False)
        self.unmap_button.clicked.connect(self.unmap_drive)
        button_layout.addWidget(self.unmap_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)
        button_layout.addWidget(self.cancel_button)

        self.layout.addLayout(button_layout)
        self.setLayout(self.layout)

        self.drive_letter_combo.currentTextChanged.connect(self.validate_inputs)

    def validate_inputs(self):
        """
        Validate inputs and enable/disable the unmap button.
        """
        drive_letter = self.drive_letter_combo.currentText().strip()
        if drive_letter:
            self.unmap_button.setEnabled(True)
        else:
            self.unmap_button.setEnabled(False)

    def unmap_drive(self):
        """
        Handle the unmapping of a network drive.
        """
        drive_letter = self.drive_letter_combo.currentText().strip()

        if not drive_letter:
            QMessageBox.warning(self, "Error", "Drive Letter is required.")
            return

        self.network_drive_manager.unmap_drive(drive_letter)
        self.close()

def get_drive_letters():
    """
    Get a list of drive letters for all connected drives.
    """
    if os.name == 'nt':
        import string
        from ctypes import windll
        drives = []
        bitmask = windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(f"{letter}:\\")
            bitmask >>= 1
        return drives
    else:
        return []

if __name__ == '__main__':
    app = QApplication(sys.argv)
    network_drive_manager = NetworkDriveManager()

    # Example usage
    map_dialog = MapDriveDialog(network_drive_manager)
    unmap_dialog = UnmapDriveDialog(network_drive_manager)

    map_dialog.show()
    unmap_dialog.show()

    sys.exit(app.exec())