"""SAR image viewer panel with matplotlib canvas embedded in PyQt6."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from pySimSAR.core.types import SARImage


class ImageViewerPanel(QWidget):
    """Panel for displaying focused SAR images with adjustable visualisation controls."""

    _COLORMAPS = ("gray", "viridis", "jet", "inferno")
    _DEFAULT_DYNAMIC_RANGE = 40.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._image: SARImage | None = None
        self._db_data: np.ndarray | None = None

        # --- matplotlib canvas ---
        self._figure = Figure(tight_layout=True)
        self._axes = self._figure.add_subplot(111)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
        self._im = None  # AxesImage handle

        # --- controls ---
        self._dynamic_range_spin = QDoubleSpinBox()
        self._dynamic_range_spin.setRange(1.0, 120.0)
        self._dynamic_range_spin.setSingleStep(1.0)
        self._dynamic_range_spin.setSuffix(" dB")
        self._dynamic_range_spin.setValue(self._DEFAULT_DYNAMIC_RANGE)
        self._dynamic_range_spin.valueChanged.connect(self._refresh_display)

        self._cmap_combo = QComboBox()
        self._cmap_combo.addItems(list(self._COLORMAPS))
        self._cmap_combo.currentTextChanged.connect(self._refresh_display)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Dynamic range:"))
        controls_layout.addWidget(self._dynamic_range_spin)
        controls_layout.addWidget(QLabel("Colormap:"))
        controls_layout.addWidget(self._cmap_combo)
        controls_layout.addStretch()

        # --- main layout ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas, stretch=1)
        layout.addLayout(controls_layout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_image(self, image: SARImage) -> None:
        """Display a new SAR image.

        For complex-valued images the magnitude is converted to dB scale
        (20 * log10(|data|)).  Real-valued images are shown directly.
        """
        self._image = image
        data = image.data

        if np.iscomplexobj(data):
            magnitude = np.abs(data)
            magnitude[magnitude == 0] = np.finfo(float).tiny
            self._db_data = 20.0 * np.log10(magnitude)
        else:
            self._db_data = data.astype(float)

        self._refresh_display()

    def clear(self) -> None:
        """Remove the current image and reset the canvas."""
        self._image = None
        self._db_data = None
        self._im = None
        self._axes.clear()
        self._axes.set_axis_off()
        self._canvas.draw_idle()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh_display(self) -> None:
        """Redraw the image using the current control settings."""
        if self._db_data is None:
            return

        vmax = float(np.nanmax(self._db_data))
        vmin = vmax - self._dynamic_range_spin.value()
        cmap = self._cmap_combo.currentText()

        self._axes.clear()
        self._im = self._axes.imshow(
            self._db_data,
            aspect="auto",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            origin="upper",
        )

        # Title with metadata
        if self._image is not None:
            parts: list[str] = []
            if self._image.algorithm:
                parts.append(self._image.algorithm)
            if self._image.channel:
                parts.append(self._image.channel)
            if self._image.geometry:
                parts.append(self._image.geometry)
            if parts:
                self._axes.set_title(" | ".join(parts), fontsize=9)

        self._canvas.draw_idle()
