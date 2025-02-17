#!/usr/bin/env python3
"""
Global hotkeys for Windows
"""

import ctypes, win32con, os
from ctypes import byref, wintypes
from win32com.client import Dispatch

from PyQt6 import QtWidgets

from menus import shutdown, win32_minimize_all_windows # FIXME: This import does not feel clean here


import subprocess

class HotKeyManager:
    def __init__(self, desktop_window=None):
        if desktop_window:
            self.desktop_window_hwnd = int(desktop_window.winId())
        self.user32 = ctypes.windll.user32
        self.VK_R = 0x52
        self.VK_D = 0x44
        self.VK_PrintScreen = 0x2C

        # Define hotkeys and their modifiers
        self.hotkeys = {
            'Alt+F4': (win32con.VK_F4, win32con.MOD_ALT),
            'Meta+R' : (self.VK_R, win32con.MOD_WIN),
            'Meta+D' : (self.VK_D, win32con.MOD_WIN),
            'PrintScreen': (self.VK_PrintScreen, 0)
        }

        # Map each hotkey to its handler function
        self.actions = {
            'Alt+F4': self.handle_alt_f4,
            'Meta+R' : self.handle_win_r,
            'Meta+D' : self.handle_win_d,
            'PrintScreen': self.handle_print_screen
        }

        # We'll store mappings of hotkey id to key name to ease reverse lookup
        self.id_to_key = {}

    def handle_alt_f4(self):
        print("Alt+F4 pressed")
        hwnd = self.user32.GetForegroundWindow()
        print("Foreground window:", hwnd)
        is_shift_pressed = self.user32.GetKeyState(win32con.VK_SHIFT) & 0x8000
        if self.desktop_window_hwnd and not is_shift_pressed:
            if hwnd == self.desktop_window_hwnd:
                print("Desktop window is active, not closing")
                shutdown()
                return
        self.user32.PostMessageA(hwnd, win32con.WM_CLOSE, 0, 0)

    def handle_win_r(self):
        print("Meta+R pressed")
        Dispatch("WScript.Shell").Run("rundll32.exe shell32.dll,#61")

    def handle_win_d(self):
        print("Meta+D pressed")
        win32_minimize_all_windows()

    def handle_print_screen(self):
        print("PrintScreen pressed")
        # Run snippingtool.exe and show error box if it fails
        result = os.system("snippingtool.exe")
        if result != 0:
            try:
                result = subprocess.run(["powershell", "Get-AppxPackage -allusers Microsoft.ScreenSketch | Foreach {Add-AppxPackage -DisableDevelopmentMode -Register \"$($_.InstallLocation)\\AppxManifest.xml\"}"], check=True)
            except subprocess.CalledProcessError as e:
                QtWidgets.QMessageBox.critical(None, "Error", f"An error occurred while executing the command: {e.cmd}")
            if result.returncode == 0:
                result = os.system("snippingtool.exe")
                if result != 0:
                    QtWidgets.QMessageBox.critical(None, "Error", "An error occurred while executing the command snippingtool.exe")

    def register_hotkeys(self):
        print("Registering hotkeys...")
        # Iterate over hotkeys and register them with user32
        for id, key in enumerate(self.hotkeys, start=1):
            vk, mod = self.hotkeys[key]
            self.id_to_key[id] = key  # map id to key name
            if not self.user32.RegisterHotKey(None, id, mod, vk):
                print(f"Unable to register hotkey for {key}")
            else:
                print(f"Registered hotkey for {key}")

    def unregister_hotkeys(self):
        print("Unregistering hotkeys...")
        # Unregister all hotkeys using the stored IDs
        for id in self.id_to_key:
            self.user32.UnregisterHotKey(None, id)
            print(f"Unregistered hotkey id {id}")

    def run(self):
        """
        Runs the hotkey manager: registers hotkeys and processes messages in a loop.
        """
        # FIXME: Find a way that is not polling to wait for messages and is less CPU intensive
        self.register_hotkeys()
        try:
            m = wintypes.MSG()
            while self.user32.GetMessageA(byref(m), None, 0, 0):
                # Check if the message is a hotkey message.
                if m.message == win32con.WM_HOTKEY:
                    hotkey_id = m.wParam
                    key = self.id_to_key.get(hotkey_id)
                    if key and key in self.actions:
                        action = self.actions[key]
                        action()
                self.user32.TranslateMessage(byref(m))
                self.user32.DispatchMessageA(byref(m))
        finally:
            self.unregister_hotkeys()


if __name__ == '__main__':
    manager = HotKeyManager()
    manager.run()
