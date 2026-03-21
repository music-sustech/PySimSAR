"""Find-peak tool for matplotlib axes in SAR image viewer."""
from __future__ import annotations

import numpy as np
from matplotlib.patches import Rectangle


class PeakMarker:
    """A marker placed at a peak location on a matplotlib axes."""

    def __init__(self, ax, x: float, y: float, value: float):
        self.ax = ax
        self.x = x
        self.y = y
        self.value = value
        self._artists: list = []
        self._draw()

    def _draw(self) -> None:
        self._clear_artists()
        artist = self.ax.plot(
            self.x, self.y, 'o', markerfacecolor='none',
            markeredgecolor='red', markersize=14, markeredgewidth=1.5,
        )[0]
        self._artists.append(artist)

        annotation = self.ax.annotate(
            f"({self.x:.1f}, {self.y:.1f}) m\n{self.value:.2f} dB",
            xy=(self.x, self.y),
            xytext=(10, 10),
            textcoords='offset points',
            fontsize=8,
            color='red',
            bbox=dict(
                boxstyle='round,pad=0.3', facecolor='white',
                alpha=0.8, edgecolor='red',
            ),
        )
        self._artists.append(annotation)

    def _clear_artists(self) -> None:
        for a in self._artists:
            try:
                a.remove()
            except (ValueError, AttributeError):
                pass
        self._artists.clear()

    def remove(self) -> None:
        self._clear_artists()


class PeakFinder:
    """Find-peak tool: drag to select region, find max, place marker.

    The image is displayed with axis coordinates in physical units (meters).
    This tool converts between axis coordinates and pixel indices using the
    origin and pixel spacing set via ``set_image_data``.
    """

    def __init__(self, ax, image_data: np.ndarray | None = None):
        self.ax = ax
        self.image_data: np.ndarray | None = image_data
        self.markers: list[PeakMarker] = []
        self._active = False
        self._start: tuple[float, float] | None = None
        self._rect_patch: Rectangle | None = None
        self._cids: list[int] = []
        self._canvas = None
        # Mapping from axis coords (meters) to pixel indices
        self._origin_x = 0.0  # axis value at pixel col 0
        self._origin_y = 0.0  # axis value at pixel row 0
        self._dx = 1.0  # axis units per pixel column
        self._dy = 1.0  # axis units per pixel row

    def set_image_data(
        self,
        data: np.ndarray,
        origin_x: float = 0.0,
        origin_y: float = 0.0,
        pixel_spacing_x: float = 1.0,
        pixel_spacing_y: float = 1.0,
    ) -> None:
        """Set image data and the axis-to-pixel mapping."""
        self.image_data = data
        self._origin_x = origin_x
        self._origin_y = origin_y
        self._dx = pixel_spacing_x
        self._dy = pixel_spacing_y

    def activate(self, canvas) -> None:
        """Connect mouse events to the canvas."""
        if self._active:
            return
        self._active = True
        self._canvas = canvas
        self._cids.append(canvas.mpl_connect('button_press_event', self._on_press))
        self._cids.append(canvas.mpl_connect('motion_notify_event', self._on_motion))
        self._cids.append(canvas.mpl_connect('button_release_event', self._on_release))

    def deactivate(self) -> None:
        """Disconnect mouse events."""
        if not self._active:
            return
        for cid in self._cids:
            self._canvas.mpl_disconnect(cid)
        self._cids.clear()
        self._remove_rect()
        self._active = False

    # ------------------------------------------------------------------
    # Mouse event handlers
    # ------------------------------------------------------------------

    def _on_press(self, event) -> None:
        if event.inaxes != self.ax or event.button != 1:
            return
        self._start = (event.xdata, event.ydata)
        self._remove_rect()

    def _on_motion(self, event) -> None:
        """Draw rubber-band rectangle while dragging."""
        if self._start is None or event.inaxes != self.ax:
            return
        x0, y0 = self._start
        x1, y1 = event.xdata, event.ydata
        self._update_rect(x0, y0, x1, y1)
        self._canvas.draw_idle()

    def _on_release(self, event) -> None:
        if self._start is None or event.inaxes != self.ax or self.image_data is None:
            self._start = None
            self._remove_rect()
            return

        x0, y0 = self._start
        x1, y1 = event.xdata, event.ydata
        self._start = None
        self._remove_rect()

        # Convert axis coordinates (meters) to pixel indices
        col0 = self._axis_to_col(min(x0, x1))
        col1 = self._axis_to_col(max(x0, x1))
        row0 = self._axis_to_row(min(y0, y1))
        row1 = self._axis_to_row(max(y0, y1))

        n_rows, n_cols = self.image_data.shape[:2]
        col0 = max(0, min(col0, n_cols - 1))
        col1 = max(0, min(col1, n_cols - 1))
        row0 = max(0, min(row0, n_rows - 1))
        row1 = max(0, min(row1, n_rows - 1))

        if row0 == row1 and col0 == col1:
            # Single click — use 5x5 neighborhood
            row0 = max(0, row0 - 2)
            row1 = min(n_rows - 1, row1 + 2)
            col0 = max(0, col0 - 2)
            col1 = min(n_cols - 1, col1 + 2)

        # image_data is already in dB (passed from _db_data)
        region = self.image_data[row0:row1 + 1, col0:col1 + 1]
        if region.size == 0:
            return

        local_idx = np.unravel_index(np.argmax(region), region.shape)
        peak_row = row0 + local_idx[0]
        peak_col = col0 + local_idx[1]
        peak_val = float(region[local_idx])

        # Convert pixel back to axis coordinates for the marker
        peak_x = self._col_to_axis(peak_col)
        peak_y = self._row_to_axis(peak_row)

        marker = PeakMarker(self.ax, peak_x, peak_y, peak_val)
        self.markers.append(marker)
        self._canvas.draw_idle()

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------

    def _axis_to_col(self, x: float) -> int:
        return int(round((x - self._origin_x) / self._dx))

    def _axis_to_row(self, y: float) -> int:
        return int(round((y - self._origin_y) / self._dy))

    def _col_to_axis(self, col: int) -> float:
        return self._origin_x + col * self._dx

    def _row_to_axis(self, row: int) -> float:
        return self._origin_y + row * self._dy

    # ------------------------------------------------------------------
    # Rubber-band rectangle
    # ------------------------------------------------------------------

    def _update_rect(self, x0: float, y0: float, x1: float, y1: float) -> None:
        rx = min(x0, x1)
        ry = min(y0, y1)
        w = abs(x1 - x0)
        h = abs(y1 - y0)
        if self._rect_patch is None:
            self._rect_patch = Rectangle(
                (rx, ry), w, h,
                linewidth=1, edgecolor='cyan', facecolor='cyan',
                alpha=0.15, linestyle='--',
            )
            self.ax.add_patch(self._rect_patch)
        else:
            self._rect_patch.set_xy((rx, ry))
            self._rect_patch.set_width(w)
            self._rect_patch.set_height(h)

    def _remove_rect(self) -> None:
        if self._rect_patch is not None:
            try:
                self._rect_patch.remove()
            except ValueError:
                pass
            self._rect_patch = None
            if self._canvas is not None:
                self._canvas.draw_idle()

    def clear_all_markers(self) -> None:
        for m in self.markers:
            m.remove()
        self.markers.clear()


__all__ = ["PeakFinder", "PeakMarker"]
