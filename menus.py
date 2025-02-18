#!/usr/bin/env python3

"""
Menu creation module with a custom menu bar.

This module provides functions to create the main application menu bar using setMenuWidget(),
allowing the "Time" menu to be positioned on the right side.
"""

import os, sys, subprocess, time, re

from PyQt6 import QtGui, QtCore, QtWidgets

from preferences import PreferencesDialog
from menubar import RoundedMenuBar

if sys.platform == "win32":
    import win32gui, win32con, win32ui # For managing windows
    import windows_start_menu

class ColorMenu(QtWidgets.QMenu):
    def __init__(self, title, window):
        self.window = window
        super().__init__(title, self.window)
        self.colors = ["red", "orange", "yellow", "green", "blue", "purple", "grey"]

        for color in self.colors:
            action = QtGui.QAction(self)
            action.setText(color.upper())
            action.triggered.connect(lambda checked, color=color: self.color_selected(color))
            self.addAction(action)
        
        action = QtGui.QAction(self)
        action.setText("None")
        action.triggered.connect(lambda checked, color=None: self.color_selected(color))
        self.addAction(action)

        # Set the stylesheet for the menu
        self.setStyleSheet("""
            QMenu {
                background-color: #fff;
            }
        """)

    def color_selected(self, color):
        print(f"Color {color} selected")
        self.window.color_selected(color)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        height = self.actionGeometry(self.actions()[0]).height()
        for i, action in enumerate(self.actions()):
            if len(self.colors) > i:
                rect = self.rect()
                rect.setTop(i * height)
                rect.setHeight(height)
                # If hovering over an action, highlight it
                if action == self.activeAction():
                    highlight_color = QtGui.QColor(self.colors[i]).lighter(150)
                    painter.setBrush(QtGui.QBrush(QtGui.QColor(highlight_color)))
                    painter.drawRect(rect)
                else:
                    painter.setBrush(QtGui.QBrush(QtGui.QColor(self.colors[i])))
                # No border
                painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.transparent))
                painter.drawRect(rect)   

def create_menus(window):
    """
    Create the main application menu bar using setMenuWidget(),
    keeping all existing actions, separators, and functionality.
    """

    app = QtWidgets.QApplication.instance()

    # Create a custom QWidget to replace the default menu bar
    menu_widget = QtWidgets.QWidget()
    menu_layout = QtWidgets.QHBoxLayout(menu_widget)  # Use horizontal layout

    # Ensure no extra spacing around layout
    menu_layout.setContentsMargins(0, 0, 0, 0)
    menu_layout.setSpacing(0)  # No extra gaps

    # === LEFT-SIDE MENU BAR ===
    if window.is_desktop_window:
        left_menubar = RoundedMenuBar(round_left=True)
    else:
        left_menubar = RoundedMenuBar()

    # Start Menu
    if sys.platform == "win32" and window.is_desktop_window:
        start_menu = windows_start_menu.StartMenu(window)
        left_menubar.addMenu(start_menu)

    # File Menu
    file_menu = left_menubar.addMenu("File")

    open_action = QtGui.QAction("Open", window)
    open_action.setShortcut("Ctrl+O")
    open_action.setShortcuts([open_action.shortcut(), "Ctrl+Down", "Ctrl+Shift+Down", "Return", "Enter"])

    file_menu.addAction(open_action)
    open_action.triggered.connect(window.open_selected_items)

    file_menu.addSeparator()

    new_folder_action = QtGui.QAction("New Folder", window)
    new_folder_action.setShortcut("Ctrl+Shift+N")
    new_folder_action.triggered.connect(window.new_folder)
    file_menu.addAction(new_folder_action)
    file_menu.addSeparator()

    get_info_action = QtGui.QAction("Get Info", window)
    get_info_action.setShortcut("Ctrl+I")
    get_info_action.triggered.connect(window.get_info)
    file_menu.addAction(get_info_action)
    file_menu.addSeparator()

    rename_action = QtGui.QAction("Rename", window)
    rename_action.setShortcut("F2")
    file_menu.addAction(rename_action)
    file_menu.addSeparator()
    
    if os.name == 'nt':
        import windows_integration
        map_drive_action = QtGui.QAction("Map Network Drive", window)
        map_drive_action.triggered.connect(windows_integration.map_network_drive)
        unmap_drive_action = QtGui.QAction("Unmap Network Drive", window)
        unmap_drive_action.triggered.connect(windows_integration.unmap_network_drive)

        file_menu.addSeparator()
        file_menu.addAction(map_drive_action)
        file_menu.addAction(unmap_drive_action)
        file_menu.addSeparator()

    if not window.is_desktop_window:
        close_action = QtGui.QAction("Close", window)
        close_action.setShortcut("Ctrl+W")
        close_action.triggered.connect(window.close)
        file_menu.addAction(close_action)
    else:
        logout_action = QtGui.QAction("Log Out", window)
        logout_action.triggered.connect(logout)
        file_menu.addAction(logout_action)

        restart_action = QtGui.QAction("Restart", window)
        restart_action.triggered.connect(restart)
        file_menu.addAction(restart_action)
        
        shutdown_action = QtGui.QAction("Shut Down", window)
        shutdown_action.triggered.connect(shutdown)
        file_menu.addAction(shutdown_action)

    # Edit Menu
    edit_menu = left_menubar.addMenu("Edit")

    undo_action = QtGui.QAction("Undo", window)
    undo_action.setShortcut("Ctrl+Z")
    edit_menu.addAction(undo_action)
    edit_menu.addSeparator()

    cut_action = QtGui.QAction("Cut", window)
    cut_action.setShortcut("Ctrl+X")
    edit_menu.addAction(cut_action)

    copy_action = QtGui.QAction("Copy", window)
    copy_action.setShortcut("Ctrl+C")
    edit_menu.addAction(copy_action)

    window.paste_action = QtGui.QAction("Paste", window)
    window.paste_action.setShortcut("Ctrl+V")
    edit_menu.addAction(window.paste_action)
    edit_menu.addSeparator()

    select_all_action = QtGui.QAction("Select All", window)
    select_all_action.setShortcut("Ctrl+A")
    edit_menu.addAction(select_all_action)

    edit_menu.addSeparator()

    delete_action = QtGui.QAction("Delete", window)
    delete_action.setShortcut("Delete")
    edit_menu.addAction(delete_action)

    move_to_trash_action = QtGui.QAction("Move to Trash", window)
    edit_menu.addAction(move_to_trash_action)

    edit_menu.addSeparator()

    empty_trash_action = QtGui.QAction("Empty Trash", window)
    edit_menu.addAction(empty_trash_action)

    if isinstance(window, QtWidgets.QMainWindow) and hasattr(window, 'selectionChanged'):
        copy_action.triggered.connect(window.copy_selected)
        cut_action.triggered.connect(window.cut_selected)
        window.paste_action.triggered.connect(window.paste_items)
        rename_action.triggered.connect(window.rename_selected)
        delete_action.triggered.connect(window.delete_selected)
        select_all_action.triggered.connect(window.select_all)
        empty_trash_action.triggered.connect(window.empty_trash)
        move_to_trash_action.triggered.connect(window.move_to_trash)

        window.selectionChanged.connect(lambda: open_action.setEnabled(window.has_selected_items()))
        window.selectionChanged.connect(lambda: get_info_action.setEnabled(window.has_selected_items()))
        window.selectionChanged.connect(lambda: cut_action.setEnabled(window.has_selected_items()))
        window.selectionChanged.connect(lambda: copy_action.setEnabled(window.has_selected_items()))
        window.selectionChanged.connect(lambda: delete_action.setEnabled(window.has_selected_items()))
        window.selectionChanged.connect(lambda: rename_action.setEnabled(window.has_selected_items()))
        # window.selectionChanged.connect(lambda: empty_trash_action.setEnabled(window.has_trash_items()))
        window.selectionChanged.connect(lambda: move_to_trash_action.setEnabled(window.has_selected_items()))
        
        open_action.setEnabled(False)
        get_info_action.setEnabled(False)
        cut_action.setEnabled(False)
        copy_action.setEnabled(False)
        window.paste_action.setEnabled(False)
        delete_action.setEnabled(False)
        rename_action.setEnabled(False)

    edit_menu.addSeparator()
    preferences_action = QtGui.QAction("Preferences", window)
    preferences_action.triggered.connect(lambda: PreferencesDialog(window).show())
    edit_menu.addAction(preferences_action)

    # Go menu
    window.go_menu = left_menubar.addMenu("Go")

    if sys.platform == "win32":
        run_action = QtGui.QAction("Run...", window)
        window.go_menu.addAction(run_action)
        run_action.triggered.connect(run_dialog)
        run_action.setShortcut("Meta+R")
        window.go_menu.addSeparator()

    go_up_action = QtGui.QAction("Go Up", window)
    go_up_action.setShortcut("Ctrl+Up")
    window.go_menu.addAction(go_up_action)

    go_up_close_action = QtGui.QAction("Go Up and Close Current", window)
    go_up_close_action.setShortcut("Ctrl+Shift+Up")
    window.go_menu.addAction(go_up_close_action)

    window.go_menu.addSeparator()

    computer_action = QtGui.QAction("Computer", window)
    if not sys.platform == "win32":
        computer_action.setShortcut("Ctrl+Shift+C")
        window.go_menu.addAction(computer_action)

    network_action = QtGui.QAction("Network", window)
    network_action.setShortcut("Ctrl+Shift+N")
    window.go_menu.addAction(network_action)

    devices_action = QtGui.QAction("Devices", window)
    if not sys.platform == "win32":
        devices_action.setShortcut("Ctrl+U")
        window.go_menu.addAction(devices_action)

    applications_action = QtGui.QAction("Applications", window)
    applications_action.setShortcut("Ctrl+Shift+A")
    window.go_menu.addAction(applications_action)

    window.go_menu.addSeparator()

    home_action = QtGui.QAction("Home", window)
    home_action.setShortcut("Ctrl+Shift+H")
    window.go_menu.addAction(home_action)

    documents_action = QtGui.QAction("Documents", window)
    documents_action.setShortcut("Ctrl+Shift+D")
    window.go_menu.addAction(documents_action)

    downloads_action = QtGui.QAction("Downloads", window)
    downloads_action.setShortcut("Ctrl+Shift+L")
    window.go_menu.addAction(downloads_action)

    music_action = QtGui.QAction("Music", window)
    music_action.setShortcut("Ctrl+Shift+M")
    window.go_menu.addAction(music_action)

    pictures_action = QtGui.QAction("Pictures", window)
    pictures_action.setShortcut("Ctrl+Shift+P")
    window.go_menu.addAction(pictures_action)

    videos_action = QtGui.QAction("Videos", window)
    videos_action.setShortcut("Ctrl+Shift+V")
    window.go_menu.addAction(videos_action)

    window.go_menu.addSeparator()

    trash_action = QtGui.QAction("Trash", window)
    trash_action.setShortcut("Ctrl+Shift+T")
    window.go_menu.addAction(trash_action)

    window.go_menu.addSeparator()

    actions = {
        'go_up': go_up_action,
        'go_up_and_close': go_up_close_action,
        'open_computer': computer_action if not sys.platform == "win32" else None,
        'open_network': network_action,
        'open_devices': devices_action,
        'open_applications': applications_action,
        'open_home': home_action,
        'open_documents': documents_action,
        'open_downloads': downloads_action,
        'open_music': music_action,
        'open_pictures': pictures_action,
        'open_videos': videos_action,
        'open_trash': trash_action
    }

    for attr, action in actions.items():
        if action and hasattr(window, attr):
            action.triggered.connect(getattr(window, attr))

    window.go_menu.aboutToShow.connect(lambda: populate_volumes(window))

    # View Menu
    view_menu = left_menubar.addMenu("View")

    if window.__class__.__name__ == "SpatialFilerWindow":
        # Checkbox for "Snap to Grid"
        snap_to_grid_action = QtGui.QAction("Snap to Grid", window)
        snap_to_grid_action.setCheckable(True)
        snap_to_grid_action.setChecked(app.snap_to_grid)
        snap_to_grid_action.triggered.connect(lambda: setattr(app, "snap_to_grid", snap_to_grid_action.isChecked()))
        view_menu.addAction(snap_to_grid_action)
        clean_up_action = QtGui.QAction("Clean Up", window)
        clean_up_action.triggered.connect(window.clean_up)
        view_menu.addAction(clean_up_action)
        view_menu.addSeparator()
        sort_menu = QtWidgets.QMenu("Sort", window)
        view_menu.addMenu(sort_menu)
        sort_name = QtGui.QAction("By Name", window)
        sort_name.triggered.connect(lambda: window.sort_items("name"))
        sort_menu.addAction(sort_name)
        sort_date = QtGui.QAction("By Date", window)
        sort_date.triggered.connect(lambda: window.sort_items("date"))
        sort_menu.addAction(sort_date)
        sort_size = QtGui.QAction("By Size", window)
        sort_size.triggered.connect(lambda: window.sort_items("size"))
        sort_menu.addAction(sort_size)
        sort_type = QtGui.QAction("By Type", window)
        sort_type.triggered.connect(lambda: window.sort_items("type"))
        sort_menu.addAction(sort_type)

    # Color menu
    color_menu = ColorMenu("Color", window)
    left_menubar.addMenu(color_menu)

    # Help menu
    help_menu = left_menubar.addMenu("Help")
    about_action = QtGui.QAction("About", window)
    about_action.triggered.connect(window.show_about)
    help_menu.addAction(about_action)
    help_menu.addSeparator()

    if "log_console" in sys.modules:
        app = QtWidgets.QApplication.instance()
        app.log_console.add_menu_items(help_menu, window)

    # Apparently maximum and minimum work exactly the opposite of what one would expect
    left_menubar.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Preferred)
    menu_layout.addWidget(left_menubar)

    # === RIGHT-SIDE MENU BAR ===
    if window.is_desktop_window:
        right_menubar = RoundedMenuBar(round_right=True)
        
        clock_menu = QtWidgets.QMenu(window)
        clock_menu.setTitle(time.strftime("%H:%M"))
        right_menubar.addMenu(clock_menu)

        clock_timer = QtCore.QTimer(window)
        clock_timer.timeout.connect(lambda: clock_menu.setTitle(time.strftime("%H:%M")))
        clock_timer.start(1000)
        date_action = QtGui.QAction(time.strftime("%A, %B %d, %Y"), window)
        date_action.setEnabled(False)
        clock_menu.addAction(date_action)
        clock_menu.aboutToShow.connect(lambda: date_action.setText(time.strftime("%A, %B %d, %Y")))

        # "Windows" menu for Windows users showing all windows
        if sys.platform == "win32":

            import windows_volume
            volume_menu = windows_volume.VolumeMenu(window)
            right_menubar.addMenu(volume_menu)

            windows_menu = QtWidgets.QMenu(window)
            windows_menu.setTitle("Windows   ") # FIXME: Add a space to make the menu wider in a proper way
            windows_menu.setStyleSheet("QMenuBar { padding-right: 10px; }")
            right_menubar.addMenu(windows_menu)
            # When opening the Windows menu, populate it with all open windows
            windows_menu.aboutToShow.connect(lambda: win32_populate_windows_menu(window, windows_menu))

        right_menubar.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Preferred)
        menu_layout.addWidget(right_menubar)

    # Set the custom menu widget
    window.setMenuWidget(menu_widget)

def populate_volumes(window):
    """
    Populate the volumes list with the available drives using QtCore.QStorageInfo.
    Clears old entries before repopulating.
    """
    for action in window.go_menu.actions():
        if hasattr(action, "is_volume") and action.is_volume:
            window.go_menu.removeAction(action)
    print("Populating volumes")
    drives = QtCore.QStorageInfo.mountedVolumes()
    # Remove all that start with anything but /mnt, /run/media, /media, /Volumes, /Volumes.localized, /net
    if not sys.platform == "win32":
        drives = [drive for drive in drives if os.path.commonprefix(["/mnt", "/run/media", "/media", "/Volumes", "/Volumes.localized", "/net"]).startswith(drive.rootPath())]
    else:
        drives = [drive for drive in drives if drive.isValid() and drive.isReady()]
    for drive in drives:
        drive_action = QtGui.QAction(drive.displayName(), window)
        drive_action.triggered.connect(lambda checked, d=drive.rootPath(): window.open_drive(d))
        drive_action.is_volume = True
        window.go_menu.addAction(drive_action)

def show_current_time(window):
    """
    Show a message box displaying the current time.
    """
    current_time = QtCore.QTime.currentTime().toString()
    QtWidgets.QMessageBox.information(window, "Current Time", f"The current time is: {current_time}")

def run_dialog():
    """
    Open the Windows Run dialog.
    """
    if sys.platform != "win32":
        return
    from win32com.client import Dispatch
    shell = Dispatch("WScript.Shell")
    shell.Run("rundll32.exe shell32.dll,#61")

def logout():
    message_box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Question, "Log Out", "Are you sure you want to log out?\nUnsaved work will be lost.", QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
    message_box.setIcon(QtWidgets.QMessageBox.Icon.Question)
    message_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
    if message_box.exec() == QtWidgets.QMessageBox.StandardButton.Yes:
        if sys.platform == "win32":
            try:
                result = subprocess.run(["shutdown", "/l"], capture_output=True)
                if stderr := result.stderr.decode("utf-8"):
                    QtWidgets.QMessageBox.critical(None, "Error", f"Failed to log out: {stderr}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(None, "Error", f"Failed to log out: {e}")
        else:
            try:
                result = subprocess.run(["pkill", "-u", os.getlogin()], capture_output=True)
                if stderr := result.stderr.decode("utf-8"):
                    QtWidgets.QMessageBox.critical(None, "Error", f"Failed to log out: {stderr}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(None, "Error", f"Failed to log out: {e}")

def restart():
    message_box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Question, "Restart", "Are you sure you want to restart the computer?\nUnsaved work will be lost.", QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
    message_box.setIcon(QtWidgets.QMessageBox.Icon.Question)
    message_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
    if message_box.exec() == QtWidgets.QMessageBox.StandardButton.Yes:
        if sys.platform == "win32":
            try:
                result = subprocess.run(["shutdown", "/r", "/t", "0"], capture_output=True)
                if stderr := result.stderr.decode("utf-8"):
                    QtWidgets.QMessageBox.critical(None, "Error", f"Failed to restart: {stderr}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(None, "Error", f"Failed to restart: {e}")
        else:
            try:
                result = subprocess.run(["reboot"], capture_output=True)
                if stderr := result.stderr.decode("utf-8"):
                    QtWidgets.QMessageBox.critical(None, "Error", f"Failed to restart: {stderr}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(None, "Error", f"Failed to restart: {e}")


def shutdown():
    message_box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Question, "Shut Down", "Are you sure you want to shut down the computer?\nUnsaved work will be lost.", QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
    message_box.setIcon(QtWidgets.QMessageBox.Icon.Question)
    message_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
    if message_box.exec() == QtWidgets.QMessageBox.StandardButton.Yes:
        if sys.platform == "win32":
            try:
                result = subprocess.run(["shutdown", "/s", "/t", "0"], capture_output=True)
                if stderr := result.stderr.decode("utf-8"):
                    QtWidgets.QMessageBox.critical(None, "Error", f"Failed to shut down: {stderr}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(None, "Error", f"Failed to shut down: {e}")
        else:
            try:
                result = subprocess.run(["shutdown", "-h", "now"], capture_output=True)
                if stderr := result.stderr.decode("utf-8"):
                    QtWidgets.QMessageBox.critical(None, "Error", f"Failed to shut down: {stderr}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(None, "Error", f"Failed to shut down: {e}")

def win32_populate_windows_menu(window, windows_menu):
    """Safely populates the Windows menu with open windows, preventing crashes and infinite loops."""
    try:
        windows_menu.clear()

        windows = []
        def window_enum_handler(hwnd, windows):
            try:
                if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                    windows.append((hwnd, win32gui.GetWindowText(hwnd)))
            except Exception as e:
                print(f"Error enumerating window: {e}")

        win32gui.EnumWindows(window_enum_handler, windows)

        if not windows:
            action = QtGui.QAction("No Windows Found", window)
            action.setEnabled(False)
            windows_menu.addAction(action)
            return

        for hwnd, title in windows:
            if not title.strip() or title.lower() == "desktop":
                continue  # Skip invalid or empty titles

            clean_title = re.sub(r'^[\s\-\|]+|[\s\-\|]+$', '', title)
            action = QtGui.QAction(clean_title, window)
            action.triggered.connect(lambda checked, h=hwnd: win32_restore_window(h))

            # Try to get the window icon safely
            try:
                icon = win32_get_icon_for_hwnd(hwnd)
                if not icon.isNull():
                    action.setIcon(icon)
            except Exception:
                pass  # Ignore icon failures

            windows_menu.addAction(action)

        # Add "Show Desktop" action
        windows_menu.addSeparator()
        show_desktop_action = QtGui.QAction("Show Desktop", window)
        show_desktop_action.triggered.connect(win32_minimize_all_windows)
        windows_menu.addAction(show_desktop_action)

    except Exception as e:
        print(f"Error populating Windows menu: {e}")

def win32_restore_window(hwnd):
    """Restores and brings a window to the front."""
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception as e:
        print(f"Error restoring window: {e}")

def win32_minimize_all_windows():
    """Minimizes all visible windows except the desktop."""
    try:
        def window_enum_handler(hwnd, windows):
            try:
                if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                    windows.append(hwnd)
            except Exception:
                pass

        windows = []
        win32gui.EnumWindows(window_enum_handler, windows)

        for hwnd in windows:
            if win32gui.GetWindowText(hwnd).lower() != "desktop":
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    except Exception as e:
        print(f"Error minimizing windows: {e}")

def win32_get_icon_for_hwnd(hwnd, size=16):
    """Retrieves the window icon safely, returning a default if none exists."""
    try:
        hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_SMALL, 0)
        if not hicon:
            hicon = win32gui.GetClassLong(hwnd, win32con.GCL_HICON)

        if not hicon:
            return QtGui.QIcon()  # Return empty icon

        hdc_screen = win32gui.GetDC(0)
        hdc = win32ui.CreateDCFromHandle(hdc_screen)
        mem_dc = hdc.CreateCompatibleDC()
        hbmp = win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc, size, size)
        mem_dc.SelectObject(hbmp)

        win32gui.DrawIconEx(mem_dc.GetSafeHdc(), 0, 0, hicon, size, size, 0, None, win32con.DI_NORMAL)
        bmpinfo = hbmp.GetInfo()
        bmp_bytes = hbmp.GetBitmapBits(True)

        qt_image = QtGui.QImage(bmp_bytes, bmpinfo["bmWidth"], bmpinfo["bmHeight"], bmpinfo["bmWidthBytes"], QtGui.QImage.Format.Format_ARGB32)
        pixmap = QtGui.QPixmap.fromImage(qt_image)

        mem_dc.DeleteDC()
        win32gui.ReleaseDC(0, hdc_screen)
        win32gui.DeleteObject(hbmp.GetHandle())

        return QtGui.QIcon(pixmap)
    except Exception as e:
        print(f"Error retrieving window icon: {e}")
        return QtGui.QIcon()  # Return an empty icon to avoid crashes