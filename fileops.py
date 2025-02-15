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
        # Disconnect the timer and close the progress dialog if visible.
        try:
            self.show_window_timer.timeout.disconnect()
        except:
            pass

        if self.progress_dialog.isVisible():
            self.progress_dialog.close()

        # Create and execute an error message box.
        err_box = QtWidgets.QMessageBox(self.parent)
        err_box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
        err_box.setWindowTitle("Error")
        err_box.setText(message)
        err_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        err_box.exec()

    def askOverwrite(self, dest):
        """
        Ask the user what to do if a destination file already exists.
        Returns one of:
          "this"  - just overwrite this file,
          "all"   - overwrite all without asking again,
          "none"  - cancel the entire operation.
        """
        msg_box = QtWidgets.QMessageBox(self.parent)
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Question)
        msg_box.setWindowTitle("Overwrite File?")
        msg_box.setText(f"The file {dest!r} already exists.\nDo you want to overwrite it?")
        this_button = msg_box.addButton("This", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        all_button = msg_box.addButton("All", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        none_button = msg_box.addButton("None", QtWidgets.QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()

        clicked = msg_box.clickedButton()
        if clicked == this_button:
            return "this"
        elif clicked == all_button:
            return "all"
        else:
            return "none"

    def run(self, operations, op_type):
        # Check if there are any operations; if not, show an error immediately.
        if not operations:
            QtWidgets.QMessageBox.critical(self.parent, "Error", "No operations provided!")
            return

        # Pre-check the operations: verify sources, prevent self-overwrite, confirm overwrites, and calculate total size.
        try:
            total_size = 0
            global_decision = None  # Determines if "all" overwriting is confirmed.
            valid_operations = []
            for src, dest in operations:
                # Prevent overwriting itself by comparing normalized absolute paths.
                if os.path.abspath(src) == os.path.abspath(dest):
                    raise ValueError(f"Source and destination are the same: {src}")
                    return
                # Verify the source exists.
                if not os.path.exists(src):
                    raise FileNotFoundError(f"Source file does not exist: {src}")
                    return
                # Ask for confirmation if the destination file exists.
                if os.path.exists(dest):
                    if global_decision is None:
                        decision = self.askOverwrite(dest)
                        if decision == "none":
                            QtWidgets.QMessageBox.information(self.parent, "Operation Cancelled",
                                                              "File operation cancelled by user.")
                            return  # Cancel the entire operation.
                        elif decision == "all":
                            global_decision = "all"
                    # If decision is "this" or global_decision is already set to "all", proceed.
                valid_operations.append((src, dest))
                total_size += os.path.getsize(src)
            if total_size == 0:
                raise ValueError("The total size of the files to process is zero.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.parent, "Error", str(e))
            return

        # At this point no errors, so show the progress dialog.
        self.progress_dialog.setValue(0)
        self.operation_finished = False
        self.show_window_timer.start(1000)

        self.op_thread = FileOperationThread(valid_operations, op_type, total_size)
        self.op_thread.progress.connect(self.progress_dialog.setValue)
        self.op_thread.error.connect(self.showError)
        self.op_thread.finished.connect(self.operation_finished_slot)
        self.progress_dialog.canceled.connect(self.op_thread.cancel)
        self.op_thread.start()

    def show_progress_dialog(self):
        # Only show the dialog if the operation isn't finished yet and progress is still below 30%.
        if not self.operation_finished and self.progress_dialog.value() < 30:
            self.progress_dialog.show()

    def operation_finished_slot(self):
        self.operation_finished = True
        self.progress_dialog.close()
        try:
            self.show_window_timer.timeout.disconnect()
        except:
            pass
        if hasattr(self.parent, "refresh_view"):
            self.parent.refresh_view()


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
    main_window = QtWidgets.QWidget()
    
    # Dummy refresh_view method for testing purposes.
    def refresh_view():
        print("Refreshed view.")
    main_window.refresh_view = refresh_view

    op = FileOperation(main_window)

    # Test case: trying to copy a file to itself should trigger an error.
    src = "test.txt"
    dest = "test.txt"  # Using the same file for src and dest.
    operations = [(src, dest)]
    
    op.run(operations, "copy")
    main_window.show()
    app.exec()
