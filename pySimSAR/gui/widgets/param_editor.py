"""Parameter editor widgets for configuring SAR simulation parameters.

Each editor provides get_params() / set_params(dict) and emits params_changed
when any value is modified by the user.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pySimSAR.core.types import LookSide, PolarizationMode, RampType, SARMode

# ---------------------------------------------------------------------------
# Reusable UnitSpinBox
# ---------------------------------------------------------------------------


class UnitSpinBox(QWidget):
    """A QDoubleSpinBox paired with a unit-selector QComboBox.

    The spinbox displays values in the currently selected unit.
    ``si_value()`` always returns the value in the SI base unit.
    ``set_si_value(v)`` sets the spinbox from an SI value.

    Parameters
    ----------
    units : dict[str, float]
        Mapping from unit label to its SI multiplier.
        Example: ``{"GHz": 1e9, "MHz": 1e6, "kHz": 1e3, "Hz": 1.0}``
    default_unit : str
        Which unit to select initially.
    value : float
        Initial display value *in the default unit*.
    minimum, maximum : float
        Spinbox range *in display units*.
    step : float
        Single-step size in display units.
    """

    value_changed = pyqtSignal()

    def __init__(
        self,
        units: dict[str, float],
        default_unit: str,
        value: float = 0.0,
        minimum: float = -1e15,
        maximum: float = 1e15,
        step: float = 1.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._units = units
        self._prev_unit = default_unit

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._spin = _CleanDoubleSpinBox()
        self._spin.setDecimals(10)
        self._spin.setRange(minimum, maximum)
        self._spin.setSingleStep(step)
        self._spin.setValue(value)
        _no_scroll_unless_focused(self._spin)

        self._combo = QComboBox()
        self._combo.addItems(list(units.keys()))
        self._combo.setCurrentText(default_unit)
        self._combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        _no_scroll_unless_focused(self._combo)

        layout.addWidget(self._spin, stretch=1)
        layout.addWidget(self._combo)

        self._spin.valueChanged.connect(lambda _: self.value_changed.emit())
        self._combo.currentTextChanged.connect(self._on_unit_changed)

    def _on_unit_changed(self, new_unit: str) -> None:
        old_mult = self._units[self._prev_unit]
        new_mult = self._units[new_unit]
        si = self._spin.value() * old_mult
        self._prev_unit = new_unit
        self._spin.blockSignals(True)
        self._spin.setValue(si / new_mult)
        self._spin.blockSignals(False)
        self.value_changed.emit()

    def si_value(self) -> float:
        """Return the current value in SI base units."""
        return self._spin.value() * self._units[self._combo.currentText()]

    def set_si_value(self, si: float) -> None:
        """Set from an SI value, converting to the current display unit."""
        mult = self._units[self._combo.currentText()]
        self._spin.setValue(si / mult)

    def display_value(self) -> float:
        return self._spin.value()

    def set_display_value(self, v: float) -> None:
        self._spin.setValue(v)


# ---------------------------------------------------------------------------
# Unit dictionaries
# ---------------------------------------------------------------------------

_FREQ = {"GHz": 1e9, "MHz": 1e6, "kHz": 1e3, "Hz": 1.0}
_POWER = {"kW": 1e3, "W": 1.0, "mW": 1e-3}
_DIST = {"km": 1e3, "m": 1.0}
_SPEED = {"m/s": 1.0, "km/h": 1.0 / 3.6}
_AREA = {"m\u00b2": 1.0, "dBsm": None}  # RCS — special, keep m² only


# ---------------------------------------------------------------------------
# Clean-display spin box (high precision, no trailing zeros)
# ---------------------------------------------------------------------------


class _CleanDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that accepts many decimals but hides trailing zeros.

    Qt adds prefix/suffix around textFromValue automatically, and strips
    them before passing text to valueFromText — so neither method should
    handle prefix/suffix.
    """

    def textFromValue(self, value: float) -> str:  # noqa: N802
        text = f"{value:.{self.decimals()}f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text

    def valueFromText(self, text: str) -> float:  # noqa: N802
        clean = text
        if self.suffix():
            clean = clean.removesuffix(self.suffix())
        if self.prefix():
            clean = clean.removeprefix(self.prefix())
        return float(clean.strip())

    def validate(self, text: str, pos: int):
        from PyQt6.QtGui import QValidator
        clean = text
        if self.suffix():
            clean = clean.removesuffix(self.suffix())
        if self.prefix():
            clean = clean.removeprefix(self.prefix())
        clean = clean.strip()
        if clean in ("", "-", "."):
            return QValidator.State.Intermediate, text, pos
        try:
            val = float(clean)
            if self.minimum() <= val <= self.maximum():
                return QValidator.State.Acceptable, text, pos
            return QValidator.State.Intermediate, text, pos
        except ValueError:
            return QValidator.State.Invalid, text, pos


# ---------------------------------------------------------------------------
# Scroll-only-when-focused helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _int_spin(
    value: int = 0,
    minimum: int = 0,
    maximum: int = 10_000_000,
) -> QSpinBox:
    sb = QSpinBox()
    sb.setRange(minimum, maximum)
    sb.setValue(value)
    _no_scroll_unless_focused(sb)
    return sb


def _combo(items: list[str], current: str = "") -> QComboBox:
    cb = QComboBox()
    cb.addItems(items)
    if current and current in items:
        cb.setCurrentText(current)
    _no_scroll_unless_focused(cb)
    return cb


def _plain_spin(
    value: float = 0.0,
    minimum: float = -1e15,
    maximum: float = 1e15,
    step: float = 1.0,
    suffix: str = "",
) -> QDoubleSpinBox:
    """Plain spin box (no unit combo) with clean decimal display."""
    sb = _CleanDoubleSpinBox()
    sb.setDecimals(10)
    sb.setRange(minimum, maximum)
    sb.setSingleStep(step)
    sb.setValue(value)
    if suffix:
        sb.setSuffix(suffix)
    _no_scroll_unless_focused(sb)
    return sb


# ---------------------------------------------------------------------------
# AntennaParamEditor
# ---------------------------------------------------------------------------


class AntennaParamEditor(QGroupBox):
    """Editor for antenna pattern parameters."""

    params_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Antenna Parameters", parent)
        form = QFormLayout(self)

        self._preset = _combo(["flat", "sinc", "gaussian"], "flat")
        self._az_beamwidth = _plain_spin(10.0, 0.01, 180.0, 0.5, "\u00b0")
        self._el_beamwidth = _plain_spin(10.0, 0.01, 180.0, 0.5, "\u00b0")

        form.addRow("Preset:", self._preset)
        form.addRow("Az Beamwidth:", self._az_beamwidth)
        form.addRow("El Beamwidth:", self._el_beamwidth)

        self._preset.currentTextChanged.connect(
            lambda _: self.params_changed.emit()
        )
        for w in (self._az_beamwidth, self._el_beamwidth):
            w.valueChanged.connect(self.params_changed)

    def get_params(self) -> dict:
        return {
            "preset": self._preset.currentText(),
            "az_beamwidth": math.radians(self._az_beamwidth.value()),
            "el_beamwidth": math.radians(self._el_beamwidth.value()),
        }

    def set_params(self, params: dict) -> None:
        if "preset" in params:
            self._preset.setCurrentText(str(params["preset"]))
        if "az_beamwidth" in params:
            self._az_beamwidth.setValue(math.degrees(params["az_beamwidth"]))
        if "el_beamwidth" in params:
            self._el_beamwidth.setValue(math.degrees(params["el_beamwidth"]))


# ---------------------------------------------------------------------------
# RadarParamEditor
# ---------------------------------------------------------------------------


class RadarParamEditor(QGroupBox):
    """Editor for radar system parameters."""

    params_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Radar Parameters", parent)
        form = QFormLayout(self)

        self._carrier_freq = UnitSpinBox(
            _FREQ, "GHz", value=9.65, minimum=0.001, maximum=999.0, step=0.01,
        )
        self._prf = UnitSpinBox(
            _FREQ, "Hz", value=1000.0, minimum=1.0, maximum=999999.0, step=100.0,
        )
        self._transmit_power = UnitSpinBox(
            _POWER, "W", value=1.0, minimum=0.01, maximum=999999.0, step=0.1,
        )
        self._receiver_gain = _plain_spin(30.0, 0.0, 120.0, 1.0, " dB")
        self._system_losses = _plain_spin(2.0, 0.0, 60.0, 0.5, " dB")
        self._noise_figure = _plain_spin(3.0, 0.0, 30.0, 0.5, " dB")
        self._reference_temp = _plain_spin(290.0, 1.0, 10000.0, 10.0, " K")
        self._squint_angle = _plain_spin(0.0, -90.0, 90.0, 1.0, "\u00b0")
        self._polarization = _combo(
            [m.value for m in PolarizationMode], PolarizationMode.SINGLE.value,
        )
        self._mode = _combo([m.value for m in SARMode], SARMode.STRIPMAP.value)
        self._look_side = _combo(
            [s.value for s in LookSide], LookSide.RIGHT.value,
        )
        self._depression_angle = _plain_spin(
            45.0, 0.0, 90.0, 1.0, "\u00b0",
        )

        form.addRow("Carrier Frequency:", self._carrier_freq)
        form.addRow("PRF:", self._prf)
        form.addRow("Transmit Power:", self._transmit_power)
        form.addRow("Receiver Gain:", self._receiver_gain)
        form.addRow("System Losses:", self._system_losses)
        form.addRow("Noise Figure:", self._noise_figure)
        form.addRow("Reference Temp:", self._reference_temp)
        form.addRow("Polarization:", self._polarization)
        form.addRow("SAR Mode:", self._mode)
        form.addRow("Look Side:", self._look_side)
        form.addRow("Depression Angle:", self._depression_angle)
        form.addRow("Squint Angle:", self._squint_angle)

        # Connect signals
        for w in (self._carrier_freq, self._prf, self._transmit_power):
            w.value_changed.connect(self.params_changed)
        for w in (self._receiver_gain, self._system_losses, self._noise_figure,
                  self._reference_temp, self._depression_angle,
                  self._squint_angle):
            w.valueChanged.connect(self.params_changed)
        for w in (self._polarization, self._mode, self._look_side):
            w.currentTextChanged.connect(lambda _: self.params_changed.emit())

    def get_params(self) -> dict:
        return {
            "carrier_freq": self._carrier_freq.si_value(),
            "prf": self._prf.si_value(),
            "transmit_power": self._transmit_power.si_value(),
            "receiver_gain_dB": self._receiver_gain.value(),
            "system_losses": self._system_losses.value(),
            "noise_figure": self._noise_figure.value(),
            "reference_temp": self._reference_temp.value(),
            "polarization": self._polarization.currentText(),
            "mode": self._mode.currentText(),
            "look_side": self._look_side.currentText(),
            "depression_angle": math.radians(self._depression_angle.value()),
            "squint_angle": math.radians(self._squint_angle.value()),
        }

    def set_params(self, params: dict) -> None:
        if "carrier_freq" in params:
            self._carrier_freq.set_si_value(params["carrier_freq"])
        if "prf" in params:
            self._prf.set_si_value(params["prf"])
        if "transmit_power" in params:
            self._transmit_power.set_si_value(params["transmit_power"])
        if "receiver_gain_dB" in params:
            self._receiver_gain.setValue(params["receiver_gain_dB"])
        if "system_losses" in params:
            self._system_losses.setValue(params["system_losses"])
        if "noise_figure" in params:
            self._noise_figure.setValue(params["noise_figure"])
        if "reference_temp" in params:
            self._reference_temp.setValue(params["reference_temp"])
        if "polarization" in params:
            self._polarization.setCurrentText(str(params["polarization"]))
        if "mode" in params:
            self._mode.setCurrentText(str(params["mode"]))
        if "look_side" in params:
            self._look_side.setCurrentText(str(params["look_side"]))
        if "depression_angle" in params:
            self._depression_angle.setValue(math.degrees(params["depression_angle"]))
        if "squint_angle" in params:
            self._squint_angle.setValue(math.degrees(params["squint_angle"]))


# ---------------------------------------------------------------------------
# WaveformParamEditor
# ---------------------------------------------------------------------------


class WaveformParamEditor(QGroupBox):
    """Editor for waveform type and parameters."""

    params_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Waveform Parameters", parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._waveform_type = _combo(["LFM", "FMCW"], "LFM")
        self._bandwidth = UnitSpinBox(
            _FREQ, "MHz", value=100.0, minimum=0.001, maximum=99999.0, step=1.0,
        )
        self._duty_cycle = _plain_spin(0.01, 0.001, 1.0, 0.01)
        self._fmcw_duty_cycle = _plain_spin(1.0, 0.001, 1.0, 0.01)
        self._ramp_type = _combo(
            [r.value for r in RampType], RampType.UP.value,
        )
        self._window = _combo(
            ["(None)", "hamming", "hanning", "blackman", "kaiser"], "(None)",
        )
        self._kaiser_beta = _plain_spin(6.0, 0.0, 40.0, 0.5, "")

        form.addRow("Waveform Type:", self._waveform_type)
        form.addRow("Bandwidth:", self._bandwidth)
        form.addRow("Duty Cycle:", self._duty_cycle)
        form.addRow("FMCW Duty Cycle:", self._fmcw_duty_cycle)
        form.addRow("Ramp Type:", self._ramp_type)
        form.addRow("Window:", self._window)
        form.addRow("Kaiser \u03b2:", self._kaiser_beta)

        # Phase noise section
        self._phase_noise_enabled = QCheckBox("Enable Phase Noise")
        form.addRow(self._phase_noise_enabled)

        self._flicker_fm = _plain_spin(-80.0, -200.0, 0.0, 1.0, " dBc/Hz")
        self._white_fm = _plain_spin(-100.0, -200.0, 0.0, 1.0, " dBc/Hz")
        self._flicker_pm = _plain_spin(-120.0, -200.0, 0.0, 1.0, " dBc/Hz")
        self._white_floor = _plain_spin(-150.0, -200.0, 0.0, 1.0, " dBc/Hz")

        form.addRow("Flicker FM:", self._flicker_fm)
        form.addRow("White FM:", self._white_fm)
        form.addRow("Flicker PM:", self._flicker_pm)
        form.addRow("White Floor:", self._white_floor)

        self._phase_noise_widgets = [
            self._flicker_fm, self._white_fm,
            self._flicker_pm, self._white_floor,
        ]

        # Show/hide phase noise fields
        self._phase_noise_enabled.toggled.connect(self._on_phase_noise_toggled)
        self._on_phase_noise_toggled(False)

        # Show/hide fields based on waveform type and window selection
        self._waveform_type.currentTextChanged.connect(self._on_type_changed)
        self._on_type_changed(self._waveform_type.currentText())
        self._window.currentTextChanged.connect(self._on_window_changed)
        self._on_window_changed(self._window.currentText())

        # Connect change signals
        self._bandwidth.value_changed.connect(self.params_changed)
        self._duty_cycle.valueChanged.connect(self.params_changed)
        self._fmcw_duty_cycle.valueChanged.connect(self.params_changed)
        self._ramp_type.currentTextChanged.connect(
            lambda _: self.params_changed.emit()
        )
        self._window.currentTextChanged.connect(
            lambda _: self.params_changed.emit()
        )
        self._kaiser_beta.valueChanged.connect(self.params_changed)
        self._waveform_type.currentTextChanged.connect(
            lambda _: self.params_changed.emit()
        )
        self._phase_noise_enabled.toggled.connect(
            lambda _: self.params_changed.emit()
        )
        for w in self._phase_noise_widgets:
            w.valueChanged.connect(self.params_changed)

    def _on_phase_noise_toggled(self, checked: bool) -> None:
        form = self.findChild(QFormLayout)
        for w in self._phase_noise_widgets:
            w.setVisible(checked)
            if form is not None:
                lbl = form.labelForField(w)
                if lbl is not None:
                    lbl.setVisible(checked)

    def _on_type_changed(self, wtype: str) -> None:
        is_lfm = wtype == "LFM"
        is_fmcw = wtype == "FMCW"
        self._duty_cycle.setVisible(is_lfm)
        self._fmcw_duty_cycle.setVisible(is_fmcw)
        form = self.findChild(QFormLayout)
        if form is not None:
            label = form.labelForField(self._duty_cycle)
            if label is not None:
                label.setVisible(is_lfm)
            label_fmcw = form.labelForField(self._fmcw_duty_cycle)
            if label_fmcw is not None:
                label_fmcw.setVisible(is_fmcw)
            label_ramp = form.labelForField(self._ramp_type)
            if label_ramp is not None:
                label_ramp.setVisible(not is_lfm)
        self._ramp_type.setVisible(not is_lfm)

    def _on_window_changed(self, text: str) -> None:
        is_kaiser = text == "kaiser"
        self._kaiser_beta.setVisible(is_kaiser)
        form = self.findChild(QFormLayout)
        if form is not None:
            label = form.labelForField(self._kaiser_beta)
            if label is not None:
                label.setVisible(is_kaiser)

    def get_params(self) -> dict:
        wtype = self._waveform_type.currentText()
        window_text = self._window.currentText()
        params: dict = {
            "waveform_type": wtype,
            "bandwidth": self._bandwidth.si_value(),
            "window": None if window_text == "(None)" else window_text,
        }
        if window_text == "kaiser":
            params["kaiser_beta"] = self._kaiser_beta.value()
        if wtype == "LFM":
            params["duty_cycle"] = self._duty_cycle.value()
        elif wtype == "FMCW":
            params["ramp_type"] = self._ramp_type.currentText()
            params["duty_cycle"] = self._fmcw_duty_cycle.value()
        if self._phase_noise_enabled.isChecked():
            params["phase_noise"] = {
                "flicker_fm_level": self._flicker_fm.value(),
                "white_fm_level": self._white_fm.value(),
                "flicker_pm_level": self._flicker_pm.value(),
                "white_floor": self._white_floor.value(),
            }
        else:
            params["phase_noise"] = None
        return params

    def set_params(self, params: dict) -> None:
        if "waveform_type" in params:
            self._waveform_type.setCurrentText(params["waveform_type"])
        if "bandwidth" in params:
            self._bandwidth.set_si_value(params["bandwidth"])
        if "duty_cycle" in params:
            wtype = self._waveform_type.currentText()
            if wtype == "FMCW":
                self._fmcw_duty_cycle.setValue(params["duty_cycle"])
            else:
                self._duty_cycle.setValue(params["duty_cycle"])
        if "ramp_type" in params:
            self._ramp_type.setCurrentText(str(params["ramp_type"]))
        if "window" in params:
            w = params["window"]
            self._window.setCurrentText("(None)" if w is None else str(w))
        if "kaiser_beta" in params:
            self._kaiser_beta.setValue(params["kaiser_beta"])
        if "phase_noise" in params:
            pn = params["phase_noise"]
            enabled = params.get("phase_noise_enabled", pn is not None)
            self._phase_noise_enabled.setChecked(enabled)
            if pn is not None:
                self._flicker_fm.setValue(pn.get("flicker_fm_level", -80.0))
                self._white_fm.setValue(pn.get("white_fm_level", -100.0))
                self._flicker_pm.setValue(pn.get("flicker_pm_level", -120.0))
                self._white_floor.setValue(pn.get("white_floor", -150.0))


# ---------------------------------------------------------------------------
# PlatformParamEditor
# ---------------------------------------------------------------------------


class PlatformParamEditor(QGroupBox):
    """Editor for platform motion parameters."""

    params_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Platform Parameters", parent)
        form = QFormLayout(self)

        self._velocity = UnitSpinBox(
            _SPEED, "m/s", value=100.0, minimum=0.1, maximum=50000.0, step=10.0,
        )
        self._heading_x = _plain_spin(0.0, -1.0, 1.0, 0.1)
        self._heading_y = _plain_spin(1.0, -1.0, 1.0, 0.1)
        self._heading_z = _plain_spin(0.0, -1.0, 1.0, 0.1)
        self._start_x = UnitSpinBox(
            _DIST, "m", value=0.0, minimum=-1e8, maximum=1e8, step=100.0,
        )
        self._start_y = UnitSpinBox(
            _DIST, "m", value=-25.0, minimum=-1e8, maximum=1e8, step=100.0,
        )
        self._start_z = UnitSpinBox(
            _DIST, "m", value=1000.0, minimum=0.0, maximum=100000.0, step=100.0,
        )

        form.addRow("Speed:", self._velocity)
        form.addRow("Heading X:", self._heading_x)
        form.addRow("Heading Y:", self._heading_y)
        form.addRow("Heading Z:", self._heading_z)
        form.addRow("Start X:", self._start_x)
        form.addRow("Start Y:", self._start_y)
        form.addRow("Start Z:", self._start_z)

        # Perturbation (turbulence)
        self._perturbation_enabled = QCheckBox("Enable Turbulence")
        form.addRow(self._perturbation_enabled)
        self._sigma_u = _plain_spin(1.0, 0.0, 100.0, 0.1, " m/s")
        self._sigma_v = _plain_spin(1.0, 0.0, 100.0, 0.1, " m/s")
        self._sigma_w = _plain_spin(0.5, 0.0, 100.0, 0.1, " m/s")
        form.addRow("Lateral \u03c3_u:", self._sigma_u)
        form.addRow("Longitudinal \u03c3_v:", self._sigma_v)
        form.addRow("Vertical \u03c3_w:", self._sigma_w)
        self._turb_widgets = [self._sigma_u, self._sigma_v, self._sigma_w]
        self._perturbation_enabled.toggled.connect(self._on_turb_toggled)
        self._on_turb_toggled(False)

        # GPS Sensor
        self._gps_enabled = QCheckBox("GPS Sensor")
        form.addRow(self._gps_enabled)
        self._gps_accuracy = _plain_spin(0.002, 0.0, 100.0, 0.001, " m")
        self._gps_rate = _plain_spin(10.0, 0.1, 1000.0, 1.0, " Hz")
        form.addRow("GPS Accuracy:", self._gps_accuracy)
        form.addRow("GPS Rate:", self._gps_rate)
        self._gps_widgets = [self._gps_accuracy, self._gps_rate]
        self._gps_enabled.toggled.connect(self._on_gps_toggled)
        self._on_gps_toggled(False)

        # IMU Sensor
        self._imu_enabled = QCheckBox("IMU Sensor")
        form.addRow(self._imu_enabled)
        self._accel_noise = _plain_spin(0.0001, 0.0, 10.0, 0.0001, " m/s\u00b2/\u221aHz")
        self._gyro_noise = _plain_spin(0.00001, 0.0, 1.0, 0.000001, " rad/s/\u221aHz")
        self._imu_rate = _plain_spin(200.0, 1.0, 10000.0, 10.0, " Hz")
        form.addRow("Accel Noise:", self._accel_noise)
        form.addRow("Gyro Noise:", self._gyro_noise)
        form.addRow("IMU Rate:", self._imu_rate)
        self._imu_widgets = [self._accel_noise, self._gyro_noise, self._imu_rate]
        self._imu_enabled.toggled.connect(self._on_imu_toggled)
        self._on_imu_toggled(False)

        for w in (self._velocity, self._start_x, self._start_y, self._start_z):
            w.value_changed.connect(self.params_changed)
        for w in (self._heading_x, self._heading_y, self._heading_z):
            w.valueChanged.connect(self.params_changed)
        for w in self._turb_widgets + self._gps_widgets + self._imu_widgets:
            w.valueChanged.connect(self.params_changed)
        for cb in (self._perturbation_enabled, self._gps_enabled, self._imu_enabled):
            cb.toggled.connect(lambda _: self.params_changed.emit())

    def _toggle_widgets(self, widgets: list, form: QFormLayout | None, visible: bool) -> None:
        for w in widgets:
            w.setVisible(visible)
            if form is not None:
                lbl = form.labelForField(w)
                if lbl is not None:
                    lbl.setVisible(visible)

    def _on_turb_toggled(self, checked: bool) -> None:
        self._toggle_widgets(self._turb_widgets, self.findChild(QFormLayout), checked)

    def _on_gps_toggled(self, checked: bool) -> None:
        self._toggle_widgets(self._gps_widgets, self.findChild(QFormLayout), checked)

    def _on_imu_toggled(self, checked: bool) -> None:
        self._toggle_widgets(self._imu_widgets, self.findChild(QFormLayout), checked)

    def get_params(self) -> dict:
        result: dict = {
            "velocity": self._velocity.si_value(),
            "altitude": self._start_z.si_value(),
            "heading": [
                self._heading_x.value(),
                self._heading_y.value(),
                self._heading_z.value(),
            ],
            "start_position": [
                self._start_x.si_value(),
                self._start_y.si_value(),
                self._start_z.si_value(),
            ],
        }
        if self._perturbation_enabled.isChecked():
            result["perturbation"] = {
                "sigma_u": self._sigma_u.value(),
                "sigma_v": self._sigma_v.value(),
                "sigma_w": self._sigma_w.value(),
            }
        else:
            result["perturbation"] = None
        if self._gps_enabled.isChecked():
            result["gps"] = {
                "accuracy": self._gps_accuracy.value(),
                "rate": self._gps_rate.value(),
            }
        else:
            result["gps"] = None
        if self._imu_enabled.isChecked():
            result["imu"] = {
                "accel_noise": self._accel_noise.value(),
                "gyro_noise": self._gyro_noise.value(),
                "rate": self._imu_rate.value(),
            }
        else:
            result["imu"] = None
        return result

    def set_params(self, params: dict) -> None:
        if "velocity" in params:
            self._velocity.set_si_value(params["velocity"])
        if "heading" in params:
            h = params["heading"]
            if isinstance(h, (list, tuple)) and len(h) >= 3:
                self._heading_x.setValue(h[0])
                self._heading_y.setValue(h[1])
                self._heading_z.setValue(h[2])
            elif isinstance(h, (int, float)):
                # Legacy scalar (degrees) → convert to direction vector
                import math
                self._heading_x.setValue(math.sin(math.radians(h)))
                self._heading_y.setValue(math.cos(math.radians(h)))
                self._heading_z.setValue(0.0)
        if "start_position" in params:
            pos = params["start_position"]
            if len(pos) >= 3:
                self._start_x.set_si_value(pos[0])
                self._start_y.set_si_value(pos[1])
                self._start_z.set_si_value(pos[2])
        if "perturbation" in params:
            p = params["perturbation"]
            enabled = params.get("perturbation_enabled", p is not None)
            self._perturbation_enabled.setChecked(enabled)
            if p is not None:
                self._sigma_u.setValue(p.get("sigma_u", 1.0))
                self._sigma_v.setValue(p.get("sigma_v", 1.0))
                self._sigma_w.setValue(p.get("sigma_w", 0.5))
        if "gps" in params:
            g = params["gps"]
            enabled = params.get("gps_enabled", g is not None)
            self._gps_enabled.setChecked(enabled)
            if g is not None:
                self._gps_accuracy.setValue(g.get("accuracy", 0.002))
                self._gps_rate.setValue(g.get("rate", 10.0))
        if "imu" in params:
            im = params["imu"]
            enabled = params.get("imu_enabled", im is not None)
            self._imu_enabled.setChecked(enabled)
            if im is not None:
                self._accel_noise.setValue(im.get("accel_noise", 0.0001))
                self._gyro_noise.setValue(im.get("gyro_noise", 0.00001))
                self._imu_rate.setValue(im.get("rate", 200.0))


# ---------------------------------------------------------------------------
# SceneParamEditor
# ---------------------------------------------------------------------------


class SceneParamEditor(QGroupBox):
    """Editor for scene origin and point target list."""

    params_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Scene Parameters", parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._origin_lat = _plain_spin(0.0, -90.0, 90.0, 0.01, "\u00b0")
        self._origin_lon = _plain_spin(0.0, -180.0, 180.0, 0.01, "\u00b0")
        self._origin_alt = UnitSpinBox(
            _DIST, "m", value=0.0, minimum=-1000.0, maximum=100000.0, step=10.0,
        )

        form.addRow("Origin Latitude:", self._origin_lat)
        form.addRow("Origin Longitude:", self._origin_lon)
        form.addRow("Origin Altitude:", self._origin_alt)

        self._origin_lat.valueChanged.connect(self.params_changed)
        self._origin_lon.valueChanged.connect(self.params_changed)
        self._origin_alt.value_changed.connect(self.params_changed)

        # Target table: columns = X(m), Y(m), Z(m), RCS(m²), Vx(m/s), Vy(m/s), Vz(m/s)
        self._target_table = QTableWidget(0, 7)
        self._target_table.setHorizontalHeaderLabels(
            ["X (m)", "Y (m)", "Z (m)", "RCS (m\u00b2)",
             "Vx (m/s)", "Vy (m/s)", "Vz (m/s)"]
        )
        header = self._target_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._target_table.cellChanged.connect(
            lambda _r, _c: self.params_changed.emit()
        )
        layout.addWidget(self._target_table)

        btn_row = QHBoxLayout()
        self._btn_add = QPushButton("Add Target")
        self._btn_remove = QPushButton("Remove Selected")
        self._btn_delete_all = QPushButton("Delete All")
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_remove)
        btn_row.addWidget(self._btn_delete_all)
        layout.addLayout(btn_row)

        self._btn_add.clicked.connect(self._add_target)
        self._btn_remove.clicked.connect(self._remove_selected)
        self._btn_delete_all.clicked.connect(self._delete_all_targets)

        layout.addWidget(
            QLabel("(Distributed targets: use Python API)")
        )

        # When the delegate finishes editing (Enter/Tab), clear selection
        delegate = self._target_table.itemDelegate()
        if delegate is not None:
            delegate.closeEditor.connect(self._on_editor_closed)

    def _on_editor_closed(self) -> None:
        self._target_table.clearSelection()
        self._target_table.setCurrentCell(-1, -1)
        self.params_changed.emit()

    def _add_target(self) -> None:
        row = self._target_table.rowCount()
        self._target_table.insertRow(row)
        for col, default in enumerate(
            ["1000.00", "0.00", "0.00", "1.00", "0.00", "0.00", "0.00"]
        ):
            self._target_table.setItem(row, col, QTableWidgetItem(default))
        self.params_changed.emit()

    def _add_target_at(self, x: float, y: float, z: float) -> None:
        row = self._target_table.rowCount()
        self._target_table.insertRow(row)
        for col, default in enumerate(
            [f"{x:.2f}", f"{y:.2f}", f"{z:.2f}", "1.00", "0.00", "0.00", "0.00"]
        ):
            self._target_table.setItem(row, col, QTableWidgetItem(default))
        self.params_changed.emit()

    def _remove_selected(self) -> None:
        rows = sorted(
            {idx.row() for idx in self._target_table.selectedIndexes()},
            reverse=True,
        )
        for r in rows:
            self._target_table.removeRow(r)
        self.params_changed.emit()

    def _delete_all_targets(self) -> None:
        self._target_table.setRowCount(0)
        self.params_changed.emit()

    def _read_targets(self) -> list[dict]:
        # Commit any cell currently being edited before reading
        self._target_table.setCurrentItem(None)
        targets = []
        for r in range(self._target_table.rowCount()):
            try:
                x = float(self._target_table.item(r, 0).text())
                y = float(self._target_table.item(r, 1).text())
                z = float(self._target_table.item(r, 2).text())
                rcs = float(self._target_table.item(r, 3).text())
                vx = float(self._target_table.item(r, 4).text())
                vy = float(self._target_table.item(r, 5).text())
                vz = float(self._target_table.item(r, 6).text())
                entry: dict = {"position": [x, y, z], "rcs": rcs}
                if vx != 0.0 or vy != 0.0 or vz != 0.0:
                    entry["velocity"] = [vx, vy, vz]
                else:
                    entry["velocity"] = None
                targets.append(entry)
            except (ValueError, AttributeError):
                continue
        return targets

    def get_params(self) -> dict:
        return {
            "origin_lat": self._origin_lat.value(),
            "origin_lon": self._origin_lon.value(),
            "origin_alt": self._origin_alt.si_value(),
            "targets": self._read_targets(),
        }

    def set_params(self, params: dict) -> None:
        if "origin_lat" in params:
            self._origin_lat.setValue(params["origin_lat"])
        if "origin_lon" in params:
            self._origin_lon.setValue(params["origin_lon"])
        if "origin_alt" in params:
            self._origin_alt.set_si_value(params["origin_alt"])
        if "targets" in params:
            self._target_table.setRowCount(0)
            for t in params["targets"]:
                row = self._target_table.rowCount()
                self._target_table.insertRow(row)
                pos = t.get("position", [0, 0, 0])
                rcs = t.get("rcs", 1.0)
                vel = t.get("velocity") or [0.0, 0.0, 0.0]
                for col, val in enumerate([*pos, rcs, *vel]):
                    self._target_table.setItem(
                        row, col, QTableWidgetItem(f"{val:.2f}")
                    )


# ---------------------------------------------------------------------------
# SimulationParamEditor
# ---------------------------------------------------------------------------


class SimulationParamEditor(QGroupBox):
    """Editor for simulation control parameters."""

    params_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Simulation Parameters", parent)
        form = QFormLayout(self)

        self._n_pulses = _int_spin(512, 1, 10_000_000)
        self._seed = _int_spin(42, 0, 2_147_483_647)
        self._near_range = UnitSpinBox(
            _DIST, "m", value=1350.0, minimum=0.0, maximum=1e8, step=100.0,
        )
        self._far_range = UnitSpinBox(
            _DIST, "m", value=1500.0, minimum=0.0, maximum=1e8, step=100.0,
        )

        # Sample rate
        self._sample_rate_auto = QCheckBox("Auto sample rate")
        self._sample_rate_auto.setChecked(True)
        self._sample_rate = UnitSpinBox(
            _FREQ, "MHz", value=300.0, minimum=0.001, maximum=999999.0, step=1.0,
        )
        self._sample_rate.setVisible(False)

        # Scene center (spotlight/scan-SAR)
        self._scene_center_x = UnitSpinBox(
            _DIST, "m", value=0.0, minimum=-1e8, maximum=1e8, step=10.0,
        )
        self._scene_center_y = UnitSpinBox(
            _DIST, "m", value=0.0, minimum=-1e8, maximum=1e8, step=10.0,
        )
        self._scene_center_z = UnitSpinBox(
            _DIST, "m", value=0.0, minimum=-1e8, maximum=1e8, step=10.0,
        )

        self._n_subswaths = _int_spin(3, 1, 20)
        self._burst_length = _int_spin(20, 1, 10000)

        form.addRow("Number of Pulses:", self._n_pulses)
        form.addRow("Random Seed:", self._seed)
        form.addRow("Near Range:", self._near_range)
        form.addRow("Far Range:", self._far_range)
        form.addRow(self._sample_rate_auto)
        form.addRow("Sample Rate:", self._sample_rate)
        self._scene_center_label = QLabel("Scene Center (spotlight/scan-SAR):")
        form.addRow(self._scene_center_label)
        form.addRow("Center X:", self._scene_center_x)
        form.addRow("Center Y:", self._scene_center_y)
        form.addRow("Center Z:", self._scene_center_z)
        form.addRow("Subswaths:", self._n_subswaths)
        form.addRow("Burst Length:", self._burst_length)

        # Toggle sample rate visibility
        self._sample_rate_auto.toggled.connect(self._on_auto_sr_toggled)

        self._n_pulses.valueChanged.connect(self.params_changed)
        self._seed.valueChanged.connect(self.params_changed)
        self._near_range.value_changed.connect(self.params_changed)
        self._far_range.value_changed.connect(self.params_changed)
        self._sample_rate.value_changed.connect(self.params_changed)
        self._sample_rate_auto.toggled.connect(
            lambda _: self.params_changed.emit()
        )
        for w in (self._scene_center_x, self._scene_center_y,
                  self._scene_center_z):
            w.value_changed.connect(self.params_changed)
        self._n_subswaths.valueChanged.connect(self.params_changed)
        self._burst_length.valueChanged.connect(self.params_changed)

    def _on_auto_sr_toggled(self, checked: bool) -> None:
        self._sample_rate.setVisible(not checked)
        form = self.findChild(QFormLayout)
        if form is not None:
            lbl = form.labelForField(self._sample_rate)
            if lbl is not None:
                lbl.setVisible(not checked)

    def get_params(self) -> dict:
        return {
            "n_pulses": self._n_pulses.value(),
            "seed": self._seed.value(),
            "swath_range": (
                self._near_range.si_value(),
                self._far_range.si_value(),
            ),
            "sample_rate": (
                None if self._sample_rate_auto.isChecked()
                else self._sample_rate.si_value()
            ),
            "scene_center": [
                self._scene_center_x.si_value(),
                self._scene_center_y.si_value(),
                self._scene_center_z.si_value(),
            ],
            "n_subswaths": self._n_subswaths.value(),
            "burst_length": self._burst_length.value(),
        }

    def set_params(self, params: dict) -> None:
        if "n_pulses" in params:
            self._n_pulses.setValue(params["n_pulses"])
        if "seed" in params:
            self._seed.setValue(params["seed"])
        if "swath_range" in params:
            near, far = params["swath_range"]
            self._near_range.set_si_value(near)
            self._far_range.set_si_value(far)
        if "sample_rate" in params:
            sr = params["sample_rate"]
            if sr is None:
                self._sample_rate_auto.setChecked(True)
            else:
                self._sample_rate_auto.setChecked(False)
                self._sample_rate.set_si_value(sr)
        if "scene_center" in params:
            sc = params["scene_center"]
            if len(sc) >= 3:
                self._scene_center_x.set_si_value(sc[0])
                self._scene_center_y.set_si_value(sc[1])
                self._scene_center_z.set_si_value(sc[2])
        if "n_subswaths" in params:
            self._n_subswaths.setValue(params["n_subswaths"])
        if "burst_length" in params:
            self._burst_length.setValue(params["burst_length"])


__all__ = [
    "UnitSpinBox",
    "AntennaParamEditor",
    "RadarParamEditor",
    "WaveformParamEditor",
    "PlatformParamEditor",
    "SceneParamEditor",
    "SimulationParamEditor",
]
