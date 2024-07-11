#!/usr/bin/env python3

from PyQt6.QtWidgets import QToolBar, QLineEdit
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import Qt

def create_toolbar(window):
    """
    Create the main application toolbar.
    """
    toolbar = QToolBar("Navigation")
    window.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    home_action = QAction(QIcon.fromTheme("home"), "Home", window)
    home_action.triggered.connect(window.go_home)
    toolbar.addAction(home_action)

    up_action = QAction(QIcon.fromTheme("go-up"), "Up", window)
    up_action.triggered.connect(window.go_up)
    toolbar.addAction(up_action)

    window.path_label = QLineEdit()
    window.path_label.setReadOnly(False)
    window.path_label.setPlaceholderText("Enter Directory Path")
    window.path_label.returnPressed.connect(window.change_path)
    toolbar.addWidget(window.path_label)

    toolbar.setMovable(False)