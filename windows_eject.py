#!/usr/bin/env python3

"""Ejecting drives on Windows using the DeviceIoControl API"""

import ctypes
from ctypes import wintypes
from abc import ABC, abstractmethod

# Windows API constants
GENERIC_READ  = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ  = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3

IOCTL_STORAGE_EJECT_MEDIA = 0x2D4808

# Load kernel32 functions using ctypes
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

CreateFile = kernel32.CreateFileW
CreateFile.argtypes = [
    wintypes.LPCWSTR,  # lpFileName
    wintypes.DWORD,    # dwDesiredAccess
    wintypes.DWORD,    # dwShareMode
    wintypes.LPVOID,   # lpSecurityAttributes (can be None)
    wintypes.DWORD,    # dwCreationDisposition
    wintypes.DWORD,    # dwFlagsAndAttributes
    wintypes.HANDLE    # hTemplateFile (can be None)
]
CreateFile.restype = wintypes.HANDLE

DeviceIoControl = kernel32.DeviceIoControl
DeviceIoControl.argtypes = [
    wintypes.HANDLE,   # hDevice
    wintypes.DWORD,    # dwIoControlCode
    wintypes.LPVOID,   # lpInBuffer
    wintypes.DWORD,    # nInBufferSize
    wintypes.LPVOID,   # lpOutBuffer
    wintypes.DWORD,    # nOutBufferSize
    ctypes.POINTER(wintypes.DWORD),  # lpBytesReturned
    wintypes.LPVOID    # lpOverlapped (can be None)
]
DeviceIoControl.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


class Ejector(ABC):
    """
    Abstract base class for drive ejectors.
    """

    @abstractmethod
    def eject_drive(self, drive_letter: str) -> bool:
        """
        Ejects a drive given its drive letter.
        Returns True if the ejection was successful, False otherwise.
        """
        pass


class WindowsEjector(Ejector):
    """
    Concrete implementation for ejecting drives on Windows.
    """

    def eject_drive(self, drive_letter: str) -> bool:
        """
        Eject drive using Windows DeviceIoControl API.
        drive_letter: The drive letter (e.g., 'E') to be ejected.
        """
        print("Ejecting drive", drive_letter)
        # Construct device path. Note that the device path should not include the trailing backslash.
        device_path = f"\\\\.\\{drive_letter}:"
        handle = CreateFile(
            device_path,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None
        )

        # Check if the handle is valid.
        if handle == wintypes.HANDLE(-1).value:
            # Failed to open handle
            return False

        bytes_returned = wintypes.DWORD(0)
        success = DeviceIoControl(
            handle,
            IOCTL_STORAGE_EJECT_MEDIA,
            None,
            0,
            None,
            0,
            ctypes.byref(bytes_returned),
            None
        )
        CloseHandle(handle)
        return bool(success)


if __name__ == "__main__":
    if WindowsEjector().eject_drive("E"):
        print(f"Ejected successfully!")
    else:
        print(f"Failed to eject.")
