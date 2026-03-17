"""Parameter editor widgets for configuring SAR simulation parameters.

Each editor provides get_params() / set_params(dict) and emits params_changed
when any value is modified by the user.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pySimSAR.core.types import LookSide, PolarizationMode, RampType, SARMode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _double_spin(
    value: float = 0.0,
    minimum: float = 0.0,
    maximum: float = 1e15,
    decimals: int = 4,
    suffix: str = "",
    step: float = 1.0,
) -> QDoubleSpinBox:
    """Create a configured QDoubleSpinBox."""
    sb = QDoubleSpinBox()
    sb.setRange(minimum, maximum)
    sb.setDecimals(decimals)
    sb.setValue(value)
    sb.setSingleStep(step)
    if suffix:
        sb.setSuffix(suffix)
    return sb


def _int_spin(
    value: int = 0,
    minimum: int = 0,
    maximum: int = 10_000_000,
) -> QSpinBox:
    sb = QSpinBox()
    sb.setRange(minimum, maximum)
    sb.setValue(value)
    return sb


def _combo(items: list[str], current: str = "") -> QComboBox:
    cb = QComboBox()
    cb.addItems(items)
    if current and current in items:
        cb.setCurrentText(current)
    return cb


# ---------------------------------------------------------------------------
# RadarParamEditor
# ---------------------------------------------------------------------------


class RadarParamEditor(QGroupBox):
    """Editor for radar system parameters."""

    params_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Radar Parameters", parent)
        form = QFormLayout(self)

        self._carrier_freq = _double_spin(9.65e9, 1e6, 100e9, 6, " Hz", 1e8)
        self._prf = _double_spin(1000.0, 1.0, 100_000.0, 2, " Hz", 100.0)
        self._transmit_power = _double_spin(1000.0, 0.01, 1e6, 2, " W", 100.0)
        self._bandwidth = _double_spin(100e6, 1e3, 10e9, 2, " Hz", 1e6)
        self._polarization = _combo(
            [m.value for m in PolarizationMode], PolarizationMode.SINGLE.value
        )
        self._mode = _combo([m.value for m in SARMode], SARMode.STRIPMAP.value)
        self._look_side = _combo(
            [s.value for s in LookSide], LookSide.RIGHT.value
        )
        self._depression_angle = _double_spin(
            math.degrees(0.7854), 0.0, 90.0, 2, "\u00b0", 1.0
        )

        form.addRow("Carrier Frequency:", self._carrier_freq)
        form.addRow("PRF:", self._prf)
        form.addRow("Transmit Power:", self._transmit_power)
        form.addRow("Bandwidth:", self._bandwidth)
        form.addRow("Polarization:", self._polarization)
        form.addRow("SAR Mode:", self._mode)
        form.addRow("Look Side:", self._look_side)
        form.addRow("Depression Angle:", self._depression_angle)

        # Connect signals
        for w in (
            self._carrier_freq,
            self._prf,
            self._transmit_power,
            self._bandwidth,
            self._depression_angle,
        ):
            w.valueChanged.connect(self.params_changed)
        for w in (self._polarization, self._mode, self._look_side):
            w.currentTextChanged.connect(lambda _: self.params_changed.emit())

    def get_params(self) -> dict:
        return {
            "carrier_freq": self._carrier_freq.value(),
            "prf": self._prf.value(),
            "transmit_power": self._transmit_power.value(),
            "bandwidth": self._bandwidth.value(),
            "polarization": self._polarization.currentText(),
            "mode": self._mode.currentText(),
            "look_side": self._look_side.currentText(),
            "depression_angle": math.radians(self._depression_angle.value()),
        }

    def set_params(self, params: dict) -> None:
        if "carrier_freq" in params:
            self._carrier_freq.setValue(params["carrier_freq"])
        if "prf" in params:
            self._prf.setValue(params["prf"])
        if "transmit_power" in params:
            self._transmit_power.setValue(params["transmit_power"])
        if "bandwidth" in params:
            self._bandwidth.setValue(params["bandwidth"])
        if "polarization" in params:
            self._polarization.setCurrentText(str(params["polarization"]))
        if "mode" in params:
            self._mode.setCurrentText(str(params["mode"]))
        if "look_side" in params:
            self._look_side.setCurrentText(str(params["look_side"]))
        if "depression_angle" in params:
            self._depression_angle.setValue(
                math.degrees(params["depression_angle"])
            )


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
        self._bandwidth = _double_spin(100e6, 1e3, 10e9, 2, " Hz", 1e6)
        self._duty_cycle = _double_spin(0.1, 0.001, 1.0, 4, "", 0.01)
        self._ramp_type = _combo(
            [r.value for r in RampType], RampType.UP.value
        )

        form.addRow("Waveform Type:", self._waveform_type)
        form.addRow("Bandwidth:", self._bandwidth)
        form.addRow("Duty Cycle:", self._duty_cycle)
        form.addRow("Ramp Type:", self._ramp_type)

        # Show/hide fields based on waveform type
        self._waveform_type.currentTextChanged.connect(self._on_type_changed)
        self._on_type_changed(self._waveform_type.currentText())

        # Connect change signals
        self._bandwidth.valueChanged.connect(self.params_changed)
        self._duty_cycle.valueChanged.connect(self.params_changed)
        self._ramp_type.currentTextChanged.connect(
            lambda _: self.params_changed.emit()
        )
        self._waveform_type.currentTextChanged.connect(
            lambda _: self.params_changed.emit()
        )

    def _on_type_changed(self, wtype: str) -> None:
        is_lfm = wtype == "LFM"
        self._duty_cycle.setVisible(is_lfm)
        # Find the label for duty_cycle row and toggle it too
        form = self.findChild(QFormLayout)
        if form is not None:
            label = form.labelForField(self._duty_cycle)
            if label is not None:
                label.setVisible(is_lfm)
            label_ramp = form.labelForField(self._ramp_type)
            if label_ramp is not None:
                label_ramp.setVisible(not is_lfm)
        self._ramp_type.setVisible(not is_lfm)

    def get_params(self) -> dict:
        params: dict = {
            "waveform_type": self._waveform_type.currentText(),
            "bandwidth": self._bandwidth.value(),
        }
        if self._waveform_type.currentText() == "LFM":
            params["duty_cycle"] = self._duty_cycle.value()
        else:
            params["ramp_type"] = self._ramp_type.currentText()
        return params

    def set_params(self, params: dict) -> None:
        if "waveform_type" in params:
            self._waveform_type.setCurrentText(params["waveform_type"])
        if "bandwidth" in params:
            self._bandwidth.setValue(params["bandwidth"])
        if "duty_cycle" in params:
            self._duty_cycle.setValue(params["duty_cycle"])
        if "ramp_type" in params:
            self._ramp_type.setCurrentText(str(params["ramp_type"]))


# ---------------------------------------------------------------------------
# PlatformParamEditor
# ---------------------------------------------------------------------------


class PlatformParamEditor(QGroupBox):
    """Editor for platform motion parameters."""

    params_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Platform Parameters", parent)
        form = QFormLayout(self)

        self._velocity = _double_spin(100.0, 0.1, 50_000.0, 2, " m/s", 10.0)
        self._altitude = _double_spin(5000.0, 0.0, 100_000.0, 1, " m", 100.0)
        self._heading = _double_spin(0.0, 0.0, 360.0, 2, "\u00b0", 1.0)
        self._start_x = _double_spin(0.0, -1e8, 1e8, 2, " m", 100.0)
        self._start_y = _double_spin(0.0, -1e8, 1e8, 2, " m", 100.0)
        self._start_z = _double_spin(5000.0, 0.0, 100_000.0, 1, " m", 100.0)

        form.addRow("Velocity:", self._velocity)
        form.addRow("Altitude:", self._altitude)
        form.addRow("Heading:", self._heading)
        form.addRow("Start X:", self._start_x)
        form.addRow("Start Y:", self._start_y)
        form.addRow("Start Z:", self._start_z)

        for w in (
            self._velocity,
            self._altitude,
            self._heading,
            self._start_x,
            self._start_y,
            self._start_z,
        ):
            w.valueChanged.connect(self.params_changed)

    def get_params(self) -> dict:
        return {
            "velocity": self._velocity.value(),
            "altitude": self._altitude.value(),
            "heading": self._heading.value(),
            "start_position": [
                self._start_x.value(),
                self._start_y.value(),
                self._start_z.value(),
            ],
        }

    def set_params(self, params: dict) -> None:
        if "velocity" in params:
            self._velocity.setValue(params["velocity"])
        if "altitude" in params:
            self._altitude.setValue(params["altitude"])
        if "heading" in params:
            self._heading.setValue(params["heading"])
        if "start_position" in params:
            pos = params["start_position"]
            if len(pos) >= 3:
                self._start_x.setValue(pos[0])
                self._start_y.setValue(pos[1])
                self._start_z.setValue(pos[2])


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

        self._origin_lat = _double_spin(0.0, -90.0, 90.0, 6, "\u00b0", 0.01)
        self._origin_lon = _double_spin(0.0, -180.0, 180.0, 6, "\u00b0", 0.01)
        self._origin_alt = _double_spin(0.0, -1000.0, 100_000.0, 1, " m", 10.0)

        form.addRow("Origin Latitude:", self._origin_lat)
        form.addRow("Origin Longitude:", self._origin_lon)
        form.addRow("Origin Altitude:", self._origin_alt)

        for w in (self._origin_lat, self._origin_lon, self._origin_alt):
            w.valueChanged.connect(self.params_changed)

        # Target table: columns = X(m), Y(m), Z(m), RCS(m^2)
        self._target_table = QTableWidget(0, 4)
        self._target_table.setHorizontalHeaderLabels(
            ["X (m)", "Y (m)", "Z (m)", "RCS (m\u00b2)"]
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
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_remove)
        layout.addLayout(btn_row)

        self._btn_add.clicked.connect(self._add_target)
        self._btn_remove.clicked.connect(self._remove_selected)

    def _add_target(self) -> None:
        row = self._target_table.rowCount()
        self._target_table.insertRow(row)
        for col, default in enumerate(["0.0", "0.0", "0.0", "1.0"]):
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

    def _read_targets(self) -> list[dict]:
        targets = []
        for r in range(self._target_table.rowCount()):
            try:
                x = float(self._target_table.item(r, 0).text())
                y = float(self._target_table.item(r, 1).text())
                z = float(self._target_table.item(r, 2).text())
                rcs = float(self._target_table.item(r, 3).text())
                targets.append({"position": [x, y, z], "rcs": rcs})
            except (ValueError, AttributeError):
                continue
        return targets

    def get_params(self) -> dict:
        return {
            "origin_lat": self._origin_lat.value(),
            "origin_lon": self._origin_lon.value(),
            "origin_alt": self._origin_alt.value(),
            "targets": self._read_targets(),
        }

    def set_params(self, params: dict) -> None:
        if "origin_lat" in params:
            self._origin_lat.setValue(params["origin_lat"])
        if "origin_lon" in params:
            self._origin_lon.setValue(params["origin_lon"])
        if "origin_alt" in params:
            self._origin_alt.setValue(params["origin_alt"])
        if "targets" in params:
            self._target_table.setRowCount(0)
            for t in params["targets"]:
                row = self._target_table.rowCount()
                self._target_table.insertRow(row)
                pos = t.get("position", [0, 0, 0])
                rcs = t.get("rcs", 1.0)
                for col, val in enumerate([*pos, rcs]):
                    self._target_table.setItem(
                        row, col, QTableWidgetItem(str(val))
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

        self._n_pulses = _int_spin(256, 1, 10_000_000)
        self._seed = _int_spin(42, 0, 2_147_483_647)

        form.addRow("Number of Pulses:", self._n_pulses)
        form.addRow("Random Seed:", self._seed)

        self._n_pulses.valueChanged.connect(self.params_changed)
        self._seed.valueChanged.connect(self.params_changed)

    def get_params(self) -> dict:
        return {
            "n_pulses": self._n_pulses.value(),
            "seed": self._seed.value(),
        }

    def set_params(self, params: dict) -> None:
        if "n_pulses" in params:
            self._n_pulses.setValue(params["n_pulses"])
        if "seed" in params:
            self._seed.setValue(params["seed"])


__all__ = [
    "RadarParamEditor",
    "WaveformParamEditor",
    "PlatformParamEditor",
    "SceneParamEditor",
    "SimulationParamEditor",
]
