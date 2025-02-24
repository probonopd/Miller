#!/usr/bin/env python3

import sys
from PyQt6 import QtGui, QtWidgets, QtCore

class RoundedMenuBar(QtWidgets.QMenuBar):
    def __init__(self, round_left=False, round_right=False):
        super().__init__()
        self.round_left = round_left
        self.round_right = round_right
        

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        
        # Draw rounded corners
        radius = self.height() // 3
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black, 1))
        painter.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.black))
        
        if self.round_left:
            painter.save()
            path = QtGui.QPainterPath()
            path.addRect(0, 0, radius+0.3, radius+0.3) # FIXME: Find a solution that works on HiDPI without hardcoding 0.3
            path.addEllipse(0, 0, radius*2, radius*2)
            path = path.simplified()
            painter.setClipPath(path)
            painter.fillRect(0, 0, radius, radius, QtCore.Qt.GlobalColor.black)
            painter.restore()
        
        if self.round_right:
            painter.save()
            path = QtGui.QPainterPath()
            path.addRect(self.width()-radius-0.3, 0, radius+0.3, radius+0.3) # FIXME: Find a solution that works on HiDPI without hardcoding 0.3
            path.addEllipse(self.width()-radius*2, 0, radius*2, radius*2)
            path = path.simplified()
            painter.setClipPath(path)
            painter.fillRect(self.width()-radius, 0, radius, radius, QtCore.Qt.GlobalColor.black)
            painter.restore()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QMainWindow()
    
    # Draw both left and right edges
    menubar1 = RoundedMenuBar()
    menubar1.addMenu("Menu1")
    menubar1.addMenu("Menu2")
    window.setMenuBar(menubar1)
    
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())
