"""Workaround for Wayland not allowing moving windows to pixel-perfect positions.
pip install python-wayland
"""

"""TODO:
* Minimize, maximize buttons
* Resize window
* Drop shadow behind window
"""

import sys
import json
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from pywayland.client import Display
from pywayland.protocol.wayland import WlCompositor, WlSeat
from pywayland.protocol.xdg_shell import XdgWmBase

class FullscreenWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.display = Display()
        self.display.connect()
        self.registry = self.display.get_registry()

        self.compositor = None
        self.xdg_wm_base = None
        self.seat = None

        self.registry.dispatcher['global'] = self.handle_global
        self.display.roundtrip()

        if self.xdg_wm_base is None or self.seat is None:
            sys.exit("Required Wayland interfaces not available")

        self.surface = self.compositor.create_surface()
        self.xdg_surface = self.xdg_wm_base.get_xdg_surface(self.surface)
        self.xdg_toplevel = self.xdg_surface.get_toplevel()

        self.xdg_toplevel.set_fullscreen(None)
        self.surface.commit()
        self.display.roundtrip()

        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

        self.init_ui()

    def handle_global(self, registry, name, interface, version):
        if interface == 'wl_compositor':
            self.compositor = registry.bind(name, WlCompositor, version)
        elif interface == 'xdg_wm_base':
            self.xdg_wm_base = registry.bind(name, XdgWmBase, version)
        elif interface == 'wl_seat':
            self.seat = registry.bind(name, WlSeat, version)

    def init_ui(self):
        self.showFullScreen()

        self.second_window = SecondWindow()
        self.second_window.init_ui(self)
        self.second_window.show()



class SecondWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

    def init_ui(self, parent):
        self.setParent(parent)
        self.load_position()
        self.setAutoFillBackground(True)

        # Drop shadow effect for the main window
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(50)
        shadow.setOffset(3, 3)
        shadow.setColor(QtCore.Qt.GlobalColor.black)
        self.setGraphicsEffect(shadow)

        self.title_bar = QtWidgets.QWidget(self)
        self.title_bar.setAutoFillBackground(True)
        self.title_bar.setGeometry(0, 0, 200, 20)
        self.title_bar.setStyleSheet("background-color: #cccccc;")
        self.title_bar.show()

        title_label = QtWidgets.QLabel('Window', self.title_bar)
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title_label.setGeometry(0, 0, 140, 20)
        title_label.show()

        close_button = QtWidgets.QPushButton('X', self.title_bar)
        close_button.setGeometry(180, 0, 20, 20)
        close_button.clicked.connect(self.close)
        close_button.show()

        minimize_button = QtWidgets.QPushButton('_', self.title_bar)
        minimize_button.setGeometry(160, 0, 20, 20)
        minimize_button.clicked.connect(self.showMinimized)
        minimize_button.show()

        maximize_button = QtWidgets.QPushButton('[]', self.title_bar)
        maximize_button.setGeometry(140, 0, 20, 20)
        maximize_button.clicked.connect(self.toggle_maximize)
        maximize_button.show()

        self.title_bar.mousePressEvent = self.get_mouse_press_event
        self.title_bar.mouseMoveEvent = self.get_mouse_move_event
        self.offset = None

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def get_mouse_press_event(self, event):
        self.offset = event.pos()

    def get_mouse_move_event(self, event):
        if self.offset is not None:
            x = event.pos().x() + self.x()
            y = event.pos().y() + self.y()
            x_w = self.offset.x()
            y_w = self.offset.y()
            self.move(x - x_w, y - y_w)

    def load_position(self):
        print('load_position')
        try:
            with open('._spatial.json', 'r') as f:
                data = json.load(f)
                self.move(data['x'], data['y'])
                self.resize(data['width'], data['height'])
        except FileNotFoundError:
            self.setGeometry(100, 100, 200, 200)

    def save_position(self):
        print('save_position')
        data = {
            'x': self.x(),
            'y': self.y(),
            'width': self.width(),
            'height': self.height()
        }
        with open('._spatial.json', 'w') as f:
            json.dump(data, f)

    def closeEvent(self, event):
        self.save_position()
        app = QtWidgets.QApplication.instance()
        app.quit()
        event.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = FullscreenWindow()
    sys.exit(app.exec())
