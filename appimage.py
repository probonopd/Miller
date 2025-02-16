#!/usr/bin/env python3

import sys, os , logging, shutil, time
from PySquashfsImage import SquashFsImage
from PySquashfsImage.file import Symlink
from elftools.elf.elffile import ELFFile
from PyQt6 import QtGui, QtWidgets, QtCore

class AppImage:
    def __init__(self, path):
        self.path = path
        self.offset = self._calculate_elf_size()
        self.icon_data = self._extract_icon_data()

    def _calculate_elf_size(self):
        try:
            with open(self.path, 'rb') as f:
                elf = ELFFile(f)
                sh_end = elf.header['e_shoff'] + (elf.header['e_shentsize'] * elf.header['e_shnum'])
                last_section = elf.get_section(elf.num_sections() - 1)
                section_end = last_section['sh_offset'] + last_section['sh_size']
                last_segment = elf.get_segment(elf.num_segments() - 1)
                segment_end = last_segment['p_offset'] + last_segment['p_filesz']
                return max(sh_end, section_end, segment_end)
        except Exception as e:
            logging.error(f"Error calculating ELF size: {e}")
            return 0

    def _extract_icon_data(self):
        try:
            with SquashFsImage.from_file(self.path, offset=self.offset) as image:
                diricon = image.select('/.DirIcon')
                if not diricon:
                    logging.warning("DirIcon not found in the SquashFS image")
                    return None
                while isinstance(diricon, Symlink):
                    target_path = diricon.readlink()
                    diricon = image.find(target_path)
                    if not diricon:
                        logging.warning(f"Symlink target not found: {target_path}")
                        return None
                return diricon.read_bytes()
        except (IOError, Exception) as e:
            logging.warning(f"Error extracting icon data: {e}")
            return None

    def get_icon(self, size=32):
        if not self.icon_data:
            return None
        pixmap = QtGui.QPixmap()
        if not pixmap.loadFromData(self.icon_data):
            icon = QtGui.QIcon.fromTheme("application-x-executable")
            return icon.pixmap(size, size)
        return QtGui.QIcon(pixmap.scaled(size, size, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation))
    
    def launch(self):
            if sys.platform == "win32":
                linux_path = self.path.replace("\\", "/").replace("C:", "/mnt/c")
            else:
                linux_path = self.path
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            QtCore.QTimer.singleShot(5, lambda: QtWidgets.QApplication.restoreOverrideCursor())
            if sys.platform == "win32":
                self.set_wait_cursor_until_launched()
                success = os.system(f"wsl {linux_path}") == 0
            else:
                # If "launch" command is available, let it launch the file
                if shutil.which("launch"):
                    success = os.system(f"launch {linux_path}") == 0
                else:
                    if not os.access(self.path, os.X_OK):
                        response = QtWidgets.QMessageBox.question(None, "Execute?", f"Execute {self.path}?", QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                        if response == QtWidgets.QMessageBox.StandardButton.Yes:
                            # Attempt to set the executable bit
                            try:
                                os.chmod(self.path, os.stat(self.path).st_mode | 0o111)
                            except Exception as e:
                                QtWidgets.QMessageBox.warning(None, "Error", f"Cannot set executable bit: {e}")
                                return
                    self.set_wait_cursor_until_launched()
                    success = os.system(self.path) == 0
            if not success:
                QtWidgets.QMessageBox.critical(None, "Error", f"Failed to open {self.path}")    
            return
    
    def set_wait_cursor_until_launched(self):
        # Set wait cursor for 15 seconds or until the application is launched as evidenced by our window no longer being the frontmost window in the z-order.
        # On Windows, this works nicely. On Linux, it remains to be seen.
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        start_time = time.time()
        this_window = QtWidgets.QApplication.activeWindow()
        while time.time() - start_time < 15:
            QtWidgets.QApplication.processEvents()
            this_window = QtWidgets.QApplication.activeWindow()
            if not this_window.isActiveWindow():
                break
        QtCore.QTimer.singleShot(5, lambda: QtWidgets.QApplication.restoreOverrideCursor())


def main():
    app = QtWidgets.QApplication(sys.argv)
    appimage_path = 'C:/Users/User/Downloads/Inkscape-e7c3feb-x86_64_0QCD8vJ.AppImage'
    appimage = AppImage(appimage_path)
    
    icon = appimage.get_icon(32)
    if icon is None:
        print("Failed to extract icon from the AppImage.")
        sys.exit(1)
    
    window = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(window)

    tool_button = QtWidgets.QToolButton()
    tool_button.setIcon(icon)
    tool_button.setIconSize(QtCore.QSize(128, 128))
    tool_button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
    tool_button.clicked.connect(appimage.launch)

    layout.addWidget(tool_button)
    layout.addWidget(QtWidgets.QLabel(f"Icon extracted successfully!\nCalculated offset: {appimage.offset}"))
    
    window.setWindowTitle("AppImage Icon Extractor")
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
