"""SAR image viewer panel with matplotlib canvas embedded in PyQt6."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _no_scroll_unless_focused(widget: QWidget) -> None:
    """Configure *widget* so that mouse-wheel changes its value only when focused."""
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    original_wheel = widget.wheelEvent

    def _wheel(event):  # type: ignore[override]
        if not widget.hasFocus():
            event.ignore()
            return
        original_wheel(event)

    widget.wheelEvent = _wheel  # type: ignore[assignment]

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
        self._colorbar = None  # Colorbar handle

        # --- controls ---
        self._dynamic_range_spin = QDoubleSpinBox()
        self._dynamic_range_spin.setRange(1.0, 120.0)
        self._dynamic_range_spin.setSingleStep(1.0)
        self._dynamic_range_spin.setSuffix(" dB")
        self._dynamic_range_spin.setDecimals(0)
        self._dynamic_range_spin.setValue(self._DEFAULT_DYNAMIC_RANGE)
        self._dynamic_range_spin.valueChanged.connect(self._refresh_display)
        _no_scroll_unless_focused(self._dynamic_range_spin)

        self._cmap_combo = QComboBox()
        self._cmap_combo.addItems(list(self._COLORMAPS))
        self._cmap_combo.currentTextChanged.connect(self._refresh_display)
        _no_scroll_unless_focused(self._cmap_combo)

        self._correct_aspect = QCheckBox("Corrected aspect")
        self._correct_aspect.setToolTip(
            "Display with correct range/azimuth pixel spacing ratio"
        )
        self._correct_aspect.stateChanged.connect(self._refresh_display)

        self._btn_zoom_full = QPushButton("Full Extent")
        self._btn_zoom_full.setToolTip("Show the entire image")
        self._btn_zoom_full.clicked.connect(self._zoom_full)

        self._btn_zoom_target = QPushButton("Zoom to Target")
        self._btn_zoom_target.setToolTip("Zoom to the region with the strongest signal")
        self._btn_zoom_target.clicked.connect(self._zoom_to_target)

        self._btn_find_peak = QPushButton("Find Peak")
        self._btn_find_peak.setCheckable(True)
        self._btn_find_peak.setToolTip("Click/drag on image to find peak value in region")
        self._btn_find_peak.toggled.connect(self._on_find_peak_toggled)

        self._btn_clear_peaks = QPushButton("Clear Peaks")
        self._btn_clear_peaks.setToolTip("Remove all peak markers")
        self._btn_clear_peaks.clicked.connect(self._on_clear_peaks)

        # Peak finder tool
        from pySimSAR.gui.widgets.peak_tool import PeakFinder
        self._peak_finder = PeakFinder(self._axes)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Dynamic range:"))
        controls_layout.addWidget(self._dynamic_range_spin)
        controls_layout.addWidget(QLabel("Colormap:"))
        controls_layout.addWidget(self._cmap_combo)
        controls_layout.addWidget(self._correct_aspect)
        controls_layout.addWidget(self._btn_zoom_full)
        controls_layout.addWidget(self._btn_zoom_target)
        controls_layout.addWidget(self._btn_find_peak)
        controls_layout.addWidget(self._btn_clear_peaks)
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
        Automatically zooms to the target region on first display.
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
        # Auto-zoom to target region on first display
        self._zoom_to_target()

    def clear(self) -> None:
        """Remove the current image and reset the canvas."""
        self._image = None
        self._db_data = None
        self._im = None
        self._colorbar = None
        self._figure.clear()
        self._axes = self._figure.add_subplot(111)
        self._axes.set_axis_off()
        self._canvas.draw_idle()

    # ------------------------------------------------------------------
    # Zoom helpers
    # ------------------------------------------------------------------

    def _find_target_region(self) -> tuple[float, float, float, float] | None:
        """Find the bounding box (in axis units) around the bright signal.

        Returns (x_min, x_max, y_min, y_max) in axis coordinates, or None.
        """
        if self._db_data is None or self._image is None:
            return None

        db = self._db_data
        vmax = float(np.nanmax(db))
        threshold = vmax - self._dynamic_range_spin.value()

        # Find pixels above threshold
        mask = db > threshold
        rows, cols = np.where(mask)
        if len(rows) == 0:
            return None

        img = self._image
        n_az, n_rng = db.shape

        # Convert pixel indices to axis units (meters)
        if img.pixel_spacing_range > 0 and img.pixel_spacing_azimuth > 0:
            near_range = img.near_range if img.near_range > 0 else 0.0
            r_min = near_range + float(cols.min()) * img.pixel_spacing_range
            r_max = near_range + float(cols.max() + 1) * img.pixel_spacing_range
            a_min = float(rows.min()) * img.pixel_spacing_azimuth
            a_max = float(rows.max() + 1) * img.pixel_spacing_azimuth
        else:
            r_min, r_max = float(cols.min()), float(cols.max() + 1)
            a_min, a_max = float(rows.min()), float(rows.max() + 1)

        # Add 20% padding
        r_pad = max((r_max - r_min) * 0.2, img.pixel_spacing_range * 20 if img.pixel_spacing_range > 0 else 20)
        a_pad = max((a_max - a_min) * 0.2, img.pixel_spacing_azimuth * 20 if img.pixel_spacing_azimuth > 0 else 20)

        return (r_min - r_pad, r_max + r_pad, a_min - a_pad, a_max + a_pad)

    def _zoom_to_target(self) -> None:
        """Zoom the view to the region containing the target signal."""
        region = self._find_target_region()
        if region is None:
            return
        r_min, r_max, a_min, a_max = region
        self._axes.set_xlim(r_min, r_max)
        self._axes.set_ylim(a_max, a_min)  # inverted for image origin=upper
        self._canvas.draw_idle()

    def _zoom_full(self) -> None:
        """Reset zoom to show the full image extent."""
        if self._db_data is None:
            return
        self._axes.autoscale()
        self._canvas.draw_idle()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh_display(self) -> None:
        """Redraw the image using the current control settings."""
        if self._db_data is None:
            return

        # Save current zoom limits before clearing
        try:
            xlim = self._axes.get_xlim()
            ylim = self._axes.get_ylim()
            has_prior_zoom = True
        except Exception:
            has_prior_zoom = False

        vmax = float(np.nanmax(self._db_data))
        vmin = vmax - self._dynamic_range_spin.value()
        cmap = self._cmap_combo.currentText()

        img = self._image
        n_az, n_rng = self._db_data.shape

        # Compute axis extents in meters
        if img is not None and img.pixel_spacing_range > 0 and img.pixel_spacing_azimuth > 0:
            near_range = img.near_range if img.near_range > 0 else 0.0
            range_extent = n_rng * img.pixel_spacing_range
            azimuth_extent = n_az * img.pixel_spacing_azimuth
            extent = [near_range, near_range + range_extent,
                      azimuth_extent, 0]  # [left, right, bottom, top]
        else:
            range_extent = n_rng
            azimuth_extent = n_az
            extent = [0, n_rng, n_az, 0]

        # Aspect ratio
        if self._correct_aspect.isChecked() and img is not None:
            if img.pixel_spacing_range > 0 and img.pixel_spacing_azimuth > 0:
                aspect = img.pixel_spacing_azimuth / img.pixel_spacing_range
            else:
                aspect = 1.0
        else:
            aspect = "auto"

        # Clear entire figure and recreate axes to avoid colorbar removal issues
        self._figure.clear()
        self._axes = self._figure.add_subplot(111)

        self._im = self._axes.imshow(
            self._db_data,
            aspect=aspect,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            origin="upper",
            extent=extent,
        )

        # Colorbar
        self._colorbar = self._figure.colorbar(
            self._im, ax=self._axes, label="dB", fraction=0.046, pad=0.04,
        )

        # Restore prior zoom if we had one
        if has_prior_zoom:
            self._axes.set_xlim(xlim)
            self._axes.set_ylim(ylim)

        # Axis labels
        if img is not None:
            geom = img.geometry or "slant_range"
            if geom == "ground_range":
                self._axes.set_xlabel("Ground Range (m)")
            else:
                self._axes.set_xlabel("Slant Range (m)")
            self._axes.set_ylabel("Azimuth (m)")
        else:
            self._axes.set_xlabel("Range (samples)")
            self._axes.set_ylabel("Azimuth (samples)")

        # Title with metadata
        if img is not None:
            parts: list[str] = []
            if img.algorithm:
                parts.append(img.algorithm)
            if img.channel:
                parts.append(img.channel)
            if img.geometry:
                parts.append(img.geometry)
            if parts:
                self._axes.set_title(" | ".join(parts), fontsize=9)

        self._canvas.draw_idle()

    # ------------------------------------------------------------------
    # Peak finder tool
    # ------------------------------------------------------------------

    def _on_find_peak_toggled(self, checked: bool) -> None:
        """Activate or deactivate the peak finder tool."""
        if checked:
            self._peak_finder.ax = self._axes
            if self._db_data is not None:
                self._peak_finder.set_image_data(self._db_data)
            self._peak_finder.activate(self._canvas)
        else:
            self._peak_finder.deactivate()

    def _on_clear_peaks(self) -> None:
        """Remove all peak markers."""
        self._peak_finder.clear_all_markers()
        self._canvas.draw_idle()
