"""3D scene viewer panel using pyqtgraph's GLViewWidget."""

from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import QVBoxLayout, QWidget
import pyqtgraph.opengl as gl

from pySimSAR.core.scene import DistributedTarget, PointTarget, Scene


def _rcs_to_scalar(rcs: float | np.ndarray) -> float:
    """Extract a scalar RCS value (dBsm-like magnitude) for coloring."""
    if isinstance(rcs, np.ndarray):
        return float(np.linalg.norm(rcs))
    return float(rcs)


def _colormap(values: np.ndarray) -> np.ndarray:
    """Map normalized values [0,1] to RGBA colors (blue-green-red ramp).

    Returns array of shape (N, 4) with float values in [0, 1].
    """
    n = len(values)
    colors = np.ones((n, 4), dtype=float)
    # Blue (low) -> Green (mid) -> Red (high)
    colors[:, 0] = np.clip(2.0 * values - 1.0, 0.0, 1.0)  # R
    colors[:, 1] = 1.0 - 2.0 * np.abs(values - 0.5)  # G
    colors[:, 2] = np.clip(1.0 - 2.0 * values, 0.0, 1.0)  # B
    return colors


class SceneViewerPanel(QWidget):
    """3D scene viewer panel for visualizing SAR scene geometry.

    Displays point targets as colored scatter points and distributed
    targets as surface plots within a pyqtgraph OpenGL widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._view = gl.GLViewWidget()
        layout.addWidget(self._view)

        # Add reference grid
        self._grid = gl.GLGridItem()
        self._grid.setSize(1000, 1000)
        self._grid.setSpacing(100, 100)
        self._view.addItem(self._grid)

        # Camera defaults
        self._view.setCameraPosition(distance=2000, elevation=30, azimuth=45)

        # Track added items for clearing
        self._scene_items: list[gl.GLGraphicsItem.GLGraphicsItem] = []

    def update_scene(self, scene: Scene) -> None:
        """Refresh the 3D display with targets from *scene*."""
        self.clear()
        self._add_point_targets(scene.point_targets)
        self._add_distributed_targets(scene.distributed_targets)

    def clear(self) -> None:
        """Remove all scene items (keeps the reference grid)."""
        for item in self._scene_items:
            self._view.removeItem(item)
        self._scene_items.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_point_targets(self, targets: list[PointTarget]) -> None:
        if not targets:
            return
        positions = np.array([t.position for t in targets], dtype=float)
        rcs_vals = np.array([_rcs_to_scalar(t.rcs) for t in targets])

        # Normalise RCS for colormap
        rmin, rmax = rcs_vals.min(), rcs_vals.max()
        if rmax > rmin:
            normed = (rcs_vals - rmin) / (rmax - rmin)
        else:
            normed = np.full_like(rcs_vals, 0.5)

        colors = _colormap(normed)
        size = np.clip(5.0 + 10.0 * normed, 5.0, 15.0)

        scatter = gl.GLScatterPlotItem(
            pos=positions, color=colors, size=size, pxMode=True
        )
        self._view.addItem(scatter)
        self._scene_items.append(scatter)

    def _add_distributed_targets(
        self, targets: list[DistributedTarget]
    ) -> None:
        for dt in targets:
            self._add_one_distributed(dt)

    def _add_one_distributed(self, dt: DistributedTarget) -> None:
        # Build x/y coordinate vectors
        xs = dt.origin[0] + np.arange(dt.nx) * dt.cell_size
        ys = dt.origin[1] + np.arange(dt.ny) * dt.cell_size

        # Elevation surface (ny x nx)
        if dt.elevation is not None:
            zdata = dt.elevation + dt.origin[2]
        else:
            zdata = np.full((dt.ny, dt.nx), dt.origin[2])

        # Color from reflectivity
        if dt.reflectivity is not None:
            refl = dt.reflectivity
            rmin, rmax = refl.min(), refl.max()
            if rmax > rmin:
                normed = (refl - rmin) / (rmax - rmin)
            else:
                normed = np.full_like(refl, 0.5)
            # Build RGBA image (ny, nx, 4)
            flat = normed.ravel()
            rgba_flat = _colormap(flat)
            rgba = rgba_flat.reshape(dt.ny, dt.nx, 4)
        else:
            rgba = np.ones((dt.ny, dt.nx, 4), dtype=float)
            rgba[:, :, :3] = 0.5  # neutral grey

        surface = gl.GLSurfacePlotItem(
            x=xs,
            y=ys,
            z=zdata,
            colors=rgba,
            shader=None,
            smooth=False,
        )
        self._view.addItem(surface)
        self._scene_items.append(surface)


__all__ = ["SceneViewerPanel"]
