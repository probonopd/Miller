#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
"""

import os
import subprocess
import dbus

def get_desktop_environment():
    desktop_session = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION")
    if not desktop_session:
        return None
    desktop_session = desktop_session.lower()
    if "gnome" in desktop_session:
        return "gnome"
    if "cinnamon" in desktop_session:
        return "cinnamon"
    if "mate" in desktop_session:
        return "mate"
    if "xfce" in desktop_session:
        return "xfce"
    if "kde" in desktop_session:
        return "kde"
    return None

def gnome_file_operation(method, src_list, dst=None):
    bus = dbus.SessionBus()
    nautilus = bus.get_object('org.gnome.Nautilus', '/org/gnome/Nautilus')
    iface = dbus.Interface(nautilus, dbus_interface='org.gnome.Nautilus.FileOperations')
    
    src_uris = [f'file://{src}' for src in src_list]
    if dst:
        dst_uri = f'file://{dst}'
    else:
        dst_uri = None

    if method == 'CopyURIs':
        iface.CopyURIs(src_uris, dst_uri)
    elif method == 'MoveURIs':
        iface.MoveURIs(src_uris, dst_uri)
    elif method == 'Trash':
        iface.Trash(src_uris)
    elif method == 'Delete':
        iface.Delete(src_uris)
    elif method == 'Rename':
        if len(src_list) != 1:
            raise ValueError("Rename operation requires exactly one source path.")
        iface.MoveURIs(src_uris, dst_uri)
    else:
        raise ValueError(f"Unsupported method: {method}")

def nemo_file_operation(method, src_list, dst=None):
    bus = dbus.SessionBus()
    nemo = bus.get_object('org.nemo.Nemo', '/org/nemo/FileOperations')
    iface = dbus.Interface(nemo, dbus_interface='org.nemo.FileOperations')

    src_uris = [f'file://{src}' for src in src_list]
    if dst:
        dst_uri = f'file://{dst}'
    else:
        dst_uri = None

    if method == 'CopyURIs':
        iface.CopyURIs(src_uris, dst_uri)
    elif method == 'MoveURIs':
        iface.MoveURIs(src_uris, dst_uri)
    elif method == 'Trash':
        iface.Trash(src_uris)
    elif method == 'Delete':
        iface.Delete(src_uris)
    elif method == 'Rename':
        if len(src_list) != 1:
            raise ValueError("Rename operation requires exactly one source path.")
        iface.MoveURIs(src_uris, dst_uri)
    else:
        raise ValueError(f"Unsupported method: {method}")

def caja_file_operation(method, src_list, dst=None):
    bus = dbus.SessionBus()
    caja = bus.get_object('org.mate.Caja', '/org/mate/Caja')
    iface = dbus.Interface(caja, dbus_interface='org.mate.Caja.FileOperations')

    src_uris = [f'file://{src}' for src in src_list]
    if dst:
        dst_uri = f'file://{dst}'
    else:
        dst_uri = None

    if method == 'CopyURIs':
        iface.CopyURIs(src_uris, dst_uri)
    elif method == 'MoveURIs':
        iface.MoveURIs(src_uris, dst_uri)
    elif method == 'Trash':
        iface.Trash(src_uris)
    elif method == 'Delete':
        iface.Delete(src_uris)
    elif method == 'Rename':
        if len(src_list) != 1:
            raise ValueError("Rename operation requires exactly one source path.")
        iface.MoveURIs(src_uris, dst_uri)
    else:
        raise ValueError(f"Unsupported method: {method}")

def thunar_file_operation(method, src_list, dst=None):
    src_paths = ' '.join(src_list)
    if dst:
        dst_path = dst
    else:
        dst_path = ""

    command_map = {
        'CopyURIs': f'thunar --bulk-rename {src_paths} {dst_path}',
        'MoveURIs': f'thunar --bulk-rename {src_paths} {dst_path}',
        'Trash': f'thunar --trash {src_paths}',
        'Delete': f'thunar --remove {src_paths}',
        'Rename': f'thunar --bulk-rename {src_paths} {dst_path}',
    }

    if method in command_map:
        subprocess.run(command_map[method], shell=True)
    else:
        raise ValueError(f"Unsupported method: {method}")

def kio_file_operation(method, src_list, dst=None):
    src_uris = ' '.join(src_list)
    if dst:
        dst_uri = dst
    else:
        dst_uri = ""

    command_map = {
        'CopyURIs': f'kioclient5 copy {src_uris} {dst_uri}',
        'MoveURIs': f'kioclient5 move {src_uris} {dst_uri}',
        'Trash': f'kioclient5 trash {src_uris}',
        'Delete': f'kioclient5 del {src_uris}',
        'Rename': f'kioclient5 move {src_uris} {dst_uri}',
    }

    if method in command_map:
        subprocess.run(command_map[method], shell=True)
    else:
        raise ValueError(f"Unsupported method: {method}")

def perform_file_operation(operation, src_list, dst=None):
    desktop_env = get_desktop_environment()
    if desktop_env == 'gnome':
        gnome_file_operation(operation, src_list, dst)
    elif desktop_env == 'cinnamon':
        nemo_file_operation(operation, src_list, dst)
    elif desktop_env == 'mate':
        caja_file_operation(operation, src_list, dst)
    elif desktop_env == 'xfce':
        thunar_file_operation(operation, src_list, dst)
    elif desktop_env == 'kde':
        kio_file_operation(operation, src_list, dst)
    else:
        raise EnvironmentError("Unsupported desktop environment or unable to detect desktop environment.")

def copy_files_with_dialog(src_list, dst):
    perform_file_operation('CopyURIs', src_list, dst)

def move_files_with_dialog(src_list, dst):
    perform_file_operation('MoveURIs', src_list, dst)

def rename_file_with_dialog(src, dst):
    perform_file_operation('Rename', [src], dst)

def delete_files_with_dialog(src_list):
    perform_file_operation('Delete', src_list)

def move_to_recycle_bin(src_list):
    perform_file_operation('Trash', src_list)

if __name__ == "__main__":
    # Example usage of the functions
    src_paths = ["/path/to/source1", "/path/to/source2"]
    dst_path = "/path/to/destination"
    new_name = "/path/to/new_name"

    # Uncomment the desired operation to test
    # copy_files_with_dialog(src_paths, dst_path)
    # move_files_with_dialog(src_paths, dst_path)
    # rename_file_with_dialog(src_paths[0], new_name)
    # delete_files_with_dialog(src_paths)
    # move_to_recycle_bin(src_paths)
