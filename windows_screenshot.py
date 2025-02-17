#!/usr/bin/env python3

import io

import win32gui, win32ui, win32con, win32api, win32clipboard

from PIL import Image

def screenshot_to_clipboard():
    # Get the desktop window handle
    hdesktop = win32gui.GetDesktopWindow()
    
    # Get screen dimensions
    width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
    height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
    left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
    top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)

    # Create a device context
    desktop_dc = win32gui.GetWindowDC(hdesktop)
    img_dc = win32ui.CreateDCFromHandle(desktop_dc)
    mem_dc = img_dc.CreateCompatibleDC()

    # Create a bitmap
    screenshot = win32ui.CreateBitmap()
    screenshot.CreateCompatibleBitmap(img_dc, width, height)
    mem_dc.SelectObject(screenshot)

    # Copy screen into memory
    mem_dc.BitBlt((0, 0), (width, height), img_dc, (left, top), win32con.SRCCOPY)

    # Save bitmap to memory
    bmpinfo = screenshot.GetInfo()
    bmpstr = screenshot.GetBitmapBits(True)

    # Convert bitmap to PIL image
    img = Image.frombuffer("RGB", (bmpinfo["bmWidth"], bmpinfo["bmHeight"]), bmpstr, "raw", "BGRX", 0, 1)

    # Convert image to DIB format for clipboard
    output = io.BytesIO()
    img.convert("RGB").save(output, format="BMP")
    bmp_data = output.getvalue()[14:]  # Strip BMP header

    # Open clipboard and set the image data
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32con.CF_DIB, bmp_data)
    win32clipboard.CloseClipboard()

    print("Screenshot copied to clipboard!")

    # Cleanup
    mem_dc.DeleteDC()
    win32gui.DeleteObject(screenshot.GetHandle())

if __name__ == "__main__":
    screenshot_to_clipboard()
