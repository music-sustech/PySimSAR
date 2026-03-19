"""Find-peak tool for matplotlib axes in SAR image viewer."""
from __future__ import annotations
import numpy as np
from matplotlib.patches import Circle
from matplotlib.text import Annotation

class PeakMarker:
    """A marker placed at a peak location on a matplotlib axes."""

    _SHAPES = {
        "circle": lambda ax, x, y, **kw: ax.plot(x, y, 'o', markerfacecolor='none',
                                                    markeredgecolor='red', markersize=12,
                                                    markeredgewidth=2, **kw)[0],
        "crosshair": lambda ax, x, y, **kw: [
            ax.plot([x-5, x+5], [y, y], 'r-', linewidth=1.5, **kw),
            ax.plot([x, x], [y-5, y+5], 'r-', linewidth=1.5, **kw),
        ],
        "diamond": lambda ax, x, y, **kw: ax.plot(x, y, 'D', markerfacecolor='none',
                                                     markeredgecolor='red', markersize=10,
                                                     markeredgewidth=2, **kw)[0],
        "square": lambda ax, x, y, **kw: ax.plot(x, y, 's', markerfacecolor='none',
                                                    markeredgecolor='red', markersize=10,
                                                    markeredgewidth=2, **kw)[0],
        "triangle": lambda ax, x, y, **kw: ax.plot(x, y, '^', markerfacecolor='none',
                                                      markeredgecolor='red', markersize=10,
                                                      markeredgewidth=2, **kw)[0],
    }

    def __init__(self, ax, x: float, y: float, value: float, shape: str = "circle"):
        self.ax = ax
        self.x = x
        self.y = y
        self.value = value
        self.shape = shape
        self._artists = []
        self._annotation = None
        self._draw(shape)

    def _draw(self, shape: str) -> None:
        self._clear_artists()
        factory = self._SHAPES.get(shape, self._SHAPES["circle"])
        result = factory(self.ax, self.x, self.y)
        if isinstance(result, list):
            for item in result:
                if isinstance(item, list):
                    self._artists.extend(item)
                else:
                    self._artists.append(item)
        else:
            self._artists.append(result)

        self._annotation = self.ax.annotate(
            f"({self.x:.0f}, {self.y:.0f})\n{self.value:.2f} dB",
            xy=(self.x, self.y),
            xytext=(10, 10),
            textcoords='offset points',
            fontsize=8,
            color='red',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='red'),
        )
        self._artists.append(self._annotation)

    def _clear_artists(self) -> None:
        for a in self._artists:
            try:
                a.remove()
            except (ValueError, AttributeError):
                pass
        self._artists.clear()

    def change_shape(self, shape: str) -> None:
        self.shape = shape
        self._draw(shape)

    def remove(self) -> None:
        self._clear_artists()


class PeakFinder:
    """Find-peak tool: drag to select region, find max, place marker."""

    def __init__(self, ax, image_data: np.ndarray | None = None):
        self.ax = ax
        self.image_data = image_data
        self.markers: list[PeakMarker] = []
        self._active = False
        self._start = None
        self._rect = None
        self._cids = []

    def activate(self, canvas) -> None:
        """Connect mouse events to the canvas."""
        if self._active:
            return
        self._active = True
        self._cids.append(canvas.mpl_connect('button_press_event', self._on_press))
        self._cids.append(canvas.mpl_connect('button_release_event', self._on_release))
        self._canvas = canvas

    def deactivate(self) -> None:
        """Disconnect mouse events."""
        if not self._active:
            return
        for cid in self._cids:
            self._canvas.mpl_disconnect(cid)
        self._cids.clear()
        self._active = False

    def set_image_data(self, data: np.ndarray) -> None:
        self.image_data = data

    def _on_press(self, event) -> None:
        if event.inaxes != self.ax or event.button != 1:
            return
        self._start = (event.xdata, event.ydata)

    def _on_release(self, event) -> None:
        if self._start is None or event.inaxes != self.ax or self.image_data is None:
            self._start = None
            return

        x0, y0 = self._start
        x1, y1 = event.xdata, event.ydata
        self._start = None

        # Define bounding box
        r0, r1 = int(min(x0, x1)), int(max(x0, x1))
        c0, c1 = int(min(y0, y1)), int(max(y0, y1))

        # Clamp to image bounds
        nr, nc = self.image_data.shape[:2]
        r0 = max(0, min(r0, nr - 1))
        r1 = max(0, min(r1, nr - 1))
        c0 = max(0, min(c0, nc - 1))
        c1 = max(0, min(c1, nc - 1))

        if r0 == r1 and c0 == c1:
            # Single click — use 5x5 neighborhood
            r0 = max(0, r0 - 2)
            r1 = min(nr - 1, r1 + 2)
            c0 = max(0, c0 - 2)
            c1 = min(nc - 1, c1 + 2)

        region = np.abs(self.image_data[c0:c1+1, r0:r1+1])
        if region.size == 0:
            return

        region_db = 20 * np.log10(region + 1e-30)
        local_idx = np.unravel_index(np.argmax(region_db), region_db.shape)
        peak_y = c0 + local_idx[0]
        peak_x = r0 + local_idx[1]
        peak_val = region_db[local_idx]

        marker = PeakMarker(self.ax, peak_x, peak_y, peak_val)
        self.markers.append(marker)
        self._canvas.draw_idle()

    def clear_all_markers(self) -> None:
        for m in self.markers:
            m.remove()
        self.markers.clear()


__all__ = ["PeakFinder", "PeakMarker"]
