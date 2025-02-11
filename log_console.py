import sys
import io
from PyQt6.QtWidgets import QMainWindow, QPlainTextEdit, QMessageBox
from PyQt6.QtGui import QAction

"""When running a GUI application, it is useful to have a log console
since the standard output and standard error streams are not visible.
This module provides a log console that can be opened from the application's
menu bar. It is a simple text window that displays the output of sys.stdout
and sys.stderr. The log console is not shown by default, but can be opened
from the application's menu bar.
"""

class ConsoleOutputStream(io.TextIOBase):
    def __init__(self):
        self.log_console = QPlainTextEdit()
        self.log_console.setStyleSheet('border: 0px')
        self.log_console.setReadOnly(True)
        self.log_console_window = QMainWindow()
        self.log_console_window.setCentralWidget(self.log_console)
        screen_geometry = self.log_console_window.screen().geometry()
        screen_height = screen_geometry.height()
        window_geometry = self.log_console_window.geometry()
        window_height = window_geometry.height()
        self.log_console_window.setGeometry(0, screen_height - window_height, 800, 300)
        self.log_console_window.setWindowTitle('Log Console')
        # Autoscroll to the bottom
        self.log_console.verticalScrollBar().rangeChanged.connect(
            lambda: self.log_console.verticalScrollBar().setValue(
                self.log_console.verticalScrollBar().maximum()))
        # Should the application ever crash, show the log console
        sys.excepthook = self.show_traceback

    def write(self, s):
        # Ignore whitespace
        if s.isspace():
            return
        # Remove newline characters; does not seem to work
        s = s.rstrip()
        self.log_console.appendHtml(s)

    def add_menu_items(self, menu, parent):
        menu.addSeparator()
        log_console_action = QAction('Open Log Console', parent)
        log_console_action.triggered.connect(self.open_log_console)
        menu.addAction(log_console_action)

    # Accept all parameters of sys.excepthook
    def open_log_console(self):
        if self.log_console_window.isVisible():
            return
        self.log_console_window.show()

    def show_traceback(self, exc_type, exc_value, tb):
        message_box = QMessageBox()
        message_box.setIcon(QMessageBox.Icon.Critical)
        message_box.setWindowTitle('Error')
        message_box.setText(f'{exc_value}')
        import traceback
        traceback_str = ''.join(traceback.format_exception(exc_type, exc_value, tb))
        message_box.setDetailedText(str(traceback_str))
        message_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        message_box.setMinimumWidth(400)
        message_box.exec()

class Tee(object):
    def __init__(self, stream1, stream2):
        self.stream1 = stream1
        self.stream2 = stream2

    def write(self, data):
        if self.stream1:
            self.stream1.write(data)
        self.stream2.write(data)

    def flush(self):
        if self.stream1:
            self.stream1.flush()
        self.stream2.flush()

"""app.log_console = log_console.ConsoleOutputStream()
sys.stdout = log_console.Tee(sys.stdout, app.log_console)
sys.stderr = log_console.Tee(sys.stderr, app.log_console)"""
