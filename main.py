#!/usr/bin/env python3

import sys
from PyQt6.QtWidgets import QApplication
from main_window import MillerColumns

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MillerColumns()
    window.show()
    sys.exit(app.exec())
