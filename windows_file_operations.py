#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
This module provides functions to perform file operations such as copy, move, delete, and rename using Windows Shell API.
It is intended for use in file manager applications, supporting operations like drag and drop.

Functions:
    copy_files_with_dialog(src_list, dst): Copies files or directories to a destination with a progress dialog.
    move_files_with_dialog(src_list, dst): Moves files or directories to a destination with a progress dialog.
    rename_file_with_dialog(src, dst): Renames a file or directory with a progress dialog.
    delete_files_with_dialog(src_list): Deletes files or directories with a progress dialog.
    move_to_recycle_bin(src_list): Moves files or directories to the recycle bin with a confirmation dialog.

Usage:
    Import the module and call the functions with appropriate parameters.

Example:
    import windows_file_operations

    src_paths = [r"C:\path\to\source1", r"C:\path\to\source2"]
    dst_path = r"C:\path\to\destination"
    new_name = r"C:\path\to\new_name"

    windows_file_operations.copy_files_with_dialog(src_paths, dst_path)
    windows_file_operations.move_files_with_dialog(src_paths, dst_path)
    windows_file_operations.rename_file_with_dialog(src_paths[0], new_name)
    windows_file_operations.delete_files_with_dialog(src_paths)
    windows_file_operations.move_to_recycle_bin(src_paths)
"""

import os
from win32com.shell import shell, shellcon

# Constants for SHFileOperation flags
FO_COPY = shellcon.FO_COPY
FO_DELETE = shellcon.FO_DELETE
FO_MOVE = shellcon.FO_MOVE
FO_RENAME = shellcon.FO_RENAME

FOF_MULTIDESTFILES = shellcon.FOF_MULTIDESTFILES
FOF_CONFIRMMOUSE = shellcon.FOF_CONFIRMMOUSE
FOF_SILENT = shellcon.FOF_SILENT
FOF_RENAMEONCOLLISION = shellcon.FOF_RENAMEONCOLLISION
FOF_NOCONFIRMATION = shellcon.FOF_NOCONFIRMATION
FOF_WANTMAPPINGHANDLE = shellcon.FOF_WANTMAPPINGHANDLE
FOF_ALLOWUNDO = shellcon.FOF_ALLOWUNDO
FOF_FILESONLY = shellcon.FOF_FILESONLY
FOF_SIMPLEPROGRESS = shellcon.FOF_SIMPLEPROGRESS
FOF_NOCONFIRMMKDIR = shellcon.FOF_NOCONFIRMMKDIR
FOF_NOERRORUI = shellcon.FOF_NOERRORUI
FOF_NOCOPYSECURITYATTRIBS = shellcon.FOF_NOCOPYSECURITYATTRIBS
FOF_NO_CONNECTED_ELEMENTS = shellcon.FOF_NO_CONNECTED_ELEMENTS
FOF_WANTNUKEWARNING = shellcon.FOF_WANTNUKEWARNING
FOF_NORECURSEREPARSE = shellcon.FOF_NORECURSEREPARSE

def convert_path_with_slashes_to_backslashes(path):
    """
    Converts a path with slashes to backslashes.

    Args:
        path (str): Path with slashes.

    Returns:
        str: Path with backslashes.
    """
    return path.replace('/', '\\')

def copy_files_with_dialog(src_list, dst):
    """
    Copies files or directories to a destination with a progress dialog.

    Args:
        src_list (list): List of source paths (files and/or directories) to be copied.
        dst (str): Destination path.

    Raises:
        OSError: If the SHFileOperation fails.
    """
    src_list = [convert_path_with_slashes_to_backslashes(src) for src in src_list]
    dst = convert_path_with_slashes_to_backslashes(dst)
    src = '\0'.join(src_list) + '\0'
    result = shell.SHFileOperation(
        (0, FO_COPY, src, dst, FOF_ALLOWUNDO | FOF_WANTNUKEWARNING | FOF_SIMPLEPROGRESS, None, None)
    )
    fAnyOperationsAborted = result[1]
    if result[0] != 0 and not fAnyOperationsAborted:
        raise OSError(f"SHFileOperation failed with error code: {result[0]}")

def move_files_with_dialog(src_list, dst):
    """
    Moves files or directories to a destination with a progress dialog.

    Args:
        src_list (list): List of source paths (files and/or directories) to be moved.
        dst (str): Destination path.

    Raises:
        OSError: If the SHFileOperation fails.
    """
    src_list = [convert_path_with_slashes_to_backslashes(src) for src in src_list]
    dst = convert_path_with_slashes_to_backslashes(dst)
    src = '\0'.join(src_list) + '\0'
    result = shell.SHFileOperation(
        (0, FO_MOVE, src, dst, FOF_ALLOWUNDO | FOF_WANTNUKEWARNING | FOF_SIMPLEPROGRESS, None, None)
    )
    fAnyOperationsAborted = result[1]
    if result[0] != 0 and not fAnyOperationsAborted:
        raise OSError(f"SHFileOperation failed with error code: {result[0]}")

def rename_file_with_dialog(src, dst):
    """
    Renames a file or directory with a progress dialog.

    Args:
        src (str): Source path (file or directory) to be renamed.
        dst (str): New name for the file or directory.

    Raises:
        OSError: If the SHFileOperation fails.
    """
    src = convert_path_with_slashes_to_backslashes(src)
    dst = convert_path_with_slashes_to_backslashes(dst)
    result = shell.SHFileOperation(
        (0, FO_RENAME, src + '\0', dst + '\0', FOF_ALLOWUNDO | FOF_WANTNUKEWARNING | FOF_SIMPLEPROGRESS, None, None)
    )
    fAnyOperationsAborted = result[1]
    if result[0] != 0 and not fAnyOperationsAborted:
        raise OSError(f"SHFileOperation failed with error code: {result[0]}")

def delete_files_with_dialog(src_list):
    """
    Deletes files or directories with a progress dialog.

    Args:
        src_list (list): List of source paths (files and/or directories) to be deleted.

    Raises:
        OSError: If the SHFileOperation fails.
    """
    src = [convert_path_with_slashes_to_backslashes(src) for src in src_list]
    src = '\0'.join(src_list) + '\0'
    result = shell.SHFileOperation(
        (0, FO_DELETE, src, None, FOF_ALLOWUNDO | FOF_WANTNUKEWARNING | FOF_SIMPLEPROGRESS, None, None)
    )
    fAnyOperationsAborted = result[1]
    if result[0] != 0 and not fAnyOperationsAborted:
        raise OSError(f"SHFileOperation failed with error code: {result[0]}")

def move_to_recycle_bin(src_list):
    """
    Moves files or directories to the recycle bin with a confirmation dialog.

    Args:
        src_list (list): List of source paths (files and/or directories) to be moved to the recycle bin.

    Raises:
        OSError: If the SHFileOperation fails.
    """
    src_list = [convert_path_with_slashes_to_backslashes(src) for src in src_list]
    src = '\0'.join(src_list) + '\0'
    result = shell.SHFileOperation(
        (0, FO_DELETE, src, None, FOF_ALLOWUNDO, None, None)
    )
    fAnyOperationsAborted = result[1]
    if result[0] != 0 and not fAnyOperationsAborted:
        raise OSError(f"SHFileOperation failed with error code: {result[0]}")
    
def create_shortcuts_with_dialog(src_list, dst):
    """
    Creates shortcuts to files or directories with a progress dialog.

    Args:
        src_list (list): List of source paths (files and/or directories) to create shortcuts for.
        dst (str): Destination path for the shortcuts.

    Raises:
        OSError: If the SHFileOperation fails.
    """
    src_list = [convert_path_with_slashes_to_backslashes(src) for src in src_list]
    dst = convert_path_with_slashes_to_backslashes(dst)
    src = '\0'.join(src_list) + '\0'
    result = shell.SHFileOperation(
        (0, FO_COPY, src, dst, FOF_ALLOWUNDO | FOF_WANTNUKEWARNING | FOF_SIMPLEPROGRESS, None, None)
    )
    fAnyOperationsAborted = result[1]
    if result[0] != 0 and not fAnyOperationsAborted:
        raise OSError(f"SHFileOperation failed with error code: {result[0]}")

if __name__ == "__main__":
    # Example usage of the functions
    src_paths = [r"C:\path\to\source1", r"C:\path\to\source2"]
    dst_path = r"C:\path\to\destination"
    new_name = r"C:\path\to\new_name"

    # Uncomment the desired operation to test
    # copy_files_with_dialog(src_paths, dst_path)
    # move_files_with_dialog(src_paths, dst_path)
    # rename_file_with_dialog(src_paths[0], new_name)
    # delete_files_with_dialog(src_paths)
    # move_to_recycle_bin(src_paths)