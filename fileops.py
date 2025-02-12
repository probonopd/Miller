#!/usr/bin/env python3

import os
from PyQt6 import QtWidgets, QtCore


class FileOperation(QtCore.QObject):
    def __init__(self, parent):
        self.parent = parent
        super().__init__(self.parent)
        # Initialize the progress dialog once, but do not show it unless necessary.
        self.progress_dialog = QtWidgets.QProgressDialog("Performing operation...", "Cancel", 0, 100, self.parent)
        self.progress_dialog.setWindowTitle("Progress")
        self.progress_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setAutoReset(True)
        self.show_window_timer = QtCore.QTimer(self.parent)
        self.show_window_timer.timeout.connect(self.show_progress_dialog)
        self.show_window_timer.setSingleShot(True)
        self.operation_finished = False

    def cancel(self):
        if hasattr(self, "op_thread"):
            self.op_thread.cancel()
        self.progress_dialog.close()

    def showError(self, message: str):
        # Close the progress dialog if it's visible; if it hasn't been shown yet,
        # this will be effectively a no-op.
        self.show_window_timer.timeout.disconnect()
        if self.progress_dialog.isVisible():
            self.progress_dialog.close()

        self.show_window_timer.timeout.disconnect()

        # Create and execute an error message box.
        err_box = QtWidgets.QMessageBox(self.parent)
        err_box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
        err_box.setWindowTitle("Error")
        err_box.setText(message)
        err_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        err_box.exec()
        
    def run(self, operations, op_type):
        # Check if there are any operations; if not, show an error immediately.
        if not operations:
            QtWidgets.QMessageBox.critical(self.parent, "Error", "No operations provided!")
            return

        # Pre-check the operations: verify sources and calculate total size.
        try:
            total_size = 0
            for src, _ in operations:
                if not os.path.exists(src):
                    raise FileNotFoundError(f"Source file does not exist: {src}")
                total_size += os.path.getsize(src)
            if total_size == 0:
                raise ValueError("The total size of the files to process is zero.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.parent, "Error", str(e))
            # At this point the progress dialog has not been shown, so we simply return.
            return

        # At this point no errors, so show the progress dialog.
        self.progress_dialog.setValue(0)
        self.operation_finished = False
        self.show_window_timer.start(1000)

        self.op_thread = FileOperationThread(operations, op_type, total_size)
        self.op_thread.progress.connect(self.progress_dialog.setValue)
        # Connect error signal to our method; this ensures that the progress dialog closes
        # before or as the error dialog appears.
        self.op_thread.error.connect(self.showError)
        self.op_thread.finished.connect(self.operation_finished_slot)
        self.progress_dialog.canceled.connect(self.op_thread.cancel)
        self.op_thread.start()

    def show_progress_dialog(self):
        # Only show the progress dialog if the operation hasn't finished yet
        # and if the current progress is still less than 30%.
        if not self.operation_finished and self.progress_dialog.value() < 30:
            self.progress_dialog.show()

    def operation_finished_slot(self):
        self.operation_finished = True
        self.progress_dialog.close()
        self.show_window_timer.timeout.disconnect()
        self.parent.refresh_view() if hasattr(self.parent, "refresh_view") else None


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
            for src, dest in self.operations:
                if self._isCanceled:
                    self.error.emit("Operation cancelled by user.")
                    return

                if not os.path.exists(src):
                    self.error.emit(f"Source file not found: {src}")
                    return

                file_size = os.path.getsize(src)
                try:
                    with open(src, "rb") as fsrc, open(dest, "wb") as fdest:
                        while True:
                            if self._isCanceled:
                                self.error.emit("Operation cancelled by user.")
                                return
                            chunk = fsrc.read(65536)
                            if not chunk:
                                break
                            fdest.write(chunk)
                            copied_size += len(chunk)
                            progress_percentage = min(int((copied_size / self.total_size) * 100), 100)
                            self.progress.emit(progress_percentage)
                except Exception as file_error:
                    self.error.emit(f"Error processing file {src} → {dest}: {str(file_error)}")
                    return

                if self.op_type == "move":
                    # Verify that the destination file exists and has the same size.
                    if os.path.exists(dest) and os.path.getsize(dest) == file_size:
                        try:
                            os.remove(src)
                        except Exception as rem_err:
                            self.error.emit(f"Could not remove source file {src}: {str(rem_err)}")
                            return
                    else:
                        self.error.emit(f"File move failed for {src} → {dest} (destination invalid).")
                        return

            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self._isCanceled = True


if __name__ == "__main__":
    # Test run of a copy operation.
    app = QtWidgets.QApplication([])
    # For testing purposes, use a simple QWidget as the parent.
    main_window = QtWidgets.QWidget()
    # Define a dummy refresh_view method on the main window.
    def refresh_view():
        print("Refreshed view.")
    main_window.refresh_view = refresh_view

    op = FileOperation(main_window)
    src = "test.txt"
    dest = "test_copy.txt"
    operations = [(src, dest)]
    op.run(operations, "copy")
    main_window.show()
    app.exec()
