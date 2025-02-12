#!/usr/bin/env python3

"""This is a rough Windows eqivalent for struts in X11. It reserves space at the top of the screen for a menu bar."""

import sys, signal, ctypes

from PyQt6 import QtWidgets, QtCore

import styling

# Constants for SystemParametersInfo
SPI_GETWORKAREA = 0x0030
SPI_SETWORKAREA = 47
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDWININICHANGE = 0x02

# Define the RECT structure
class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long)]

def get_work_area():
    rect = RECT()
    result = ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    if not result:
        print("Failed to get current work area")
    return rect

def set_work_area(new_rect: RECT):
    result = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETWORKAREA,
        0,
        ctypes.byref(new_rect),
        SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
    )
    if not result:
        print("Failed to set new work area")
    else:
        print("Work area set to:", new_rect.left, new_rect.top, new_rect.right, new_rect.bottom)
    return result

class Strut(QtCore.QObject):
    def __init__(self):
        super().__init__()

        # Calculate the desired size of the menu bar
        menubar = QtWidgets.QMenuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction("Open")
        menubar.setFixedHeight(menubar.minimumSizeHint().height())
        reserved_height = menubar.minimumSizeHint().height()
        
        screen = QtWidgets.QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        self.reserve_rect = QtCore.QRect(
            screen_geometry.left(),
            screen_geometry.top(),
            screen_geometry.width(),
            reserved_height
        )
        
        # Save the original work area so we can restore it later.
        self.original_work_area = get_work_area()
        
        # Reserve the space (update the system work area)
        self.reserve_space(self.reserve_rect)
    
    def reserve_space(self, rect: QtCore.QRect):
        new_work_area = RECT()
        new_work_area.left = self.original_work_area.left
        new_work_area.top = rect.bottom() + 1
        new_work_area.right = self.original_work_area.right
        new_work_area.bottom = self.original_work_area.bottom
        set_work_area(new_work_area)
    
    def restore_work_area(self):
        set_work_area(self.original_work_area)
    
    def closeEvent(self, event):
        self.restore_work_area()
        event.accept()

def handle_sigint(signal_number, frame):
    QtWidgets.QApplication.quit()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    # Apply styling to the application so that the size of the reserved area fits the menu bar of the app.
    styling.apply_styling(app)
    
    # Set up a timer to allow Python's signal handling to run.
    # Without this, the SIGINT handler does not work as expected.
    # In a real application, we have a main window or other event loop.
    timer = QtCore.QTimer()
    timer.start(100)  # 100 ms interval
    timer.timeout.connect(lambda: None)
    
    # Install the SIGINT handler.
    signal.signal(signal.SIGINT, handle_sigint)
    
    appbar = Strut()
    app.aboutToQuit.connect(appbar.restore_work_area)
    
    sys.exit(app.exec())
