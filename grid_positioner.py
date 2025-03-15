#!/usr/bin/env python3
from PyQt6 import QtCore

class GridPositioner:
    def __init__(self, grid_width=100, grid_height=60, container_width=800, container_height=600, desktop=False):
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.container_width = container_width
        self.container_height = container_height
        self.desktop = desktop
        self.occupied_positions = set()

    def find_next_available_position(self) -> QtCore.QPointF:
        """Finds the first free grid position based on current layout strategy."""
        if self.desktop:
            x = (self.container_width // self.grid_width) - 1
            y = 0
            while (x, y) in self.occupied_positions:
                x -= 1  # Move left
                if x < 0:
                    x = (self.container_width // self.grid_width) - 1
                    y += 1
        else:
            x, y = 0, 0
            while (x, y) in self.occupied_positions:
                x += 1  # Move right
                if x * self.grid_width > self.container_width - 2 * self.grid_width:
                    x = 0
                    y += 1
        self.occupied_positions.add((x, y))
        return QtCore.QPointF(x * self.grid_width, y * self.grid_height)

    def snap_to_grid(self, pos: QtCore.QPointF) -> QtCore.QPointF:
        """Snaps a given position to the nearest grid point."""
        new_x = self.grid_width * round(pos.x() / self.grid_width)
        new_y = self.grid_height * round(pos.y() / self.grid_height)
        return QtCore.QPointF(new_x, new_y)
