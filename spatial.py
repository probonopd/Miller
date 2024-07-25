#!/usr/bin/env python3

# Tested on Windows 11. Moving items within the window not perfect here, but it is using Qt drag and drop
# Key is to avoid QListView and QFileSystemModel because they are not suited for our purpose of creating a spatial file manager

import sys
import os
import json
import subprocess
import math

from PyQt6.QtCore import Qt, QPoint, QSize, QDir, QRect, QMimeData, QUrl, QFileSystemWatcher, QFileInfo
from PyQt6.QtGui import QFontMetrics, QPainter, QPen, QAction, QDrag, QColor, QLinearGradient, QPainter, QPen, QBrush, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QScrollArea, QLabel, QSizePolicy, QFileIconProvider, QMenuBar, QGridLayout, QMessageBox, QMenu, QDialog

if sys.platform == "win32":
    from win32com.client import Dispatch
    import winreg

class SpatialFiler(QWidget):

    def __init__(self, path=None):
        super().__init__()
        
        self.path = path if path else QDir.homePath()
        self.setWindowTitle(self.path)
        self.setGeometry(100, 100, 800, 600)

        self.setAcceptDrops(True)

        # There might be a file .DS_Spatial in the directory that contains the window position and size. If it exists, read the settings from it.
        # Example file content:
        # {"position": {"x": 499, "y": 242}, "size": {"width": 800, "height": 600}, "items": [{"name": "known_hosts", "x": 110, "y": 0}, {"name": "known_hosts.old", "x": 220, "y": 0}]}
        settings_file = os.path.join(self.path, app.desktop_settings_file)
        if os.path.exists(settings_file):
            with open(settings_file, "r") as file:
                try:
                    settings = json.load(file)
                    print("Settings from %s" % (settings_file))
                    # Check if there is a position for the window in the settings file; if yes, set the window position
                    if "position" in settings:
                        self.move(settings["position"]["x"], settings["position"]["y"])
                    # Check if there is a size for the window in the settings file; if yes, set the window size
                    if "size" in settings:
                        self.resize(settings["size"]["width"], settings["size"]["height"])
                    # Check if the window is out of the screen; if yes, move it to the top-left corner
                    if self.x() < 0 or self.y() < 0:
                        self.move(0, 0)
                except json.JSONDecodeError as e:
                    print(f"Error reading settings file: {e}")
        else:
            print(f"Settings file {settings_file} does not exist")

        # Create the menu bar
        self.menu_bar = QMenuBar(self)
        self.layout = QVBoxLayout(self)
        self.layout.setMenuBar(self.menu_bar)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.container = QWidget()
        self.scroll_area.setWidget(self.container)
        self.layout.addWidget(self.scroll_area)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        # Initialize menu bar items
        self.init_menu_bar()

        # Initialize other components
        self.files = []
        self.vertical_spacing = 5
        self.line_height = 80
        self.horizontal_spacing = 10
        self.start_x = 0
        self.start_y = 0
        self.populate_items()
        self.dragging = False
        self.last_pos = QPoint(0, 0)
        self.selected_files = []
        self.selection_rect = QRect(0, 0, 0, 0)
        self.is_selecting = False

        # Watch for changes in the directory
        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.directoryChanged.connect(self.directory_changed)
        self.file_watcher.fileChanged.connect(self.file_changed)
        self.file_watcher.addPath(self.path)

    def directory_changed(self, path):
        # Remove items from the window that are not in the directory anymore
        items_to_remove = []
        for item in self.files:
            if not os.path.exists(item.path):
                items_to_remove.append(item)
        for item in items_to_remove:
            item.hide()
            if self.container.layout():
                self.container.layout().removeWidget(item)
            self.files.remove(item)
            item.deleteLater()
        self.populate_items()  # This adds new items to the window
        self.update_container_size()

    def file_changed(self, path):
        self.update_container_size()

    def paintEvent(self, event):
        if self.is_selecting:
            painter = QPainter(self)
            painter.setPen(QPen(Qt.GlobalColor.gray, 1))
            painter.drawRect(self.selection_rect)
        
    def init_menu_bar(self):
        # File Menu
        file_menu = self.menu_bar.addMenu("File")
        self.open_action = QAction("Open", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.open_selected_items)
        self.open_action.setEnabled(False)
        self.close_action = QAction("Close", self)
        self.close_action.setShortcut("Ctrl+W")
        self.close_action.triggered.connect(self.close)
        file_menu.addAction(self.open_action)
        file_menu.addSeparator()
        file_menu.addAction(self.close_action)
        # Edit Menu
        edit_menu = self.menu_bar.addMenu("Edit")
        self.cut_action = QAction("Cut", self)
        self.cut_action.setShortcut("Ctrl+X")
        self.copy_action = QAction("Copy", self)
        self.copy_action.setShortcut("Ctrl+C")
        self.paste_action = QAction("Paste", self)
        self.paste_action.setShortcut("Ctrl+V")
        self.delete_action = QAction("Delete", self)
        self.delete_action.setShortcut("Delete")
        edit_menu.addAction(self.cut_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.paste_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.delete_action)
        for action in [self.cut_action, self.copy_action, self.paste_action, self.delete_action]:
            action.setEnabled(False)
        # Go Menu
        go_menu = self.menu_bar.addMenu("Go")
        home_action = QAction("Home", self)
        home_action.triggered.connect(self.open_home)
        go_menu.addAction(home_action)
        if sys.platform == "win32":
            start_menu_action = QAction("Applications", self)
            start_menu_action.triggered.connect(self.open_start_menu_folder)
            go_menu.addAction(start_menu_action)
        # View Menu
        view_menu = self.menu_bar.addMenu("View")
        if os.path.normpath(os.path.dirname(self.path)) == os.path.normpath(QDir.homePath()) and os.path.basename(self.path) == "Desktop":
            align_items_desktop_action = QAction("Align Items", self)
            align_items_desktop_action.triggered.connect(self.align_items_desktop)
            view_menu.addAction(align_items_desktop_action)
        else:
            align_items_action = QAction("Align Items", self)
            align_items_action.triggered.connect(self.align_items)
            view_menu.addAction(align_items_action)
            align_items_staggered_action = QAction("Align Items Staggered", self)
            align_items_staggered_action.triggered.connect(self.align_items_staggered)
            view_menu.addAction(align_items_staggered_action)
            align_items_circle_action = QAction("Align Items in Circle", self)
            align_items_circle_action.triggered.connect(self.align_items_circle)
            view_menu.addAction(align_items_circle_action)
        # Help Menu
        help_menu = self.menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def open_home(self):
        i = Item(QDir.homePath(), True, QPoint(0, 0), self.container)
        i.open(None)
        i = None

    def open_start_menu_folder(self):
        self.start_menu_folder = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs')
        i = Item(self.start_menu_folder, True, QPoint(0, 0), self.container)
        i.open(None)
        i = None

    def populate_items(self):
        print(f"Populating items for path: {self.path}")

        if os.path.normpath(os.path.dirname(self.path)) == os.path.normpath(QDir.homePath()) and os.path.basename(self.path) == "Desktop":

            # Add every disk in the system
            print("Adding disks")
            for disk in QDir.drives():
                if not any(item.name == disk.path() for item in self.files):
                    # The name of the disk is the first part of the path, e.g. "C:" or "D:"
                    disk_name = disk.path()
                    print("Adding disk", disk_name)
                    self.add_file(disk.path(), True)

            # Add the Trash item
            if not any(item.name == app.trash_name for item in self.files):
                print("Adding Trash item")
                trash = os.path.join(self.path, app.trash_name)
                self.add_file(trash, True)
    
        try:
            entries = os.listdir(self.path)
            if not entries:
                print("No items found.")
            else:
                for entry in entries:
                    # Skip if already in the list
                    if any(item.name == entry for item in self.files):
                        continue
                    # .DS_Spatial is a special file that we don't want to show
                    if entry == app.desktop_settings_file:
                        continue
                    # ~/Desktop is a special case; we don't want to show it
                    if self.path == QDir.homePath() and entry == "Desktop":
                        continue
                        entry = os.path.splitext(entry)[0]
                    entry_path = os.path.join(self.path, entry)
                    is_directory = os.path.isdir(entry_path)

                    self.add_file(entry_path, is_directory)

        except Exception as e:
            print(f"Error accessing directory: {e}")

    def calculate_max_width(self):
        return max(item.width() for item in self.files) if self.files else 150

    def add_file(self, path, is_directory):
        position = QPoint(self.start_x + len(self.files) % 5 * (self.calculate_max_width() + self.horizontal_spacing), 
                          self.start_y + len(self.files) // 5 * (self.line_height + self.vertical_spacing))
        # Check whether a position is provided in the .DS_Spatial file; if yes, use it
        settings_file = os.path.join(self.path, app.desktop_settings_file)
        if os.path.exists(settings_file):
            with open(settings_file, "r") as file:
                try:
                    settings = json.load(file)
                    for item in settings["items"]:
                        if item["name"] == robust_filename(path):
                            position = QPoint(item["x"], item["y"])
                except json.JSONDecodeError as e:
                    print(f"Error reading settings file: {e}")

        item = Item(path, is_directory, position, self.container)
        item.move(position)
        item.show()
        self.files.append(item)
        self.update_container_size()

    def update_container_size(self):
        max_x = max(item.x() + item.width() for item in self.files) + 10
        max_y = max(item.y() + item.height() for item in self.files) + 10
        self.container.setMinimumSize(QSize(max_x, max_y))

    def mousePressEvent(self, event):
        scroll_pos = QPoint(self.scroll_area.horizontalScrollBar().value(),
                            self.scroll_area.verticalScrollBar().value())
        adjusted_pos = event.pos() + scroll_pos

        if event.button() == Qt.MouseButton.LeftButton:
            clicked_widget = None
            for item in self.files:
                if (item.x() <= adjusted_pos.x() <= item.x() + item.width()) and \
                (item.y() <= adjusted_pos.y() <= item.y() + item.height()):
                    clicked_widget = item
                    break
            
            if clicked_widget:
                if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                    if clicked_widget in self.selected_files:
                        self.selected_files.remove(clicked_widget)
                        clicked_widget.setStyleSheet("border: 1px dotted lightgrey; background-color: transparent;")
                    else:
                        self.selected_files.append(clicked_widget)
                        clicked_widget.setStyleSheet("border: 1px dotted blue; background-color: lightblue;")
                else:
                    if clicked_widget not in self.selected_files:
                        self.selected_files = [clicked_widget]
                        for f in self.files:
                            if f != clicked_widget:
                                f.setStyleSheet("border: 1px dotted lightgrey; background-color: transparent;")
                        clicked_widget.setStyleSheet("border: 1px dotted blue; background-color: lightblue;")
                    
                    self.dragging = True
                    self.last_pos = adjusted_pos
                    self.update_menu_state()
                    # Set mime data for all selected items
                    mime_data = QMimeData()
                    for item in self.selected_files:
                        mime_data.setUrls([QUrl.fromLocalFile(f.path) for f in self.selected_files])
                    drag = QDrag(self)
                    drag.setMimeData(mime_data)
                    drag.setPixmap(self.selected_files[0].icon_label.pixmap())
                    # TODO: Make it so that the icon doesn't jump to be at the top left corner of the mouse cursor
                    # FIXME: Instead of hardcoding the hot spot to be half the icon size, it should be the position of the mouse cursor relative to the item
                    drag.setHotSpot(QPoint(int(48/2), int(48/2)))
                    drag.exec()
            else:
                self.is_selecting = True
                self.selection_rect = QRect(adjusted_pos.x(), adjusted_pos.y(), 0, 0)
                self.update()
                self.selected_files = []
                for item in self.files:
                    item.setStyleSheet("border: 1px dotted lightgrey; background-color: transparent;")
                self.update_menu_state()

    def mouseMoveEvent(self, event):
        scroll_pos = QPoint(self.scroll_area.horizontalScrollBar().value(),
                            self.scroll_area.verticalScrollBar().value())
        adjusted_pos = event.pos() + scroll_pos

        if self.dragging:
            # Check if at least one of the selected items is being dragged, if not, return
            if not any(item.underMouse() for item in self.selected_files):
                return
            print("Dragging")
            # Let Qt drag the selected items
            # Set mime data
            mime_data = QMimeData()
            mime_data.setUrls([QUrl.fromLocalFile(f.path) for f in self.selected_files])
            drag = QDrag(self)
            drag.setMimeData(mime_data)
            drag.setPixmap(self.selected_files[0].icon_label.pixmap())
            # TODO: Make it so that the icon doesn't jump to be at the top left corner of the mouse cursor
            # FIXME: Instead of hardcoding the hot spot to be half the icon size, it should be the position of the mouse cursor relative to the item
            drag.setHotSpot(QPoint(int(48/2), int(48/2)))
            drag.exec()

        elif self.is_selecting:
            self.selection_rect = QRect(min(self.selection_rect.x(), adjusted_pos.x()),
                                        min(self.selection_rect.y(), adjusted_pos.y()),
                                        abs(adjusted_pos.x() - self.selection_rect.x()),
                                        abs(adjusted_pos.y() - self.selection_rect.y()))
            self.update()
            for item in self.files:
                if (self.selection_rect.x() <= item.x() + item.width() and
                    item.x() <= self.selection_rect.x() + self.selection_rect.width() and
                    self.selection_rect.y() <= item.y() + item.height() and
                    item.y() <= self.selection_rect.y() + self.selection_rect.height()):
                    if item not in self.selected_files:
                        self.selected_files.append(item)
                        item.setStyleSheet("border: 1px dotted blue; background-color: lightblue;")
                else:
                    if item in self.selected_files:
                        self.selected_files.remove(item)
                        item.setStyleSheet("border: 1px dotted lightgrey; background-color: transparent;")

    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.dragging = False
            self.update_container_size()
        elif self.is_selecting:
            self.is_selecting = False
            self.selection_rect = QRect(0, 0, 0, 0)
            self.update()

    def open_selected_items(self):
        for item in self.selected_files:
            item.open(None)

    def update_menu_state(self):
        # Enable/disable menu actions based on the selection
        has_selection = bool(self.selected_files)
        self.open_action.setEnabled(has_selection)
        self.cut_action.setEnabled(has_selection)
        self.copy_action.setEnabled(has_selection)
        self.paste_action.setEnabled(has_selection)
        self.delete_action.setEnabled(has_selection)

    def closeEvent(self, event):
        # Remove the window from the dictionary of open windows
        if self.path in app.open_windows:
            del app.open_windows[self.path]

        # Store window position and size in .DS_Spatial JSON file in the directory of the window
        settings_file = os.path.join(self.path, app.desktop_settings_file)
        if os.access(self.path, os.W_OK):
            settings = {}
            settings["position"] = {"x": self.pos().x(), "y": self.pos().y()}
            # Determine the screen this window is on
            for screen in QApplication.screens():
                if screen.geometry().contains(QApplication.activeWindow().frameGeometry()):
                    settings["screen"] = {"x": screen.geometry().x(), "y": screen.geometry().y(), "width": screen.geometry().width(), "height": screen.geometry().height()}
                    break
            settings["size"] = {"width": self.width(), "height": self.height()}
            settings["items"] = []
            for item in self.files:
                if item.name != app.desktop_settings_file:
                    settings["items"].append({"name": robust_filename(item.path), "x": item.pos().x(), "y": item.pos().y()})
            try:
                with open(settings_file, "w") as file:
                    json.dump(settings, file, indent=4)
                    print(f"Written settings to {settings_file}")
            except Exception as e:
                print(f"Error writing settings file: {e}")
        else:
            print(f"Cannot write to {settings_file}")
        event.accept()

    def dragEnterEvent(self, event):
        print("Drag enter event")
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        # print("Drag move event")
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        print("Drop event")
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                # NOTE: normpath needs to be used to avoid issues with different path separators like / and \ on Windows
                print("Dropped file:", os.path.normpath(path))
                print("Dropped in window for path:", os.path.normpath((self.path)))
                # Check if the file is already in the directory; if yes, just move its position
                if os.path.normpath(os.path.dirname(path)) == os.path.normpath(self.path):
                    print("File was moved within the same directory")
                    for item in self.files:
                        if os.path.normpath(item.path) == os.path.normpath(path):
                            drop_position = event.position()
                            print("Moving to coordinates", drop_position.x(), drop_position.y())
                            # Somehow these coordinates are not correct; they are always too deep in the window, so we need to adjust them
                            # FIXME: The -20 is trial and error; it should be calculated based on something
                            # Apparently, QDropEvent's pos() method gives the position of the mouse cursor at the time of the drop event.
                            # That is not what we want. We want the position of the item that is being dropped, not the mouse cursor.
                            # Do we need mapToGlobal() or mapFromGlobal()? Or do we need to do something differently in the startDrag event first, like adding all selected item locations to the drag event?
                            pixmap_height = item.icon_label.pixmap().height()
                            drop_position = QPoint(int(drop_position.x() - 20), int(drop_position.y() - pixmap_height))
                            # Half an icon height to the top and to the left
                            # FIXME: Instead of hardcoding the hot spot to be half the icon size, it should be corrected based on the position of the mouse cursor relative to the item at the time of the drag event
                            drop_position = QPoint(drop_position.x() - int(48/2), drop_position.y() - int(48/2))
                            # Take into consideration the scroll position
                            drop_position += QPoint(self.scroll_area.horizontalScrollBar().value(), self.scroll_area.verticalScrollBar().value())
                            # If the Alt modifier key is pressed, move to something that is a multiple of 24 - this is kind of a grid
                            if event.modifiers() == Qt.KeyboardModifier.AltModifier:
                                drop_position = QPoint(int(drop_position.x() / 48) * 48, int(drop_position.y() / 48) * 48)
                            item.move(drop_position)
                            break
                else:
                    print("Not implemented yet: dropEvent for items from other directories")
            event.accept()
        else:
            event.ignore()

    def align_items(self):
        width =  200
        num_columns = self.width() // width
        horizontal_spacing = 10
        vertical_spacing = 5
        line_height = 70
        current_column = 0
        current_row = 0

        # Iterate over the items
        for item in self.files:
            # Calculate the new position of the item
            new_x = current_column * (width + horizontal_spacing)
            new_y = current_row * (line_height + vertical_spacing)

            # If the item's text is wider than the item's icon, need to adjust the x position by moving it to the left
            if item.text_label.width() > item.icon_label.width():
                new_x -= int((item.text_label.width() - item.icon_label.width()) / 2)

            # Space on top and at the left of the window, at the top 10 pixels, at the left half of the item width
            new_x += int(width/4)
            new_y += 10

            # Move the item to the new position
            item.move(new_x, new_y)

            # Increment the current column
            current_column += 1

            # If the current column is equal to the number of columns, reset it and increment the current row
            if current_column == num_columns:
                current_column = 0
                current_row += 1

        # Update the container size
        self.update_container_size()

    def align_items_staggered(self):
        width =  200
        num_columns = self.width() // width
        horizontal_spacing = 10
        vertical_spacing = 5
        line_height = 40
        current_column = 0
        current_row = 0

        # Sort the items by name
        self.files.sort(key=lambda x: x.name, reverse=False)

        # Iterate over the items
        for i, item in enumerate(self.files):
            # Calculate the new position of the item
            if current_row % 2 == 0:  # Even row
                new_x = current_column * (width + horizontal_spacing)
            else:  # Odd row
                new_x = (current_column + 0.5) * (width + horizontal_spacing)

            new_y = current_row * (line_height + vertical_spacing)

            # If the item's text is wider than the item's icon, need to adjust the x position by moving it to the left
            if item.text_label.width() > item.icon_label.width():
                new_x -= int((item.text_label.width() - item.icon_label.width()) / 2)

            # Space on top and at the left of the window, at the top 10 pixels, at the left half of the item width
            new_x += int(width/4)
            new_y += 10

            # Move the item to the new position
            item.move(int(new_x), int(new_y))

            # Increment the current column
            if current_row % 2 == 0:  # Even row
                current_column += 1
                if current_column >= num_columns:
                    current_column = 0
                    current_row += 1
            else:  # Odd row
                current_column += 1
                if current_column >= num_columns - 1:
                    current_column = 0
                    current_row += 1

        # Update the container size
        self.update_container_size()

    def align_items_desktop(self):
        horizontal_spacing = 10
        vertical_spacing = 5
        width = 200
        line_height = 70
        num_rows = (self.height() // line_height ) - 2
        current_column = 0
        current_row = 0

        start_x = self.width() - width - 10
        start_y = 10

        for item in self.files:

            # Calculate the new position of the item
            new_x = start_x - current_column * (width + horizontal_spacing)
            new_y = start_y + current_row * (line_height + vertical_spacing)

            # If the item's text is wider than the item's icon, need to adjust the x position by moving it to the left
            if item.text_label.width() > item.icon_label.width():
                new_x -= int((item.text_label.width() - item.icon_label.width()) / 2)

            # Space on top and at the left of the window, at the top 10 pixels, at the left half of the item width
            new_x += int(width/4)
            new_y += 10

            # Move the item to the new position
            item.move(new_x, new_y)

            # Increment the current column
            current_row += 1

            # If the current row is equal to the number of rows, reset it and increment the current column
            if current_row == num_rows:
                current_row = 0
                current_column += 1

    def align_items_circle(self):
        width = 200
        horizontal_spacing = 10
        vertical_spacing = 5
        radius = self.width() // 2 - horizontal_spacing - width // 2

        # Calculate the center of the circle
        circle_center_x = radius + width // 2
        circle_center_y = radius + vertical_spacing

        # Iterate over the items
        for i, item in enumerate(self.files):
            # Calculate the new position of the item
            angle = i * 2 * math.pi / len(self.files)
            new_x = circle_center_x + radius * math.cos(angle)
            new_y = circle_center_y + radius * math.sin(angle)

            # If the item's text is wider than the item's icon, need to adjust the x position by moving it to the left
            if item.text_label.width() > item.icon_label.width():
                new_x -= int((item.text_label.width() - item.icon_label.width()) / 2)

            # Move the item to the new position
            item.move(int(new_x), int(new_y))

    def show_about(self):
        QMessageBox.about(self, "About", "Spatial File Manager\n\nA simple file manager that uses a spatial interface.")

def robust_filename(path):
    # Use this instead of os.path.basename to avoid issues on Windows
    name = os.path.basename(path)
    # If the path is e.g., "C:/", the name should be "C:"
    if name == "":
        name = path
    # Remove the final slash if it ends with one
    if name.endswith("/"):
        name = name[:-1]
    return name

class Item(QWidget):
    def __init__(self, path, is_directory, position, parent=None):
        super().__init__(parent)
        self.path = path
        self.name = robust_filename(path)

        # On Windows, files ending with .lnk are shortcuts; we remove the final extension from the name
        if sys.platform == "win32" and self.name.endswith(".lnk"):
            self.name = os.path.splitext(self.name)[0]
        
        self.is_directory = is_directory
        self.position = position

        icon_provider = QFileIconProvider()
        if self.path == os.path.normpath(os.path.join(QDir.homePath(), "Desktop", app.trash_name)):
            icon = icon_provider.icon(QFileIconProvider.IconType.Trashcan).pixmap(48, 48)
        else:
            icon = icon_provider.icon(QFileInfo(self.path)).pixmap(48, 48)

        # Maximum 150 pixels wide, elide the text in the middle
        font_metrics = QFontMetrics(self.font())
        self.elided_name = font_metrics.elidedText(self.name, Qt.TextElideMode.ElideMiddle, 150)

        # Set icon size and padding
        self.icon_size = 48
        padding = 0  # Padding around icon and text

        # Calculate the text width
        text_width = font_metrics.horizontalAdvance(self.elided_name)

        # Determine the widget width
        widget_width = max(self.icon_size, text_width) + padding * 2

        # Set the fixed size for the widget, including some padding above and below the content
        self.setFixedSize(widget_width, self.icon_size + font_metrics.height() + padding * 2)

        # Layout setup
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)  # Space between icon and text
        self.layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        # Icon label setup
        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(self.icon_size, self.icon_size)
        self.icon_label.setPixmap(icon)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Text label setup
        self.text_label = QLabel(self.elided_name, self)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.text_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Ensure the widget's size policy does not expand
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Double-click event to open the item
        self.mouseDoubleClickEvent = self.open

        # Add a context menu to the item
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        context_menu = QMenu(self)
        self.open_action = QAction("Open", self)
        self.open_action.triggered.connect(self.open)
        context_menu.addAction(self.open_action)
        context_menu.addSeparator()
        self.get_info_action = QAction("Get Info", self)
        self.get_info_action.triggered.connect(self.get_info)
        context_menu.addAction(self.get_info_action)
        context_menu.addSeparator()
        self.cut_action = QAction("Cut", self)
        self.cut_action.setDisabled(True)
        context_menu.addAction(self.cut_action)
        self.copy_action = QAction("Copy", self)
        self.copy_action.setDisabled(True)
        context_menu.addAction(self.copy_action)
        self.paste_action = QAction("Paste", self)
        self.paste_action.setDisabled(True)
        context_menu.addAction(self.paste_action)
        self.trash_action = QAction("Move to Trash", self)
        self.trash_action.setDisabled(True)
        context_menu.addAction(self.trash_action)
        context_menu.exec(self.mapToGlobal(pos))

    def get_info(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Information")

        layout = QGridLayout(dialog)
        dialog.setLayout(layout)
        
        properties = ["Name", "Kind", "Size", "Location", "Created", "Modified", "Last opened"]
        file_info = QFileInfo(self.path)
        values = [""] * len(properties)
        values[0] = file_info.fileName()
        values[1] = "Folder" if file_info.isDir() else "Document"
        values[2] = "N/A" if file_info.isDir() else str(file_info.size()) + " bytes"
        values[3] = file_info.absolutePath()
        try:
            values[4] = file_info.birthTime().toString()
        except:
            values[4] = "N/A"
        values[5] = file_info.lastModified().toString()
        values[6] = file_info.lastRead().toString()
        
        for i, property in enumerate(properties):
            label = QLabel(property, dialog)
            label.setStyleSheet("font-weight: bold; text-align: right;")
            label.setAlignment(Qt.AlignmentFlag.AlignRight)
            value = QLabel(values[i], dialog)
            layout.addWidget(label, i, 0)  # Add label to left column
            layout.addWidget(value, i, 1)  # Add value to right column
        
        dialog.exec()

    def open(self, event):
        self.path = os.path.realpath(self.path)
        if self.is_directory:
            existing_window = app.open_windows.get(self.path)
            if existing_window:
                existing_window.raise_()
                existing_window.activateWindow()
            else:
                new_window = SpatialFiler(self.path)
                new_window.show()
                app.open_windows[self.path] = new_window
        else:
            if sys.platform == "win32":
                if self.path.endswith(".AppImage"):
                    try:
                        # Run wsl and pass in the Linux path to the AppImage; tested on Windows 11
                        drive_letter = self.path[0]
                        linux_path = self.path.replace("\\", "/")
                        linux_path = linux_path.replace(drive_letter + ":", "/mnt/" + drive_letter.lower())
                        linux_path = linux_path.replace("(", "").replace(")", "")
                        print(f"Launching AppImage with WSL: {linux_path}")
                        # sudo apt-get -y install fuse libfuse2
                        command = ["wsl", linux_path]
                        subprocess.Popen(command)
                        # TODO: Show any error messages coming from the subprocess in a QMessageBox.critical if possible
                    except Exception as e:
                        print(f"Error opening AppImage: {e}")
                else:
                    try:
                        os.startfile(self.path)
                    except Exception as e:
                        print(f"Error opening file: {e}")
            else:
                os.system(f"xdg-open \"{self.path}\"")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.open_windows = {}
    app.desktop_settings_file = ".DS_Spatial"
    app.trash_name = "Trash"
    
    for screen in QApplication.screens():
        # TODO: Possibly only create the desktop window on the primary screen and just show a background image on the other screens
        desktop = SpatialFiler(os.path.normpath(QDir.homePath() + "/Desktop"))
        desktop.move(screen.geometry().x(), screen.geometry().y())
        desktop.resize(screen.geometry().width(), screen.geometry().height())
        desktop.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        # If .DS_Spatial does not exist, align the items like on the desktop
        if not os.path.exists(os.path.join(QDir.homePath(), app.desktop_settings_file)):
            desktop.align_items_desktop()
        # Change the background color of the container
        p = desktop.container.palette()
        p.setColor(desktop.container.backgroundRole(), QColor(Qt.GlobalColor.lightGray))
        desktop.container.setPalette(p)

        desktop.setWindowFlag(Qt.WindowType.WindowStaysOnBottomHint)

        # On Windows, get the wallpaper and set it as the background of the window
        if sys.platform == "win32":
            shell = Dispatch("WScript.Shell")
            windows_wallpaper_path = os.path.normpath(shell.RegRead("HKEY_CURRENT_USER\\Control Panel\\Desktop\\Wallpaper")).replace("\\", "/")
            print("Windows wallpaper path:", windows_wallpaper_path)
            # Set the background image of the window
            p = desktop.container.palette()
            p.setBrush(desktop.container.backgroundRole(), QBrush(QPixmap(windows_wallpaper_path).scaled(desktop.width(), desktop.height(), Qt.AspectRatioMode.KeepAspectRatioByExpanding)))
            desktop.container.setPalette(p)
          
        desktop.show()

    sys.exit(app.exec())