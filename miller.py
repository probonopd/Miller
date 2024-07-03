import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QHBoxLayout, QListView,
    QWidget, QAbstractItemView, QMenu, QToolBar,
    QMessageBox, QLineEdit, QLabel
)
from PyQt6.QtCore import QModelIndex, QSettings, QByteArray, Qt, QSize
from PyQt6.QtGui import QFileSystemModel, QIcon, QAction

if os.name == 'nt':
    import windowsproperties
    import windowscontextmenu
    import windowsmapdrives

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
        self.resize(800, 600)  # Default size

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QHBoxLayout(self.central_widget)

        self.columns = []
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath('')
        self.file_model.setOption(QFileSystemModel.Option.DontUseCustomDirectoryIcons, False)  # Enable color icons

        home_dir = os.path.expanduser('~')
        self.add_column(self.file_model.index(home_dir))

        self.create_menus()
        self.create_toolbar()
        self.create_status_bar()  # Create status bar
        self.read_settings()

    def create_status_bar(self):
        """
        Create and initialize the status bar.
        """
        self.statusBar = self.statusBar()

        self.selected_files_label = QLabel()
        self.statusBar.addWidget(self.selected_files_label)

        self.selected_files_size_label = QLabel()
        self.statusBar.addWidget(self.selected_files_size_label)

        self.update_status_bar()

    def update_status_bar(self):
        """
        Update the status bar with current selection information.
        """
        selected_indexes = self.columns[-1].selectionModel().selectedIndexes()
        num_selected_files = len(selected_indexes)
        total_size = sum(self.file_model.size(index) for index in selected_indexes if index.isValid())

        self.selected_files_label.setText(f"Selected files: {num_selected_files}")
        # Depending on the size, display in bytes, KB, MB, or GB
        if total_size >= 1024 ** 3:
            total_size = f"{total_size / 1024 ** 3:.2f} GB"
        elif total_size >= 1024 ** 2:
            total_size = f"{total_size / 1024 ** 2:.2f} MB"
        elif total_size >= 1024:
            total_size = f"{total_size / 1024:.2f} KB"
        else:
            total_size = f"{total_size} bytes"
        self.selected_files_size_label.setText(f"Total size: {total_size}")

    def show_context_menu(self, pos, column_view):
        """
        Display a context menu at the given position for the specified column view.
        """
        index = column_view.indexAt(pos)

        if not index.isValid():
            parent_index = column_view.rootIndex()
            if parent_index.isValid():
                file_path = self.file_model.filePath(parent_index)
            else:
                return
        else:
            file_path = self.file_model.filePath(index)

        if os.name == 'nt':
            self.show_windows_context_menu(file_path)
            return

        context_menu = QMenu()

        open_action = context_menu.addAction("Open")
        open_action.triggered.connect(lambda: self.on_double_clicked(index))
        context_menu.addSeparator()

        context_menu.addAction(self.cut_action)
        context_menu.addAction(self.copy_action)
        context_menu.addAction(self.paste_action)
        context_menu.addSeparator()

        context_menu.addAction(self.move_to_trash_action)
        context_menu.addAction(self.delete_action)
        context_menu.addSeparator()

        properties_action = context_menu.addAction("Properties")
        properties_action.triggered.connect(lambda: self.show_properties(index))

        if os.name == 'nt':
            context_menu.addSeparator()
            show_windows_context_menu = context_menu.addAction("Show Windows Context Menu")
            show_windows_context_menu.triggered.connect(lambda: self.show_windows_context_menu(file_path))
            context_menu.addAction(show_windows_context_menu)

        context_menu.exec(column_view.viewport().mapToGlobal(pos))

    def show_windows_context_menu(self, file_path):
        """
        Display the Windows context menu for the specified file path.
        """
        try:
            windowscontextmenu.show_context_menu(file_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"{e}")

    def show_properties(self, index: QModelIndex):
        """
        Show properties for the file or directory specified by the QModelIndex.
        """
        if index.isValid():
            file_path = self.file_model.filePath(index)
            if os.name == 'nt':
                windowsproperties.get_file_properties(file_path)
            else:
                print("show_properties not implemented for this platform")

    def create_menus(self):
        """
        Create the main application menu bar and add menus.
        """
        # Create a menubar
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")
        close_action = QAction("Close", self)
        close_action.triggered.connect(self.close)
        map_drive_action = QAction("Map Network Drive", self)
        map_drive_action.triggered.connect(self.map_network_drive)
        unmap_drive_action = QAction("Unmap Network Drive", self)
        unmap_drive_action.triggered.connect(self.unmap_network_drive)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        file_menu.addAction(close_action)
        file_menu.addSeparator()
        if os.name == 'nt':
            file_menu.addAction(map_drive_action)
            file_menu.addAction(unmap_drive_action)
            file_menu.addSeparator()
        file_menu.addAction(quit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        self.undo_action = QAction("Undo", self)
        self.undo_action.setEnabled(False)
        self.cut_action = QAction("Cut", self)
        self.cut_action.setEnabled(False)
        self.copy_action = QAction("Copy", self)
        self.copy_action.setEnabled(False)
        self.paste_action = QAction("Paste", self)
        self.paste_action.setEnabled(False)
        self.move_to_trash_action = QAction("Move to Trash", self)
        self.move_to_trash_action.setEnabled(False)
        self.delete_action = QAction("Delete", self)
        self.delete_action.setEnabled(False)
        self.empty_trash_action = QAction("Empty Trash", self)
        self.empty_trash_action.setEnabled(False)
        self.empty_trash_action.triggered.connect(self.empty_trash)

        edit_menu.addAction(self.undo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.cut_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.paste_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.move_to_trash_action)
        edit_menu.addAction(self.delete_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.empty_trash_action)

        # Help menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def map_network_drive(self):
        """
        Open a dialog to map a network drive.
        """
        if os.name == 'nt':
            network_drive_manager = windowsmapdrives.NetworkDriveManager()
            map_dialog = windowsmapdrives.MapDriveDialog(network_drive_manager)
            map_dialog.exec()

    def unmap_network_drive(self):
        """
        Open a dialog to unmap a network drive.
        """
        if os.name == 'nt':
            network_drive_manager = windowsmapdrives.NetworkDriveManager()
            unmap_dialog = windowsmapdrives.UnmapDriveDialog(network_drive_manager)
            unmap_dialog.exec()

    def move_to_trash(self, indexes):
        """
        Move the specified indexes to the trash.
        """
        print("Move to trash")

    def delete(self, indexes):
        """
        Delete the specified indexes.
        """
        print("Delete")

    def empty_trash(self):
        """
        Empty the trash.
        """
        print("Empty trash")

    def create_toolbar(self):
        """
        Create the main application toolbar.
        """
        # Create a toolbar
        toolbar = QToolBar("Navigation")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        up_action = QAction(QIcon.fromTheme("go-up"), "Up", self)
        up_action.triggered.connect(self.go_up)
        toolbar.addAction(up_action)

        home_action = QAction(QIcon.fromTheme("home"), "Home", self)
        home_action.triggered.connect(self.go_home)
        toolbar.addAction(home_action)

        # Add a QLineEdit to show current directory path
        self.path_label = QLineEdit()
        self.path_label.setReadOnly(False)  # Make it editable
        self.path_label.setPlaceholderText("Enter Directory Path")
        self.path_label.returnPressed.connect(self.change_path)  # Connect the returnPressed signal to change_path method
        toolbar.addWidget(self.path_label)

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
        QMessageBox.about(self, "About", "Miller Columns File Manager\nhttps://github.com/probonopd/Miller")

    def _update_view(self, parent_index):
        """
        Update the view with the contents of the specified parent_index.
        """
        if parent_index.isValid():
            for column_view in self.columns[1:]:
                self.layout.removeWidget(column_view)
                column_view.deleteLater()
            self.columns = self.columns[:1]
            self.columns[0].setRootIndex(parent_index)

            # Update current directory path if it is a valid directory
            if self.file_model.isDir(parent_index):
                self.path_label.setText(self.file_model.filePath(parent_index))

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
        """
        Add a new column view displaying the contents of the directory at parent_index.
        """
        column_view = QListView()
        column_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # Allow multiple selections
        column_view.setUniformItemSizes(True)
        column_view.setAlternatingRowColors(True)  # Enable alternating row colors
        column_view.setModel(self.file_model)

        if parent_index:
            column_view.setRootIndex(parent_index)

        self.layout.addWidget(column_view)
        self.columns.append(column_view)

        column_view.selectionModel().currentChanged.connect(self.on_selection_changed)
        column_view.doubleClicked.connect(self.on_double_clicked)

        # Ensure context menu policy is set
        column_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Connect the custom context menu
        column_view.customContextMenuRequested.connect(lambda pos: self.show_context_menu(pos, column_view))

        # Connect selection change to update status bar
        column_view.selectionModel().selectionChanged.connect(self.update_status_bar)

        # Allow dragging
        column_view.setDragEnabled(True)

    def on_selection_changed(self, current: QModelIndex, previous: QModelIndex):
        """
        Handle the selection change in the column view.
        """
        column_index = self.get_column_index(current)
        if column_index is not None:
            # Remove all columns to the right of the current column
            while len(self.columns) > column_index + 1:
                column_to_remove = self.columns.pop()
                self.layout.removeWidget(column_to_remove)
                column_to_remove.deleteLater()

            # Add a new column if the selected item is a directory
            if self.file_model.isDir(current):
                self.add_column(current)

            # Update current directory path if it is a valid directory
            if self.file_model.isDir(current):
                self.path_label.setText(self.file_model.filePath(current))

    def on_double_clicked(self, index: QModelIndex):
        """
        Handle the double-click event on an item in the column view.
        """
        file_path = self.file_model.filePath(index)
        os.startfile(file_path)

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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MillerColumns()
    window.show()
    sys.exit(app.exec())
