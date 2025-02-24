import os
import zipfile
import sys
import logging
from PyQt6 import QtWidgets, QtCore

from trace import Trace
Trace()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ZipperThread(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    error = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

    def __init__(self, path_to_zip):
        super().__init__()
        self.path_to_zip = path_to_zip
        self._is_running = True
        self.output_zip_file = f"{self.path_to_zip}.zip"
        self.new_zip_created = False

    def show_error(self, message):
        QtWidgets.QMessageBox.critical(None, "Error", message)

    def run(self):
        logging.info(f"Starting to zip: {self.path_to_zip} to {self.output_zip_file}")

        if os.path.exists(self.output_zip_file):
            self.error.emit(f"The ZIP file '{self.output_zip_file}' already exists.")
            return

        total_size = sum(os.path.getsize(os.path.join(root, file))
                        for root, _, files in os.walk(self.path_to_zip))
        if total_size == 0:
            self.error.emit("The selected directory is empty.")
            return

        self.progress.emit(0)

        try:
            self.new_zip_created = True
            with zipfile.ZipFile(self.output_zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                current_size = 0
                for root, _, files in os.walk(self.path_to_zip):
                    for file in files:
                        if not self._is_running:
                            return

                        file_path = os.path.join(root, file)
                        try:
                            zipf.write(file_path, os.path.relpath(file_path, self.path_to_zip))
                            current_size += os.path.getsize(file_path)
                            self.progress.emit(int((current_size / total_size) * 100))
                        except Exception as e:
                            self.error.emit(f"Error adding file {file_path}: {str(e)}")
                            return

            logging.info(f"Zipping completed: {self.output_zip_file}")
            self.progress.emit(100)
            self.finished.emit()
        except Exception as e:
            self.error.emit(f"Error creating zip file: {str(e)}")
        finally:
            if self.new_zip_created and not self._is_running:
                if os.path.exists(self.output_zip_file):
                    os.remove(self.output_zip_file)
                    logging.info(f"Deleted the zip file: {self.output_zip_file}")

    def cancel(self):
        self._is_running = False

class UnzipperThread(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    error = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

    def __init__(self, zip_file, extract_to):
        super().__init__()
        self.zip_file = zip_file

        self.extract_to = extract_to
        
        self._is_running = True

    def show_error(self, message):
        QtWidgets.QMessageBox.critical(None, "Error", message)

    def run(self):
        logging.info(f"Starting to unzip: {self.zip_file} to {self.extract_to}")

        if not os.path.exists(self.zip_file):
            self.error.emit(f"The ZIP file '{self.zip_file}' does not exist.")
            return
        
        with zipfile.ZipFile(self.zip_file, 'r') as zipf:
            total_files = len(zipf.namelist())
            if total_files == 0:
                self.error.emit("The ZIP file is empty.")
                return

            self.progress.emit(0)

            for index, file in enumerate(zipf.namelist()):
                if not self._is_running:
                    return  # Ensure we exit immediately

                try:
                    zipf.extract(file, self.extract_to)
                    self.progress.emit(int((index + 1) / total_files * 100))
                except Exception as e:
                    self.error.emit(f"Error extracting file {file}: {str(e)}")
                    return

        logging.info(f"Unzipping completed: {self.zip_file}")
        self.progress.emit(100)
        self.finished.emit()


    def cancel(self):
        self._is_running = False

class ZipFolderApp(QtWidgets.QWidget):

    error = QtCore.pyqtSignal(str) 

    def __init__(self, path_to_zip):
        super().__init__()
        self.path_to_zip = path_to_zip
        self.zipper_thread = None
        self.init_ui()
        self.start_zipping()

    def init_ui(self):
        self.setWindowTitle('Zipping')
        self.setGeometry(100, 100, 400, 50)

        self.layout = QtWidgets.QVBoxLayout()

        self.label = QtWidgets.QLabel(f'Zipping: {self.path_to_zip}')
        self.layout.addWidget(self.label)

        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setTextVisible(True)
        self.layout.addWidget(self.progress_bar)

        button_layout = QtWidgets.QHBoxLayout()
        self.cancel_button = QtWidgets.QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.cancel_zipping)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(button_layout)

        self.setLayout(self.layout)

    def start_zipping(self):
        output_zip_file = f"{self.path_to_zip}.zip"
        if os.path.exists(output_zip_file):
            QtWidgets.QMessageBox.critical(None, "Error", f"The ZIP file '{output_zip_file}' already exists.")
            return

        self.zipper_thread = ZipperThread(self.path_to_zip)
        self.zipper_thread.progress.connect(self.update_progress)
        self.zipper_thread.finished.connect(self.on_finished)
        self.zipper_thread.error.connect(self.error.emit)
        self.zipper_thread.start()
        self.show()

    def update_progress(self, value):
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(f"{value}%")

    def on_finished(self):
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("100%")
        self.cancel_button.setEnabled(False)
        self.close()

    def show_error(self, message):
        QtWidgets.QMessageBox.critical(None, "Error", message)

    def cancel_zipping(self):
        if self.zipper_thread:
            self.zipper_thread.cancel()
            self.zipper_thread.wait()
        self.close()

    def closeEvent(self, event):
        self.cancel_zipping()
        event.accept()

class UnzipFolderApp(QtWidgets.QWidget):

    error = QtCore.pyqtSignal(str) 

    def __init__(self, zip_file, extract_to=None):
        super().__init__()
        self.zip_file = zip_file
        self.unzipper_thread = None
        self.init_ui()
        self.start_unzipping(extract_to)

    def init_ui(self):
        self.setWindowTitle('Unzipping')
        self.setGeometry(100, 100, 400, 50)

        self.layout = QtWidgets.QVBoxLayout()

        self.label = QtWidgets.QLabel(f'Unzipping: {self.zip_file}')
        self.layout.addWidget(self.label)

        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setTextVisible(True)
        self.layout.addWidget(self.progress_bar)

        button_layout = QtWidgets.QHBoxLayout()
        self.cancel_button = QtWidgets.QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.cancel_unzipping)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(button_layout)

        self.setLayout(self.layout)

    def start_unzipping(self, extract_to=None):
        if not extract_to:
            extract_to = QtWidgets.QFileDialog.getExistingDirectory(self, "Select a folder to extract to")
        if not extract_to:
            QtWidgets.QMessageBox.critical(None, "Error", "No extraction folder selected.")
            self.close()
            return
        
        # If destination folder exists, check if it's empty. If it is not empty, ask the user to confirm
        if os.path.exists(extract_to):
            if os.listdir(extract_to):
                confirm = QtWidgets.QMessageBox.question(None, "Confirm Extract",
                    f"The folder '{extract_to}' is not empty. Do you want to continue and overwrite existing files?",
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                if confirm == QtWidgets.QMessageBox.StandardButton.No:
                    return
                
        # Create the destination folder if it does not exist
        if not os.path.exists(extract_to):
            try:
                os.makedirs(extract_to)
            except Exception as e:
                self.error.emit(f"Error creating folder {extract_to}: {str(e)}")
                return

        self.unzipper_thread = UnzipperThread(self.zip_file, extract_to)
        self.unzipper_thread.progress.connect(self.update_progress)
        self.unzipper_thread.finished.connect(self.on_finished)
        self.unzipper_thread.error.connect(self.error.emit)
        self.unzipper_thread.start()
        self.show()

    def update_progress(self, value):
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(f"{value}%")

    def on_finished(self):
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("100%")
        self.cancel_button.setEnabled(False)
        self.close()

    def show_error(self, message):
        QtWidgets.QMessageBox.critical(None, "Error", message)

    def cancel_unzipping(self):
        if self.unzipper_thread and self.unzipper_thread.isRunning():
            self.unzipper_thread.cancel()
            self.unzipper_thread.quit()  # Requests clean exit
            self.unzipper_thread.wait()  # Ensures it has stopped
        self.close()


    def closeEvent(self, event):
        self.cancel_unzipping()
        event.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    # Open a file dialog to select a folder to zip
    path_to_zip = QtWidgets.QFileDialog.getExistingDirectory(None, "Select a folder to zip")
    if path_to_zip:
        window = ZipFolderApp(path_to_zip)
    else:
        # Open a file dialog to select a ZIP file to unzip
        zip_file = QtWidgets.QFileDialog.getOpenFileName(None, "Select a ZIP file to unzip", "", "ZIP Files (*.zip)")[0]
        if zip_file:
            window = UnzipFolderApp(zip_file)
        else:
            sys.exit()  # Exit if no folder or ZIP file is selected

    sys.exit(app.exec())
