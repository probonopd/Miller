#!/usr/bin/env python3

import os
from PyQt6 import QtWidgets, QtCore


class FileOperation(QtCore.QObject):
    def __init__(self, parent):
        self.parent = parent
        super().__init__(self.parent)
        self._isCanceled = False
        self.progress_dialog = QtWidgets.QProgressDialog("Performing operation...", "Cancel", 0, 100, self.parent)
        self.progress_dialog.setWindowTitle("Progress")
        self.progress_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(True)

    def cancel(self):
        self.op_thread.cancel()
        self.progress_dialog.close()

    def run(self, operations, op_type):
        total_size = sum(os.path.getsize(src) for src, _ in operations if os.path.exists(src))

        self.progress_dialog.show()

        self.op_thread = FileOperationThread(operations, op_type, total_size)
        self.op_thread.progress.connect(self.progress_dialog.setValue)
        self.op_thread.error.connect(lambda msg: (self.progress_dialog.close(), QtWidgets.QMessageBox.critical(self.parent, "Error", msg)))
        self.op_thread.finished.connect(lambda: (self.progress_dialog.close(), self.parent.refresh_view()))
        self.progress_dialog.canceled.connect(self.op_thread.cancel)
        self.op_thread.start()


class FileOperationThread(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)

    def __init__(self, operations, op_type, total_size, parent=None):
        super().__init__(parent)
        self.operations = operations
        self.op_type = op_type
        self.total_size = total_size
        self._isCanceled = False

    def run(self):
        try:
            copied_size = 0
            for index, (src, dest) in enumerate(self.operations):
                if self._isCanceled:
                    break
                file_size = os.path.getsize(src) if os.path.exists(src) else 0
                copied = 0
                with open(src, "rb") as fsrc, open(dest, "wb") as fdest:
                    while chunk := fsrc.read(65536):
                        if self._isCanceled:
                            return
                        fdest.write(chunk)
                        copied += len(chunk)
                        copied_size += len(chunk)
                        progress_percentage = int((copied_size / self.total_size) * 100)
                        self.progress.emit(progress_percentage)
                if self.op_type == "move":
                    # TODO: Do some sanity checks to verify that the file was copied successfully before deleting the source
                    os.remove(src)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
    
    def cancel(self):
        self._isCanceled = True

if __name__ == "__main__":
    # Do a test run of a copy operation
    app = QtWidgets.QApplication([])
    op = FileOperation(None)
    src = "test.txt"
    dest = "test_copy.txt"
    operations = [(src, dest)]
    op.run(operations, "copy")
    app.exec()

