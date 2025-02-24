#!/usr/bin/env python3

# A file manager in Python?
# "These days I prefer programming in Python... it's beautiful, exppressive, and simple" - Andy Hertzfeld, https://youtu.be/kqm7ahl2ZYg?feature=shared&t=3705

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
* Why does snap_to_grid not sync across windows? -> Use app.preferences for this if we want to sync across windows.
* Get rid of open_windows registry completely. Instead, whenever a window is created, set an attribute with the normalized path on it. Then, whenever a window shall be opened, check if a window with that attribute already exists. This way, we can get rid of the open_windows dictionary which is not robust and may get out of sync.
* Incorporate fake windows for Wayland absolute positioning
* Implement coloring the items when they are selected and a color is chosen from the color menu.
* Persist coloring in the ._layout.json file.
* Implement choosing desktop picture for Linux

FOR TESTING:
* Windows is ideal for testing because one can test the same code easily using WSL on Debian without and with Wayland, and on Windows natively.
"""

import os, sys, signal, json, shutil, math, time

from PyQt6 import QtWidgets, QtGui, QtCore

if sys.platform == "win32":
    from win32com.client import Dispatch
    import windows_struts
    import windows_hotkeys
    import windows_eject
    import windows_trash

import getinfo, menus, fileops, appimage, zipping

from styling import Styling

LAYOUT_FILENAME = "._layout.json"

item_width = grid_width = 100
item_height = grid_height = 60

# DriveWatcher: Detects newly inserted drives and updates the UI
class DriveWatcher(QtCore.QThread):
    newDriveDetected = QtCore.pyqtSignal(str)
    driveRemoved = QtCore.pyqtSignal(str)

    def run(self):
        seen_drives = set(disk.rootPath() for disk in QtCore.QStorageInfo.mountedVolumes() if disk.isValid and disk.isReady())
        while True:
            current_drives = set(disk.rootPath() for disk in QtCore.QStorageInfo.mountedVolumes() if disk.isValid and disk.isReady())

            new_drives = current_drives - seen_drives
            for drive in new_drives:
                self.newDriveDetected.emit(drive)

            drives_removed = seen_drives - current_drives
            for drive in drives_removed:
                self.driveRemoved.emit(drive)

            seen_drives = current_drives
            time.sleep(3) # Poll every 3 seconds; FIXME: Find a solution that doesn't involve polling

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
        self.setStyleSheet("QGraphicsView { border: 0px; }")

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down, 
                           QtCore.Qt.Key.Key_Left, QtCore.Qt.Key.Key_Right):
            print(f"Forwarding arrow key: {event.key()}")  # Debugging
            self.parent().keyPressEvent(event)  # Send to the main window
            event.accept() # Stop futher propagation to prevent it being called twice
        else:
            super().keyPressEvent(event)  # Process normally

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
            if self.spring_item != item:
                self.spring_item = item
                self.spring_timer.start()
                self.spring_close_timer.stop()
        else:
            self.spring_timer.stop()
            self.spring_close_timer.start()

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
                        if app.snap_to_grid:
                            new_pos = QtCore.QPointF(
                                grid_width * round(new_pos.x() / grid_width),
                                grid_height * round(new_pos.y() / grid_height)
                            )
                        item.setPos(new_pos)
                event.ignore()
                return
            
            # Otherwise, for cross-window drag, you can store the drop positions for later processing.
            # For example:
            menu = QtWidgets.QMenu(self)
            menu.addSeparator()
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
                window = open_windows.get(self.spring_item.file_path)
                if window is not None and getattr(window, "spring_loaded", False):
                    window.close()
                self.spring_item = None
        self.spring_close_timer.stop()


# ---------------- File Item (represents a file or folder icon) ----------------
class FileItem(QtWidgets.QGraphicsObject):
    # Signal to request opening a folder.
    openFolderRequested = QtCore.pyqtSignal(str)

    def __init__(self, file_path: str, pos, width = item_width, height = item_height):
        super().__init__()
        self.file_path = file_path
        self.width = width
        self.height = height
        self.hidden = False
        self.color = None
        self.setFlags(
            QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        if pos:
            self.setPos(pos)
        self.is_folder = os.path.isdir(file_path)

        self.font = QtGui.QFont()
        self.font.setPointSize(8)

        self.pixmap = None # Will be populated on first paint
        self.icon = None # Will be populated on first paint
        self.drag_start_position = None

        mountpoints = [drive.rootPath() for drive in QtCore.QStorageInfo.mountedVolumes()]
        if file_path in mountpoints:
            storage_info = QtCore.QStorageInfo(file_path)
            self.volume_name = storage_info.displayName() or file_path  # Store volume name separately
            if sys.platform == "win32":
                self.display_name = self.volume_name.replace("/", "\\")
            else:
                self.display_name = self.volume_name
        elif sys.platform != "win32" and os.path.splitext(file_path)[1].lower() == (".desktop"):
            self.volume_name = None
            with open(self.file_path, "r") as f:
                self.display_name = os.path.basename(file_path)
                for line in f:
                    if line.startswith("Name="):
                        print(f"Name line found:", line)
                        self.display_name = line[5:].strip()
                        break
        else:
            self.volume_name = None
            self.display_name = os.path.basename(file_path)

        self.is_trash = False

    def boundingRect(self) -> QtCore.QRectF:
        # Accommodate the icon and file name.
        return QtCore.QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionGraphicsItem, widget=None):

        if not app.preferences.value("show_hidden_files", False, type=bool) and self.hidden:
            print(f"Hidden file: {self.file_path}")
            return

        if os.path.islink(self.file_path) or (sys.platform == "win32" and os.path.splitext(self.file_path)[1].lower() == (".lnk" or ".url")):
            self.font.setItalic(True)

        if not self.pixmap:
            # If the item extension is ".desktop", we read each line, find the line that starts with Icon=, and extract the icon name.
            if os.path.splitext(self.file_path)[1].lower() == ".desktop":
                with open(self.file_path, "r") as f:
                    icon_value = None
                    for line in f:
                        if line.startswith("Icon="):
                            icon_value = line[5:].strip()
                            break
                    if icon_value:
                        if icon_value.startswith("/"):
                            # If the icon name is an absolute path, use it directly
                            self.icon = QtGui.QIcon(icon_value)
                        elif QtGui.QIcon.hasThemeIcon(icon_value):
                            self.icon = QtGui.QIcon.fromTheme(icon_value)
                        if not self.icon:
                            # Look for a file with the same name as the icon name and .png or .svg or .xpm in /usr/share/pixmaps and /usr/local/share/pixmaps
                            for path in ["/usr/share/pixmaps", "/usr/local/share/pixmaps"]:
                                for ext in [".png", ".svg", ".xpm"]:
                                    icon_path = os.path.join(path, icon_value + ext)
                                    if os.path.exists(icon_path):
                                        self.icon = QtGui.QIcon(icon_path)
                                        break
                if self.icon:
                    self.pixmap = self.icon.pixmap(QtCore.QSize(32, 32))
                if self.pixmap == None:
                    self.icon = QtGui.QIcon.fromTheme("application-x-executable")
                    self.pixmap = self.icon.pixmap(QtCore.QSize(32, 32))
            elif self.is_trash:
                self.icon = QtGui.QIcon.fromTheme("user-trash")
                self.pixmap = self.icon.pixmap(QtCore.QSize(32, 32))
            else:
                file_info = QtCore.QFileInfo(self.file_path)
                if self.is_folder and not os.path.ismount(self.file_path):
                    self.icon = QtGui.QIcon.fromTheme("folder")
                elif file_info.suffix().lower() == "appimage":
                    appimage_obj = appimage.AppImage(self.file_path)
                    self.icon = appimage_obj.get_icon(32)
                    if self.icon is None:
                        self.icon = QtGui.QIcon.fromTheme("application-x-executable")
                else:
                    icon_provider = QtWidgets.QFileIconProvider()
                    self.icon = icon_provider.icon(file_info)
                icon_size = QtCore.QSize(32, 32)
                self.pixmap = self.icon.pixmap(icon_size)
                if self.pixmap.width() < icon_size.width() or self.pixmap.height() < icon_size.height():
                    self.pixmap = self.pixmap.scaled(icon_size, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
        
        # Ensure offsets are always defined
        pix_w = self.pixmap.width()
        pix_h = self.pixmap.height()
        offset_x = (self.width - pix_w) / 2
        offset_y = 48 - pix_h - 12

        # Ensure text position calculations are always performed
        metrics = QtGui.QFontMetrics(self.font)
        
        space_before_and_after = 6

        display_name = self.display_name
        if app.preferences.value("hide_file_extensions", False, type=bool):
            display_name_without_extension = QtCore.QFileInfo(display_name).completeBaseName()
            if display_name_without_extension != "":
                display_name = display_name_without_extension
        elided_text = metrics.elidedText(display_name, QtCore.Qt.TextElideMode.ElideMiddle, self.width - space_before_and_after)

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

        # If it is a directory, check if we can read it using listdir; if not draw it as disabled
        locked = False
        if self.is_folder:
            try:
                os.listdir(self.file_path)
            except Exception as e:
                locked = True
        
        # Draw the icon, optionally with the tint adjusted to the color
        if self.color:
            # FIXME: Find a proper way to tint the icon
            temp_pixmap = self.pixmap.copy()
            painter_temp = QtGui.QPainter(temp_pixmap)
            painter_temp.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Multiply)
            color = QtGui.QColor(self.color)
            painter_temp.fillRect(QtCore.QRectF(0, 0, temp_pixmap.width(), temp_pixmap.height()), color)
            painter_temp.end()
            painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.drawPixmap(QtCore.QPointF(offset_x, offset_y), temp_pixmap)
        else:
            if self.hidden:
                painter.setOpacity(0.5)
            painter.drawPixmap(QtCore.QPointF(offset_x, offset_y), self.pixmap)

        # Draw symbolic icon (badge)
        if locked:
            lock_icon = QtGui.QIcon.fromTheme("emblem-noread")
            lock_pixmap = lock_icon.pixmap(QtCore.QSize(16, 16))
            painter.drawPixmap(QtCore.QPointF(offset_x + pix_w - 16, offset_y + pix_h - 16), lock_pixmap)
        elif not os.access(self.file_path, os.W_OK):
            lock_icon = QtGui.QIcon.fromTheme("emblem-readonly")
            lock_pixmap = lock_icon.pixmap(QtCore.QSize(16, 16))
            painter.drawPixmap(QtCore.QPointF(offset_x + pix_w - 16, offset_y + pix_h - 16), lock_pixmap)

        # Draw translucent white box under the text
        painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 128)))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        painter.drawRect(QtCore.QRectF(text_x - space_before_and_after/2, text_y - text_height, text_width + space_before_and_after, text_height))
        
        # Draw the file/folder name
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        painter.setFont(self.font)
        painter.drawText(int(text_x), int(text_y-3), elided_text)
        self.font.setItalic(False)

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

        # For dragging to external applications, set the URLs of the selected items.
        file_paths = [itm.file_path for itm in selected_items if isinstance(itm, FileItem)]
        mime_data.setUrls([QtCore.QUrl.fromLocalFile(path) for path in file_paths])

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

        def close_if_modifier_key_pressed():
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            if self.scene().views() and self.scene().views()[0].window():
                if modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier and not self.scene().views()[0].window().is_desktop_window:
                    self.scene().views()[0].window().close()

        self.animate_opening()

        # Special case: On Windows, .lnk files are shortcuts to files or folders.
        target_path = self.file_path
        if sys.platform == "win32" and self.file_path.lower().endswith(".lnk" or ".url"):
            target_path = self.resolve_lnk(self.file_path)

        if target_path.lower().endswith(".appimage"):
            appimage_obj = appimage.AppImage(target_path)
            success = appimage_obj.launch()
            if success:
                close_if_modifier_key_pressed()
            return
        elif os.path.isdir(target_path):
            self.openFolderRequested.emit(target_path)
            close_if_modifier_key_pressed()
        else:
            url = QtCore.QUrl.fromLocalFile(target_path)
            result = QtGui.QDesktopServices.openUrl(url)
            if not result:
                QtWidgets.QMessageBox.critical(None, "Error", f"Failed to open {target_path}")
                return
            else:
                close_if_modifier_key_pressed()
                # Set wait cursor for 15 seconds or until the application is launched as evidenced by our window no longer being the frontmost window in the z-order.
                # On Windows, this works nicely. On Linux, it remains to be seen.
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
                start_time = time.time()
                while time.time() - start_time < 15:
                    QtWidgets.QApplication.processEvents()
                    this_window = self.scene().views()[0].window()
                    if not this_window.isActiveWindow():
                        break
                QtCore.QTimer.singleShot(5, lambda: QtWidgets.QApplication.restoreOverrideCursor())

    def animate_opening(self):
        """Animate the item when opened: Increase size x2 and fade out, then reset."""
        animation = QtCore.QPropertyAnimation(self, b"scale")
        animation.setDuration(300)
        animation.setStartValue(1.0)
        animation.setEndValue(2.0)
        animation.setEasingCurve(QtCore.QEasingCurve.Type.InOutQuad)
        animation.finished.connect(lambda: self.setScale(1.0))  # Reset after animation
        animation.start()

    def unzip_files(self, file_paths):
        """Unzips the selected files in the current folder."""
        if not all(f.lower().endswith(".zip") for f in file_paths):
            QtWidgets.QMessageBox.critical(None, "Error", "All selected files must be ZIP archives.")
            return
        self.unzip_windows = []  # Store references to keep them alive
        print("Unzipping files:", file_paths)
        for file_path in file_paths:
            if file_path != None:
                z = zipping.UnzipFolderApp(file_path, file_path.replace(".zip", ""))
                self.unzip_windows.append(z)

    def zip_files(self, file_paths):
        """Zips the selected files in the current folder."""
        self.zip_windows = []
        print("Zipping files:", file_paths)
        for file_path in file_paths:
            if file_path != None:
                z = zipping.ZipFolderApp(file_path)
                self.zip_windows.append(z)

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
        menu.addSeparator()
        # Extract if file ends with .zip
        file_paths = [os.path.normpath(item.file_path) for item in self.scene().selectedItems() if isinstance(item, FileItem)]
        if all(f.lower().endswith(".zip") for f in file_paths):
            unzip_action = menu.addAction("Extract")
            unzip_action.triggered.connect(lambda: self.unzip_files(file_paths))
        else:
            zip_action = menu.addAction("Zip")
            zip_action.triggered.connect(lambda: self.zip_files(file_paths))
        menu.addSeparator()
        info_action = menu.addAction("Get Info...")
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        menu.addSeparator()
        if self.volume_name:
            eject_action = menu.addAction("Eject")
            eject_action.triggered.connect(self.eject_volume)

        action = menu.exec(event.screenPos())

        if action == open_action:
            if self.is_folder:
                self.openFolderRequested.emit(self.file_path)
            else:
                url = QtCore.QUrl.fromLocalFile(self.file_path)
                QtGui.QDesktopServices.openUrl(url)

        elif action == info_action:
            self.show_info()

        elif action == rename_action:
            self.rename_item()

        elif action == delete_action:
            # Call delete_selected() from the main window
            main_window = self.scene().views()[0].window()
            if isinstance(main_window, SpatialFilerWindow):
                main_window.delete_selected()

    def show_info(self):
        main_window = self.scene().views()[0].window()  # Get the main window
        if isinstance(main_window, SpatialFilerWindow):
            main_window.get_info()

    def rename_item(self):
        main_window = self.scene().views()[0].window()  # Get the main window
        if isinstance(main_window, SpatialFilerWindow):
            main_window.rename_selected()

    def eject_volume(self):
        if not self.volume_name:
            return
        
        # Ensure the drive path is valid
        if not isinstance(self.file_path, str) or not self.file_path:
            print(f"Invalid drive path: {self.file_path}")
            return

        normalized_drive = os.path.normpath(self.file_path) 

        if sys.platform == "win32":
            success = windows_eject.WindowsEjector().eject_drive(normalized_drive[0])  # Use only the drive letter
        else:
            success = os.system(f"eject {normalized_drive}") == 0
            
        if success:
            print(f"Successfully ejected {normalized_drive}")
            self.scene().removeItem(self)
            # Mark as ejected so we don't show a warning later
            ejected_drives.add(normalized_drive)
        else:
            QtWidgets.QMessageBox.critical(None, "Error", f"Failed to eject {normalized_drive}")


# ---------------- Spatial Filer Window (main file/folder view) ----------------
class SpatialFilerWindow(QtWidgets.QMainWindow):

    selectionChanged = QtCore.pyqtSignal()

    def __init__(self, folder_path: str, layout_data: dict = None):

        # Do not create the window if the folder content is not accessible.
        try:
            os.listdir(folder_path)
        except Exception as e:
            raise Exception(e)

        super().__init__()

        self.folder_path = folder_path

        self.is_desktop_window = (folder_path == QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.DesktopLocation))

        app.snap_to_grid = False

        if os.path.ismount(folder_path):
            storage_info = QtCore.QStorageInfo(folder_path)
            self.volume_name = storage_info.displayName() or None  # Store volume name
            self.setWindowTitle(self.volume_name or folder_path)
        else:
            self.volume_name = None
            self.setWindowTitle(os.path.basename(folder_path))

        if self.windowTitle() == "" or self.windowTitle() == None:
            self.setWindowTitle(" ")

        self.setGeometry(100, 100, 800, 600)
        self.spring_loaded = False  # will be set True if opened via spring–load

        self.scene = QtWidgets.QGraphicsScene(self)
        self.view = SpatialFilerView(self)
        self.view.setScene(self.scene)
        self.setCentralWidget(self.view)

        # Set scroll policies on the QGraphicsView (SpatialFilerView)
        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.items = []
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
        open_windows[self.folder_path] = self

        self.watcher = QtCore.QFileSystemWatcher(self)
        self.watcher.addPath(self.folder_path)
        self.watcher.directoryChanged.connect(self.refresh_view)

        self.scene.selectionChanged.connect(self.emit_selection_changed)

        # When the clipboard changes, update the Edit menu.
        QtWidgets.QApplication.clipboard().dataChanged.connect(self.paste_action_update)

        # Text the user is typing
        self.typed_text = ""
        self.search_timer = QtCore.QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(1000)  # Reset buffer after 1 second of inactivity
        self.search_timer.timeout.connect(self.clear_typed_text)

        # Ensure the window gets typed text events even if an item is selected.
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        if self.is_desktop_window:
            # Disable the ability to close the desktop window
            self.setWindowFlag(QtCore.Qt.WindowType.WindowCloseButtonHint, False)
            self.closeEvent = lambda event: None

    def close(self):
        if self.folder_path in open_windows:
            del open_windows[self.folder_path]
        try:
            self.save_layout()
        except:
            # The drive may already have been removed
            print("Could not save layout for", self.folder_path)
            pass
        super().close()

    def color_selected_items(self, color):
        """Tint the selected items with the given color."""
        for item in self.items:
            if item.isSelected():
                item.color = color
                item.update()

    def open_selected_items(self):
        """Call open_item on the selected items"""
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier and not self.is_desktop_window:
            self.close()
        for item in self.items:
            if item.isSelected():
                item.open_item()

    def paste_action_update(self):
        """Tell all open windows to update their Edit menu based on the clipboard contents."""
        # FIXME: There is probably a more elegant way to do this.
        for window in open_windows.values():
            window.update_edit_menu()

    def update_edit_menu(self):
        """Enable/disable the Paste action based on the clipboard contents."""
        clipboard = QtWidgets.QApplication.clipboard()
        mime_data = clipboard.mimeData()
        if mime_data.hasFormat("application/x-fileitems"):
            self.paste_action.setEnabled(True)
        else:
            self.paste_action.setEnabled(False)

    def emit_selection_changed(self):
        # Do not try this when the window is already closed, for example when quitting the application. 
        if self.scene:
            self.selectionChanged.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_scene_rect()

    def go_up(self):
        if self.folder_path:
            parent_dir = os.path.dirname(self.folder_path)
            if os.path.exists(parent_dir):
                self.get_or_create_window(parent_dir)

    def go_up_and_close(self):
        if self.folder_path:
            parent_dir = os.path.dirname(self.folder_path)
            if os.path.exists(parent_dir):
                self.get_or_create_window(parent_dir)
                self.close()

    def open_computer(self):
        path = "C:\\" if sys.platform == "win32" else "/"
        self.get_or_create_window(path)

    def open_network(self):
        if sys.platform == "win32":
            path = os.path.join(os.getenv("APPDATA"), "Microsoft", "Windows", "Network Shortcuts")
        else:
            QMessageBox.information(self, "Network", "TODO: Implement network browsing")
            return
        self.get_or_create_window(path)

    def open_devices(self):
        if sys.platform == "win32":
            path = "This PC"
        else:
            path = "/media" if os.path.exists("/media") else "/mnt"
        self.get_or_create_window(path)

    def open_applications(self):
        if sys.platform == "win32":
            path = os.path.join(os.getenv("ProgramFiles", "C:\\Program Files"))
        else:
            path = "/usr/share/applications" if os.path.exists("/usr/share/applications") else os.path.expanduser("~/Applications")
        self.get_or_create_window(path)

    def open_home(self):
        path = os.path.expanduser("~")
        self.get_or_create_window(path)

    def open_documents(self):
        if sys.platform == "win32":
            path = os.path.join(os.path.expanduser("~"), "Documents")
        else:
            path = os.path.join(os.path.expanduser("~"), "Documents")
        self.get_or_create_window(path)

    def open_downloads(self):
        if sys.platform == "win32":
            path = os.path.join(os.path.expanduser("~"), "Downloads")
        else:
            path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.get_or_create_window(path)

    def open_music(self):
        if sys.platform == "win32":
            path = os.path.join(os.path.expanduser("~"), "Music")
        else:
            path = os.path.join(os.path.expanduser("~"), "Music")
        self.get_or_create_window(path)

    def open_pictures(self):
        if sys.platform == "win32":
            path = os.path.join(os.path.expanduser("~"), "Pictures")
        else:
            path = os.path.join(os.path.expanduser("~"), "Pictures")
        self.get_or_create_window(path)

    def open_videos(self):
        if sys.platform == "win32":
            path = os.path.join(os.path.expanduser("~"), "Videos")
        else:
            path = os.path.join(os.path.expanduser("~"), "Videos")
        self.get_or_create_window(path)

    def open_trash(self):
        """Open the Trash directory."""
        if sys.platform == "win32":
            # C:\$Recycle.Bin\
            trash_dir =  'C:\\$Recycle.Bin\\'
        else:
            trash_dir = os.path.expanduser("~/.local/share/Trash/files")
        SpatialFilerWindow.get_or_create_window(trash_dir)

    def open_drive(self, drive):
        """Open a specific drive (Windows only)."""
        SpatialFilerWindow.get_or_create_window(drive.replace("\\", "/"))

    def has_selected_items(self):
        """Check if any item is selected. Returns True if at least one item is selected."""
        return any(item.isSelected() for item in self.items)
    
    def has_trash_items(self):
        """Check if any item is in the Trash folder."""
        print("TODO: Implement has_trash_items()")
        return False
    
    def move_to_trash(self):
        if sys.platform == "win32":
            windows_trash.empty_recycle_bin()
        else:
            # Use file operation thread to move selected items to Trash.
            QtWidgets.QMessageBox.information(self, "Move to Trash", "Not implemented yet.")

    def empty_trash(self):
        """Delete all files in the Trash folder."""
        if sys.platform == "win32":
            windows_trash.empty_trash()
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

    def clean_up(self):
        """Snap items to a grid."""
        for item in self.items:
            grid_x = round(item.x() / grid_width)
            grid_y = round(item.y() / grid_height)
            item.setPos(grid_x * grid_width, grid_y * grid_height)

    def load_files(self):
        layout_file_path = os.path.join(self.folder_path, LAYOUT_FILENAME)
        try:
            folder_files = os.listdir(self.folder_path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Cannot read folder: {e}")
            return
        
        # Add every disk in the system
        if self.is_desktop_window:
            print("Adding disks")

            for disk in QtCore.QDir.drives():
                drive_info = QtCore.QStorageInfo(disk.canonicalFilePath())
                if not drive_info.isValid() or not drive_info.isReady():
                    continue
                # The name of the disk is the first part of the path, e.g. "C:" or "D:"
                print(disk.canonicalFilePath())
                disk_name = disk.canonicalFilePath()
                if disk_name not in folder_files:
                    folder_files.append(disk_name)

        # Load stored positions from layout file if available
        stored_positions = {}
        if os.path.exists(layout_file_path):
            try:
                with open(layout_file_path, "r") as f:
                    stored_positions = json.load(f).get("items", {})
            except Exception as e:
                print(f"Warning: Could not load layout file ({e})")
                fallback_dir = get_fallback_path(self.folder_path)
                if os.path.exists(fallback_dir):
                    try:
                        with open(os.path.join(fallback_dir, LAYOUT_FILENAME), "r") as f:
                            stored_positions = json.load(f).get("items", {})
                    except Exception as e:
                        print(f"Warning: Could not load fallback layout file ({e})")

        # Skip Desktop folder. NOTE: We might want to show it instead but make it show the desktop window when double-clicked.
        # It is important that we do not break the Spatial paradigm by showing the Desktop folder in home directory as well as on the desktop.
        if sys.platform != "win32":
            # Check if we are in the user's home directory
            if os.path.expanduser("~") == self.folder_path:
                folder_files = [name for name in folder_files if name.lower() not in ("desktop",)]
        else:
            if self.folder_path.lower() == os.getenv('USERPROFILE').lower():
                folder_files = [name for name in folder_files if name.lower() not in ("desktop",)]

        # Add Trash item
        # Define Trash item position: last column before the second column starts
        if self.is_desktop_window:
            trash_x = (self.width() // grid_width) - 2  # Second last column
            trash_y = (self.height() // grid_height) - 1  # Bottom row

            trash_path = os.path.expanduser("~/.local/share/Trash/files") if sys.platform != "win32" else "C:\\$Recycle.Bin\\"
            trash_item = FileItem(trash_path, QtCore.QPointF(trash_x * grid_width, trash_y * grid_height))
            trash_item.display_name = "Trash"
            trash_item.is_trash = True
            self.items.append(trash_item)
            if trash_item not in self.scene.items():
                self.scene.addItem(trash_item)

        # Append each file or folder to self.items
        # Only add items that are not hidden, based on the user's preference
        for name in sorted(folder_files):
            full_path = os.path.join(self.folder_path, name)
            item = FileItem(full_path, None)
            # Check if item should be hidden
            if name.startswith(".") or name.startswith("$") or name.startswith("~") or name.lower() in ("desktop.ini", "thumbs.db"):
                item.hidden = True
            else:
                item.hidden = False

            # Add item only if it's not hidden or if the user wants to show hidden files
            if not item.hidden or app.preferences.value("show_hidden_files", True, type=bool):
                self.items.append(item)

        occupied_positions = set()  # Store occupied positions

        # Mark positions of already existing visible items
        for item in self.items:
            if item.pos() == QtCore.QPointF(0, 0):
                continue
            # Skip hidden items in grid position calculation
            grid_x = round(item.x() / grid_width)
            grid_y = round(item.y() / grid_height)
            occupied_positions.add((grid_x, grid_y))

        # Also mark stored positions to avoid overlapping them
        for path, (pos_x, pos_y) in stored_positions.items():
            item = next((item for item in self.items if item.file_path == path), None)
            if item:
                grid_x = round(pos_x / grid_width)
                grid_y = round(pos_y / grid_height)
                occupied_positions.add((grid_x, grid_y))

        def find_next_available_position():
            """Finds the first free position based on layout direction."""
            if self.is_desktop_window:
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

        # Now set the positions for visible items only
        for item in self.items:
            name = item.display_name
            # Restore position if stored, otherwise find a free one
            if name in stored_positions:
                pos_x, pos_y = stored_positions[name]
                pos = QtCore.QPointF(pos_x, pos_y)
            elif name in self.drop_target_positions:
                pos = self.drop_target_positions.pop(name)
            else:
                pos = find_next_available_position()

            # Set the position and ensure visibility based on preferences
            item.setPos(pos)
            item.setVisible(True)   # Ensure visible items are visible
            item.openFolderRequested.connect(self.open_folder_from_item)
            if item not in self.scene.items():
                self.scene.addItem(item)

        self.update_scene_rect()

    def get_layout(self) -> dict:
        layout = {"items": {}}
        for item in self.items:
            layout["items"][item.display_name] = (item.x(), item.y())
        
        geom = self.saveGeometry().toBase64().data().decode("utf-8")
        layout["window_geometry"] = geom
        return layout

    def save_layout(self):
        # Check if the drive containing the folder is still mounted
        normalized_folder_path = os.path.normpath(self.folder_path)
        storage_info = QtCore.QStorageInfo(normalized_folder_path)
        if not storage_info.isValid() or not storage_info.isReady():
            print(f"Drive {normalized_folder_path} is no longer mounted. Not saving layout.")
            return
        # Get the current layout dictionary.
        layout = self.get_layout()
        # Add the app.snap_to_grid state into the layout.
        layout["app.snap_to_grid"] = app.snap_to_grid

        layout_file_path = os.path.join(normalized_folder_path, LAYOUT_FILENAME)
        saved = False
        try:
            with open(layout_file_path, "w") as f:
                json.dump(layout, f, indent=4)
                saved = True
        # Read-only file system, in this case, we save to ~/.cache/Spatial subdirectories instead
        except PermissionError:
            fallback_dir = get_fallback_path(normalized_folder_path)
            layout_file_path = os.path.join(fallback_dir, LAYOUT_FILENAME)
            try:
                with open(layout_file_path, "w") as f:
                    json.dump(layout, f, indent=4)
            except Exception as e:
                print(f"Error saving layout: {e}")
                return
            saved = True
        if not saved:
            print(f"Error saving layout to {layout_file_path}")

        # Blink the window title to indicate a save.
        # self.setWindowTitle(f"Saved: {self.windowTitle()}")
        # QtCore.QTimer.singleShot(1000, lambda: self.setWindowTitle(self.windowTitle().replace("Saved: ", "")))

    def open_folder_from_item(self, folder_path: str, spring_loaded: bool = False):
        success = False
        try:
            os.listdir(folder_path)
            success = True
        except Exception as e:
            success = False
        if success:
            SpatialFilerWindow.get_or_create_window(folder_path, spring_loaded)

    def rename_selected(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.information(self, "Rename", "No items selected.")
            return

        if len(selected_items) > 1:
            QtWidgets.QMessageBox.information(self, "Rename", "Select only one item to rename.")
            return

        item = selected_items[0]
        new_name, ok = QtWidgets.QInputDialog.getText(self, "Rename", "New name:", QtWidgets.QLineEdit.EchoMode.Normal, item.display_name)
        if ok and new_name:
            new_path = os.path.join(self.folder_path, new_name)
            try:
                os.rename(item.file_path, new_path)
                item.file_path = new_path
                item.display_name = new_name
                self.save_layout()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Error renaming {item.file_path}: {e}")

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
                    if item in self.items:
                        self.items.remove(item)
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Error", f"Error deleting {item.file_path}: {e}")
            self.update_status_bar()

    def update_scene_rect(self):
        """Ensure the scene fits all items without shifting them unexpectedly."""
        if self.items:
            bounding_rect = self.scene.itemsBoundingRect()
            visible_rect = self.view.mapToScene(self.view.rect()).boundingRect()
            self.scene.setSceneRect(0, 0, max(visible_rect.width(), bounding_rect.width()), max(visible_rect.height(), bounding_rect.height()))
        else:
            self.scene.setSceneRect(0, 0, self.width(), self.height())

    def keyPressEvent(self, event):
        key = event.key()
        if (key in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down, QtCore.Qt.Key.Key_Left, QtCore.Qt.Key.Key_Right) and event.type() == QtCore.QEvent.Type.KeyPress) and not (key in (QtCore.Qt.Key.Key_Control, QtCore.Qt.Key.Key_Shift, QtCore.Qt.Key.Key_Alt)):
            self.navigate_selection(key)
        elif key == QtCore.Qt.Key.Key_F5:
            self.refresh_view()
            return

        if key == QtCore.Qt.Key.Key_Backspace:
            self.typed_text = self.typed_text[:-1]
        elif key == QtCore.Qt.Key.Key_Escape:
            self.clear_typed_text()
        elif 32 <= event.key() <= 126:  # Printable ASCII range
            self.typed_text += event.text()

        self.search_timer.start()
        self.highlight_matching_item()

        super().keyPressEvent(event)  # Let other key events propagate

    def clear_typed_text(self):
        self.typed_text = ""
        
    def highlight_matching_item(self):
        """Select and highlight the first matching file."""
        if not self.typed_text:
            return

        for item in self.items:
            if os.path.basename(item.display_name).lower().startswith(self.typed_text.lower()):
                self.scene.clearSelection()
                item.setSelected(True)
                self.view.centerOn(item)
                return
            
    def navigate_selection(self, key):
        """
        Select the closest neighbor by Euclidean distance.
        """

        # TODO: Handle Shift-Arrow for multi-selection more like Finder/Explorer using a mental/virtual selection rectangle.

        print("Navigating selection")
        if not self.items:
            return

        # Get the currently selected item (or default to the first item)
        selected_items = self.scene.selectedItems()
        if not selected_items:
            selected_items = [self.items[0]]
        selected_item = selected_items[0]
        selected_pos = selected_item.pos()

        # Determine arrow direction as a unit vector based on the pressed key.
        # (If an unsupported key is pressed, we simply consider all items.)
        arrow_dir = None
        if key == QtCore.Qt.Key.Key_Up:
            arrow_dir = QtCore.QPointF(0, -1)
        elif key == QtCore.Qt.Key.Key_Down:
            arrow_dir = QtCore.QPointF(0, 1)
        elif key == QtCore.Qt.Key.Key_Left:
            arrow_dir = QtCore.QPointF(-1, 0)
        elif key == QtCore.Qt.Key.Key_Right:
            arrow_dir = QtCore.QPointF(1, 0)

        best_item = None
        best_distance = float('inf')
        candidates = []

        # First pass: if an arrow direction is provided, consider only items in the forward half-plane.
        for item in self.items:
            if item == selected_item:
                continue
            item_pos = item.pos()
            delta = QtCore.QPointF(item_pos.x() - selected_pos.x(),
                                item_pos.y() - selected_pos.y())
            if arrow_dir is not None:
                # Compute projection of delta onto arrow direction.
                projection = delta.x() * arrow_dir.x() + delta.y() * arrow_dir.y()
                if projection <= 0:
                    continue  # Candidate is not in the forward half-plane.
            distance = math.hypot(delta.x(), delta.y())
            candidates.append((distance, item))
        
        # If no candidate meets the directional criterion, fallback to all items.
        if not candidates:
            for item in self.items:
                if item == selected_item:
                    continue
                item_pos = item.pos()
                delta = QtCore.QPointF(item_pos.x() - selected_pos.x(),
                                    item_pos.y() - selected_pos.y())
                distance = math.hypot(delta.x(), delta.y())
                candidates.append((distance, item))
        
        # Choose the candidate with the smallest Euclidean distance.
        for distance, item in candidates:
            if distance < best_distance:
                best_distance = distance
                best_item = item

        if best_item:
            if not QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier:
                self.scene.clearSelection()
            best_item.setSelected(True)
            self.view.centerOn(best_item)

    def refresh_view(self):
        self.layout_data = self.get_layout()  # store current positions
        for item in self.items:
            self.scene.removeItem(item)
        self.items.clear()
        self.load_files()
        self.update_status_bar()
        self.update_scene_rect() 

    def align_to_grid(self):
        for item in self.items:
            new_x = round(item.x() / grid_width) * grid_width
            new_y = round(item.y() / grid_height) * grid_height
            item.setPos(new_x, new_y)
        self.update_status_bar()
        self.update_scene_rect()

    def sort_items(self, criterion):
        """Sort items and layout them correctly based on the window type."""
        # Invalidate stored positions to ensure items are laid out correctly
        self.layout_data = {}

        # Sort items based on the selected criterion, ignoring upper/lowercase
        if criterion == "name":
            sorted_items = sorted(self.items, key=lambda x: os.path.basename(x.file_path).lower())
        elif criterion == "date":
            sorted_items = sorted(self.items, key=lambda x: os.path.getmtime(x.file_path), reverse=True)
        elif criterion == "size":
            sorted_items = sorted(self.items, key=lambda x: os.path.getsize(x.file_path), reverse=True)
        elif criterion == "type":
            sorted_items = sorted(self.items, key=lambda x: os.path.splitext(x.file_path)[1].lower())
        # Ensure volumes are at the top
        sorted_items = sorted(sorted_items, key=lambda x: x.volume_name is not None, reverse=True)

        occupied_positions = set()

        # Identify the Trash item
        trash_item = None
        for item in sorted_items:
            if getattr(item, "is_trash", False):  # Ensure 'is_trash' is a property
                trash_item = item
                break

        if self.is_desktop_window:
            # Reserve Trash position first
            trash_x = (self.width() // grid_width) - 1
            trash_y = (self.height() // grid_height) - 2
            occupied_positions.add((trash_x, trash_y))

            # Desktop: Move downward first, then shift left
            x = (self.width() // grid_width) - 1  # Start at rightmost column
            y = 0

            for item in sorted_items:
                if item == trash_item:
                    continue  # Skip placing Trash for now

                while (x, y) in occupied_positions:
                    y += 1  # Move downward
                    if y * grid_height > self.height() - 2 * grid_height:
                        y = 0  # Reset and shift left
                        x -= 1

                item.setPos(QtCore.QPointF(x * grid_width, y * grid_height))
                occupied_positions.add((x, y))

            # Place Trash at its reserved position
            if trash_item:
                trash_item.setPos(QtCore.QPointF(trash_x * grid_width, trash_y * grid_height))

        else:
            # Normal case: Move right first, then shift down
            x, y = 0, 0
            for item in sorted_items:
                if item == trash_item:
                    continue  # Skip placing Trash for now

                while (x, y) in occupied_positions:
                    x += 1  # Move right
                    if x * grid_width > self.width() - grid_width:
                        x = 0
                        y += 1

                item.setPos(QtCore.QPointF(x * grid_width, y * grid_height))
                occupied_positions.add((x, y))

            # Place Trash item at the end in a separate logic
            if trash_item:
                occupied_positions.add((trash_x, trash_y))  # 🚀 Fix: Ensure Trash's spot is not overwritten
                trash_item.setPos(QtCore.QPointF(trash_x * grid_width, trash_y * grid_height))

        self.update_scene_rect()
        self.save_layout()

    def update_status_bar(self):
        self.statusBar().showMessage(f"Folder: {self.folder_path} | Items: {len(self.items)}")

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
        fileops.FileOperation(self).run(operations, op_type=operation)

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
        mime_data.setData("application/x-fileitems", json.dumps({"files": self.clipboard, "operation": "move"}).encode("utf-8"))
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

        fileops.FileOperation(self).run(operations, op_type=operation)

        if operation == "cut":
            # Clear clipboard after moving
            self.clipboard = []
            self.clipboard_operation = None
            clipboard.clear()

    def show_about(self):
        QtWidgets.QMessageBox.about(
            self,
            "About Spatial Filer",
            "Spatial Filer\n\nA spatial file manager implemented in PyQt6\nInspired by Siracusa-style spatial file managers.\n\nSee https://arstechnica.com/gadgets/2003/04/finder/\nfor a description of what that means.",
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
        for item in self.items:
            item.setSelected(True)

    def closeEvent(self, event):
        self.save_layout()
        if self.folder_path in open_windows:
            del open_windows[self.folder_path]
        super().closeEvent(event)

    @staticmethod # This means the method can be called on the class itself, without an instance.
    def get_or_create_window(folder_path, spring_loaded: bool = False):
        if folder_path in open_windows:
            window = open_windows[folder_path]
            if window.isMinimized():
                window.showNormal()
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

"""def handle_drive_removal(drive):
        normalized_drive = os.path.normpath(drive)

        # Close any open windows associated with the removed drive
        removed_volume_name = QtCore.QStorageInfo(normalized_drive).displayName()
        window_to_close = None
        for window in open_windows.values():
            path = window.folder_path
            print("A window is open with title:", window.windowTitle(), "at path:", path)
            if os.path.normpath(path) == normalized_drive or window.volume_name == removed_volume_name:
                window_to_close = window # Do not close here to avoid modifying the dictionary while iterating
                print(f"Closing window for {normalized_drive} at {path}")
        if window_to_close:
            window_to_close.close()

        desktop_window.refresh_view()

        # If the drive was ejected by the application, do not show the warning
        if normalized_drive in ejected_drives:
            ejected_drives.discard(normalized_drive)
            return
        else:
            if normalized_drive.startswith("/tmp") or os.path.basename(normalized_drive).startswith("."):
                return
            # Show error message only if it was NOT ejected by the app
            QtWidgets.QMessageBox.critical(
                None, "Warning",
                f"Volume {normalized_drive} was removed without being ejected first.\n\n"
                "To prevent data loss, always eject volumes before removal."
            )"""

def is_dialog_open(title):
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.windowTitle() == title:
            return True
    return False

def handle_drive_removal(drive):
        normalized_drive = os.path.normpath(drive)

        # Close any open windows associated with the removed drive
        removed_volume_name = QtCore.QStorageInfo(normalized_drive).displayName()
        windows_to_close = []
        for window in open_windows.values():
            path = window.folder_path
            print("A window is open with title:", window.windowTitle(), "at path:", path)
            if os.path.normpath(path).startswith(normalized_drive) or window.volume_name == removed_volume_name:
                windows_to_close.append(window) # Do not close here to avoid modifying the dictionary while iterating
                print(f"Closing window for {normalized_drive} at {path}")
        for window in windows_to_close:
            window.close()

        desktop_window.refresh_view()

        # If the drive was ejected by the application, do not show the warning
        if normalized_drive in ejected_drives:
            ejected_drives.discard(normalized_drive)
            return
        else:
            if normalized_drive.startswith("/tmp") or os.path.basename(normalized_drive).startswith("."):
                return
            # Show error message only if it was NOT ejected by the app
            if not normalized_drive.startswith("/tmp") and not os.path.basename(normalized_drive).startswith("."):
                dialog_title = f"Warning - {normalized_drive}"
                if not is_dialog_open(dialog_title):
                    QtWidgets.QMessageBox.critical(
                        None, dialog_title,
                        f"Volume {normalized_drive} was removed without being ejected first.\n\n"
                        "To prevent data loss, always eject volumes before removal."
                    )

def get_fallback_path(folder_path):
    fallback_layout_file_dir = os.path.join(os.path.expanduser("~"), ".cache", "Spatial", "DesktopData")
    # Check if the folder path is absolute
    if os.path.isabs(folder_path):
        # On Windows, remove the ':' from the drive letter if it exists
        if sys.platform == "win32" and len(folder_path) > 1 and folder_path[1] == ":":
            folder_path = folder_path[0] + folder_path[2:]
            folder_path = folder_path.replace("\\", "/")
        folder_path = folder_path.lstrip("/")
    fallback_dir = os.path.join(fallback_layout_file_dir, folder_path)
    try:
        os.makedirs(fallback_dir, exist_ok=True)
    except Exception as e:
        QtGui.QMessageBox.critical(None, "Error", f"Could not create fallback directory: {e}")
    return fallback_dir

def apply_desktop_picture_with_gradient(view, desktop_picture_path, target_width, target_height):
    """
    Applies a scaled desktop_picture with a darkening gradient at the top to the provided QGraphicsView.
    
    Args:
        view (QGraphicsView): The view on which to set the background brush.
        desktop_picture_path (str): File path to the desktop_picture image.
        target_width (int): The width to which the desktop_picture should be scaled.
        target_height (int): The height to which the desktop_picture should be scaled.
    """
    # Load and scale the desktop_picture while keeping the aspect ratio and expanding it to fill the area.
    scaled_pixmap = QtGui.QPixmap(desktop_picture_path).scaled(
        target_width,
        target_height,
        QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        QtCore.Qt.TransformationMode.SmoothTransformation
    )

    # Create a temporary pixmap with the same size as the scaled desktop_picture.
    blended_pixmap = QtGui.QPixmap(scaled_pixmap.size())
    blended_pixmap.fill(QtCore.Qt.GlobalColor.transparent)

    # Use QPainter to paint the desktop_picture and the gradient overlay.
    painter = QtGui.QPainter(blended_pixmap)
    painter.drawPixmap(0, 0, scaled_pixmap)

    # Create a linear gradient
    gradient = QtGui.QLinearGradient(0, 0, 0, 25)
    gradient.setColorAt(0, QtGui.QColor(0, 0, 0, 64))
    gradient.setColorAt(0.5, QtGui.QColor(0, 0, 0, 16))
    gradient.setColorAt(1, QtGui.QColor(0, 0, 0, 0))
    gradient_brush = QtGui.QBrush(gradient)

    # Set the painting composition mode to Multiply for darkening effect.
    painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Multiply)
    painter.fillRect(0, 0, blended_pixmap.width(), 100, gradient_brush)
    painter.end()

    # Set the resulting pixmap as the background brush of the view.
    view.setBackgroundBrush(QtGui.QBrush(blended_pixmap))

if __name__ == "__main__":
    # Ctrl-C quits
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QtWidgets.QApplication(sys.argv)
    s = Styling(app)

    # app = QtWidgets.QApplication(sys.argv) # See top of this file
    app.setApplicationName("Spatial")
    app.preferences = QtCore.QSettings(app.applicationName())
    app.setWindowIcon(QtGui.QIcon.fromTheme("folder"))

    # Global registry of open windows by folder path.
    open_windows = {}

    # Reserving space for the menu bar on Windows
    if sys.platform == "win32":
        appbar = windows_struts.Strut()
        app.aboutToQuit.connect(appbar.restore_work_area)

    # Output not only to the console but also to the GUI
    try:
        import log_console
    except ImportError:
        pass
    if "log_console" in sys.modules:
        app.log_console = log_console.ConsoleOutputStream()
        sys.stdout = log_console.Tee(sys.stdout, app.log_console)
        sys.stderr = log_console.Tee(sys.stderr, app.log_console)

    app.snap_to_grid = False

    desktop = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.DesktopLocation)
    # If the desktop directory does not exist, create it.
    if not os.path.exists(desktop):
        os.makedirs(desktop)
    screen = QtWidgets.QApplication.primaryScreen()
    desktop_window = SpatialFilerWindow.get_or_create_window(desktop)
    desktop_window.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
    desktop_window.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnBottomHint)
    ejected_drives = set()  # Keep track of drives that the user has ejected using the application
    drive_watcher = DriveWatcher()
    drive_watcher.start()
    drive_watcher.newDriveDetected.connect(lambda drive: desktop_window.refresh_view())
    drive_watcher.driveRemoved.connect(lambda drive: handle_drive_removal(drive))
    drive_watcher.start()
    desktop_window.move(screen.geometry().x(), screen.geometry().y())
    desktop_window.resize(screen.geometry().width(), screen.geometry().height())
    desktop_window.statusBar().hide()
    # If no saved layout is found for the desktop window, sort items by name
    if not desktop_window.layout_data:
        desktop_window.sort_items("name")
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
        # https://drewdevault.com/2018/07/29/Wayland-shells.html
        # Since wl_shell is not ready yet, we need to use xdg_shell?
        # https://pywayland.readthedocs.io/en/latest/module/protocol/xdg_shell.html
        # Look into https://github.com/flacjacket/pywayland/

        # TODO: Investigate whether we could use https://pywayland.readthedocs.io/en/latest/module/protocol/xdg_shell.html#pywayland.protocol.xdg_shell.XdgToplevel.move
        # to simulate the broken Qt .move() of windows when running under Wayland.


    # On Windows, get the desktop_picture and set it as the background of the window
    if sys.platform == "win32":
        try:
            from win32com.client import Dispatch
            shell = Dispatch("WScript.Shell")
            reg_desktop_picture = shell.RegRead("HKEY_CURRENT_USER\\Control Panel\\Desktop\\Wallpaper")
            desktop_picture_path = os.path.normpath(reg_desktop_picture).replace("\\", "/")
        except Exception as e:
            print("Error reading registry:", e)
    elif sys.platform == "darwin":
        # Get the selected desktop_picture on macOS
        desktop_picture_path = subprocess.run(["osascript", "-e", "tell application \"Finder\" to get desktop picture"], capture_output=True, text=True).stdout.strip()
    else:
        # On Linux, get the desktop_picture from the user's settings in KDE
        try:
            if os.path.exists("/usr/bin/kreadconfig5"):
                desktop_picture_path = subprocess.run(["kreadconfig5", "--file", "kwinrc", "--group", "Wallpaper", "--key", "Image"], capture_output=True, text=True).stdout.strip()
            elif os.path.exists("/usr/bin/gsettings"):
                desktop_picture_path = subprocess.run(["gsettings", "get", "org.gnome.desktop.background", "picture-uri"], capture_output=True, text=True).stdout.strip()
        except Exception as e:
            print("Error reading desktop_picture path:", e)
            desktop_picture_path = None
                
    # If a valid desktop_picture path is obtained and the file exists, apply the desktop_picture with gradient.
    if desktop_picture_path and os.path.exists(desktop_picture_path):
        # Screen size of main monitor
        target_width = screen.geometry().width()
        target_height = screen.geometry().height()
        apply_desktop_picture_with_gradient(desktop_window.view, desktop_picture_path, target_width, target_height)

    desktop_window.show()

    # Register global hotkeys
    if sys.platform == "win32":
        hotkey_manager =  windows_hotkeys.HotKeyManager(desktop_window).run()
        # When the application gets killed or otherwise exits, unregister the hotkeys
        app.aboutToQuit.connect(hotkey_manager.unregister_hotkeys)

    # Alt+Shift+F4 quits the application
    QtGui.QShortcut(QtGui.QKeySequence("Alt+Shift+F4"), desktop_window, QtWidgets.QApplication.quit)

    # Check for the presence of WAYLAND_DISPLAY and show info box for Wayland users
    if "WAYLAND_DISPLAY" in os.environ:
        QtWidgets.QMessageBox.information(desktop_window, "Wayland", "Spatial Filer does not work properly on Wayland yet.\nWindows are all over the place.\nMenu mouse releasing doesn't work properly.")

    sys.exit(app.exec())
