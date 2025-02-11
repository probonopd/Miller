#!/usr/bin/env python3
import os
import time
import mimetypes
from PyQt6 import QtWidgets, QtCore


class FileInfoDialog(QtWidgets.QDialog):
    """
    A single-class solution to display file/folder information.
    
    The constructor accepts a list that can contain either file/folder paths (strings)
    or objects (such as FileItem) that have a file_path attribute.
    
    Title Behavior:
      • For a single item, the dialog title is "Info <name>" where <name> is the file or folder name.
      • For multiple items, the dialog title is "Selected Items Info".
      • When the provided list is empty, the current working directory is used.
    """
    # Mapping for permissions option values.
    PERMISSION_OPTIONS = {
        "No Access": "0",
        "Execute Only": "1",
        "Write Only": "2",
        "Write & Execute": "3",
        "Read Only": "4",
        "Read & Execute": "5",
        "Read & Write": "6",
        "Full Control": "7"
    }

    def __init__(self, items, parent=None):
        """
        items  - a list of file/folder paths or objects having a file_path attribute.
        parent - an optional parent widget.
        """
        super().__init__(parent)
        # Extract paths from the list regardless of whether items are plain strings or objects.
        self.paths = self._extract_paths(items) if items else [os.getcwd()]
        self.parent = parent
        self.setMinimumSize(200, 10)

        if len(self.paths) == 1:
            self.mode = "single"
            self.file_path = self.paths[0]
            # Use basename if available; for root directories (or empty basenames) display full path.
            name = os.path.basename(self.file_path) or self.file_path
            self.setWindowTitle(f"Info {name}")
            self.info_dict = self._get_item_info(self.file_path)
            self.permissions = self._get_permissions(self.file_path)
        else:
            self.mode = "multiple"
            self.setWindowTitle("Selected Items Info")
            self.info_dict, self.permissions = self._get_multiple_info(self.paths)

        # Keep a copy of original permissions for potential reversion.
        self.original_permissions = self.permissions.copy() if self.permissions else {}

        self._build_ui()

    def _extract_paths(self, items):
        """
        Given a list of items (strings or objects with file_path attribute),
        returns a list of file system paths.
        """
        paths = []
        for item in items:
            if isinstance(item, (str, bytes, os.PathLike)):
                paths.append(item)
            elif hasattr(item, "file_path"):
                paths.append(item.file_path)
            else:
                raise TypeError("Item must be a path or have a file_path attribute")
        return paths

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # File Info Section using a grid layout.
        form_layout = QtWidgets.QGridLayout()
        for row, (key, value) in enumerate(self.info_dict.items()):
            form_layout.addWidget(QtWidgets.QLabel(f"<b>{key}:</b>"), row, 0)
            form_layout.addWidget(QtWidgets.QLabel(value), row, 1)
            # Set TextSelectableByMouse for row 1 (value) to allow text selection.
            form_layout.itemAtPosition(row, 1).widget().setTextInteractionFlags(
                QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
            )
            
        layout.addLayout(form_layout)

        # Permissions section appears only if there's permission data (only for a single item).
        if self.permissions:
            group = QtWidgets.QGroupBox("Permissions")
            perm_layout = QtWidgets.QGridLayout()
            perm_layout.addWidget(QtWidgets.QLabel("Entity"), 0, 0)
            perm_layout.addWidget(QtWidgets.QLabel("Access"), 0, 1)
            self.permission_boxes = {}
            for i, entity in enumerate(["Owner", "Group", "Everyone"], start=1):
                perm_layout.addWidget(QtWidgets.QLabel(entity), i, 0)
                combo = QtWidgets.QComboBox()
                combo.addItems(list(self.PERMISSION_OPTIONS.keys()))
                current_access = self.permissions.get(entity, "No Access")
                combo.setCurrentText(current_access)
                # Disable permission changes if not a single file or file is not writable.
                if (self.mode != "single") or (not os.access(self.file_path, os.W_OK)):
                    combo.setEnabled(False)
                combo.currentTextChanged.connect(
                    lambda new_access, e=entity: self._update_permissions(e, new_access)
                )
                self.permission_boxes[entity] = combo
                perm_layout.addWidget(combo, i, 1)
            group.setLayout(perm_layout)
            layout.addWidget(group)

    def _get_item_info(self, file_path):
        """Returns a dict with file/folder information for a single path."""
        try:
            st = os.stat(file_path)
            item_type = "Folder" if os.path.isdir(file_path) else (mimetypes.guess_type(file_path)[0] or "File")
            info = {
                "Path": file_path,
                "Type": item_type,
                "Size": self._format_size(st.st_size),
                "Modified": time.ctime(st.st_mtime),
                "Created": time.ctime(st.st_ctime)
            }
        except Exception as e:
            info = {"Error": str(e)}
        return info

    def _get_multiple_info(self, paths):
        """Returns aggregated info dictionary and an empty permissions dict for multiple paths."""
        info = {"Total Items": str(len(paths))}
        total_size = 0
        for path in paths:
            try:
                st = os.stat(path)
                total_size += st.st_size
            except Exception:
                pass
        info["Total Size"] = self._format_size(total_size)
        return info, {}

    def _update_permissions(self, entity, new_access):
        """Handle permission changes for a given entity."""
        new_perms = "".join(
            self.PERMISSION_OPTIONS[self.permission_boxes[ent].currentText()]
            for ent in ["Owner", "Group", "Everyone"]
        )
        try:
            os.chmod(self.file_path, int(new_perms, 8))
        except PermissionError:
            QtWidgets.QMessageBox.warning(
                self,
                "Permission Denied",
                f"Cannot modify permissions for {entity}."
            )
            self.permission_boxes[entity].setCurrentText(self.original_permissions[entity])
        else:
            self.original_permissions[entity] = new_access

    @staticmethod
    def _format_size(size):
        """Returns a human-readable file size."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    @staticmethod
    def _get_permissions(path):
        """Return file permissions for Owner, Group, and Everyone as a dict."""
        try:
            st = os.stat(path)
            perms = oct(st.st_mode)[-3:]
            mapping = {
                '0': "No Access",
                '1': "Execute Only",
                '2': "Write Only",
                '3': "Write & Execute",
                '4': "Read Only",
                '5': "Read & Execute",
                '6': "Read & Write",
                '7': "Full Control"
            }
            return {entity: mapping[p] for entity, p in zip(["Owner", "Group", "Everyone"], perms)}
        except Exception:
            return {}


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)

    # For testing via command line, pass paths or objects with a file_path attribute.
    # Example: python file_info_Dialog.py "C:\Temp\example.txt"
    # If no items are provided, the current folder is used.
    items = sys.argv[1:]
    dlg = FileInfoDialog(items, parent=None)
    sys.exit(dlg.exec())