#!/usr/bin/env python

import sys
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
from PyQt6 import QtWidgets, QtCore, QtGui

class VolumeControlWidget(QtWidgets.QWidget):
    volumeChanged = QtCore.pyqtSignal(int, bool)

    def __init__(self):
        super().__init__()
        self.volume = self.get_volume_interface()
        self.setFixedSize(32, 128)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Vertical)
        self.slider.setRange(0, 100)
        self.slider.setFixedSize(32, 128)
        self.slider.setValue(int(self.volume.GetMasterVolumeLevelScalar() * 100))
        self.slider.valueChanged.connect(self.on_volume_change)
        layout.addWidget(self.slider)
        self.muted = self.volume.GetMute()

    def on_volume_change(self, value):
        self.volume.SetMasterVolumeLevelScalar(value/100.0, None)
        self.muted = self.volume.GetMute()
        self.volumeChanged.emit(value, self.muted)

    def get_volume_interface(self):
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return interface.QueryInterface(IAudioEndpointVolume)

class MuteButton(QtWidgets.QToolButton):
    muteChanged = QtCore.pyqtSignal(int, bool) 

    def __init__(self, volume_interface, parent=None):
        super().__init__(parent)
        self.volume = volume_interface
        self.setCheckable(True)
        self.setFixedSize(32, 32)
        self.setChecked(bool(self.volume.GetMute()))
        self.update_icon()
        self.clicked.connect(self.toggle_mute)  # Changed from toggled to clicked

    def toggle_mute(self):
        muted = not self.volume.GetMute()  # Toggle the mute state
        self.volume.SetMute(muted, None)
        self.setChecked(muted)
        self.update_icon()
        current_volume = int(self.volume.GetMasterVolumeLevelScalar() * 100)
        self.muteChanged.emit(current_volume, muted)
        self.parent().close()

    def update_icon(self):
        if self.isChecked():
            icon = QtGui.QIcon.fromTheme("audio-volume-muted")
            if icon.isNull():
                icon = QtGui.QIcon("mute_icon.png")
        else:
            icon = QtGui.QIcon.fromTheme("audio-volume-high")
            if icon.isNull():
                icon = QtGui.QIcon("speaker_icon.png")
        self.setIcon(icon)
        self.setIconSize(QtCore.QSize(16, 16))
        self.setToolTip("Muted" if self.isChecked() else "Sound On")

class VolumeMenu(QtWidgets.QMenu):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_menu()

    def setup_menu(self):
        self.volWidget = VolumeControlWidget()
        volWidgetAction = QtWidgets.QWidgetAction(self)
        volWidgetAction.setDefaultWidget(self.volWidget)
        self.addAction(volWidgetAction)
        
        self.muteBtn = MuteButton(self.volWidget.volume)
        muteBtnAction = QtWidgets.QWidgetAction(self)
        muteBtnAction.setDefaultWidget(self.muteBtn)
        self.addAction(muteBtnAction)

        # Connect signals
        self.volWidget.volumeChanged.connect(self.update_menu_icon)
        self.muteBtn.muteChanged.connect(self.update_menu_icon)

        self.update_menu_icon(self.volWidget.slider.value(), self.muteBtn.isChecked())
        # self.volWidget.mouseReleaseEvent = lambda event: self.close()
        self.volWidget.slider.mouseReleaseEvent = self.close_menu

    def close_menu(self, event):
        self.close()

    def update_menu_icon(self, volume, muted):
        if muted or volume == 0:
            icon_name = "audio-volume-muted"
            fallback_icon = "mute_icon.png"
        elif volume < 34:
            icon_name = "audio-volume-low"
            fallback_icon = "speaker_low.png"
        elif volume < 67:
            icon_name = "audio-volume-medium"
            fallback_icon = "speaker_med.png"
        else:
            icon_name = "audio-volume-high"
            fallback_icon = "speaker_high.png"

        icon = QtGui.QIcon.fromTheme(icon_name)
        if icon.isNull():
            icon = QtGui.QIcon(fallback_icon)
        
        self.setIcon(icon)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Volume Control in Menu")
        self.setGeometry(300, 300, 400, 300)
        self.setup_menu()

    def setup_menu(self):
        menubar = self.menuBar()
        self.volMenu = VolumeMenu(self)
        menubar.addMenu(self.volMenu)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
