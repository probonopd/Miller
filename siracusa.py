#!/usr/bin/env python3
"""
A spatial file manager (“Siracusa style spatial Filer) implemented in PyQt6.
Features:
  • Files and folders are represented as movable icons in a QGraphicsScene.
  • When dragging an item (i.e. dragging it out of the window), its rendered appearance is used as visual feedback.
  • A full menu bar is provided with File, Edit, View, and Help menus.
  • Double clicking a folder opens a new window for that folder.
  • Double clicking a file opens it using the system’s default application.
  • You can delete selected items via the Edit menu.
  • Layout (item positions, window geometry) in each folder is saved/restored to/from ._layout.json in that folder.
  • Copy/Cut/Paste actions are implemented with progress dialogs (cancelable, with a status bar).
  • Drag-and-drop between windows is supported – on drop a popup menu lets you choose copy/move/symlink.
  • Spring‐loaded folders: while dragging, hovering over a folder for 1 second opens it;
        if the cursor then moves away, the spring‐loaded window will close after a delay.
  • Items have context menus (with Open, Get Info… and Delete).
  • “Align to Grid” action aligns items to a grid.
  • “Sort by Name/Date/Size/Type” actions are available.
  • When a window for a folder is already open, it is brought to the front.
  • When a window is closed, its layout is automatically saved.
  • A status bar shows useful information.
  • “Get Info…” action (and context menu) shows file/folder properties (Ctrl+I shortcut).
  • Free movement of items and drag-and-drop. Free movement within the window, and drag-and-drop between windows.
  • Dropped items are placed at the exact drop position, not at the top-left corner of the window.
  • The representation of what is being dragged looks exactly like the item being dragged when in the window.
  • We watch the filesystem for changes and update the view accordingly. This includes new files/folders, deletions, and modifications. We use QFileSystemWatcher for this.
  • We render the desktop folder in full-screen mode when the application starts.

TODO/FIXME:
* When multiple items are dragged outside of the window, the items are not positioned at the correct coordinates (relative to each other like in the original window) in the new window.
* When multiple items are dragged outside of the window, the free movement of the items needs to be reset to the original positions in the original window, like we do for a single item.
* When refreshing a window, the scene is not positioned correctly; unlike what happens when the window is first opened or is resized.

* During free movement, the position of the item relative to the mouse cursor is not maintained correctly. However, when dragging an item, the position is correct - it should be consistent between the two modes.

* File operations also need to work with Cut/Copy/Paste from the main and context menus, not just drag-and-drop.
"""

import os
import sys
import json
import shutil
import time

from PyQt6 import QtWidgets, QtGui, QtCore

# Name of the file used to store layout information in each folder.
LAYOUT_FILENAME = "._layout.json"


# ---------------- File Operation Thread (for copy/cut/paste and drag–drop operations) ----------------
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
                    os.remove(src)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
    
    def cancel(self):
        self._isCanceled = True


# ---------------- Spatial Filer View (subclassed QGraphicsView for drag–drop, multiple selection, and spring–loaded folders) ----------------
class SpatialFilerView(QtWidgets.QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        # Enable rubber band selection (allows Shift and drag–selection)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.RubberBandDrag)
        self.spring_item = None
        # Timer used to trigger spring loaded folder opening
        self.spring_timer = QtCore.QTimer(self)
        self.spring_timer.setSingleShot(True)
        self.spring_timer.setInterval(1000)
        self.spring_timer.timeout.connect(self.handleSpringOpen)
        # Timer for closing spring loaded windows when cursor moves away
        self.spring_close_timer = QtCore.QTimer(self)
        self.spring_close_timer.setSingleShot(True)
        self.spring_close_timer.setInterval(1000)
        self.spring_close_timer.timeout.connect(self.handleSpringClose)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if (event.mimeData().hasFormat("application/x-fileitem") or
            event.mimeData().hasFormat("application/x-fileitems")):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent):
        if event.mimeData().hasFormat("application/x-fileitem") or event.mimeData().hasFormat("application/x-fileitems"):
            event.acceptProposedAction()
            pos = event.position().toPoint()
            item = self.itemAt(pos)
            if isinstance(item, FileItem) and item.is_folder:
                # If we are hovering over a new folder icon, start the spring open timer
                if self.spring_item != item:
                    self.spring_item = item
                    self.spring_timer.start()
                    self.spring_close_timer.stop()
            else:
                # If not hovering over the same folder, start the close timer for any spring–loaded window.
                if self.spring_item is not None:
                    self.spring_timer.stop()
                    self.spring_close_timer.start()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event: QtGui.QDragLeaveEvent):
        # When the drag leaves the view, cancel any spring timers.
        self.spring_timer.stop()
        self.spring_close_timer.start()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent):
        if (event.mimeData().hasFormat("application/x-fileitems") or
            event.mimeData().hasFormat("application/x-fileitem")):
            event.acceptProposedAction()
            # Determine drop position in scene coordinates.
            drop_scene_pos = self.mapToScene(event.position().toPoint())
            # Check for multiple items drag first.
            if event.mimeData().hasFormat("application/x-fileitems"):
                data = event.mimeData().data("application/x-fileitems")
                try:
                    file_paths = json.loads(bytes(data).decode("utf-8"))
                except Exception:
                    file_paths = []
            else:
                data = event.mimeData().data("application/x-fileitem")
                file_paths = [bytes(data).decode("utf-8")]
            # Popup a menu to choose the action.
            menu = QtWidgets.QMenu(self)
            copy_action = menu.addAction("Copy")
            move_action = menu.addAction("Move")
            symlink_action = menu.addAction("Symlink")
            cancel_action = menu.addAction("Cancel")
            global_pos = self.mapToGlobal(event.position().toPoint())
            action = menu.exec(global_pos)
            if action == copy_action:
                chosen = "copy"
            elif action == move_action:
                chosen = "move"
            elif action == symlink_action:
                chosen = "symlink"
            else:
                chosen = None

            if chosen:
                main_window = self.window()
                if isinstance(main_window, SpatialFilerWindow):
                    main_window.process_drop_operation(file_paths, chosen, drop_scene_pos)
        else:
            super().dropEvent(event)

    def handleSpringOpen(self):
        # Called when the spring timer expires; if the cursor is still over the same folder, open it.
        if self.spring_item is not None:
            current_item = self.itemAt(self.mapFromGlobal(QtGui.QCursor.pos()))
            if current_item == self.spring_item:
                main_window = self.window()
                if isinstance(main_window, SpatialFilerWindow):
                    # Open the folder in spring–loaded mode
                    main_window.open_folder_from_item(self.spring_item.file_path, spring_loaded=True)
            self.spring_timer.stop()

    def handleSpringClose(self):
        # If the cursor is no longer over the spring–loaded folder, close its window.
        if self.spring_item is not None:
            current_item = self.itemAt(self.mapFromGlobal(QtGui.QCursor.pos()))
            if current_item != self.spring_item:
                # If a spring–loaded window exists for this folder, close it.
                window = SpatialFilerWindow.open_windows.get(self.spring_item.file_path)
                if window is not None and getattr(window, "spring_loaded", False):
                    window.close()
                self.spring_item = None
        self.spring_close_timer.stop()


# ---------------- File Item (represents a file or folder icon) ----------------
class FileItem(QtWidgets.QGraphicsObject):
    # Signal to request opening a folder.
    openFolderRequested = QtCore.pyqtSignal(str)

    def __init__(self, file_path: str, pos: QtCore.QPointF, width: int = 80, height: int = 80):
        super().__init__()
        self.file_path = file_path
        self.width = width
        self.height = height
        self.setFlags(
            QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setPos(pos)
        self.is_folder = os.path.isdir(file_path)

        icon_provider = QtWidgets.QFileIconProvider()
        file_info = QtCore.QFileInfo(file_path)
        self.icon = icon_provider.icon(file_info)
        icon_size = QtCore.QSize(48, 48)
        self.pixmap = self.icon.pixmap(icon_size)

        self.font = QtGui.QFont()
        self.font.setPointSize(8)

        self.drag_start_position = None

    def boundingRect(self) -> QtCore.QRectF:
        # Accommodate the icon and file name.
        return QtCore.QRectF(0, 0, self.width, self.height + 20)

    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionGraphicsItem, widget=None):
        # Draw background rectangle.
        if self.isSelected():
            painter.setBrush(QtGui.QBrush(QtGui.QColor(200, 220, 255)))
        else:
            painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, 0)))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        painter.drawRect(0, 0, self.width, self.height)

        # Draw the icon centered.
        pix_w = self.pixmap.width()
        pix_h = self.pixmap.height()
        offset_x = (self.width - pix_w) / 2
        offset_y = 48 - pix_h
        painter.drawPixmap(QtCore.QPointF(offset_x, offset_y), self.pixmap)

        # Draw the file/folder name.
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        painter.setFont(self.font)
        base_name = os.path.basename(self.file_path)
        metrics = painter.fontMetrics()
        elided_text = metrics.elidedText(base_name, QtCore.Qt.TextElideMode.ElideMiddle, self.width)
        text_width = metrics.horizontalAdvance(elided_text)
        painter.drawText(int((self.width - text_width) / 2), self.height - 15, elided_text)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        self.setOpacity(0.6)
        # Record the screen position where the press occurred.
        self.drag_start_position = event.screenPos()
        # Also store the current (original) scene position for potential reversion.
        self._original_pos = self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        # Get the current global mouse position.
        global_pos = event.screenPos()

        # Check if the mouse is inside the window's frame.
        if self.scene() and self.scene().views():
            main_window = self.scene().views()[0].window()
            if main_window.frameGeometry().contains(global_pos):
                # The mouse is inside the window: continue free repositioning.
                super().mouseMoveEvent(event)
                return

        # The mouse is outside the window.
        if self.drag_start_position is None:
            self.drag_start_position = event.screenPos()

        # Calculate the distance moved from the original press position.
        distance = (event.screenPos() - self.drag_start_position).manhattanLength()
        if distance > 10:
            # The mouse has moved enough outside the window: cancel any repositioning.
            self.setPos(self._original_pos)
            # Prepare to start a drag–drop operation.
            drag = QtGui.QDrag(event.widget())
            mime_data = QtCore.QMimeData()
            selected = self.scene().selectedItems()
            if len(selected) > 1:
                # Handle dragging multiple items.
                file_paths = [item.file_path for item in selected if isinstance(item, FileItem)]
                mime_data.setData("application/x-fileitems", json.dumps(file_paths).encode("utf-8"))
                # Create a composite pixmap for all selected items.
                rect = QtCore.QRectF()
                for item in selected:
                    rect = rect.united(item.sceneBoundingRect())
                pixmap = QtGui.QPixmap(int(rect.width()), int(rect.height()))
                pixmap.fill(QtCore.Qt.GlobalColor.transparent)
                painter = QtGui.QPainter(pixmap)
                self.scene().render(painter, target=QtCore.QRectF(pixmap.rect()), source=rect)
                painter.end()
                drag.setPixmap(pixmap)
            else:
                # Single item drag.
                mime_data.setData("application/x-fileitem", self.file_path.encode("utf-8"))
                rect = self.boundingRect()
                pixmap = QtGui.QPixmap(int(rect.width()), int(rect.height()))
                pixmap.fill(QtCore.Qt.GlobalColor.transparent)
                painter = QtGui.QPainter(pixmap)
                option = QtWidgets.QStyleOptionGraphicsItem()
                if self.scene().views():
                    option.widget = self.scene().views()[0]
                self.paint(painter, option)
                painter.end()
                drag.setPixmap(pixmap)
            drag.setMimeData(mime_data)
            drag.exec(QtCore.Qt.DropAction.MoveAction | QtCore.Qt.DropAction.CopyAction)
            self.drag_start_position = None
            return

        # Otherwise, continue with the default free repositioning.
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        self.setOpacity(1.0)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        # On double-click, open folder or launch file.
        if self.is_folder:
            self.openFolderRequested.emit(self.file_path)
        else:
            url = QtCore.QUrl.fromLocalFile(self.file_path)
            QtGui.QDesktopServices.openUrl(url)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event: QtWidgets.QGraphicsSceneContextMenuEvent):
        # Context menu with Open, Get Info, and Delete.
        menu = QtWidgets.QMenu()
        open_action = menu.addAction("Open")
        info_action = menu.addAction("Get Info...")
        delete_action = menu.addAction("Delete")
        action = menu.exec(event.screenPos())
        if action == open_action:
            if self.is_folder:
                self.openFolderRequested.emit(self.file_path)
            else:
                url = QtCore.QUrl.fromLocalFile(self.file_path)
                QtGui.QDesktopServices.openUrl(url)
        elif action == info_action:
            self.show_info()
        elif action == delete_action:
            reply = QtWidgets.QMessageBox.question(
                None, "Delete Confirmation",
                f"Are you sure you want to delete {os.path.basename(self.file_path)}?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                try:
                    if os.path.islink(self.file_path):
                        os.remove(self.file_path)
                    elif os.path.isdir(self.file_path) and not os.path.islink(self.file_path):
                        shutil.rmtree(self.file_path)
                    else:
                        os.remove(self.file_path)
                    if self.scene():
                        self.scene().removeItem(self)
                except Exception as e:
                    QtWidgets.QMessageBox.critical(None, "Error", f"Error deleting file: {e}")

    def show_info(self):
        try:
            info = os.stat(self.file_path)
            size = info.st_size
            mtime = time.ctime(info.st_mtime)
            ctime = time.ctime(info.st_ctime)
            info_text = (f"Path: {self.file_path}\nSize: {size} bytes\n"
                         f"Modified: {mtime}\nCreated: {ctime}")
            QtWidgets.QMessageBox.information(None, "File Info", info_text)
        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Error", f"Could not retrieve file info: {e}")


# ---------------- Spatial Filer Window (main file/folder view) ----------------
class SpatialFilerWindow(QtWidgets.QMainWindow):
    # Global registry of open windows by folder path.
    open_windows = {}

    def __init__(self, folder_path: str, layout_data: dict = None):
        super().__init__()
        self.folder_path = folder_path
        self.setWindowTitle(f"Spatial Filer - {os.path.basename(folder_path)}")
        self.setGeometry(100, 100, 800, 600)
        self.spring_loaded = False  # will be set True if opened via spring–load

        self.scene = QtWidgets.QGraphicsScene(self)
        self.view = SpatialFilerView(self)
        self.view.setScene(self.scene)
        self.setCentralWidget(self.view)

        self.file_items = []
        self.clipboard = []          # For Copy/Cut/Paste: list of file paths.
        self.clipboard_operation = None  # "copy" or "cut"
        self.child_windows = []
        self.drop_target_positions = {}  # Mapping destination file paths to drop positions.

        self.layout_data = layout_data if layout_data else {}
        # Restore window geometry if available.
        if self.layout_data.get("window_geometry"):
            try:
                geom = QtCore.QByteArray.fromBase64(
                    self.layout_data["window_geometry"].encode("utf-8")
                )
                self.restoreGeometry(geom)
            except Exception:
                pass

        self.create_menus()
        self.load_files()
        self.update_status_bar()

        # Register this window (keyed by folder path).
        SpatialFilerWindow.open_windows[self.folder_path] = self

        self.watcher = QtCore.QFileSystemWatcher(self)
        self.watcher.addPath(self.folder_path)
        self.watcher.directoryChanged.connect(self.refresh_view)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scene.setSceneRect(0, 0, event.size().width(), event.size().height())

    def create_menus(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("File")
        open_folder_action = QtGui.QAction("Open Folder", self)
        open_folder_action.setShortcut("Ctrl+O")
        open_folder_action.triggered.connect(self.open_folder)
        file_menu.addAction(open_folder_action)

        new_folder_action = QtGui.QAction("New Folder", self)
        new_folder_action.setShortcut("Ctrl+Shift+N")
        new_folder_action.triggered.connect(self.new_folder)
        file_menu.addAction(new_folder_action)
        file_menu.addSeparator()

        get_info_action = QtGui.QAction("Get Info...", self)
        get_info_action.setShortcut("Ctrl+I")
        get_info_action.triggered.connect(self.get_info)
        file_menu.addAction(get_info_action)
        file_menu.addSeparator()

        exit_action = QtGui.QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit Menu
        edit_menu = menubar.addMenu("Edit")
        copy_action = QtGui.QAction("Copy", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self.copy_selected)
        edit_menu.addAction(copy_action)

        cut_action = QtGui.QAction("Cut", self)
        cut_action.setShortcut("Ctrl+X")
        cut_action.triggered.connect(self.cut_selected)
        edit_menu.addAction(cut_action)

        paste_action = QtGui.QAction("Paste", self)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(self.paste_items)
        edit_menu.addAction(paste_action)
        edit_menu.addSeparator()

        delete_action = QtGui.QAction("Delete", self)
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self.delete_selected)
        edit_menu.addAction(delete_action)

        select_all_action = QtGui.QAction("Select All", self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(self.select_all)
        edit_menu.addAction(select_all_action)

        # View Menu
        view_menu = menubar.addMenu("View")
        refresh_action = QtGui.QAction("Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_view)
        view_menu.addAction(refresh_action)

        align_action = QtGui.QAction("Align to Grid", self)
        align_action.setShortcut("Ctrl+G")
        align_action.triggered.connect(self.align_to_grid)
        view_menu.addAction(align_action)

        sort_menu = view_menu.addMenu("Sort")
        sort_name = QtGui.QAction("By Name", self)
        sort_name.triggered.connect(lambda: self.sort_items("name"))
        sort_menu.addAction(sort_name)
        sort_date = QtGui.QAction("By Date", self)
        sort_date.triggered.connect(lambda: self.sort_items("date"))
        sort_menu.addAction(sort_date)
        sort_size = QtGui.QAction("By Size", self)
        sort_size.triggered.connect(lambda: self.sort_items("size"))
        sort_menu.addAction(sort_size)
        sort_type = QtGui.QAction("By Type", self)
        sort_type.triggered.connect(lambda: self.sort_items("type"))
        sort_menu.addAction(sort_type)

        # Help Menu (now without Get Info...)
        help_menu = menubar.addMenu("Help")
        about_action = QtGui.QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def load_files(self):
        try:
            folder_files = os.listdir(self.folder_path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Cannot read folder: {e}")
            return

        # Skip hidden files/folders and system files.
        folder_files = [name for name in folder_files if not name.startswith(".")]
        folder_files = [name for name in folder_files if name.lower() not in ("desktop.ini", ".ds_store")]

        margin = 100
        x, y = 0, 0
        for name in sorted(folder_files):
            full_path = os.path.join(self.folder_path, name)
            if os.path.isfile(full_path) or os.path.isdir(full_path):
                if self.layout_data.get("items", {}).get(full_path):
                    pos_x, pos_y = self.layout_data["items"][full_path]
                elif full_path in self.drop_target_positions:
                    pos = self.drop_target_positions.pop(full_path)
                    pos_x, pos_y = pos.x(), pos.y()
                else:
                    pos_x, pos_y = x, y
                    x += margin
                    if x > self.width() - margin:
                        x = 0
                        y += margin
                item = FileItem(full_path, QtCore.QPointF(pos_x, pos_y))
                item.openFolderRequested.connect(self.open_folder_from_item)
                self.scene.addItem(item)
                self.file_items.append(item)
        self.scene.setSceneRect(0, 0, x, y + margin)

    def get_layout(self) -> dict:
        layout = {"items": {}}
        for item in self.file_items:
            layout["items"][item.file_path] = (item.x(), item.y())
        # Save window geometry as a base64-encoded string.
        geom = self.saveGeometry().toBase64().data().decode("utf-8")
        layout["window_geometry"] = geom
        return layout

    def save_layout(self):
        layout = self.get_layout()
        layout_file_path = os.path.join(self.folder_path, LAYOUT_FILENAME)
        try:
            with open(layout_file_path, "w") as f:
                json.dump(layout, f, indent=4)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error saving layout: {e}")

    def open_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder", self.folder_path)
        if folder:
            SpatialFilerWindow.get_or_create_window(folder)

    def open_folder_from_item(self, folder_path: str, spring_loaded: bool = False):
        SpatialFilerWindow.get_or_create_window(folder_path, spring_loaded)

    def delete_selected(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.information(self, "Delete", "No items selected.")
            return

        names = "\n".join([os.path.basename(item.file_path) for item in selected_items])
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Confirmation",
            f"Delete the following items?\n{names}",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            for item in selected_items:
                try:
                    if os.path.islink(item.file_path):
                        os.remove(item.file_path)
                    elif os.path.isdir(item.file_path) and not os.path.islink(item.file_path):
                        shutil.rmtree(item.file_path)
                    else:
                        os.remove(item.file_path)
                    self.scene.removeItem(item)
                    if item in self.file_items:
                        self.file_items.remove(item)
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Error", f"Error deleting {item.file_path}: {e}")
            self.update_status_bar()

    def refresh_view(self):
        self.layout_data = self.get_layout()  # store current positions
        for item in self.file_items:
            self.scene.removeItem(item)
        self.file_items.clear()
        self.load_files()
        self.update_status_bar()
        self.scene.setSceneRect(0, 0, self.width(), self.height())

    def align_to_grid(self):
        grid_size = 80
        for item in self.file_items:
            new_x = round(item.x() / grid_size) * grid_size
            new_y = round(item.y() / grid_size) * grid_size
            item.setPos(new_x, new_y)
        self.update_status_bar()

    def sort_items(self, criterion):
        def get_key(item):
            try:
                if criterion == "name":
                    return os.path.basename(item.file_path).lower()
                elif criterion == "date":
                    return os.path.getmtime(item.file_path)
                elif criterion == "size":
                    return os.path.getsize(item.file_path)
                elif criterion == "type":
                    return os.path.splitext(item.file_path)[1].lower()
            except Exception:
                return 0

        sorted_items = sorted(self.file_items, key=get_key)
        margin = 100
        x, y = 0, 0
        for item in sorted_items:
            item.setPos(x, y)
            x += margin
            if x > self.width() - margin:
                x = 0
                y += margin
        self.update_status_bar()

    def update_status_bar(self):
        self.statusBar().showMessage(f"Folder: {self.folder_path} | Items: {len(self.file_items)}")

    def get_info(self):
        selected = self.scene.selectedItems()
        if selected:
            if len(selected) == 1:
                try:
                    st = os.stat(selected[0].file_path)
                    size = st.st_size
                    mtime = time.ctime(st.st_mtime)
                    ctime = time.ctime(st.st_ctime)
                    info_text = (f"Path: {selected[0].file_path}\nSize: {size} bytes\n"
                                 f"Modified: {mtime}\nCreated: {ctime}")
                except Exception as e:
                    info_text = f"Error retrieving info: {e}"
                QtWidgets.QMessageBox.information(self, "Info", info_text)
            else:
                info_text = ""
                total_size = 0
                for item in selected:
                    try:
                        st = os.stat(item.file_path)
                        size = st.st_size
                        total_size += size
                        info_text += f"{os.path.basename(item.file_path)}: {size} bytes\n"
                    except Exception as e:
                        info_text += f"{os.path.basename(item.file_path)}: error\n"
                info_text += f"\nTotal items: {len(selected)}\nTotal size: {total_size} bytes"
                QtWidgets.QMessageBox.information(self, "Selected Items Info", info_text)
        else:
            QtWidgets.QMessageBox.information(
                self, "Folder Info", f"Folder: {self.folder_path}\nItems: {len(self.file_items)}"
            )

    def process_drop_operation(self, src_file, operation, drop_pos=None):
        # Accept either a single file path (string) or a list of paths.
        operations = []
        if isinstance(src_file, list):
            for i, f in enumerate(src_file):
                dest = os.path.join(self.folder_path, os.path.basename(f))
                operations.append((f, dest))
                if drop_pos is not None:
                    offset = QtCore.QPointF(i * 10, i * 10)
                    self.drop_target_positions[dest] = drop_pos + offset
        else:
            dest = os.path.join(self.folder_path, os.path.basename(src_file))
            operations = [(src_file, dest)]
            if drop_pos is not None:
                self.drop_target_positions[dest] = drop_pos
        self.run_file_operation(operations, operation)

    def run_file_operation(self, operations, op_type):
        total_size = sum(os.path.getsize(src) for src, _ in operations if os.path.exists(src))
        progress_dialog = QtWidgets.QProgressDialog("Performing operation...", "Cancel", 0, 100, self)
        progress_dialog.setWindowTitle("Progress")
        progress_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress_dialog.show()

        self.op_thread = FileOperationThread(operations, op_type, total_size)
        self.op_thread.progress.connect(progress_dialog.setValue)
        self.op_thread.error.connect(lambda msg: QtWidgets.QMessageBox.critical(self, "Error", msg))
        self.op_thread.finished.connect(lambda: (progress_dialog.close(), self.refresh_view()))
        progress_dialog.canceled.connect(self.op_thread.cancel)
        self.op_thread.start()

    def copy_selected(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.information(self, "Copy", "No items selected.")
            return

        self.clipboard = [item.file_path for item in selected_items]
        self.clipboard_operation = "copy"

        clipboard = QtWidgets.QApplication.clipboard()
        mime_data = QtCore.QMimeData()
        mime_data.setData("application/x-fileitems", json.dumps({"files": self.clipboard, "operation": "copy"}).encode("utf-8"))
        clipboard.setMimeData(mime_data)

        self.statusBar().showMessage(f"Copied {len(self.clipboard)} item(s)")

    def cut_selected(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.information(self, "Cut", "No items selected.")
            return

        self.clipboard = [item.file_path for item in selected_items]
        self.clipboard_operation = "cut"

        clipboard = QtWidgets.QApplication.clipboard()
        mime_data = QtCore.QMimeData()
        mime_data.setData("application/x-fileitems", json.dumps({"files": self.clipboard, "operation": "cut"}).encode("utf-8"))
        clipboard.setMimeData(mime_data)

        self.statusBar().showMessage(f"Cut {len(self.clipboard)} item(s)")

    def paste_items(self):
        clipboard = QtWidgets.QApplication.clipboard()
        mime_data = clipboard.mimeData()

        if not mime_data.hasFormat("application/x-fileitems"):
            QtWidgets.QMessageBox.information(self, "Paste", "Clipboard is empty or invalid.")
            return

        try:
            data = json.loads(mime_data.data("application/x-fileitems").data().decode("utf-8"))
            files = data["files"]
            operation = data["operation"]
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Invalid clipboard data: {e}")
            return

        if not files:
            return

        operations = []
        for src in files:
            dest = os.path.join(self.folder_path, os.path.basename(src))
            operations.append((src, dest))

        self.run_file_operation(operations, operation)

        if operation == "cut":
            # Clear clipboard after moving
            self.clipboard = []
            self.clipboard_operation = None
            clipboard.clear()


    def show_about(self):
        QtWidgets.QMessageBox.about(
            self,
            "About Spatial Filer",
            "Spatial Filer Demo\n\nA spatial file manager implemented in PyQt6\nInspired by Siracusa-style spatial file managers.",
        )

    def new_folder(self):
        folder_name, ok = QtWidgets.QInputDialog.getText(self, "New Folder", "Folder Name:")
        if ok and folder_name:
            new_folder_path = os.path.join(self.folder_path, folder_name)
            try:
                os.mkdir(new_folder_path)
                self.refresh_view()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Could not create folder: {e}")

    def select_all(self):
        for item in self.file_items:
            item.setSelected(True)

    def closeEvent(self, event):
        self.save_layout()
        if self.folder_path in SpatialFilerWindow.open_windows:
            del SpatialFilerWindow.open_windows[self.folder_path]
        super().closeEvent(event)

    @staticmethod
    def get_or_create_window(folder_path, spring_loaded: bool = False):
        if folder_path in SpatialFilerWindow.open_windows:
            window = SpatialFilerWindow.open_windows[folder_path]
            window.raise_()
            window.activateWindow()
            if spring_loaded:
                window.spring_loaded = True
            return window
        else:
            layout_data = {}
            layout_file_path = os.path.join(folder_path, LAYOUT_FILENAME)
            if os.path.exists(layout_file_path):
                try:
                    with open(layout_file_path, "r") as f:
                        layout_data = json.load(f)
                except Exception:
                    pass
            new_window = SpatialFilerWindow(folder_path, layout_data)
            new_window.spring_loaded = spring_loaded
            new_window.show()
            return new_window


# ---------------- Main Application Object ----------------
class MainObject:
    def __init__(self):
        desktop = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.DesktopLocation)
        for screen in QtWidgets.QApplication.screens():
            desktop_window = SpatialFilerWindow.get_or_create_window(desktop)
            desktop_window.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
            desktop_window.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnBottomHint)
            desktop_window.move(screen.geometry().x(), screen.geometry().y())
            desktop_window.resize(screen.geometry().width(), screen.geometry().height())
            desktop_window.show()

def main():
    app = QtWidgets.QApplication(sys.argv)
    main_obj = MainObject()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
