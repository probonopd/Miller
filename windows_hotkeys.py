#!/usr/bin/env python3
"""
Global hotkeys for Windows refactored into a class-based design
"""

import ctypes
import win32con
from ctypes import byref, wintypes
from win32com.client import Dispatch

class HotKeyManager:
    def __init__(self, desktop_window_hwnd=None):
        self.desktop_window_hwnd = desktop_window_hwnd
        self.user32 = ctypes.windll.user32
        self.VK_R = 0x52

        # Define hotkeys and their modifiers
        self.hotkeys = {
            'alt_f4': (win32con.VK_F4, win32con.MOD_ALT),
            'win_r' : (self.VK_R, win32con.MOD_WIN)
        }

        # Map each hotkey to its handler function
        self.actions = {
            'alt_f4': self.handle_alt_f4,
            'win_r' : self.handle_win_r
        }

        # We'll store mappings of hotkey id to key name to ease reverse lookup
        self.id_to_key = {}

    def handle_alt_f4(self):
        print("Alt+F4 pressed")
        hwnd = self.user32.GetForegroundWindow()
        print("Foreground window:", hwnd)
        if self.desktop_window_hwnd:
            if hwnd == self.desktop_window_hwnd:
                print("Desktop window is active, not closing")
                return
        """buf = ctypes.create_string_buffer(512)
        self.user32.GetWindowTextA(hwnd, buf, len(buf))
        print(buf.value)
        if buf.value != b"Desktop":"""
        self.user32.PostMessageA(hwnd, win32con.WM_CLOSE, 0, 0)

    def handle_win_r(self):
        print("Win+R pressed")
        Dispatch("WScript.Shell").Run("rundll32.exe shell32.dll,#61")

    def register_hotkeys(self):
        print("Registering hotkeys...")
        # Iterate over hotkeys and register them with user32
        for id, key in enumerate(self.hotkeys, start=1):
            vk, mod = self.hotkeys[key]
            self.id_to_key[id] = key  # map id to key name
            print(f"Registering {key}: id {id}, vk {vk}, mod {mod}")
            if not self.user32.RegisterHotKey(None, id, mod, vk):
                print(f"Unable to register hotkey for {key}")

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
