#!/usr/bin/env python3

# TODO: Rename activate/deactivate to highlight/unhighlight

# Tested on Windows 11. Moving items within the window not perfect here, but it is using Qt drag and drop
# Key is to avoid QListView and QFileSystemModel because they are not suited for our purpose of creating a spatial file manager

import sys
import os
import json
import subprocess
import math
import shutil

from PyQt6.QtCore import Qt, QPoint, QSize, QDir, QRect, QMimeData, QUrl, QFileSystemWatcher, QFileInfo, QTimer
from PyQt6.QtGui import QFontMetrics, QPainter, QPen, QAction, QDrag, QColor, QPainter, QPen, QBrush, QPixmap, QKeySequence, QFont, QIcon, QShortcut
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QScrollArea, QLabel, QSizePolicy, QMainWindow
from PyQt6.QtWidgets import QStatusBar, QComboBox, QFileIconProvider, QMenuBar, QGridLayout, QMessageBox, QMenu, QDialog

if sys.platform == "win32":
    from win32com.client import Dispatch
    import windows_context_menu

import appdir

class SpatialFiler(QMainWindow):

    def __init__(self, path=None, is_desktop_window=False):
        super().__init__()
        
        self.path = path if path else QDir.homePath()
        self.setWindowTitle(self.path)
        self.setGeometry(100, 100, 800, 600)
        self.is_desktop_window = is_desktop_window
        self.is_spring_opened = False

        # Set folder icon on window; unfortunately Windows doesn't use this for the taskbar icon
        icon_provider = QFileIconProvider()
        icon = icon_provider.icon(QFileInfo(self.path))
        self.setWindowIcon(icon)

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

        # Create the central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.scroll_area = QScrollArea(self.central_widget)
        self.scroll_area.setContentsMargins(0, 0, 0, 0)
        self.scroll_area.setWidgetResizable(True)
        self.container = QWidget()
        palette = self.container.palette()
        palette.setColor(self.container.backgroundRole(), Qt.GlobalColor.white)
        self.container.setPalette(palette)
        self.scroll_area.setWidget(self.container)
        self.layout.addWidget(self.scroll_area)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.central_widget.setLayout(self.layout)

        # Create the menu bar
        self.menu_bar = QMenuBar(self)
        self.setMenuBar(self.menu_bar)
        self.init_menu_bar()

        # Initialize other components
        self.items = []
        self.vertical_spacing = 0
        self.line_height = app.icon_size + QFontMetrics(self.font()).height() + 16
        self.horizontal_spacing = 0
        self.item_width_for_positioning = 150
        self.start_x = 0
        self.start_y = 0
        self.populate_items()
        self.dragging = False
        self.last_pos = QPoint(0, 0)
        self.selected_files = []
        self.selection_rect = QRect(0, 0, 0, 0)
        self.is_selecting = False

        # Setup status bar with a dropdown if this is not the desktop window
        if not self.is_desktop_window:
            self.status_bar = QStatusBar()
            self.setStatusBar(self.status_bar)
            self.dropdown = QComboBox()
            self.populate_dropdown()
            self.dropdown.currentIndexChanged.connect(self.on_dropdown_changed)
            self.status_bar.addPermanentWidget(self.dropdown)
            self.status_bar.setSizeGripEnabled(False)
            self.status_bar.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
            # Add a 10px wide spacer to the right of the dropdown to leave some space for the resize handle
            spacer_widget = QWidget()
            spacer_widget.setFixedWidth(15)
            spacer_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.status_bar.addPermanentWidget(spacer_widget)
            # Timer to update the status bar every 5 seconds
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_status_bar)
            self.timer.start(5000)
            self.update_status_bar()

        # To keep track of drag distances
        self.initial_position = None

        # Watch for changes in the directory
        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.directoryChanged.connect(self.directory_changed)
        self.file_watcher.fileChanged.connect(self.file_changed)
        self.file_watcher.addPath(self.path)

    def keyPressEvent(self, event):
        # Handle Tab and Shift-Tab to select the next and previous item
        if event.key() == Qt.Key.Key_Tab:
            if QApplication.keyboardModifiers() == Qt.KeyboardModifier.ShiftModifier:
                # FIXME: Why does this never get called?
                self.select_previous_item()
            else:
                self.select_next_item()

    def select_next_item(self):
        print("Selecting next item")
        if self.selected_files:
            item = self.selected_files[0]
            self.selected_files.remove(item)
        else:
            item = self.items[0]        
        item.deactivate()

        # Select the next item if there is one, otherwise select the first item
        if item in self.items:
            index = self.items.index(item)
            if index < len(self.items) - 1:
                next_item = self.items[index + 1]
            else:
                next_item = self.items[0]
            self.selected_files = [next_item]
            next_item.activate()

    def select_previous_item(self):
        print("Selecting previous item")
        if self.selected_files:
            item = self.selected_files[0]
            self.selected_files.remove(item)
        else:
            item = self.items[len(self.items) - 1]   
        item.deactivate()

        # Select the previous item if there is one, otherwise select the last item
        if item in self.items:
            index = self.items.index(item)
            if index > 0:
                previous_item = self.items[index - 1]
            else:
                previous_item = self.items[-1]
            self.selected_files = [previous_item]
            previous_item.activate()

    def populate_dropdown(self):
        try:
            path = self.path
            if path.startswith("//") or path.startswith("\\\\"):
                print("Skipping network path")  # TODO: Implement network path handling for Windows
                self.dropdown.hide()
                return
            paths = []
            while os.path.exists(path):
                paths.append(path)
                if os.path.normpath(path) == os.path.normpath(QDir.rootPath()):
                    break
                # On Windows, stop at the drive letter, otherwise we can get an infinite loop
                if sys.platform == "win32" and len(path) == 3 and path[1] == ":":
                    break
                path = os.path.dirname(path)
            paths.reverse()
            for path in paths:
                self.dropdown.addItem(robust_filename(path))
                self.dropdown.setItemData(self.dropdown.count() - 1, path, Qt.ItemDataRole.UserRole)
            self.dropdown.setCurrentIndex(self.dropdown.count() - 1)
        except Exception as e:
            print(f"Error populating dropdown: {e}")

    def on_dropdown_changed(self):
        selected_path = self.dropdown.currentData(Qt.ItemDataRole.UserRole)
        print("Dropdown changed, selected path:", selected_path)
        self.dropdown.blockSignals(True)
        self.dropdown.setCurrentIndex(self.dropdown.count() - 1)
        self.dropdown.blockSignals(False)
        self.open(selected_path)

    def update_status_bar(self):
        path = self.path
        item_count = len([f for f in QDir(path).entryList() if f not in [".", ".."]])
        try:
            free_space = shutil.disk_usage(path).free
            if free_space < 1024:
                free_space_str = f"{free_space} Bytes"
            elif free_space < 1024 ** 2:
                free_space_str = f"{free_space / 1024:.2f} KB"
            elif free_space < 1024 ** 3:
                free_space_str = f"{free_space / (1024 ** 2):.2f} MB"
            else:
                free_space_str = f"{free_space / (1024 ** 3):.2f} GB"
        except Exception as e:
            free_space_str = "Unknown"
            print(f"Error getting free space: {e}")
        self.status_bar.showMessage(f"{item_count} items, {free_space_str} available")

    def open(self, path):
        i = Item(path, True, QPoint(0, 0), self.container)
        i.open(None)
        i = None

    def directory_changed(self, path):
        if not os.path.exists(self.path):
            self.close()
            return

        # Remove items from the window that are not in the directory anymore
        items_to_remove = []
        for item in self.items:
            if not os.path.exists(item.path):
                items_to_remove.append(item)
        for item in items_to_remove:
            item.hide()
            if self.container.layout():
                self.container.layout().removeWidget(item)
            self.items.remove(item)
            item.deleteLater()
        self.populate_items()  # This adds new items to the window
        self.update_container_size()

    def file_changed(self, path):
        if not os.path.exists(self.path):
            self.close()
            return
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
        self.open_action.setShortcuts([QKeySequence("Ctrl+O"), QKeySequence("Shift+Ctrl+O"), QKeySequence("Ctrl+Down"), QKeySequence("Shift+Ctrl+Down")])
        # "Enter" is a non-modifier key shortcut, so we need to use a QShortcut object to catch it
        self.open_action.triggered.connect(self.open_selected_items)
        self.open_shortcut = QShortcut(QKeySequence("Enter"), self)
        self.open_shortcut.activated.connect(self.open_selected_items)
        self.open_action.setEnabled(False)
        if self.is_desktop_window == True:
            self.close_action = QAction("Quit", self)
            self.close_action.setShortcut("Ctrl+Q")
        else:
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
        edit_menu.addSeparator()
        self.select_all_action = QAction("Select All", self)
        self.select_all_action.setShortcut("Ctrl+A")
        self.select_all_action.triggered.connect(self.select_all)
        edit_menu.addAction(self.select_all_action)
        # Go Menu
        go_menu = self.menu_bar.addMenu("Go")
        parent = os.path.dirname(self.path)
        up_action = QAction("Up", self)
        up_action.setShortcuts(["Ctrl+Up", "Ctrl+Shift+Up"])
        up_action.triggered.connect(self.open_parent)
        if not os.path.exists(parent) or os.path.normpath(self.path) == os.path.normpath(QDir.rootPath()):
            up_action.setDisabled(True)
        go_menu.addAction(up_action)
        go_menu.addSeparator()
        home_action = QAction("Home", self)
        home_action.triggered.connect(self.open_home)
        go_menu.addAction(home_action)
        if sys.platform == "win32":
            start_menu_action = QAction("Applications", self)
            start_menu_action.triggered.connect(self.open_start_menu_folder)
            go_menu.addAction(start_menu_action)
        # View Menu
        view_menu = self.menu_bar.addMenu("View")
        if os.path.normpath(self.path) == get_desktop_directory():
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
            view_menu.addSeparator()
            adjust_window_size_action = QAction("Adjust Window Size", self)
            adjust_window_size_action.triggered.connect(self.adjust_window_size)
            view_menu.addAction(adjust_window_size_action)
        
        # Help Menu
        help_menu = self.menu_bar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        help_menu.addSeparator
        if "log_console" in sys.modules:
            app.log_console.add_menu_items(help_menu, self)

    def select_all(self):
        for item in self.items:
            self.selected_files.clear()
            self.selected_files.append(item)
            item.activate()

    def open_parent(self):
        # Detect whether the Shift key is pressed; if yes; if yes, close the current window if it is not the fullscreen desktop window
        parent = os.path.dirname(self.path)
        if (QApplication.keyboardModifiers() == Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier) and self.is_desktop_window == False:
            if os.path.exists(parent):
                self.open(parent)
                self.close()
        else:
            if os.path.exists(parent):
                self.open(parent)

    def open_home(self):
        # TODO: Detect whether the Shift key is pressed; if yes; if yes, close the current window if it is not the fullscreen desktop window
        self.open(QDir.homePath())

    def open_start_menu_folder(self):
        # TODO: Detect whether the Shift key is pressed; if yes, close the current window if it is not the fullscreen desktop window
        self.start_menu_folder = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs')
        self.open(self.start_menu_folder)

    def adjust_window_size(self):
        # Adjust the window size to fit the items
        max_x = max(item.x() + item.width() for item in self.items) + 30
        max_y = max(item.y() + item.height() for item in self.items) + 40
        # If the window has a status bar, add its height to the window height
        if self.status_bar.isVisible():
            max_y += self.status_bar.height()
        self.resize(max_x, max_y)

    def populate_items(self):
        if os.path.normpath(self.path) == get_desktop_directory():

            # Add every disk in the system
            print("Adding disks")
            for disk in QDir.drives():
                if not any(item.name == robust_filename(disk.path()) for item in self.items):
                    # The name of the disk is the first part of the path, e.g. "C:" or "D:"
                    disk_name = disk.path()
                    print("Adding disk", disk_name)
                    self.add_file(disk.path(), True)

            # Add the Trash item
            if not any(item.name == app.trash_name for item in self.items):
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
                    if any(item.name == entry for item in self.items):
                        continue
                    # .DS_Spatial is a special file that we don't want to show
                    if entry == app.desktop_settings_file:
                        continue
                    # ~/Desktop is a special case; we don't want to show it
                    if self.path == os.path.basename(get_desktop_directory()) and entry == "Desktop":
                        continue
                    entry_path = os.path.join(self.path, entry)
                    is_directory = os.path.isdir(entry_path)
                    # print(f"Adding item: {entry}")
                    self.add_file(entry_path, is_directory)
        except Exception as e:
            print(f"Error accessing directory: {e}")

    def calculate_max_width(self):
        return max(item.width() for item in self.items) if self.items else 150

    def add_file(self, path, is_directory):
        position = QPoint(self.start_x + len(self.items) % 5 * (self.calculate_max_width() + self.horizontal_spacing), 
                          self.start_y + len(self.items) // 5 * (self.line_height + self.vertical_spacing))
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
        self.items.append(item)
        self.update_container_size()

    def update_container_size(self):
        if len(self.items) > 0:
            max_x = max(item.x() + item.width() for item in self.items) + 10
            max_y = max(item.y() + item.height() for item in self.items) + 10
            self.container.setMinimumSize(QSize(max_x, max_y))

    def mousePressEvent(self, event):

        for item in self.items:
            item.text_label_deactivate()

        scroll_pos = QPoint(self.scroll_area.horizontalScrollBar().value(),
                            self.scroll_area.verticalScrollBar().value())
        adjusted_pos = event.pos() + scroll_pos

        if event.button() == Qt.MouseButton.LeftButton:
            clicked_item = None
            for item in self.items:
                if (item.x() <= adjusted_pos.x() <= item.x() + item.width()) and \
                (item.y() <= adjusted_pos.y() <= item.y() + item.height()):
                    # Find out if the click was on the icon or not, 
                    # assuming the icon at the center bottom of the item rectangle;
                    # TODO: Find a better way to determine if the click was on the icon independent of the geometry of the item,
                    # similar to how we do it for right-clicks in the context menu
                    icon_center_x = item.x() + item.width() / 2
                    icon_center_y = item.y() + item.icon_size / 2
                    if (icon_center_x - item.icon_size / 2 <= adjusted_pos.x() <= icon_center_x + item.icon_size / 2) and \
                    (icon_center_y <= adjusted_pos.y() <= icon_center_y + item.icon_size):
                        # Clicked on the icon
                        clicked_item = item
                        break

            if clicked_item:
                if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                    if clicked_item in self.selected_files:
                        self.selected_files.remove(clicked_item)
                        clicked_item.deactivate()
                    else:
                        self.selected_files.append(clicked_item)
                        clicked_item.activate()
                else:
                    if clicked_item not in self.selected_files:
                        self.selected_files = [clicked_item]
                        for f in self.items:
                            if f != clicked_item:
                                f.deactivate()
                        clicked_item.activate()
                    
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
                    drag.setHotSpot(QPoint(int(app.icon_size/2), int(app.icon_size/2)))
                    drag.exec()
            else:
                self.is_selecting = True
                self.selection_rect = QRect(adjusted_pos.x(), adjusted_pos.y(), 0, 0)
                self.update()
                self.selected_files = []
                for item in self.items:
                    item.deactivate()
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
            drag.setHotSpot(QPoint(int(app.icon_size/2), int(app.icon_size/2)))
            drag.exec()

        elif self.is_selecting:
            self.selection_rect = QRect(min(self.selection_rect.x(), adjusted_pos.x()),
                                        min(self.selection_rect.y(), adjusted_pos.y()),
                                        abs(adjusted_pos.x() - self.selection_rect.x()),
                                        abs(adjusted_pos.y() - self.selection_rect.y()))
            self.update()
            for item in self.items:
                if (self.selection_rect.x() <= item.x() + item.width() and
                    item.x() <= self.selection_rect.x() + self.selection_rect.width() and
                    self.selection_rect.y() <= item.y() + item.height() and
                    item.y() <= self.selection_rect.y() + self.selection_rect.height()):
                    if item not in self.selected_files:
                        self.selected_files.append(item)
                        item.activate()
                else:
                    if item in self.selected_files:
                        self.selected_files.remove(item)
                        item.deactivate()

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
        if (QApplication.keyboardModifiers() == Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier) and self.is_desktop_window == False:
            self.close()

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
            for item in self.items:
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
        if self.initial_position is None:
            self.initial_position = event.position()

        print("Drag enter event")
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def startDrag(self, event):
        self.initial_position = event.pos()

    def dragLeaveEvent(self, event):
        # If this window was spring-loaded, close it when the drag leaves the window
        if self.is_spring_opened:
            # FIXME: For some reason, the following line does not work. May need to iterate through all item rects
            # to see if the mouse is within them (and possibly some margin)
            if any(item.underMouse() for item in self.items):
                event.ignore()
            else:
                self.close()
                event.accept()
            
    def dropEvent(self, event):
        initial_position = self.initial_position
        self.initial_position = None
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
                    distance = (event.position() - initial_position).manhattanLength()
                    print("Distance from initial position:", distance)
                    # Ignore moves below a threshold distance
                    # QApplication.startDragDistance() is the default value that Qt uses for this
                    if distance < 20:
                        event.ignore()
                        return
                    for item in self.items:
                        if os.path.normpath(item.path) == os.path.normpath(path):
                            drop_position = event.position()
                            print("Moving to coordinates", drop_position.x(), drop_position.y())
                            # FIXME: Apparently, QDropEvent's pos() method gives the position of the mouse cursor at the time of the drop event.
                            # That is not what we want. We want the position of the item that is being dropped, not the mouse cursor.
                            # Do we need mapToGlobal() or mapFromGlobal()? Or do we need to do something differently in the startDrag event first, like adding all selected item locations to the drag event?
                            pixmap_height = item.icon_label.pixmap().height()
                            drop_position = QPoint(int(drop_position.x()), int(drop_position.y() - pixmap_height))
                            # The next line currently works because the mouse is set to be in the center of the item when the drag starts,
                            # but that is not a good solution because it makes the dragged icon jump at the beginning of the drag
                            drop_position = QPoint(drop_position.x() - int(item.width()/2), drop_position.y() - int(app.icon_size/4))
                            # Take into consideration the scroll position
                            drop_position += QPoint(self.scroll_area.horizontalScrollBar().value(), self.scroll_area.verticalScrollBar().value())
                            # If the Alt modifier key is pressed, move to something that is a multiple of 24 - this is kind of a grid
                            if event.modifiers() == Qt.KeyboardModifier.AltModifier:
                                drop_position = QPoint(int(drop_position.x() / app.icon_size) * app.icon_size, int(drop_position.y() / app.icon_size) * app.icon_size)
                            item.move(drop_position)
                            break
                else:
                    print("Not implemented yet: dropEvent for items from other directories")
            event.accept()
        else:
            event.ignore()

    def align_items(self):
        if not self.items:
            return
        num_columns = self.width() // self.item_width_for_positioning
        current_column = 0
        current_row = 0

        # Iterate over the items
        for item in self.items:
            # Calculate the new position of the item
            new_x = current_column * (self.item_width_for_positioning + self.horizontal_spacing)
            new_y = current_row * (self.line_height + self.vertical_spacing)

            # If the item's text is wider than the item's icon, need to adjust the x position by moving it to the left
            if item.text_label.width() > item.icon_label.width():
                new_x -= int((item.text_label.width() - item.icon_label.width()) / 2)

            # Space on top and at the left of the window, at the top 10 pixels, at the left half of the item width
            new_x += int(self.item_width_for_positioning/4)
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

        if not self.is_desktop_window:
            self.adjust_window_size()

    def align_items_staggered(self):
        if not self.items:
            return
        num_columns = (self.width() // self.item_width_for_positioning)
        line_height = int(self.line_height - 1.1 * app.icon_size) # 0.5
        current_column = 0
        current_row = 0

        # Sort the items by name
        self.items.sort(key=lambda x: x.name, reverse=False)

        # Iterate over the items
        for i, item in enumerate(self.items):
            # Calculate the new position of the item
            if current_row % 2 == 0:  # Even row
                new_x = current_column * (self.item_width_for_positioning + self.horizontal_spacing + app.icon_size)
            else:  # Odd row
                new_x = (current_column + 0.5) * (self.item_width_for_positioning + self.horizontal_spacing + app.icon_size)

            new_y = current_row * (line_height + self.vertical_spacing)

            # If the item's text is wider than the item's icon, need to adjust the x position by moving it to the left
            if item.text_label.width() > item.icon_label.width():
                new_x -= int((item.text_label.width() - item.icon_label.width()) / 2)

            # Space on top and at the left of the window, at the top 10 pixels, at the left half of the item width
            new_x += int(self.item_width_for_positioning/4)
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

        if not self.is_desktop_window:
            self.adjust_window_size()

    def align_items_desktop(self):
        if not self.items:
            return
        num_rows = (self.height() // self.line_height ) - 1
        current_column = 0
        current_row = 0

        start_x = self.width() - self.item_width_for_positioning
        start_y = 10

        for item in self.items:

            # Calculate the new position of the item
            new_x = start_x - current_column * (self.item_width_for_positioning + self.horizontal_spacing)
            new_y = start_y + current_row * (self.line_height + self.vertical_spacing)

            # If the item's text is wider than the item's icon, need to adjust the x position by moving it to the left
            if item.text_label.width() > item.icon_label.width():
                new_x -= int((item.text_label.width() - item.icon_label.width()) / 2)

            # Space on top and at the left of the window, at the top 10 pixels, at the left half of the item width
            new_x += int(self.item_width_for_positioning/4)
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
        if not self.items:
            return
        radius = self.width() // 2 - self.horizontal_spacing - self.item_width_for_positioning // 2

        # Calculate the center of the circle
        circle_center_x = radius + self.item_width_for_positioning // 2
        circle_center_y = radius + self.vertical_spacing

        # Iterate over the items
        for i, item in enumerate(self.items):
            # Calculate the new position of the item
            angle = i * 2 * math.pi / len(self.items)
            new_x = circle_center_x + radius * math.cos(angle)
            new_y = circle_center_y + radius * math.sin(angle)

            # If the item's text is wider than the item's icon, need to adjust the x position by moving it to the left
            if item.text_label.width() > item.icon_label.width():
                new_x -= int((item.text_label.width() - item.icon_label.width()) / 2)

            # Move the item to the new position
            item.move(int(new_x), int(new_y))

        if not self.is_desktop_window:
            self.adjust_window_size()

    def show_about(self):
        dialog = QMessageBox(self)
        dialog.setIconPixmap(app.icon.pixmap(app.icon_size, app.icon_size))
        dialog.setWindowTitle("About")
        dialog.setText("Spatial File Manager\n\nA simple file manager that uses a spatial interface.")
        dialog.exec()


def robust_filename(path):
    # Use this instead of os.path.basename to avoid issues on Windows
    name = os.path.basename(path)
    # If the path is e.g., "C:/", the name should be "C:"
    if name == "":
        name = path
    # Remove the final slash if it ends with one
    if name.endswith("/") or name.endswith("\\"):
        name = name[:-1]
    return name

class Item(QWidget):
    def __init__(self, path, is_directory, position, parent=None):
        super().__init__(parent)
        self.path = os.path.normpath(path)
        self.name = robust_filename(path)

        # For spring-loaded folders
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self.spring_open)

        # On Windows, files ending with .lnk are shortcuts; we remove the final extension from the name
        if sys.platform == "win32" and self.name.endswith(".lnk"):
            self.name = os.path.splitext(self.name)[0]
        
        self.is_directory = is_directory
        self.position = position

        self.setAcceptDrops(True)

        icon_provider = QFileIconProvider()
        # Trash
        if self.path == os.path.normpath(get_desktop_directory() + "/" + app.trash_name):
            icon = icon_provider.icon(QFileIconProvider.IconType.Trashcan).pixmap(app.icon_size, app.icon_size)
        elif appdir.is_appdir(self.path):
            A = appdir.AppDir(self.path)
            icon_path = A.get_icon_path()
            if icon_path:
                icon = QIcon(icon_path).pixmap(app.icon_size, app.icon_size)
            else:
                icon = icon_provider.icon(QFileInfo(self.path)).pixmap(app.icon_size, app.icon_size)
        else:
            icon = icon_provider.icon(QFileInfo(self.path)).pixmap(app.icon_size, app.icon_size)
        
        # Maximum 150 pixels wide, elide the text in the middle
        font_metrics = QFontMetrics(self.font())
        self.elided_name = font_metrics.elidedText(self.name, Qt.TextElideMode.ElideMiddle, 150)

        # For screenshotting: Replace each letter in the elided name with a random letter; preserve the length. Preserve the case of the letters.
        # import random
        # import string
        # self.elided_name = "".join(random.choice(string.ascii_letters) if c.isalpha() else c for c in self.elided_name)
        # if len(self.elided_name) > 12:
        #     self.elided_name = self.elided_name[5:]

        # Set icon size and padding
        self.icon_size = app.icon_size
        padding = 0  # Padding around icon and text

        # Calculate the text width
        text_width = font_metrics.horizontalAdvance(self.elided_name)
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
        # FIXME: Increase width of the QLabel by 4 pixels while still having the QLabel centered in the box

        font = QFont()
        font.setPointSize(8)
        self.text_label.setFont(font)

        self.layout.addWidget(self.text_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # If text label is clicked, call on_label_clicked
        self.text_label.mousePressEvent = self.on_label_clicked

        # Ensure the widget's size policy does not expand
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Double-click event to open the item
        self.mouseDoubleClickEvent = self.open

        # Add a context menu to the item
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.text_label_deactivate()

    def on_label_clicked(self, event):
        # TODO: Deactivate the text labels of all other items; how to get to the other items?
        self.text_label_activate()
    
    def activate(self):
        self.icon_label.setStyleSheet("background-color: lightblue;")

    def deactivate(self):
        self.icon_label.setStyleSheet("border: 0px; background-color: transparent;")

    def text_label_activate(self):
        if os.access(self.path, os.W_OK):
            self.text_label.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
            self.text_label.setStyleSheet("background-color: black; color: white;")

    def text_label_deactivate(self):
        self.text_label.setStyleSheet("background-color: rgba(255, 255, 255, 0.66); color: black;")

    def show_context_menu(self, pos):
        # Check if the click happened on the icon or the text label
        if self.icon_label.geometry().contains(pos):
            print("Clicked on the icon")
        elif self.text_label.geometry().contains(pos):
            print("Clicked on the text label")
        else:
            return

        # On Windows, use windows_context_menu.py
        if sys.platform == "win32" and self.path is not None:
            windows_context_menu.show_context_menu(self.path)
        else:
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

    def spring_open(self):
        self.open(event=None, spring_open=True)

    def open(self, event=None, spring_open=False):
        print(f"Asked to open {self.path}")
        self.hover_timer.stop()
        self.deactivate()
        self.path = os.path.realpath(self.path)

        if not os.path.exists(self.path):
            QMessageBox.critical(self, "Error", "%s does not exist." % self.path)
            return
        
        if appdir.is_appdir(self.path):
            A = appdir.AppDir(self.path)
            apprun_path = A.get_apprun_path()
            if apprun_path.endswith(".bat"):
                # TODO: Find a way to run bat files without opening a window
                os.startfile(A.get_apprun_path())
            else:
                os.startfile(A.get_apprun_path())
            return

        if self.is_directory:
            existing_window = app.open_windows.get(self.path)
            if existing_window:
                existing_window.raise_()
                existing_window.activateWindow()
            else:
                new_window = SpatialFiler(self.path)
                if spring_open == True:
                    new_window.is_spring_opened = True
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

    def dragEnterEvent(self, event):
        print("dragEnterEvent called")
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            print("Dragging over this item:", [url.toLocalFile() for url in urls])
            self.activate()
            # Spring-loaded folders
            if self.is_directory == True and appdir.is_appdir(self.path) == False:
                print("Starting hover timer")
                self.hover_timer.start(1500)
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        print("No longer dragging over this item")
        self.hover_timer.stop()
        self.deactivate()

    def dropEvent(self, event):
        print("dropEvent called")
        self.hover_timer.stop()
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            print("Dropped onto this item:", [url.toLocalFile() for url in urls])
            event.ignore() # Do not move the item in the window
            # TODO: If this item is an application, then launch this item with the dropped items as arguments;
            # if this item is a directory, or move/copy the items there
        else:
            event.ignore()  # Ignore the event if it's not valid

def get_desktop_directory():
    """Get the desktop directory of the user."""
    if sys.platform == "win32":
        from win32com.client import Dispatch
        shell = Dispatch("WScript.Shell")
        desktop = os.path.normpath(shell.SpecialFolders("Desktop"))
    else:
        desktop = QDir.homePath() + "/Desktop"
    return os.path.normpath(desktop)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    if sys.platform == "win32":
        app.setStyle("Fusion")
    app.open_windows = {}
    app.desktop_settings_file = ".DS_Spatial"
    app.trash_name = "Trash"
    app.icon_size = 32
    app.icon = QFileIconProvider().icon(QFileIconProvider.IconType.Folder)

    # Output not only to the console but also to the GUI
    try:
        import log_console
    except ImportError:
        pass
    if "log_console" in sys.modules:
        app.log_console = log_console.ConsoleOutputStream()
        sys.stdout = log_console.Tee(sys.stdout, app.log_console)
        sys.stderr = log_console.Tee(sys.stderr, app.log_console)

    for screen in QApplication.screens():
        # TODO: Possibly only create the desktop window on the primary screen and just show a background image on the other screens
        desktop = SpatialFiler(get_desktop_directory(), is_desktop_window = True)
        desktop.move(screen.geometry().x(), screen.geometry().y())
        desktop.resize(screen.geometry().width(), screen.geometry().height())
        desktop.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        # If .DS_Spatial does not exist, align the items like on the desktop
        if not os.path.exists(os.path.join(QDir.homePath(), app.desktop_settings_file)):
            desktop.align_items_desktop()
        # Change the background color of the container
        p = desktop.container.palette()
        p.setColor(desktop.container.backgroundRole(), QColor(Qt.GlobalColor.gray))
        desktop.container.setPalette(p)

        desktop.setWindowFlag(Qt.WindowType.WindowStaysOnBottomHint)

        # On Windows, get the wallpaper and set it as the background of the window
        if sys.platform == "win32":
            shell = Dispatch("WScript.Shell")
            windows_wallpaper_path = os.path.normpath(shell.RegRead("HKEY_CURRENT_USER\\Control Panel\\Desktop\\Wallpaper")).replace("\\", "/")
            print("Windows wallpaper path:", windows_wallpaper_path)
            if windows_wallpaper_path != "." and os.path.exists(windows_wallpaper_path):
                p = desktop.container.palette()
                p.setBrush(desktop.container.backgroundRole(), QBrush(QPixmap(windows_wallpaper_path).scaled(desktop.width(), desktop.height(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)))
                desktop.container.setPalette(p)
            else:
                print("No wallpaper found")

        desktop.show()

    sys.exit(app.exec())
