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
* When multiple items are dragged, the items are not positioned at the correct coordinates in the pixmap (especially the one clicked on vs. the others; positions should stay relative to each other like in the original window). Could using a QGraphicsItemGroup help?
* Why is no filename shown underneath the icon for disks? Maybe first create all FileItems and then set their positions in a second loop? This way we could set a nice display title for disks.

FOR TESTING:
* WIndows is ideal for testing because one can test the same code easily using WSL on Debian without and with Wayland, and on Windows natively.
"""

import os, sys, signal, json, shutil, subprocess

from PyQt6 import QtWidgets, QtGui, QtCore

if sys.platform == "win32":
    from win32com.client import Dispatch

import getinfo, menus
LAYOUT_FILENAME = "._layout.json"

item_width = grid_width = 100
item_height = grid_height = 60

from styling import setup_icon_theme
setup_icon_theme()
icon_provider = QtWidgets.QFileIconProvider()

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
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
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
        # 0px border is crucial for scroll bars to be visible when needed and invisible when not needed.
        self.setStyleSheet("QGraphicsView { border: 0px solid red; }")

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if (event.mimeData().hasFormat("application/x-fileitem") or
            event.mimeData().hasFormat("application/x-fileitems")):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent):
        print("Drag move event")
        if event.mimeData().hasFormat("application/x-fileitem") or event.mimeData().hasFormat("application/x-fileitems"):
            event.acceptProposedAction()
            pos = event.position().toPoint()
            item = self.itemAt(pos)
            print("Hovering over item:", item)
            if isinstance(item, FileItem) and item.is_folder:
                print("Hovering over folder in dragMoveEvent:", item.file_path)
                if self.spring_item != item:
                    self.spring_item = item
                    self.spring_timer.start()
                    self.spring_close_timer.stop()
            else:
                if self.spring_item is not None:
                    self.spring_timer.stop()
                    self.spring_close_timer.start()
        else:
            super().dragMoveEvent(event)

    def mouseMoveEvent(self, event):
        item = self.itemAt(event.pos())
        if item is not None and item.isSelected():
            # If the item is selected, we should not trigger spring-loaded folder opening to prevent spring-opening the folder we are dragging.
            self.spring_item = None
            self.spring_timer.stop()
            self.spring_close_timer.stop()
        elif isinstance(item, FileItem) and item.is_folder:
            print("Hovering over folder in mouseMoveEvent:", item)
            if self.spring_item != item:
                self.spring_item = item
                self.spring_timer.start()
                self.spring_close_timer.stop()
        else:
            self.spring_timer.stop()
            self.spring_close_timer.start()

        # FIXME: Start a drag operation if the mouse leaves the window while dragging an item? Or do we have to start the drag even earlier?

        return super().mouseMoveEvent(event)

    def dragLeaveEvent(self, event: QtGui.QDragLeaveEvent):
        # When the drag leaves the view, cancel any spring timers.
        self.spring_timer.stop()
        self.spring_close_timer.start()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent):
        if (event.mimeData().hasFormat("application/x-fileitem") or
            event.mimeData().hasFormat("application/x-fileitems")):
            event.acceptProposedAction()
            drop_scene_pos = self.mapToScene(event.position().toPoint())
            
            if event.mimeData().hasFormat("application/x-fileitems"):
                data = event.mimeData().data("application/x-fileitems")
                try:
                    drag_data = json.loads(bytes(data).decode("utf-8"))
                    file_paths = drag_data.get("files", [])
                    offsets = drag_data.get("offsets", {})
                    hotspot = drag_data.get("hotspot", {"x": 0, "y": 0})
                except Exception:
                    file_paths = []
                    offsets = {}
                    hotspot = {"x": 0, "y": 0}
            
            # If the source and destination folders are the same, reposition items.
            if os.path.dirname(file_paths[0]) == self.parent().folder_path:
                # Compute what the union rectangle’s top left should be in the destination:
                # We want the hotspot (from the union pixmap) to align with the drop position.
                new_union_top_left = drop_scene_pos - QtCore.QPointF(hotspot["x"], hotspot["y"])
                for f in file_paths:
                    item = next((item for item in self.scene().items() 
                                if isinstance(item, FileItem) and item.file_path == f), None)
                    if item and f in offsets:
                        off = offsets[f]  # This is a tuple (dx, dy)
                        new_pos = new_union_top_left + QtCore.QPointF(off[0], off[1])
                        item.setPos(new_pos)
                event.ignore()
                return
            
            # Otherwise, for cross-window drag, you can store the drop positions for later processing.
            # For example:
            menu = QtWidgets.QMenu(self)
            copy_action = menu.addAction("Copy")
            move_action = menu.addAction("Move")
            symlink_action = menu.addAction("Symlink")
            menu.addSeparator()
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
                    # Compute new drop positions based on the union offsets.
                    new_drop_positions = {}
                    new_union_top_left = drop_scene_pos - QtCore.QPointF(hotspot["x"], hotspot["y"])
                    for f in file_paths:
                        off = offsets.get(f, [0, 0])
                        new_drop_positions[f] = new_union_top_left + QtCore.QPointF(off[0], off[1])
                    # Update the drop target positions so that when the new window loads the files,
                    # they are placed at the correct positions.
                    main_window.drop_target_positions.update({
                        os.path.join(main_window.folder_path, os.path.basename(f)): new_drop_positions[f]
                        for f in file_paths
                    })
                    main_window.process_drop_operation(file_paths, chosen, drop_scene_pos)
        else:
            super().dropEvent(event)

    def handleSpringOpen(self):
        """Open a folder when hovering over it for a set time."""
        if self.spring_item:
            current_item = self.itemAt(self.mapFromGlobal(QtGui.QCursor.pos()))
            if current_item == self.spring_item:
                main_window = self.window()
                if isinstance(main_window, SpatialFilerWindow):
                    main_window.open_folder_from_item(self.spring_item.file_path, spring_loaded=True)
            self.spring_item = None  # Reset to prevent multiple triggers
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

    def __init__(self, file_path: str, pos: QtCore.QPointF, width = item_width, height = item_height):
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

        file_info = QtCore.QFileInfo(file_path)
        self.icon = icon_provider.icon(file_info)
        icon_size = QtCore.QSize(32, 32)
        self.pixmap = self.icon.pixmap(icon_size)
        if self.pixmap.width() < icon_size.width() or self.pixmap.height() < icon_size.height():
            self.pixmap = self.pixmap.scaled(icon_size, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)

        self.font = QtGui.QFont()
        self.font.setPointSize(8)

        self.drag_start_position = None

    def boundingRect(self) -> QtCore.QRectF:
        # Accommodate the icon and file name.
        return QtCore.QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionGraphicsItem, widget=None):
        # Ensure offsets are always defined
        pix_w = self.pixmap.width()
        pix_h = self.pixmap.height()
        offset_x = (self.width - pix_w) / 2
        offset_y = 48 - pix_h - 12

        # Ensure text position calculations are always performed
        metrics = QtGui.QFontMetrics(self.font)
        base_name = os.path.basename(self.file_path)
        space_before_and_after = 6
        elided_text = metrics.elidedText(base_name, QtCore.Qt.TextElideMode.ElideMiddle, self.width - space_before_and_after)
        text_width = metrics.horizontalAdvance(elided_text)
        text_height = metrics.height()
        text_x = (self.width - text_width) / 2 + 3 - space_before_and_after/2
        text_y = self.height - int(text_height / 2)

        # Draw selection highlight only around the icon and text
        if self.isSelected():
            painter.setBrush(QtGui.QBrush(QtGui.QColor(200, 220, 255, 100)))  # Semi-transparent blue
            painter.setPen(QtGui.QPen(QtGui.QColor(100, 100, 255), 2))  # Blue border

            # Draw the icon highlighted, meaning some blue overlay
            self.highlighted_pixmap = self.pixmap.copy()
            # Modify the pixmap to add a blue overlay but only where the icon is not transparent
            painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Multiply)
            # Fill pixmap where it is not transparent with blue
            painter.fillRect(QtCore.QRectF(offset_x, offset_y, pix_w, pix_h), QtGui.QColor(200, 220, 255, 100))
            painter.drawPixmap(QtCore.QPointF(offset_x, offset_y), self.highlighted_pixmap)
            
            # Text highlight
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
            # TODO: Set different pen if user clicked on the text
            text_rect = QtCore.QRectF(text_x, text_y - text_height, text_width, text_height)
            painter.drawRect(text_rect)

        # Draw the icon
        painter.drawPixmap(QtCore.QPointF(offset_x, offset_y), self.pixmap)

        # Draw translucent white box under the text
        painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 128)))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        painter.drawRect(QtCore.QRectF(text_x - space_before_and_after/2, text_y - text_height, text_width + space_before_and_after, text_height))
        
        # Draw the file/folder name
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        painter.setFont(self.font)
        painter.drawText(int(text_x), int(text_y-3), elided_text)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        # Record the screen position where the press occurred.
        self.drag_start_position = event.screenPos()
        # Also store the current (original) scene position for potential reversion.
        self._original_pos = self.pos()
        
        click_pos = event.pos()  # Local position relative to the item

        # Calculate icon area
        pix_w = self.pixmap.width()
        pix_h = self.pixmap.height()
        offset_x = (self.width - pix_w) / 2
        offset_y = 48 - pix_h - 12
        icon_rect = QtCore.QRectF(offset_x, offset_y, pix_w, pix_h)

        # Calculate text area
        metrics = QtGui.QFontMetrics(self.font)
        base_name = os.path.basename(self.file_path)
        elided_text = metrics.elidedText(base_name, QtCore.Qt.TextElideMode.ElideMiddle, self.width)
        text_width = metrics.horizontalAdvance(elided_text)
        text_height = metrics.height()
        text_x = (self.width - text_width) / 2
        text_y = self.height - int(text_height / 2)
        text_rect = QtCore.QRectF(text_x, text_y - text_height, text_width, text_height)

        # Accept click only if inside icon or text
        if icon_rect.contains(click_pos) or text_rect.contains(click_pos):
            super().mousePressEvent(event)
        else:
            event.ignore()

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        # Only process drag if items are selected (and we're in a drag situation)
        selected_items = self.scene().selectedItems()
        # Check whether the mouse is over one of the selected items
        if not selected_items or not any(item == self for item in selected_items):
            super().mouseMoveEvent(event)
            return
        if not selected_items:
            super().mouseMoveEvent(event)
            return

        # Set a movement threshold to initiate a drag (10 pixels, for example)
        if self.drag_start_position is None:
            self.drag_start_position = event.screenPos()
        if (event.screenPos() - self.drag_start_position).manhattanLength() < 10:
            super().mouseMoveEvent(event)
            return

        # Cancel free repositioning (restore the original position)
        self.setPos(self._original_pos)

        # Prepare the drag operation.
        drag = QtGui.QDrag(event.widget())
        mime_data = QtCore.QMimeData()

        # Hide all selected items during the drag
        for itm in selected_items:
            itm.setOpacity(0.0)


        # Compute the union rectangle of all selected items (in scene coordinates).
        union_rect = None
        for itm in selected_items:
            item_scene_rect = itm.mapToScene(itm.boundingRect()).boundingRect()
            union_rect = item_scene_rect if union_rect is None else union_rect.united(item_scene_rect)

        # If for some reason no union rectangle could be computed, abort the custom drag.
        if union_rect is None:
            super().mouseMoveEvent(event)
            return

        # Create a pixmap covering the union rectangle.
        pixmap = QtGui.QPixmap(int(union_rect.width()), int(union_rect.height()))
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        # We'll store each item's offset relative to the union rectangle
        relative_offsets = {}
        for itm in selected_items:
            item_scene_top_left = itm.mapToScene(itm.boundingRect().topLeft())
            offset = item_scene_top_left - union_rect.topLeft()
            relative_offsets[itm.file_path] = (offset.x(), offset.y())
            painter.save()
            painter.translate(offset)
            option = QtWidgets.QStyleOptionGraphicsItem()
            if self.scene().views():
                option.widget = self.scene().views()[0]
            itm.paint(painter, option)
            painter.restore()
        painter.end()

        # Compute the drag hotspot using the initiating item (self)
        # Convert the event position (local to self) to scene coordinates, then compute its offset from union_rect.topLeft().
        hotspot_scene = self.mapToScene(event.pos())
        hotspot_point = hotspot_scene - union_rect.topLeft()
        hotspot = QtCore.QPoint(int(hotspot_point.x()), int(hotspot_point.y()))

        # Package the necessary data (file paths, offsets, and hotspot) into the MIME data.
        drag_data = {
            "files": [itm.file_path for itm in selected_items if isinstance(itm, FileItem)],
            "offsets": relative_offsets,
            "hotspot": {"x": hotspot.x(), "y": hotspot.y()}
        }
        mime_data.setData("application/x-fileitems", json.dumps(drag_data).encode("utf-8"))

        # Finalize the drag setup.
        drag.setPixmap(pixmap)
        drag.setHotSpot(hotspot)
        drag.setMimeData(mime_data)
        drag.exec(QtCore.Qt.DropAction.MoveAction | QtCore.Qt.DropAction.CopyAction)

        # Restore the opacities after the drag operation.
        for itm in selected_items:
            itm.setOpacity(1.0)

        self.drag_start_position = None
        event.accept()
    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        self.setOpacity(1.0)

        if self.drag_start_position is not None:
            distance = (event.screenPos() - self.drag_start_position).manhattanLength()
            if self.scene() and self.scene().views() and distance > 2:
                main_window = self.scene().views()[0].window()
                main_window.save_layout()

        self.drag_start_position = None  # Reset the variable
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        self.open_item()
        super().mouseDoubleClickEvent(event)

    def resolve_lnk(self, path):
        """Resolves a Windows .lnk file to its target using ctypes."""
        if not path.lower().endswith(".lnk"):
            return path

        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(path)
        return shortcut.TargetPath

    def open_item(self):
        """Opens a folder or launches a file."""
        # Special case: On Windows, .lnk files are shortcuts to files or folders.
        target_path = self.file_path
        if os.name == "nt" and self.file_path.lower().endswith(".lnk"):
            target_path = self.resolve_lnk(self.file_path)

        if os.path.isdir(target_path):
            self.openFolderRequested.emit(target_path)
        else:
            url = QtCore.QUrl.fromLocalFile(target_path)
            QtGui.QDesktopServices.openUrl(url)

        # TODO: Animate the item when opened: Increase size x2 and fade out, then reset.

    def contextMenuEvent(self, event: QtWidgets.QGraphicsSceneContextMenuEvent):
        """Right-click selects the item before opening the context menu."""
        if not self.isSelected():  
            # Select this item and deselect others unless Shift/Ctrl is pressed
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            if not (modifiers & QtCore.Qt.KeyboardModifier.ControlModifier or 
                    modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier):
                self.scene().clearSelection()  # Deselect all if no modifier is pressed
            self.setSelected(True)  # Select right-clicked item

        # Create context menu
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
            # Call delete_selected() from the main window
            main_window = self.scene().views()[0].window()
            if isinstance(main_window, SpatialFilerWindow):
                main_window.delete_selected()


    def show_info(self):
        main_window = self.scene().views()[0].window()  # Get the main window
        if isinstance(main_window, SpatialFilerWindow):
            main_window.get_info()



# ---------------- Spatial Filer Window (main file/folder view) ----------------
class SpatialFilerWindow(QtWidgets.QMainWindow):

    selectionChanged = QtCore.pyqtSignal()

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

        # Set scroll policies on the QGraphicsView (SpatialFilerView)
        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

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

        if self.isVisible():
            # Do not try this when the window is already closed, for example when quitting the application.
            self.scene.selectionChanged.connect(self.selectionChanged.emit)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_scene_rect()

    def go_home(self):
        """Open the user's home directory."""
        home_dir = os.path.expanduser("~")
        SpatialFilerWindow.get_or_create_window(home_dir)

    def go_trash(self):
        """Open the Trash directory."""
        if os.name == "nt":
            trash_dir = os.path.join(os.getenv('USERPROFILE'), 'Recycle Bin')
        else:
            trash_dir = os.path.expanduser("~/.local/share/Trash/files")
        SpatialFilerWindow.get_or_create_window(trash_dir)

    def go_drive(self, drive):
        """Open a specific drive (Windows only)."""
        SpatialFilerWindow.get_or_create_window(drive.replace("\\", "/"))

    def has_selected_items(self):
        """Check if any item is selected. Returns True if at least one item is selected."""
        return any(item.isSelected() for item in self.file_items)
    
    def has_trash_items(self):
        """Check if any item is in the Trash folder."""
        print("TODO: Implement has_trash_items()")
        return False
    
    def move_to_trash(self):
        # Use file operation thread to move selected items to Trash.
        QtWidgets.QMessageBox.information(self, "Move to Trash", "Not implemented yet.")

    def empty_trash(self):
        """Delete all files in the Trash folder."""
        if os.name == "nt":
            trash_dir = os.path.join(os.getenv('USERPROFILE'), 'Recycle Bin')
        else:
            trash_dir = os.path.expanduser("~/.local/share/Trash/files")
        try:
            for file in os.listdir(trash_dir):
                file_path = os.path.join(trash_dir, file)
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)
            QtWidgets.QMessageBox.information(self, "Trash", "Trash emptied successfully.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to empty trash: {e}")

    def create_menus(self):
        menus.create_menus(self)

    def load_files(self):
        
        # Check if this is the Desktop in fullscreen mode
        is_desktop_fullscreen = self.folder_path == QtCore.QStandardPaths.writableLocation(
            QtCore.QStandardPaths.StandardLocation.DesktopLocation
        )

        try:
            folder_files = os.listdir(self.folder_path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Cannot read folder: {e}")
            return
        
        # Add every disk in the system
        if is_desktop_fullscreen:
            print("Adding disks")
            for disk in QtCore.QDir.drives():
                # The name of the disk is the first part of the path, e.g. "C:" or "D:"
                print(disk.canonicalFilePath())
                disk_name = disk.canonicalFilePath()
                folder_files.append(disk_name)

        # Load stored positions from layout file if available
        layout_file_path = os.path.join(self.folder_path, LAYOUT_FILENAME)
        stored_positions = {}
        if os.path.exists(layout_file_path):
            try:
                with open(layout_file_path, "r") as f:
                    stored_positions = json.load(f).get("items", {})
            except Exception as e:
                print(f"Warning: Could not load layout file ({e})")

        # Skip hidden/system files
        folder_files = [name for name in folder_files if not name.startswith(".")]
        folder_files = [name for name in folder_files if name.lower() not in ("desktop.ini", ".ds_store")]

        occupied_positions = set()  # Store occupied positions

        # Mark positions of already existing items
        for item in self.file_items:
            grid_x = round(item.x() / grid_width)
            grid_y = round(item.y() / grid_height)
            occupied_positions.add((grid_x, grid_y))

        # Also mark stored positions to avoid overlapping them
        for path, (pos_x, pos_y) in stored_positions.items():
            grid_x = round(pos_x / grid_width)
            grid_y = round(pos_y / grid_height)
            occupied_positions.add((grid_x, grid_y))

        def find_next_available_position():
            """Finds the first free position based on layout direction."""
            if is_desktop_fullscreen:
                # Desktop: Layout from top-right to bottom-left
                x = (self.width() // grid_width) - 1
                y = 0
                while (x, y) in occupied_positions:
                    x -= 1  # Move left
                    if x < 0:  # Move to next row if needed
                        x = (self.width() // grid_width) - 1
                        y += 1
            else:
                # Normal case: Layout from top-left to bottom-right
                x, y = 0, 0
                while (x, y) in occupied_positions:
                    x += 1  # Move right
                    if x * grid_width > self.width() - 2 * grid_width:
                        x = 0
                        y += 1

            occupied_positions.add((x, y))
            return QtCore.QPointF(x * grid_width, y * grid_height)

        for name in sorted(folder_files):

            # Skip items already in the scene
            if any(item.file_path == name for item in self.file_items):
                continue

            # Restore position if stored, otherwise find a free one
            if name in stored_positions:
                pos_x, pos_y = stored_positions[name]
                pos = QtCore.QPointF(pos_x, pos_y)
            elif name in self.drop_target_positions:
                pos = self.drop_target_positions.pop(name)
            else:
                pos = find_next_available_position()

            # Create and add the new item
            full_path = os.path.join(self.folder_path, name)
            item = FileItem(full_path, pos)
            item.openFolderRequested.connect(self.open_folder_from_item)
            self.scene.addItem(item)
            self.file_items.append(item)

        self.update_scene_rect()

    def get_layout(self) -> dict:
        layout = {"items": {}}
        for item in self.file_items:
            relative_path = os.path.basename(item.file_path)
            layout["items"][relative_path] = (item.x(), item.y())
        
        geom = self.saveGeometry().toBase64().data().decode("utf-8")
        layout["window_geometry"] = geom
        return layout

    def save_layout(self):
        layout = self.get_layout()
        layout_file_path = os.path.join(self.folder_path, LAYOUT_FILENAME)
        try:
            with open(layout_file_path, "w") as f:
                json.dump(layout, f, indent=4)
        except:
            pass    
        # Blink the window title to indicate a save
        # self.setWindowTitle(f"Saved: {self.windowTitle()}")
        # QtCore.QTimer.singleShot(1000, lambda: self.setWindowTitle(self.windowTitle().replace("Saved: ", "")))

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

    def update_scene_rect(self):
        """Ensure the scene fits all items without shifting them unexpectedly."""
        if self.file_items:
            bounding_rect = self.scene.itemsBoundingRect()
            visible_rect = self.view.mapToScene(self.view.rect()).boundingRect()
            self.scene.setSceneRect(0, 0, max(visible_rect.width(), bounding_rect.width()), max(visible_rect.height(), bounding_rect.height()))
        else:
            self.scene.setSceneRect(0, 0, self.width(), self.height())

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts that have no menu item/action."""
        if event.key() == QtCore.Qt.Key.Key_F5:
            self.refresh_view()
        else:
            super().keyPressEvent(event)

    def refresh_view(self):
        self.layout_data = self.get_layout()  # store current positions
        for item in self.file_items:
            self.scene.removeItem(item)
        self.file_items.clear()
        self.load_files()
        self.update_status_bar()
        self.update_scene_rect() 

    def align_to_grid(self):
        for item in self.file_items:
            new_x = round(item.x() / grid_width) * grid_width
            new_y = round(item.y() / grid_height) * grid_height
            item.setPos(new_x, new_y)
        self.update_status_bar()
        self.update_scene_rect()

    def sort_items(self, criterion):
        """Sort items and layout them correctly based on the window type."""
        
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

        # Check if this is the Desktop in fullscreen mode
        is_desktop_fullscreen = self.folder_path == QtCore.QStandardPaths.writableLocation(
            QtCore.QStandardPaths.StandardLocation.DesktopLocation
        )

        # Sort items based on the selected criterion
        sorted_items = sorted(self.file_items, key=get_key)

        occupied_positions = set()

        if is_desktop_fullscreen:
            # Desktop: Move downward first, then shift left
            x = (self.width() // grid_width) - 1  # Start at rightmost column
            y = 0
            for item in sorted_items:
                while (x, y) in occupied_positions:
                    y += 1  # Move downward
                    if y * grid_height > self.height() - 2 * grid_height:
                        y = 0  # Reset and shift left
                        x -= 1
                item.setPos(QtCore.QPointF(x * grid_width, y * grid_height))
                occupied_positions.add((x, y))
        else:
            # Normal case: Move right first, then shift down
            x, y = 0, 0
            for item in sorted_items:
                while (x, y) in occupied_positions:
                    x += 1  # Move right
                    if x * grid_width > self.width() - grid_width:
                        x = 0
                        y += 1
                item.setPos(QtCore.QPointF(x * grid_width, y * grid_height))
                occupied_positions.add((x, y))
        
        self.update_scene_rect()
        self.save_layout()

    def update_status_bar(self):
        self.statusBar().showMessage(f"Folder: {self.folder_path} | Items: {len(self.file_items)}")

    def get_info(self):
        selected_items = self.scene.selectedItems()
        getinfo.FileInfoDialog(selected_items, self).exec()

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
        self.op_thread.error.connect(lambda msg: (progress_dialog.close(), QtWidgets.QMessageBox.critical(self, "Error", msg)))
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

    @staticmethod # This means the method can be called on the class itself, without an instance.
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

            if os.path.exists(folder_path) and os.access(folder_path, os.R_OK):
                new_window = SpatialFilerWindow(folder_path, layout_data)
                new_window.spring_loaded = spring_loaded
                new_window.show()
                return new_window
            else:
                QtWidgets.QMessageBox.critical(None, "Error", f"Cannot access folder: {folder_path}")
                return None

    def selectedItems(self):
        return self.scene.selectedItems()


# ---------------- Main Application Object ----------------
class MainObject:
    def __init__(self):
        desktop = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.DesktopLocation)
        # If the desktop directory does not exist, create it.
        if not os.path.exists(desktop):
            os.makedirs(desktop)
        screen = QtWidgets.QApplication.primaryScreen()
        desktop_window = SpatialFilerWindow.get_or_create_window(desktop)
        desktop_window.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        desktop_window.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnBottomHint)
        desktop_window.move(screen.geometry().x(), screen.geometry().y())
        desktop_window.resize(screen.geometry().width(), screen.geometry().height())
        desktop_window.statusBar().hide()
        # Set the background color of the desktop window to gray
        desktop_window.view.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(128, 128, 128)))
        # If we are running on X11, set the desktop window to be the root window
        if "DISPLAY" in os.environ:
            # Set a hint that this is the desktop window
            desktop_window.view.viewport().setWindowFlags(QtCore.Qt.WindowType.X11BypassWindowManagerHint)
            desktop_window.view.viewport().setProperty("_q_desktop", True)

        # If we are runnnig on Wayland, set the desktop window to be the root window
        if "WAYLAND_DISPLAY" in os.environ:
            print("FIXME: Wayland: How to set the desktop window to be the root window on Wayland?")

        # On Windows, get the wallpaper and set it as the background of the window
        if sys.platform == "win32":
            shell = Dispatch("WScript.Shell")
            windows_wallpaper_path = os.path.normpath(shell.RegRead("HKEY_CURRENT_USER\\Control Panel\\Desktop\\Wallpaper")).replace("\\", "/")
            if windows_wallpaper_path != "." and os.path.exists(windows_wallpaper_path):
                desktop_window.view.setBackgroundBrush(QtGui.QBrush(QtGui.QPixmap(windows_wallpaper_path).scaled(desktop_window.width(),
                                                                                                                 desktop_window.height(),
                                                                                                                 QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                                                                                 QtCore.Qt.TransformationMode.SmoothTransformation)))
        # Remove the last item in the first menu and replace it with a Quit action (Ctrl+Q)
        file_menu = desktop_window.menuBar().findChildren(QtWidgets.QMenu)[0]
        quit_action = QtGui.QAction("Quit", desktop_window)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(QtWidgets.QApplication.quit)
        file_menu.removeAction(file_menu.actions()[-1])
        file_menu.addAction(quit_action)

        # Add shutdown action to the file menu
        shutdown_action = QtGui.QAction("Shut Down", desktop_window)
        shutdown_action.triggered.connect(self.shutdown)
        file_menu.addAction(shutdown_action)
        
        desktop_window.show()
        self.desktop_window = desktop_window

    def shutdown(self):
        message_box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Question, "Shut Down", "Are you sure you want to shut down the computer?\nUnsaved work will be lost.", QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        message_box.setIcon(QtWidgets.QMessageBox.Icon.Question)
        message_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
        if message_box.exec() == QtWidgets.QMessageBox.StandardButton.Yes:
            if sys.platform == "win32":
                try:
                    subprocess.run(["shutdown", "/s", "/t", "0"])
                except Exception as e:
                    QtWidgets.QMessageBox.critical(None, "Error", f"Failed to shut down: {e}")
            else:
                try:
                    subprocess.run(["shutdown", "-h", "now"])
                except Exception as e:
                    QtWidgets.QMessageBox.critical(None, "Error", f"Failed to shut down: {e}")


if __name__ == "__main__":
    # Ctrl-C quits
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QtWidgets.QApplication(sys.argv)

    app.setWindowIcon(app.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon))

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

    m = MainObject()

    # Check for the presence of WAYLAND_DISPLAY and show info box for Wayland users
    if "WAYLAND_DISPLAY" in os.environ:
        QtWidgets.QMessageBox.information(m.desktop_window, "Wayland", "Spatial Filer does not work properly on Wayland yet.\nWindows are all over the place.\nMenu mouse releasing doesn't work properly.")

    sys.exit(app.exec())