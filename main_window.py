#!/usr/bin/env python3

"""
Main module for Miller Columns File Manager application.

This module defines the main window (`MillerColumns`) and its functionalities,
including file navigation, status bar updates, etc.
"""

import sys
import os

# FIXME: Import Qt like this: from PyQt6 import QtWidgets, QtGui, QtCore, QtWebEngineWidgets
from PyQt6.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QListView, QWidget, QAbstractItemView, QMessageBox, QLabel, QTextEdit, QStackedWidget, QInputDialog, QMenu, QStyle
from PyQt6.QtCore import QSettings, QByteArray, Qt, QDir, QModelIndex, QUrl, QMimeData
from PyQt6.QtGui import QFileSystemModel, QAction, QPixmap, QDrag, QCursor
from PyQt6.QtWebEngineWidgets import QWebEngineView # pip install PyQt6-WebEngine
import mimetypes
if sys.platform == 'win32':
    from windows_integration import show_context_menu
    import windows_file_operations

import menus, toolbar, status_bar, getinfo

class CustomFileSystemModel(QFileSystemModel):
    """
    Custom file system model that allows us to customize e.g., the icons being used.
    """
    def data(self, index, role):
        if role == Qt.ItemDataRole.DecorationRole:
            if self.isDir(index):
                return self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        return super().data(index, role)

    def style(self):
        # To access the style in the model, we need to create a temporary widget
        # This is a workaround because models don't have a style method
        from PyQt6.QtWidgets import QWidget
        return QWidget().style()
    

class DragDropListView(QListView):
    """
    Custom list view that supports drag and drop operations.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
   
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():

            # FIXME: Pressing or letting go of the control key should change the drop action during a drag operation but it doesn't; 
            # only the initial key state is considered
            if QApplication.keyboardModifiers() == Qt.KeyboardModifier.ControlModifier:
                event.setDropAction(Qt.DropAction.CopyAction)
            else:
                event.setDropAction(Qt.DropAction.MoveAction)
        
            event.acceptProposedAction()

    def startDrag(self, supportedActions):
        index = self.currentIndex()
        if index.isValid():
            drag = QDrag(self)
            mime_data = QMimeData()
            item_path = self.model().filePath(index)
            mime_data.setUrls([QUrl.fromLocalFile(item_path)])
            drag.setMimeData(mime_data)

            # The icon of the dragged item
            icon = self.model().fileIcon(index)
            drag.setPixmap(icon.pixmap(16, 16))
            drag.setHotSpot(drag.pixmap().rect().center())

            self.setDragEnabled(True)

            drag.exec()

class MillerColumns(QMainWindow):
    """
    Main application window for Miller Columns File Manager.
    """
    def __init__(self):
        """
        Initialize the MillerColumns instance.
        """
        super().__init__()
        self.setWindowTitle("Miller Columns File Manager")
        self.resize(1000, 600)  # Default size

        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QHBoxLayout(self.central_widget)

        self.column_layout = QHBoxLayout()
        self.columns = []

        self.file_model = CustomFileSystemModel()
        self.file_model.setRootPath('')
        self.file_model.setOption(CustomFileSystemModel.Option.DontUseCustomDirectoryIcons, False)  # Enable color icons
        self.file_model.setFilter(QDir.Filter.AllEntries | QDir.Filter.Hidden | QDir.Filter.System)
        # FIXME: . and .. should not be shown in the view, but things like $RECYCLE.BIN should be shown

        home_dir = os.path.expanduser('~')
        self.add_column(self.file_model.index(home_dir))

        self.create_preview_panel()

        self.main_layout.addLayout(self.column_layout)
        self.main_layout.addWidget(self.preview_panel)

        self.create_menus()  # Create menus directly in the constructor
        toolbar.create_toolbar(self)
        status_bar.create_status_bar(self)
        self.read_settings()

        self.setAcceptDrops(False) # Dropping is only allowed in the column views, which handle it themselves using a QListView subclass

    def dragEnterEvent(self, event):
        print("Drag enter event")
        if event.mimeData().hasUrls():
            print("Has URLs, accepting proposed action %s" % event.proposedAction())
            event.acceptProposedAction()

    def dropEvent(self, event):
        print("Drop event")
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            print("Has URLs, accepting proposed action %s" % event.proposedAction())
            file_paths = [url.toLocalFile() for url in urls]
            # Path onto which the files were dropped
            drop_target = self.file_model.filePath(self.columns[-1].rootIndex())
            if not file_paths:
                return
            event.acceptProposedAction()

            try:
                    menu = QMenu()
                    move_action = menu.addAction("Move")
                    copy_action = menu.addAction("Copy")
                    link_action = menu.addAction("Link")
                    menu.addSeparator()
                    cancel_action = menu.addAction("Cancel")
                    action = menu.exec(QCursor.pos())
                    if action == move_action:
                        if sys.platform == 'win32':
                            windows_file_operations.move_files_with_dialog(file_paths, drop_target)
                    elif action == copy_action:
                        if sys.platform == 'win32':
                            windows_file_operations.copy_files_with_dialog(file_paths, drop_target)
                    elif action == link_action:
                        if sys.platform == 'win32':
                            windows_file_operations.create_shortcuts_with_dialog(file_paths, drop_target)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"{e}")
    
    def create_preview_panel(self):
        """
        Create the file preview panel on the right side of the window.
        """
        self.preview_panel = QStackedWidget()
        self.text_preview = QTextEdit()
        self.text_preview.setReadOnly(True)
        self.image_preview = QLabel()
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pdf_preview = QWebEngineView()

        self.preview_panel.setFixedWidth(200)

        main_window_palette = self.palette()
        background_color = main_window_palette.color(main_window_palette.ColorRole.Window)
        background_color_name = background_color.name()
        self.preview_panel.setStyleSheet(f"background-color: {background_color_name}")

        self.preview_panel.addWidget(self.text_preview)
        self.preview_panel.addWidget(self.image_preview)
        self.preview_panel.addWidget(self.pdf_preview)

    def quit_application(self):
        app = QApplication.instance()
        app.quit()

    def change_path(self):
        """
        Change to the directory specified in the path_label.
        """
        path = self.path_label.text()
        print("Should change path to %s" % path)
        if self.is_valid_path(path):
            parent_index = self.file_model.index(path)
            self._update_view(parent_index)
        else:
            QMessageBox.critical(self, "Error", f"The path '{path}' does not exist or is not a directory.")

    def is_valid_path(self, path):
        """
        Check if the given path is a valid directory or network path.
        """
        if os.name == 'nt' and path.startswith('\\\\'):
            QMessageBox.information(self, "Network Path", "This is a network path. Please map it first.")
            return False
        return os.path.exists(path) and os.path.isdir(path)

    def show_about(self):
        """
        Show information about the application.
        """
        QMessageBox.about(self, "About", "Miller Columns File Manager\nVersion 1.0")

    def _update_view(self, parent_index):
        """
        Update the view with the contents of the specified parent_index.
        """
        if parent_index.isValid():
            for column_view in self.columns[1:]:
                self.column_layout.removeWidget(column_view)
                column_view.deleteLater()
            self.columns = self.columns[:1]
            self.columns[0].setRootIndex(parent_index)

            # Update current directory path if it is a valid directory
            if self.file_model.isDir(parent_index):
                self.path_label.setText(os.path.dirname(self.file_model.filePath(parent_index)))

    def go_up(self):
        """
        Navigate up one directory level.
        """
        if self.columns:
            first_view = self.columns[0]
            current_index = first_view.rootIndex()
            if current_index.isValid():
                parent_index = current_index.parent()
                self._update_view(parent_index)

    def go_home(self):
        """
        Navigate to the user's home directory.
        """
        if self.columns:
            first_view = self.columns[0]
            current_index = first_view.rootIndex()
            if current_index.isValid():
                home_dir = os.path.expanduser('~')
                parent_index = self.file_model.index(home_dir)
                self._update_view(parent_index)

    def add_column(self, parent_index=None):
        column_view = DragDropListView()
        column_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        column_view.setUniformItemSizes(True)

        column_view.setAlternatingRowColors(True)
        # Set alternating row colors and text color using a style sheet
        column_view.setStyleSheet("""
            QListView::item {
                background-color: white;
                color: black;
            }
            QListView::item:alternate {
                background-color: #f7f7f7;
                color: black;
            }
            QListView::item:selected {
                color: white;
                background-color: palette(highlight);
            }
            QListView::item:selected:active {
                color: palette(highlightedText);
                background-color: palette(highlight);
            }
        """)

        column_view.setModel(self.file_model)

        if parent_index:
            column_view.setRootIndex(parent_index)

        column_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        column_view.customContextMenuRequested.connect(lambda pos: self.show_context_menu(pos, column_view))
        column_view.setDragEnabled(True)

        column_view.dragEnterEvent = self.dragEnterEvent
        column_view.dropEvent = self.dropEvent

        column_view.selectionModel().currentChanged.connect(self.on_selection_changed)
        column_view.doubleClicked.connect(self.on_double_clicked)
        column_view.selectionModel().selectionChanged.connect(lambda: status_bar.update_status_bar(self))

        self.column_layout.addWidget(column_view)
        self.columns.append(column_view)

    def on_selection_changed(self, current: QModelIndex, previous: QModelIndex):
        """
        Handle the selection change in the column view.
        """
        column_index = self.get_column_index(current)
        if column_index is not None:
            # Remove all columns to the right of the current column
            while len(self.columns) > column_index + 1:
                column_to_remove = self.columns.pop()
                self.column_layout.removeWidget(column_to_remove)
                column_to_remove.deleteLater()

            # Add a new column if the selected item is a directory
            if self.file_model.isDir(current):
                self.add_column(current)

            # Update current directory path if it is a valid directory
            if self.file_model.isDir(current):
                self.path_label.setText(self.file_model.filePath(current))

            # Update the preview panel with the selected file's content
            self.update_preview_panel(current)

    def open_folder(self, folder_path):
        """
        Open the specified folder in the column view.
        """
        if not self.is_valid_path(folder_path):
            QMessageBox.critical(self, "Error", f"The path '{folder_path}' does not exist or is not a directory.")
            return

        parent_index = self.file_model.index(folder_path)
        self._update_view(parent_index)

    def new_folder(self):
        """
        Create a new folder in the current directory.
        """
        current_index = self.columns[-1].rootIndex()
        if current_index.isValid():
            new_folder_name, ok = QInputDialog.getText(self, "New Folder", "Enter the name of the new folder:")
            if ok and new_folder_name:
                new_folder_path = os.path.join(self.file_model.filePath(current_index), new_folder_name)
                try:
                    os.mkdir(new_folder_path)
                    self.columns[-1].setRootIndex(current_index)  # Refresh the view
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"{e}")

    def get_info(self):
        selected_indexes = self.columns[-1].selectedIndexes()
        if not selected_indexes:
            # A folder is selected but no files or folders inside it are selected yet, so we need to select the folder itself
            selected_indexes = self.columns[-2].selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "No Selection", "No files or folders selected.")
            return
        paths = [self.file_model.filePath(index) for index in selected_indexes]
        getinfo.FileInfoDialog(paths, self).exec()

    def on_double_clicked(self, index: QModelIndex):
        """
        Handle the double-click event on an item in the column view.
        """
        file_path = self.file_model.filePath(index)
        try:
            os.startfile(file_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"{e}")

    def update_preview_panel(self, index: QModelIndex):
        """
        Update the preview panel with the content of the selected file.
        """
        file_path = self.file_model.filePath(index)
        file_size = self.file_model.size(index)
        if os.path.isfile(file_path) and file_size < 1024*1024*1: # Limit file size to 1 MB
            try:
                mime_type, _ = mimetypes.guess_type(file_path)
                if mime_type and mime_type.startswith('image'):
                    pixmap = QPixmap(file_path)
                    self.image_preview.setPixmap(pixmap)
                    self.preview_panel.setCurrentWidget(self.image_preview)
                elif mime_type == 'application/pdf':
                    self.pdf_preview.setUrl(QUrl.fromLocalFile(file_path))
                    self.preview_panel.setCurrentWidget(self.pdf_preview)
                else:
                    with open(file_path, 'r', errors='ignore') as file:
                        content = file.read()
                    self.text_preview.setPlainText(content)
                    self.preview_panel.setCurrentWidget(self.text_preview)
            except Exception as e:
                self.text_preview.clear()
                self.image_preview.clear()
                self.pdf_preview.setUrl(QUrl())
                self.preview_panel.setCurrentWidget(self.text_preview)
        else:
            self.text_preview.clear()
            self.image_preview.clear()
            self.pdf_preview.setUrl(QUrl())

    def get_column_index(self, index: QModelIndex):
        """
        Retrieve the index of the column associated with the given QModelIndex.
        """
        for i, column in enumerate(self.columns):
            if column.selectionModel() == self.sender():
                return i
        return None

    def closeEvent(self, event):
        """
        Handle the close event of the main window.
        """
        self.write_settings()
        super().closeEvent(event)

    def read_settings(self):
        """
        Read and apply stored application settings.
        """
        settings = QSettings("MyCompany", "MillerColumnsFileManager")
        geometry = settings.value("geometry", QByteArray())
        if geometry:
            self.restoreGeometry(geometry)

    def write_settings(self):
        """
        Save current application settings.
        """
        settings = QSettings("MyCompany", "MillerColumnsFileManager")
        settings.setValue("geometry", self.saveGeometry())

    def create_menus(self):
        """
        Create the main application menu bar and add menus.
        """
        menus.create_menus(self)

    def show_context_menu(self, pos, column_view):
        """
        Display a context menu at the given position for the specified column view.
        """
        show_context_menu(self, pos, column_view)

    def go_trash(self):
        """
        Navigate to the trash directory.
        """
        if sys.platform == 'win32':
            sys_drive = os.getenv('SystemDrive')
            trash_dir = f"{sys_drive}\\$Recycle.Bin"
        else:
            trash_dir = QDir.homePath() + '/.local/share/Trash/files/'
        self._update_view(self.file_model.index(trash_dir))

    def open_drive(self, drive):
        """
        Go to the specified drive.
        """
        parent_index = self.file_model.index(drive)
        self._update_view(parent_index)

    def add_drive_actions(self):
        """
        Add actions for every existing/connected drive letter to the Go menu.
        """
        drives = QDir.drives()
        go_menu = self.menuBar().addMenu("Go")

        for drive in drives:
            drive_path = drive.absolutePath()
            drive_action = QAction(drive_path, self)
            drive_action.triggered.connect(lambda _, path=drive_path: self._update_view(self.file_model.index(path)))
            go_menu.addAction(drive_action)

    def empty_trash(self):
        """
        Empty the trash.
        """
        trash_dir = QDir.homePath() + '/.local/share/Trash/files/'
        # Implementation to empty trash

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Output not only to the console but also to the GUI
    try:
        import log_console
    except ImportError:
        pass
    if "log_console" in sys.modules:
        app.log_console = log_console.ConsoleOutputStream()
        sys.stdout = log_console.Tee(sys.stdout, app.log_console)
        sys.stderr = log_console.Tee(sys.stderr, app.log_console)

    try:
        import styling
    except ImportError:
        pass
    if "styling" in sys.modules:
        styling.apply_styling(app)

    app.setWindowIcon(app.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
    window = MillerColumns()
    window.show()
    sys.exit(app.exec())
