"""Trajectory viewer panel — 3D visualization of ideal and perturbed flight paths."""

from __future__ import annotations

import numpy as np
import pyqtgraph.opengl as gl
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from pySimSAR.gui.panels.scene_3d import _ScalingAxes
from pySimSAR.motion.trajectory import Trajectory


class TrajectoryViewerPanel(QWidget):
    """3D trajectory viewer showing ideal and perturbed flight paths.

    Displays trajectories as colored lines in a GLViewWidget with an axis
    grid for spatial reference. Ideal path is blue; perturbed path is red.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 3D view
        self._view = gl.GLViewWidget()
        self._view.setCameraPosition(distance=500, elevation=30, azimuth=45)
        layout.addWidget(self._view)

        # Axis grid
        self._grid = gl.GLGridItem()
        self._grid.setSize(10000, 10000, 1)
        self._grid.setSpacing(1000, 1000, 0)
        self._view.addItem(self._grid)

        # XYZ axes (scale with camera zoom)
        self._axes = _ScalingAxes(self._view)

        # Line plot items
        self._ideal_line: gl.GLLinePlotItem | None = None
        self._perturbed_line: gl.GLLinePlotItem | None = None

        # Legend overlay
        self._legend = QLabel(self)
        self._legend.setText(
            '<span style="color:#4488ff;">\u2014 Ideal</span>'
            '&nbsp;&nbsp;'
            '<span style="color:#ff4444;">\u2014 Perturbed</span>'
        )
        self._legend.setStyleSheet(
            "background: rgba(0,0,0,160); color: white; padding: 4px 8px; "
            "border-radius: 4px; font-size: 11px;"
        )
        self._legend.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._legend.adjustSize()
        self._legend.move(8, 8)
        self._legend.raise_()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_trajectories(
        self,
        ideal: Trajectory | None,
        perturbed: Trajectory | None,
    ) -> None:
        """Update the displayed trajectories.

        Parameters
        ----------
        ideal : Trajectory or None
            Ideal (nominal) trajectory shown in blue.
        perturbed : Trajectory or None
            Perturbed (true) trajectory shown in red.
        """
        self._remove_lines()

        if ideal is not None:
            self._ideal_line = gl.GLLinePlotItem(
                pos=ideal.position.astype(np.float32),
                color=(0.27, 0.53, 1.0, 1.0),
                width=2.0,
                antialias=True,
            )
            self._view.addItem(self._ideal_line)

        if perturbed is not None:
            self._perturbed_line = gl.GLLinePlotItem(
                pos=perturbed.position.astype(np.float32),
                color=(1.0, 0.27, 0.27, 1.0),
                width=2.0,
                antialias=True,
            )
            self._view.addItem(self._perturbed_line)

        # Auto-fit camera to data extent
        self._auto_camera(ideal, perturbed)

    def clear(self) -> None:
        """Remove all trajectory lines from the view."""
        self._remove_lines()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _remove_lines(self) -> None:
        if self._ideal_line is not None:
            self._view.removeItem(self._ideal_line)
            self._ideal_line = None
        if self._perturbed_line is not None:
            self._view.removeItem(self._perturbed_line)
            self._perturbed_line = None

    def _auto_camera(
        self,
        ideal: Trajectory | None,
        perturbed: Trajectory | None,
    ) -> None:
        """Set camera distance based on trajectory extent."""
        positions = [
            t.position for t in (ideal, perturbed) if t is not None
        ]
        if not positions:
            return
        all_pos = np.concatenate(positions, axis=0)
        extent = float(np.max(np.ptp(all_pos, axis=0)))
        distance = max(extent * 1.5, 100.0)
        center = all_pos.mean(axis=0)
        self._view.setCameraPosition(distance=distance, elevation=30, azimuth=45)
        self._view.pan(*center, relative="global")


__all__ = ["TrajectoryViewerPanel"]
