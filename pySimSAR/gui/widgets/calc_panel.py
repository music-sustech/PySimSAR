"""Calculated values panel — displays derived SAR quantities with warning indicators."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pySimSAR.core.calculator import SARCalculator

# Display configuration: key -> (display_name, category, decimal_places)
# All continuous values use 2 decimal places; integer counts use 0.
_DISPLAY_CONFIG: list[tuple[str, str, str, int]] = [
    # key, display_name, category, decimal_places
    ("antenna_gain", "Antenna Gain", "Radar", 2),
    ("wavelength", "Wavelength", "Radar", 2),
    ("pulse_width", "Pulse Width", "Radar", 2),
    ("range_resolution", "Range Resolution", "Radar", 2),
    ("azimuth_resolution", "Azimuth Resolution", "Radar", 2),
    ("unambiguous_range", "Unamb. Range", "Geometry", 2),
    ("unambiguous_doppler", "Unamb. Doppler Vel.", "Geometry", 2),
    ("swath_width_ground", "Swath Width (gnd)", "Geometry", 2),
    ("nesz", "NESZ", "Performance", 2),
    ("snr_single_look", "Single-Look SNR", "Performance", 2),
    ("n_range_samples", "Range Samples", "Performance", 0),
    ("synthetic_aperture", "Synth. Aperture", "Geometry", 2),
    ("doppler_bandwidth", "Doppler Bandwidth", "Performance", 2),
    ("n_pulses", "Num. Pulses", "Flight", 0),
    ("flight_time", "Flight Time", "Flight", 2),
    ("track_length", "Track Length", "Flight", 2),
]

# Number of logical columns in the grid
_N_COLUMNS = 3

# --------------------------------------------------------------------------
# Unit scaling helpers
# --------------------------------------------------------------------------

_METER_SCALES = [
    (1e3, "km"),
    (1.0, "m"),
    (1e-2, "cm"),
    (1e-3, "mm"),
    (1e-6, "\u00b5m"),  # µm
]

_SECOND_SCALES = [
    (1.0, "s"),
    (1e-3, "ms"),
    (1e-6, "\u00b5s"),  # µs
    (1e-9, "ns"),
]

_HERTZ_SCALES = [
    (1e9, "GHz"),
    (1e6, "MHz"),
    (1e3, "kHz"),
    (1.0, "Hz"),
]

_SPEED_SCALES = [
    (1e3, "km/s"),
    (1.0, "m/s"),
    (1e-2, "cm/s"),
]

_SCALE_MAP: dict[str, list[tuple[float, str]]] = {
    "m": _METER_SCALES,
    "s": _SECOND_SCALES,
    "Hz": _HERTZ_SCALES,
    "m/s": _SPEED_SCALES,
}


def _format_scaled(value: float, unit: str, precision: int) -> tuple[str, str]:
    """Return (formatted_value, scaled_unit) with the best SI prefix.

    For units not in the scale map (dB, count, etc.), returns the value
    formatted with the given precision and the original unit.
    """
    scales = _SCALE_MAP.get(unit)
    if scales is None:
        # No scaling — dB, count, dimensionless
        if precision == 0:
            return f"{value:.0f}", unit
        return f"{value:.{precision}f}", unit

    abs_val = abs(value)
    if abs_val == 0.0:
        return f"{0:.{precision}f}", scales[-1][1]

    # Pick the scale where the displayed number is in [1, 1000)
    for threshold, scaled_unit in scales:
        if abs_val >= threshold * 0.9995:  # slight margin for rounding
            scaled = value / threshold
            return f"{scaled:.{precision}f}", scaled_unit

    # Fallback to smallest scale
    threshold, scaled_unit = scales[-1]
    scaled = value / threshold
    return f"{scaled:.{precision}f}", scaled_unit


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

        title = QLabel("Critical System Parameters (Calculated)")
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

        # Each logical column uses 4 physical grid columns:
        # [warning(16px)] [name] [value] [unit]
        # Plus a spacer column between logical columns.
        # Total physical columns = N_COLUMNS * 4 + (N_COLUMNS - 1) spacers.

        # Add spacer columns between logical columns
        for col_idx in range(_N_COLUMNS - 1):
            spacer_col = (col_idx + 1) * 4 + col_idx
            grid.setColumnMinimumWidth(spacer_col, 12)

        # Monospace font for value labels — ensures digit alignment
        mono_font = QFont("Consolas, Courier New, monospace")
        mono_font.setStyleHint(QFont.StyleHint.Monospace)

        # Bold font for parameter names
        name_font = QFont()
        name_font.setBold(True)

        row = 0
        col_idx = 0
        for key, display_name, _category, _prec in _DISPLAY_CONFIG:
            # Physical column offset for this logical column
            phys_col = col_idx * 5  # 4 data cols + 1 spacer

            # Warning icon
            warn_lbl = QLabel("")
            warn_lbl.setFixedWidth(16)
            self._warning_labels[key] = warn_lbl
            grid.addWidget(warn_lbl, row, phys_col)

            # Name (bold)
            name_lbl = QLabel(display_name)
            name_lbl.setFont(name_font)
            grid.addWidget(name_lbl, row, phys_col + 1)

            # Value (monospace, right-aligned, fixed width)
            val_lbl = QLabel("\u2014")  # em dash
            val_lbl.setFont(mono_font)
            val_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            val_lbl.setFixedWidth(80)
            self._value_labels[key] = val_lbl
            grid.addWidget(val_lbl, row, phys_col + 2)

            # Unit
            unit_lbl = QLabel("")
            unit_lbl.setStyleSheet("color: #888;")
            unit_lbl.setMinimumWidth(36)
            self._unit_labels[key] = unit_lbl
            grid.addWidget(unit_lbl, row, phys_col + 3)

            col_idx += 1
            if col_idx >= _N_COLUMNS:
                col_idx = 0
                row += 1

        # Fill remaining row stretch
        if col_idx != 0:
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
            az_beamwidth, el_beamwidth, depression_angle,
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
                val_lbl.setText("\u2014")
                unit_lbl.setText("")
                warn_lbl.setText("")
                warn_lbl.setToolTip("")
                continue

            # Format with smart unit scaling
            formatted_val, scaled_unit = _format_scaled(
                result.value, result.unit, precision
            )
            val_lbl.setText(formatted_val)
            unit_lbl.setText(scaled_unit)

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
            self._value_labels[key].setText("\u2014")
            self._unit_labels[key].setText("")
            self._warning_labels[key].setText("")
            self._warning_labels[key].setToolTip("")
            self._value_labels[key].setStyleSheet("")


__all__ = ["CalculatedValuesPanel"]
