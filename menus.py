#!/usr/bin/env python3

"""
Menu creation module with a custom menu bar.

This module provides functions to create the main application menu bar using setMenuWidget(),
allowing the "Time" menu to be positioned on the right side.
"""

import os, sys, subprocess, time
from PyQt6 import QtGui, QtCore, QtWidgets

if sys.platform == "win32":
    import win32gui, win32con # For managing windows
    import window_start_menu

def create_menus(window):
    """
    Create the main application menu bar using setMenuWidget(),
    keeping all existing actions, separators, and functionality.
    """

    # Create a custom QWidget to replace the default menu bar
    menu_widget = QtWidgets.QWidget()
    menu_layout = QtWidgets.QHBoxLayout(menu_widget)  # Use horizontal layout

    # Ensure no extra spacing around layout
    menu_layout.setContentsMargins(0, 0, 0, 0)
    menu_layout.setSpacing(0)  # No extra gaps

    # === LEFT-SIDE MENU BAR ===
    left_menubar = QtWidgets.QMenuBar()

    # Start Menu
    if sys.platform == "win32":
        start_menu = window_start_menu.StartMenu(window)
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

    delete_action = QtGui.QAction("Delete", window)
    delete_action.setShortcut("Delete")
    edit_menu.addAction(delete_action)

    select_all_action = QtGui.QAction("Select All", window)
    select_all_action.setShortcut("Ctrl+A")
    edit_menu.addAction(select_all_action)

    empty_trash_action = QtGui.QAction("Empty Trash", window)
    empty_trash_action.setEnabled(False)
    edit_menu.addAction(empty_trash_action)

    move_to_trash_action = QtGui.QAction("Move to Trash", window)
    move_to_trash_action.setEnabled(False)
    edit_menu.addAction(move_to_trash_action)

    if isinstance(window, QtWidgets.QMainWindow) and hasattr(window, 'selectionChanged'):
        copy_action.triggered.connect(window.copy_selected)
        cut_action.triggered.connect(window.cut_selected)
        window.paste_action.triggered.connect(window.paste_items)
        delete_action.triggered.connect(window.delete_selected)
        select_all_action.triggered.connect(window.select_all)
        empty_trash_action.triggered.connect(window.empty_trash)
        move_to_trash_action.triggered.connect(window.move_to_trash)

        window.selectionChanged.connect(lambda: open_action.setEnabled(window.has_selected_items()))
        window.selectionChanged.connect(lambda: get_info_action.setEnabled(window.has_selected_items()))
        window.selectionChanged.connect(lambda: cut_action.setEnabled(window.has_selected_items()))
        window.selectionChanged.connect(lambda: copy_action.setEnabled(window.has_selected_items()))
        window.selectionChanged.connect(lambda: delete_action.setEnabled(window.has_selected_items()))
        window.selectionChanged.connect(lambda: empty_trash_action.setEnabled(window.has_trash_items()))
        window.selectionChanged.connect(lambda: move_to_trash_action.setEnabled(window.has_selected_items()))
        
        open_action.setEnabled(False)
        get_info_action.setEnabled(False)
        cut_action.setEnabled(False)
        copy_action.setEnabled(False)
        window.paste_action.setEnabled(False)
        delete_action.setEnabled(False)

    # Go menu
    window.go_menu = left_menubar.addMenu("Go")

    if sys.platform == "win32":
        run_action = QtGui.QAction("Run...", window)
        window.go_menu.addAction(run_action)
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

    if isinstance(window, QtWidgets.QMainWindow):
        go_up_action.triggered.connect(window.go_up)
        go_up_close_action.triggered.connect(window.go_up_and_close)
        if not sys.platform == "win32":
            computer_action.triggered.connect(window.open_computer)
        network_action.triggered.connect(window.open_network)
        devices_action.triggered.connect(window.open_devices)
        applications_action.triggered.connect(window.open_applications)
        home_action.triggered.connect(window.open_home)
        documents_action.triggered.connect(window.open_documents)
        downloads_action.triggered.connect(window.open_downloads)
        music_action.triggered.connect(window.open_music)
        pictures_action.triggered.connect(window.open_pictures)
        videos_action.triggered.connect(window.open_videos)
        trash_action.triggered.connect(window.open_trash)

    window.go_menu.aboutToShow.connect(lambda: populate_volumes(window))

    # View Menu
    view_menu = left_menubar.addMenu("View")

    if window.__class__.__name__ == "SpatialFilerWindow":
        align_action = QtGui.QAction("Align to Grid")
        align_action.setShortcut("Ctrl+G")
        align_action.triggered.connect(window.align_to_grid)
        view_menu.addAction(align_action)
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
        right_menubar = QtWidgets.QMenuBar()
        
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
            windows_menu = QtWidgets.QMenu(window)
            windows_menu.setTitle("Windows")
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

    drives = QtCore.QStorageInfo.mountedVolumes()
    # Remove all that start with anything but /mnt, /run/media, /media, /Volumes, /Volumes.localized, /net
    drives = [drive for drive in drives if os.path.commonprefix(["/mnt", "/run/media", "/media", "/Volumes", "/Volumes.localized", "/net"]).startswith(drive.rootPath())]
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
    # Clear the menu
    windows_menu.clear()
    # Use the Windows API to get a list of all open windows
    def window_enum_handler(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            windows.append((hwnd, win32gui.GetWindowText(hwnd)))
        return True
    windows = []
    win32gui.EnumWindows(window_enum_handler, windows)
    windows_menu.setTitle("Windows")
    for hwnd, title in windows:
        if title != "Desktop":
            action = windows_menu.addAction(title)
            action.triggered.connect(lambda checked, hwnd=hwnd: win32_restore_window(hwnd))
            windows_menu.addAction(action)
    windows_menu.addSeparator()
    # "Show Desktop" action
    show_desktop_action = windows_menu.addAction("Show Desktop")
    show_desktop_action.triggered.connect(win32_minimize_all_windows)

def win32_minimize_all_windows():
    def window_enum_handler(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            windows.append((hwnd, win32gui.GetWindowText(hwnd)))
        return True
    windows = []
    win32gui.EnumWindows(window_enum_handler, windows)
    for hwnd, title in windows:
        # Minimize all windows except the desktop window (called "Desktop")
        if title != "Desktop":
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

def win32_restore_window(hwnd):
    # If minimized, restore the window
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    win32gui.SetForegroundWindow(hwnd)
