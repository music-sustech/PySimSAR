"""Calculated values panel — displays derived SAR quantities with warning indicators."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pySimSAR.core.calculator import CalculatedResult, SARCalculator


# Display configuration: key -> (display_name, category, precision)
_DISPLAY_CONFIG: list[tuple[str, str, str, int]] = [
    # key, display_name, category, decimal_places
    ("wavelength", "Wavelength", "Radar", 6),
    ("pulse_width", "Pulse Width", "Radar", 6),
    ("range_resolution", "Range Resolution", "Radar", 3),
    ("azimuth_resolution", "Azimuth Resolution", "Radar", 3),
    ("unambiguous_range", "Unamb. Range", "Geometry", 1),
    ("unambiguous_doppler", "Unamb. Doppler Vel.", "Geometry", 2),
    ("swath_width_ground", "Swath Width (gnd)", "Geometry", 1),
    ("nesz", "NESZ", "Performance", 1),
    ("snr_single_look", "Single-Look SNR", "Performance", 1),
    ("n_range_samples", "Range Samples", "Performance", 0),
    ("synthetic_aperture", "Synth. Aperture", "Geometry", 2),
    ("doppler_bandwidth", "Doppler Bandwidth", "Performance", 1),
    ("n_pulses", "Num. Pulses", "Flight", 0),
    ("flight_time", "Flight Time", "Flight", 3),
    ("track_length", "Track Length", "Flight", 1),
]


class CalculatedValuesPanel(QWidget):
    """Panel displaying live-computed derived quantities.

    Call ``update(params)`` whenever parameters change. The panel
    recomputes all derived values and refreshes the display.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._calculator = SARCalculator()
        self._value_labels: dict[str, QLabel] = {}
        self._unit_labels: dict[str, QLabel] = {}
        self._warning_labels: dict[str, QLabel] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)

        title = QLabel("Calculated Values")
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setSpacing(2)

        row = 0
        current_category = ""
        for key, display_name, category, _prec in _DISPLAY_CONFIG:
            # Category header
            if category != current_category:
                current_category = category
                cat_label = QLabel(category)
                cat_font = QFont()
                cat_font.setBold(True)
                cat_label.setFont(cat_font)
                cat_label.setStyleSheet("color: #666; padding-top: 4px;")
                grid.addWidget(cat_label, row, 0, 1, 4)
                row += 1

            # Warning icon
            warn_lbl = QLabel("")
            warn_lbl.setFixedWidth(16)
            self._warning_labels[key] = warn_lbl
            grid.addWidget(warn_lbl, row, 0)

            # Name
            name_lbl = QLabel(display_name)
            grid.addWidget(name_lbl, row, 1)

            # Value
            val_lbl = QLabel("—")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val_lbl.setMinimumWidth(80)
            self._value_labels[key] = val_lbl
            grid.addWidget(val_lbl, row, 2)

            # Unit
            unit_lbl = QLabel("")
            unit_lbl.setStyleSheet("color: #888;")
            self._unit_labels[key] = unit_lbl
            grid.addWidget(unit_lbl, row, 3)

            row += 1

        grid.setRowStretch(row, 1)
        scroll.setWidget(content)

    def update(self, params: dict) -> None:
        """Recompute all derived values and refresh display.

        Parameters
        ----------
        params : dict
            Parameter dict with keys matching SARCalculator expectations:
            carrier_freq, prf, bandwidth, duty_cycle, transmit_power,
            az_beamwidth, el_beamwidth, peak_gain_dB, depression_angle,
            velocity, altitude, noise_figure, system_losses, receiver_gain_dB,
            reference_temp, mode, near_range, far_range, etc.
        """
        try:
            results = self._calculator.compute(params)
        except Exception:
            return

        for key, _display_name, _category, precision in _DISPLAY_CONFIG:
            val_lbl = self._value_labels[key]
            unit_lbl = self._unit_labels[key]
            warn_lbl = self._warning_labels[key]

            result = results.get(key)
            if result is None:
                val_lbl.setText("—")
                unit_lbl.setText("")
                warn_lbl.setText("")
                warn_lbl.setToolTip("")
                continue

            # Format value
            val_lbl.setText(f"{result.value:.{precision}f}")
            unit_lbl.setText(result.unit)

            # Warning
            if result.warning:
                warn_lbl.setText("\u26a0")  # ⚠
                warn_lbl.setToolTip(result.warning)
                warn_lbl.setStyleSheet("color: #e6a817;")
                val_lbl.setStyleSheet("color: #e6a817;")
            else:
                warn_lbl.setText("")
                warn_lbl.setToolTip("")
                warn_lbl.setStyleSheet("")
                val_lbl.setStyleSheet("")

    def clear(self) -> None:
        """Reset all values to placeholder."""
        for key in self._value_labels:
            self._value_labels[key].setText("—")
            self._unit_labels[key].setText("")
            self._warning_labels[key].setText("")
            self._warning_labels[key].setToolTip("")
            self._value_labels[key].setStyleSheet("")


__all__ = ["CalculatedValuesPanel"]
