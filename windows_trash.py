#!/usr/bin/env python3

import sys
import ctypes
from ctypes import wintypes
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt


def _really_empty_recycle_bin():
    """
    Empties the Windows Recycle Bin using SHEmptyRecycleBinW.
    Returns True on success, or False if an error occurred.
    """

    HRESULT = ctypes.c_long
    shell32 = ctypes.windll.shell32
    shell32.SHEmptyRecycleBinW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.DWORD]
    shell32.SHEmptyRecycleBinW.restype = HRESULT

    SHERB_NOCONFIRMATION = 0x00000001  # Do not show a confirmation dialog box
    SHERB_NOPROGRESSUI   = 0x00000002  # Do not display a progress dialog box
    SHERB_NOSOUND        = 0x00000004  # Do not play a sound when the operation is complete

    # Combine the flags
    flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
    
    app = QApplication.instance()
    app.setOverrideCursor(Qt.CursorShape.WaitCursor)
    result = shell32.SHEmptyRecycleBinW(0, None, flags)
    return result

def empty_trash():
    msgBox = QMessageBox()
    msgBox.setIcon(QMessageBox.Icon.Question)
    msgBox.setWindowTitle("Empty Recycle Bin?")
    msgBox.setText("Do you want to permanently delete all items in the Recycle Bin?")

    yesButton = msgBox.addButton("Yes", QMessageBox.ButtonRole.YesRole)
    noButton = msgBox.addButton("No", QMessageBox.ButtonRole.RejectRole)

    msgBox.setDefaultButton(noButton)

    msgBox.exec()

    app = QApplication.instance()

    if msgBox.clickedButton() == yesButton:
        if _really_empty_recycle_bin():
            app.restoreOverrideCursor()
            QMessageBox.information(None, "Success", "Recycle Bin emptied successfully.")
        else:
            app.restoreOverrideCursor()
            QMessageBox.critical(None, "Error", "Failed to empty Recycle Bin.")
    else:
        print("Operation cancelled by the user.")

    sys.exit(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    empty_trash()
