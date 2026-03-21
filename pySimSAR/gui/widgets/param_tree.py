"""Hierarchical parameter tree widget (Cadence Virtuoso style).

Replaces the flat sidebar with a two-column QTreeWidget:
  Column 0 — Parameter name
  Column 1 — Inline editor widget (via setItemWidget)

Node types:
  CATEGORY          Bold top-level, expandable
  GROUP             Sub-group, expandable
  PARAMETER         Leaf with inline editor
  ALGORITHM_SELECTOR  Dropdown that dynamically loads child params
"""

from __future__ import annotations

import math
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pySimSAR.core.types import LookSide, PolarizationMode, RampType, SARMode
from pySimSAR.gui.widgets._algo_schemas import ALGORITHM_SCHEMAS
from pySimSAR.gui.widgets.param_editor import (
    UnitSpinBox,
    _CleanDoubleSpinBox,
    _combo,
    _int_spin,
    _plain_spin,
)

# ---------------------------------------------------------------------------
# Unit dictionaries (mirrors param_editor but kept local for clarity)
# ---------------------------------------------------------------------------

_FREQ = {"GHz": 1e9, "MHz": 1e6, "kHz": 1e3, "Hz": 1.0}
_POWER = {"kW": 1e3, "W": 1.0, "mW": 1e-3}
_DIST = {"km": 1e3, "m": 1.0}
_SPEED = {"m/s": 1.0, "km/h": 1.0 / 3.6}
_PRF_UNITS = {"kHz": 1e3, "Hz": 1.0}

# ---------------------------------------------------------------------------
# Tooltip descriptions for every parameter
# ---------------------------------------------------------------------------

_TOOLTIPS: dict[str, str] = {
    # Simulation
    "simulation.seed": "Random seed for reproducible noise generation",
    "simulation.near_range": "Minimum slant range for the receive window (m)",
    "simulation.far_range": "Maximum slant range for the receive window (m)",
    # SAR Imaging
    "imaging.mode": "SAR imaging mode: stripmap, spotlight, or ScanSAR",
    "imaging.look_side": "Antenna look direction: left or right of flight track",
    "imaging.depression_angle": "Depression angle from horizontal to beam center (degrees)",
    "imaging.scene_center_x": "Scene center X coordinate for beam pointing (spotlight/ScanSAR)",
    "imaging.scene_center_y": "Scene center Y coordinate for beam pointing (spotlight/ScanSAR)",
    "imaging.scene_center_z": "Scene center Z coordinate for beam pointing (spotlight/ScanSAR)",
    "imaging.n_subswaths": "Number of sub-swaths (ScanSAR mode)",
    "imaging.burst_length": "Pulses per burst (ScanSAR mode)",
    "imaging.squint_angle": "Antenna squint angle from broadside (degrees). 0 = perpendicular to flight track",
    # Radar
    "radar.carrier_freq": "RF carrier frequency. Determines wavelength = c / f_c",
    "radar.transmit_power": "Peak transmit power at the antenna feed (W)",
    "radar.receiver_gain_dB": "Total receiver chain gain (dB)",
    "radar.system_losses": "Aggregate system losses: feed, radome, processing (dB)",
    "radar.noise_figure": "Receiver noise figure (dB). Lower = better sensitivity",
    "radar.reference_temp": "Reference noise temperature (K), typically 290 K",
    "radar.polarization": "Polarization mode: single (HH), dual (HH+HV), or quad",
    "radar.sample_rate_auto": "When checked, sample rate is auto-derived from bandwidth",
    "radar.sample_rate": "ADC sample rate. Must be >= bandwidth for Nyquist. Default: auto",
    "waveform.prf": "Pulse Repetition Frequency — sets azimuth sampling rate (Hz)",
    # Antenna
    "antenna.preset": "Antenna pattern type: flat, sinc, or Gaussian taper",
    "antenna.az_beamwidth": "Azimuth 3-dB beamwidth (degrees)",
    "antenna.el_beamwidth": "Elevation 3-dB beamwidth (degrees)",
    # Waveform
    "waveform.waveform_type": "Pulse type: LFM (pulsed chirp) or FMCW (continuous wave)",
    "waveform.bandwidth": "Chirp bandwidth — determines range resolution = c / (2B)",
    "waveform.duty_cycle": "Fraction of PRI occupied by the pulse (0-1)",
    "waveform.fmcw_duty_cycle": "FMCW ramp duty cycle (typically 1.0)",
    "waveform.ramp_type": "FMCW ramp direction: up, down, or triangular",
    "waveform.window": "Spectral window for sidelobe control (None = rectangular)",
    "waveform.phase_noise_enabled": "Enable phase noise PSD model",
    "waveform.flicker_fm": "Flicker FM noise level (dBc/Hz)",
    "waveform.white_fm": "White FM noise level (dBc/Hz)",
    "waveform.flicker_pm": "Flicker PM noise level (dBc/Hz)",
    "waveform.white_floor": "White noise floor (dBc/Hz)",
    # Platform
    "platform.flight_path_mode": "start_stop: specify endpoints; heading_time: specify direction + duration",
    "platform.start_x": "Flight path start position X (m)",
    "platform.start_y": "Flight path start position Y (m)",
    "platform.start_z": "Flight path altitude (m)",
    "platform.stop_x": "Flight path stop position X (m)",
    "platform.stop_y": "Flight path stop position Y (m)",
    "platform.stop_z": "Flight path stop altitude (m)",
    "platform.heading_x": "Heading direction vector X component",
    "platform.heading_y": "Heading direction vector Y component",
    "platform.heading_z": "Heading direction vector Z component",
    "platform.velocity": "Platform ground speed (m/s)",
    "platform.flight_time": "Total flight duration (s)",
    "platform.perturbation_enabled": "Enable Dryden turbulence model for motion errors",
    "platform.sigma_u": "Turbulence intensity along-track (m/s)",
    "platform.sigma_v": "Turbulence intensity cross-track (m/s)",
    "platform.sigma_w": "Turbulence intensity vertical (m/s)",
    "platform.gps_enabled": "Enable GPS sensor for navigation solution",
    "platform.gps_accuracy": "GPS position accuracy RMS (m)",
    "platform.gps_rate": "GPS update rate (Hz)",
    "platform.imu_enabled": "Enable IMU sensor for motion measurement",
    "platform.accel_noise": "Accelerometer noise density (m/s\u00b2/\u221aHz)",
    "platform.gyro_noise": "Gyroscope noise density (rad/s/\u221aHz)",
    "platform.imu_rate": "IMU sample rate (Hz)",
    # Scene
    "scene.origin_lat": "Scene origin latitude (degrees)",
    "scene.origin_lon": "Scene origin longitude (degrees)",
    "scene.origin_alt": "Scene origin altitude above WGS-84 ellipsoid (m)",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BOLD_FONT = QFont()
_BOLD_FONT.setBold(True)

def _category_item(label: str) -> QTreeWidgetItem:
    """Top-level bold category node."""
    item = QTreeWidgetItem([label])
    item.setFont(0, _BOLD_FONT)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
    return item


def _group_item(label: str) -> QTreeWidgetItem:
    """Sub-group node (expandable, not editable)."""
    item = QTreeWidgetItem([label])
    item.setFont(0, _BOLD_FONT)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
    return item


def _param_item(label: str) -> QTreeWidgetItem:
    """Leaf parameter node."""
    item = QTreeWidgetItem([label])
    item.setFlags(
        item.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsEditable
    )
    return item


# ---------------------------------------------------------------------------
# Point Target Editor Dialog
# ---------------------------------------------------------------------------


class PointTargetDialog(QDialog):
    """Dialog for editing point targets in a table (X, Y, Z, RCS, Vx, Vy, Vz)."""

    def __init__(self, targets: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Point Targets")
        self.setMinimumSize(650, 400)

        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["X (m)", "Y (m)", "Z (m)", "RCS (m\u00b2)",
             "Vx (m/s)", "Vy (m/s)", "Vz (m/s)"]
        )
        header = self._table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("Add Target")
        btn_remove = QPushButton("Remove Selected")
        btn_remove_all = QPushButton("Remove All")
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addWidget(btn_remove_all)
        layout.addLayout(btn_row)

        btn_add.clicked.connect(self._add_row)
        btn_remove.clicked.connect(self._remove_selected)
        btn_remove_all.clicked.connect(self._remove_all)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Populate
        for t in targets:
            self._add_target(t)

    def _add_row(self) -> None:
        self._add_target({"position": [1000, 0, 0], "rcs": 1.0})

    def _add_target(self, t: dict) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        pos = t.get("position", [0, 0, 0])
        vel = t.get("velocity") or [0, 0, 0]
        vals = [pos[0], pos[1], pos[2], t.get("rcs", 1.0), vel[0], vel[1], vel[2]]
        for col, v in enumerate(vals):
            self._table.setItem(row, col, QTableWidgetItem(f"{v:.4g}"))

    def _remove_selected(self) -> None:
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()}, reverse=True)
        for r in rows:
            self._table.removeRow(r)

    def _remove_all(self) -> None:
        self._table.setRowCount(0)

    def get_targets(self) -> list[dict]:
        self._table.setCurrentItem(None)
        targets = []
        for r in range(self._table.rowCount()):
            try:
                x = float(self._table.item(r, 0).text())
                y = float(self._table.item(r, 1).text())
                z = float(self._table.item(r, 2).text())
                rcs = float(self._table.item(r, 3).text())
                t: dict = {"position": [x, y, z], "rcs": rcs}
                vx = float(self._table.item(r, 4).text())
                vy = float(self._table.item(r, 5).text())
                vz = float(self._table.item(r, 6).text())
                if vx != 0 or vy != 0 or vz != 0:
                    t["velocity"] = [vx, vy, vz]
                targets.append(t)
            except (ValueError, AttributeError):
                continue
        return targets


# ---------------------------------------------------------------------------
# ParameterTreeWidget
# ---------------------------------------------------------------------------


class ParameterTreeWidget(QWidget):
    """Hierarchical inline-editing parameter tree.

    Signals
    -------
    parameter_changed(key, value)
        Emitted whenever any parameter changes.  *key* is a dot-path such
        as ``"radar.carrier_freq"``.
    tree_ready
        Emitted once the tree has been fully populated.
    """

    parameter_changed = pyqtSignal(str, object)
    tree_ready = pyqtSignal()

    # -----------------------------------------------------------------
    # Construction
    # -----------------------------------------------------------------

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._widgets: dict[str, QWidget] = {}
        self._items: dict[str, QTreeWidgetItem] = {}
        self._target_data: list[dict] = []
        self._distributed_target_data: list[dict] = []
        self._distributed_target_items: list[QTreeWidgetItem] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Search box ---
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter parameters\u2026")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_filter_text_changed)
        layout.addWidget(self._search)

        # --- Tree widget ---
        self._tree = QTreeWidget()
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Parameter", "Value"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(12)
        header = self._tree.header()
        if header is not None:
            header.setStretchLastSection(True)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._tree)

        # --- Populate categories ---
        self._build_scene()
        self._build_platform()
        self._build_radar()
        self._build_antenna()
        self._build_waveform()
        self._build_sar_imaging()
        self._build_simulation()
        self._build_processing()

        # Expand all top-level categories by default
        self._tree.expandAll()

        # Apply initial visibility rules
        self._on_waveform_type_changed(self._w("waveform.waveform_type").currentText())
        self._on_window_changed(self._w("waveform.window").currentText())
        self._on_sample_rate_auto_toggled(self._w("radar.sample_rate_auto").isChecked())
        self._on_flight_path_mode_changed(self._w("platform.flight_path_mode").currentText())
        self._on_phase_noise_toggled(self._w("waveform.phase_noise_enabled").isChecked())
        self._on_perturbation_toggled(self._w("platform.perturbation_enabled").isChecked())
        self._on_gps_toggled(self._w("platform.gps_enabled").isChecked())
        self._on_imu_toggled(self._w("platform.imu_enabled").isChecked())

        self.tree_ready.emit()

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _w(self, key: str) -> Any:
        """Shortcut to retrieve a widget by dot-path key."""
        return self._widgets[key]

    def _register(
        self,
        parent: QTreeWidgetItem,
        key: str,
        label: str,
        widget: QWidget,
    ) -> QTreeWidgetItem:
        """Create a leaf item, attach *widget* in column 1, and register both."""
        item = _param_item(label)
        parent.addChild(item)
        self._tree.setItemWidget(item, 1, widget)
        self._widgets[key] = widget
        self._items[key] = item
        # Apply tooltip if available
        tip = _TOOLTIPS.get(key)
        if tip:
            item.setToolTip(0, tip)
            item.setToolTip(1, tip)
            widget.setToolTip(tip)
        return item

    def _emit_change(self, key: str) -> None:
        """Emit ``parameter_changed`` with the current widget value."""
        w = self._widgets.get(key)
        if w is None:
            return
        val: object = None
        if isinstance(w, UnitSpinBox):
            val = w.si_value()
        elif isinstance(w, QCheckBox):
            val = w.isChecked()
        elif isinstance(w, QComboBox):
            val = w.currentText()
        elif isinstance(w, QSpinBox):
            val = w.value()
        elif isinstance(w, (_CleanDoubleSpinBox, QDoubleSpinBox)):
            val = w.value()
        self.parameter_changed.emit(key, val)

    def _connect_spin(self, key: str, widget: QDoubleSpinBox | QSpinBox) -> None:
        widget.valueChanged.connect(lambda _v, k=key: self._emit_change(k))

    def _connect_unit(self, key: str, widget: UnitSpinBox) -> None:
        widget.value_changed.connect(lambda k=key: self._emit_change(k))

    def _connect_combo(self, key: str, widget: QComboBox) -> None:
        widget.currentTextChanged.connect(lambda _t, k=key: self._emit_change(k))

    def _connect_check(self, key: str, widget: QCheckBox) -> None:
        widget.toggled.connect(lambda _c, k=key: self._emit_change(k))

    # -----------------------------------------------------------------
    # Visibility helpers
    # -----------------------------------------------------------------

    def _set_visible(self, key: str, visible: bool) -> None:
        item = self._items.get(key)
        if item is not None:
            item.setHidden(not visible)

    def _set_group_visible(self, keys: list[str], visible: bool) -> None:
        for k in keys:
            self._set_visible(k, visible)

    # -----------------------------------------------------------------
    # 1. Simulation
    # -----------------------------------------------------------------

    def _build_simulation(self) -> None:
        cat = _category_item("Simulation")
        self._tree.addTopLevelItem(cat)
        self._items["simulation"] = cat

        # seed
        w = _int_spin(42, 0, 2_147_483_647)
        self._register(cat, "simulation.seed", "Seed", w)
        self._connect_spin("simulation.seed", w)

        # near_range
        w = UnitSpinBox(_DIST, "m", value=1350.0, minimum=0.0, maximum=1e8, step=100.0)
        self._register(cat, "simulation.near_range", "Near Range", w)
        self._connect_unit("simulation.near_range", w)

        # far_range
        w = UnitSpinBox(_DIST, "m", value=1500.0, minimum=0.0, maximum=1e8, step=100.0)
        self._register(cat, "simulation.far_range", "Far Range", w)
        self._connect_unit("simulation.far_range", w)

    # -----------------------------------------------------------------
    # 2. SAR Imaging
    # -----------------------------------------------------------------

    def _build_sar_imaging(self) -> None:
        cat = _category_item("SAR Imaging")
        self._tree.addTopLevelItem(cat)
        self._items["imaging"] = cat

        # SAR mode
        w = _combo([m.value for m in SARMode], SARMode.STRIPMAP.value)
        self._register(cat, "imaging.mode", "SAR Mode", w)
        self._connect_combo("imaging.mode", w)
        w.currentTextChanged.connect(self._on_mode_changed)

        # look_side
        w = _combo([s.value for s in LookSide], LookSide.RIGHT.value)
        self._register(cat, "imaging.look_side", "Look Side", w)
        self._connect_combo("imaging.look_side", w)

        # depression_angle
        w = _plain_spin(45.0, 0.0, 90.0, 1.0, "\u00b0")
        self._register(cat, "imaging.depression_angle", "Depression Angle", w)
        self._connect_spin("imaging.depression_angle", w)

        # squint_angle
        w = _plain_spin(0.0, -90.0, 90.0, 1.0, "\u00b0")
        self._register(cat, "imaging.squint_angle", "Squint Angle", w)
        self._connect_spin("imaging.squint_angle", w)

        # scene_center (visible only for spotlight/ScanSAR)
        for axis, default in [("x", 0.0), ("y", 0.0), ("z", 0.0)]:
            w = UnitSpinBox(_DIST, "m", value=default, minimum=-1e8, maximum=1e8, step=10.0)
            key = f"imaging.scene_center_{axis}"
            self._register(cat, key, f"Scene Center {axis.upper()}", w)
            self._connect_unit(key, w)

        # n_subswaths (ScanSAR only)
        w = _int_spin(3, 1, 20)
        self._register(cat, "imaging.n_subswaths", "Subswaths", w)
        self._connect_spin("imaging.n_subswaths", w)

        # burst_length (ScanSAR only)
        w = _int_spin(20, 1, 10000)
        self._register(cat, "imaging.burst_length", "Burst Length", w)
        self._connect_spin("imaging.burst_length", w)

        # Apply initial mode constraints
        self._on_mode_changed(SARMode.STRIPMAP.value)

    def _on_mode_changed(self, mode: str) -> None:
        self.set_mode_constraints(mode)

    def _on_sample_rate_auto_toggled(self, checked: bool) -> None:
        self._set_visible("radar.sample_rate", not checked)

    # -----------------------------------------------------------------
    # 3. Radar
    # -----------------------------------------------------------------

    def _build_radar(self) -> None:
        cat = _category_item("Radar")
        self._tree.addTopLevelItem(cat)
        self._items["radar"] = cat

        # carrier_freq
        w = UnitSpinBox(_FREQ, "GHz", value=9.65, minimum=0.001, maximum=999.0, step=0.01)
        self._register(cat, "radar.carrier_freq", "Carrier Frequency", w)
        self._connect_unit("radar.carrier_freq", w)

        # transmit_power
        w = UnitSpinBox(_POWER, "W", value=1.0, minimum=0.01, maximum=999999.0, step=0.1)
        self._register(cat, "radar.transmit_power", "Transmit Power", w)
        self._connect_unit("radar.transmit_power", w)

        # receiver_gain_dB
        w = _plain_spin(30.0, 0.0, 120.0, 1.0, " dB")
        self._register(cat, "radar.receiver_gain_dB", "Receiver Gain", w)
        self._connect_spin("radar.receiver_gain_dB", w)

        # system_losses
        w = _plain_spin(2.0, 0.0, 60.0, 0.5, " dB")
        self._register(cat, "radar.system_losses", "System Losses", w)
        self._connect_spin("radar.system_losses", w)

        # noise_figure
        w = _plain_spin(3.0, 0.0, 30.0, 0.5, " dB")
        self._register(cat, "radar.noise_figure", "Noise Figure", w)
        self._connect_spin("radar.noise_figure", w)

        # reference_temp
        w = _plain_spin(290.0, 1.0, 10000.0, 10.0, " K")
        self._register(cat, "radar.reference_temp", "Reference Temp", w)
        self._connect_spin("radar.reference_temp", w)

        # polarization
        w = _combo([m.value for m in PolarizationMode], PolarizationMode.SINGLE.value)
        self._register(cat, "radar.polarization", "Polarization", w)
        self._connect_combo("radar.polarization", w)

        # sample_rate_auto
        cb = QCheckBox()
        cb.setChecked(True)
        self._register(cat, "radar.sample_rate_auto", "Auto Sample Rate", cb)
        self._connect_check("radar.sample_rate_auto", cb)
        cb.toggled.connect(self._on_sample_rate_auto_toggled)

        # sample_rate
        w = UnitSpinBox(_FREQ, "MHz", value=300.0, minimum=0.001, maximum=999999.0, step=1.0)
        self._register(cat, "radar.sample_rate", "Sample Rate", w)
        self._connect_unit("radar.sample_rate", w)

    # -----------------------------------------------------------------
    # 4. Antenna
    # -----------------------------------------------------------------

    def _build_antenna(self) -> None:
        cat = _category_item("Antenna")
        self._tree.addTopLevelItem(cat)
        self._items["antenna"] = cat

        w = _combo(["flat", "sinc", "gaussian"], "flat")
        self._register(cat, "antenna.preset", "Preset", w)
        self._connect_combo("antenna.preset", w)

        w = _plain_spin(10.0, 0.01, 180.0, 0.5, "\u00b0")
        self._register(cat, "antenna.az_beamwidth", "Az Beamwidth", w)
        self._connect_spin("antenna.az_beamwidth", w)

        w = _plain_spin(10.0, 0.01, 180.0, 0.5, "\u00b0")
        self._register(cat, "antenna.el_beamwidth", "El Beamwidth", w)
        self._connect_spin("antenna.el_beamwidth", w)



    # -----------------------------------------------------------------
    # 4. Waveform
    # -----------------------------------------------------------------

    def _build_waveform(self) -> None:
        cat = _category_item("Waveform")
        self._tree.addTopLevelItem(cat)
        self._items["waveform"] = cat

        # prf
        w = UnitSpinBox(_PRF_UNITS, "Hz", value=1000.0, minimum=1.0, maximum=999999.0, step=100.0)
        self._register(cat, "waveform.prf", "PRF", w)
        self._connect_unit("waveform.prf", w)

        # waveform_type
        w = _combo(["LFM", "FMCW"], "LFM")
        self._register(cat, "waveform.waveform_type", "Waveform Type", w)
        self._connect_combo("waveform.waveform_type", w)
        w.currentTextChanged.connect(self._on_waveform_type_changed)

        # bandwidth
        w = UnitSpinBox(_FREQ, "MHz", value=100.0, minimum=0.001, maximum=99999.0, step=1.0)
        self._register(cat, "waveform.bandwidth", "Bandwidth", w)
        self._connect_unit("waveform.bandwidth", w)

        # duty_cycle (LFM)
        w = _plain_spin(0.01, 0.001, 1.0, 0.01)
        self._register(cat, "waveform.duty_cycle", "Duty Cycle", w)
        self._connect_spin("waveform.duty_cycle", w)

        # fmcw_duty_cycle
        w = _plain_spin(1.0, 0.001, 1.0, 0.01)
        self._register(cat, "waveform.fmcw_duty_cycle", "FMCW Duty Cycle", w)
        self._connect_spin("waveform.fmcw_duty_cycle", w)

        # ramp_type (FMCW)
        w = _combo([r.value for r in RampType], RampType.UP.value)
        self._register(cat, "waveform.ramp_type", "Ramp Type", w)
        self._connect_combo("waveform.ramp_type", w)

        # window
        w = _combo(["(None)", "hamming", "hanning", "blackman", "kaiser"], "(None)")
        self._register(cat, "waveform.window", "Window", w)
        self._connect_combo("waveform.window", w)
        w.currentTextChanged.connect(self._on_window_changed)

        # kaiser beta (shown only when window == "kaiser")
        w = _plain_spin(6.0, 0.0, 40.0, 0.5, "")
        self._register(cat, "waveform.kaiser_beta", "Kaiser \u03b2", w)
        self._connect_spin("waveform.kaiser_beta", w)

        # --- Phase Noise group ---
        grp = _group_item("Phase Noise")
        cat.addChild(grp)
        self._items["waveform.phase_noise"] = grp

        cb = QCheckBox()
        cb.setChecked(False)
        self._tree.setItemWidget(grp, 1, cb)
        self._widgets["waveform.phase_noise_enabled"] = cb
        self._items["waveform.phase_noise_enabled"] = grp
        self._connect_check("waveform.phase_noise_enabled", cb)
        cb.toggled.connect(self._on_phase_noise_toggled)

        for key_suffix, label, default in [
            ("flicker_fm", "Flicker FM", -80.0),
            ("white_fm", "White FM", -100.0),
            ("flicker_pm", "Flicker PM", -120.0),
            ("white_floor", "White Floor", -150.0),
        ]:
            w = _plain_spin(default, -200.0, 0.0, 1.0, " dBc/Hz")
            full_key = f"waveform.{key_suffix}"
            self._register(grp, full_key, label, w)
            self._connect_spin(full_key, w)

    def _on_waveform_type_changed(self, wtype: str) -> None:
        is_lfm = wtype == "LFM"
        self._set_visible("waveform.duty_cycle", is_lfm)
        self._set_visible("waveform.fmcw_duty_cycle", not is_lfm)
        self._set_visible("waveform.ramp_type", not is_lfm)

    def _on_window_changed(self, text: str) -> None:
        self._set_visible("waveform.kaiser_beta", text == "kaiser")

    def _on_phase_noise_toggled(self, checked: bool) -> None:
        for suffix in ("flicker_fm", "white_fm", "flicker_pm", "white_floor"):
            self._set_visible(f"waveform.{suffix}", checked)

    # -----------------------------------------------------------------
    # 5. Platform
    # -----------------------------------------------------------------

    def _build_platform(self) -> None:
        cat = _category_item("Platform")
        self._tree.addTopLevelItem(cat)
        self._items["platform"] = cat

        # --- Flight Path group ---
        grp_fp = _group_item("Flight Path")
        cat.addChild(grp_fp)
        self._items["platform.flight_path"] = grp_fp

        w = _combo(["heading_time", "start_stop"], "heading_time")
        self._register(grp_fp, "platform.flight_path_mode", "Mode", w)
        self._connect_combo("platform.flight_path_mode", w)
        w.currentTextChanged.connect(self._on_flight_path_mode_changed)

        for axis, default in [("x", 0.0), ("y", -25.0), ("z", 1000.0)]:
            mn = 0.0 if axis == "z" else -1e8
            mx = 100000.0 if axis == "z" else 1e8
            w = UnitSpinBox(_DIST, "m", value=default, minimum=mn, maximum=mx, step=100.0)
            key = f"platform.start_{axis}"
            self._register(grp_fp, key, f"Start {axis.upper()}", w)
            self._connect_unit(key, w)

        for axis in ("x", "y", "z"):
            w = UnitSpinBox(_DIST, "m", value=0.0, minimum=-1e8, maximum=1e8, step=100.0)
            key = f"platform.stop_{axis}"
            self._register(grp_fp, key, f"Stop {axis.upper()}", w)
            self._connect_unit(key, w)

        for axis, default in [("x", 0.0), ("y", 1.0), ("z", 0.0)]:
            w = _plain_spin(default, -1.0, 1.0, 0.1)
            key = f"platform.heading_{axis}"
            self._register(grp_fp, key, f"Heading {axis.upper()}", w)
            self._connect_spin(key, w)

        w = UnitSpinBox(_SPEED, "m/s", value=100.0, minimum=0.1, maximum=50000.0, step=10.0)
        self._register(grp_fp, "platform.velocity", "Velocity", w)
        self._connect_unit("platform.velocity", w)

        w = _plain_spin(0.5, 0.001, 1e6, 0.1, " s")
        self._register(grp_fp, "platform.flight_time", "Flight Time", w)
        self._connect_spin("platform.flight_time", w)

        # --- Turbulence group ---
        grp_turb = _group_item("Turbulence")
        cat.addChild(grp_turb)
        self._items["platform.turbulence"] = grp_turb

        cb = QCheckBox()
        cb.setChecked(False)
        self._tree.setItemWidget(grp_turb, 1, cb)
        self._widgets["platform.perturbation_enabled"] = cb
        self._items["platform.perturbation_enabled"] = grp_turb
        self._connect_check("platform.perturbation_enabled", cb)
        cb.toggled.connect(self._on_perturbation_toggled)

        for suffix, default in [("sigma_u", 1.0), ("sigma_v", 1.0), ("sigma_w", 0.5)]:
            w = _plain_spin(default, 0.0, 100.0, 0.1, " m/s")
            key = f"platform.{suffix}"
            self._register(grp_turb, key, suffix.replace("_", " ").title(), w)
            self._connect_spin(key, w)

        # --- GPS Sensor group ---
        grp_gps = _group_item("GPS Sensor")
        cat.addChild(grp_gps)
        self._items["platform.gps_group"] = grp_gps

        cb = QCheckBox()
        cb.setChecked(False)
        self._tree.setItemWidget(grp_gps, 1, cb)
        self._widgets["platform.gps_enabled"] = cb
        self._items["platform.gps_enabled"] = grp_gps
        self._connect_check("platform.gps_enabled", cb)
        cb.toggled.connect(self._on_gps_toggled)

        w = _plain_spin(0.002, 0.0, 100.0, 0.001, " m")
        self._register(grp_gps, "platform.gps_accuracy", "Accuracy", w)
        self._connect_spin("platform.gps_accuracy", w)

        w = _plain_spin(10.0, 0.1, 1000.0, 1.0, " Hz")
        self._register(grp_gps, "platform.gps_rate", "Rate", w)
        self._connect_spin("platform.gps_rate", w)

        # --- IMU Sensor group ---
        grp_imu = _group_item("IMU Sensor")
        cat.addChild(grp_imu)
        self._items["platform.imu_group"] = grp_imu

        cb = QCheckBox()
        cb.setChecked(False)
        self._tree.setItemWidget(grp_imu, 1, cb)
        self._widgets["platform.imu_enabled"] = cb
        self._items["platform.imu_enabled"] = grp_imu
        self._connect_check("platform.imu_enabled", cb)
        cb.toggled.connect(self._on_imu_toggled)

        w = _plain_spin(0.0001, 0.0, 10.0, 0.0001, " m/s\u00b2/\u221aHz")
        self._register(grp_imu, "platform.accel_noise", "Accel Noise", w)
        self._connect_spin("platform.accel_noise", w)

        w = _plain_spin(0.00001, 0.0, 1.0, 0.000001, " rad/s/\u221aHz")
        self._register(grp_imu, "platform.gyro_noise", "Gyro Noise", w)
        self._connect_spin("platform.gyro_noise", w)

        w = _plain_spin(200.0, 1.0, 10000.0, 10.0, " Hz")
        self._register(grp_imu, "platform.imu_rate", "Rate", w)
        self._connect_spin("platform.imu_rate", w)

    def _on_flight_path_mode_changed(self, mode: str) -> None:
        is_start_stop = mode == "start_stop"
        for axis in ("x", "y", "z"):
            self._set_visible(f"platform.stop_{axis}", is_start_stop)
            self._set_visible(f"platform.heading_{axis}", not is_start_stop)
        self._set_visible("platform.flight_time", not is_start_stop)

    def _on_perturbation_toggled(self, checked: bool) -> None:
        grp = self._items["platform.turbulence"]
        for i in range(grp.childCount()):
            child = grp.child(i)
            if child is not None:
                child.setHidden(not checked)

    def _on_gps_toggled(self, checked: bool) -> None:
        grp = self._items["platform.gps_group"]
        for i in range(grp.childCount()):
            child = grp.child(i)
            if child is not None:
                child.setHidden(not checked)

    def _on_imu_toggled(self, checked: bool) -> None:
        grp = self._items["platform.imu_group"]
        for i in range(grp.childCount()):
            child = grp.child(i)
            if child is not None:
                child.setHidden(not checked)

    def _on_proc_step_toggled(self, step_key: str, checked: bool) -> None:
        """Show/hide algorithm combo and params for an optional processing step."""
        parent_item = self._items[f"processing.{step_key}"]
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child is not None:
                child.setHidden(not checked)

    def _on_moco_toggled(self, checked: bool) -> None:
        """Auto-enable perturbation and GPS when MoCo is enabled."""
        if checked:
            perturb_cb = self._w("platform.perturbation_enabled")
            if not perturb_cb.isChecked():
                perturb_cb.setChecked(True)
            gps_cb = self._w("platform.gps_enabled")
            if not gps_cb.isChecked():
                gps_cb.setChecked(True)

    # -----------------------------------------------------------------
    # 6. Scene
    # -----------------------------------------------------------------

    def _build_scene(self) -> None:
        cat = _category_item("Scene")
        self._tree.addTopLevelItem(cat)
        self._items["scene"] = cat

        w = _plain_spin(0.0, -90.0, 90.0, 0.01, "\u00b0")
        self._register(cat, "scene.origin_lat", "Origin Latitude", w)
        self._connect_spin("scene.origin_lat", w)

        w = _plain_spin(0.0, -180.0, 180.0, 0.01, "\u00b0")
        self._register(cat, "scene.origin_lon", "Origin Longitude", w)
        self._connect_spin("scene.origin_lon", w)

        w = UnitSpinBox(_DIST, "m", value=0.0, minimum=-1000.0, maximum=100000.0, step=10.0)
        self._register(cat, "scene.origin_alt", "Origin Altitude", w)
        self._connect_unit("scene.origin_alt", w)

        # Point targets — group with Edit button
        grp_pt = _group_item("Point Targets")
        cat.addChild(grp_pt)
        self._items["scene.point_targets"] = grp_pt

        self._target_count_item = _param_item("Count")
        grp_pt.addChild(self._target_count_item)
        self._items["scene.targets_info"] = self._target_count_item
        self._target_count_item.setText(1, "0 targets")

        btn_item = QTreeWidgetItem()
        grp_pt.addChild(btn_item)
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_edit = QPushButton("Edit Targets...")
        btn_layout.addWidget(btn_edit)
        self._tree.setItemWidget(btn_item, 1, btn_container)
        btn_item.setText(0, "")
        btn_edit.clicked.connect(self._open_point_target_editor)

        # --- Distributed Targets group ---
        grp_dt = _group_item("Distributed Targets")
        cat.addChild(grp_dt)
        self._items["scene.distributed_targets"] = grp_dt
        self._dt_group = grp_dt

        # Add/Remove buttons (embedded in a tree item)
        btn_item = QTreeWidgetItem()
        grp_dt.addChild(btn_item)
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_add = QPushButton("Add")
        btn_remove = QPushButton("Remove")
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        self._tree.setItemWidget(btn_item, 1, btn_container)
        btn_item.setText(0, "")
        self._dt_btn_item = btn_item

        btn_add.clicked.connect(self._add_distributed_target)
        btn_remove.clicked.connect(self._remove_distributed_target)

        self._dt_count_item = _param_item("Count")
        grp_dt.addChild(self._dt_count_item)
        self._dt_count_item.setText(1, "0")

    def _add_distributed_target(self) -> None:
        """Add a new distributed target sub-group to the tree."""
        idx = len(self._distributed_target_data)
        dt = {
            "origin": [500.0, 0.0, 0.0],
            "extent": [100.0, 100.0],
            "cell_size": 1.0,
            "reflectivity_mode": "uniform",
            "mean_rcs": 0.1,
            "stddev_rcs": 0.01,
            "file_path": "",
        }
        self._distributed_target_data.append(dt)

        grp = _group_item(f"Target {idx + 1}")
        # Insert before the count item
        count_idx = self._dt_group.indexOfChild(self._dt_count_item)
        self._dt_group.insertChild(count_idx, grp)
        self._distributed_target_items.append(grp)

        prefix = f"scene.dt_{idx}"

        # Origin X/Y/Z
        for i, (axis, val) in enumerate([("x", dt["origin"][0]), ("y", dt["origin"][1]), ("z", dt["origin"][2])]):
            w = _plain_spin(val, -1e8, 1e8, 10.0, " m")
            self._register(grp, f"{prefix}.origin_{axis}", f"Origin {axis.upper()}", w)
            self._connect_spin(f"{prefix}.origin_{axis}", w)

        # Extent DX/DY
        for axis, val in [("dx", dt["extent"][0]), ("dy", dt["extent"][1])]:
            w = _plain_spin(val, 0.1, 1e6, 10.0, " m")
            self._register(grp, f"{prefix}.{axis}", axis.upper(), w)
            self._connect_spin(f"{prefix}.{axis}", w)

        # Cell size
        w = _plain_spin(dt["cell_size"], 0.01, 100.0, 0.1, " m")
        self._register(grp, f"{prefix}.cell_size", "Cell Size", w)
        self._connect_spin(f"{prefix}.cell_size", w)

        # Reflectivity mode
        w = _combo(["uniform", "file"], "uniform")
        self._register(grp, f"{prefix}.refl_mode", "Reflectivity", w)
        self._connect_combo(f"{prefix}.refl_mode", w)
        w.currentTextChanged.connect(lambda text, p=prefix: self._on_dt_refl_mode_changed(p, text))

        # Mean RCS
        w = _plain_spin(dt["mean_rcs"], 0.0, 1e6, 0.01)
        self._register(grp, f"{prefix}.mean_rcs", "Mean RCS", w)
        self._connect_spin(f"{prefix}.mean_rcs", w)

        # Stddev RCS
        w = _plain_spin(dt["stddev_rcs"], 0.0, 1e6, 0.001)
        self._register(grp, f"{prefix}.stddev_rcs", "Stddev RCS", w)
        self._connect_spin(f"{prefix}.stddev_rcs", w)

        # File path (hidden by default)
        w = QLineEdit("")
        w.setPlaceholderText("Path to .npy or .csv")
        file_item = _param_item("File Path")
        grp.addChild(file_item)
        self._tree.setItemWidget(file_item, 1, w)
        self._widgets[f"{prefix}.file_path"] = w
        self._items[f"{prefix}.file_path"] = file_item
        file_item.setHidden(True)

        grp.setExpanded(True)
        self._update_dt_count_label()
        self.parameter_changed.emit("scene.distributed_targets", len(self._distributed_target_data))

    def _remove_distributed_target(self) -> None:
        """Remove the last distributed target."""
        if not self._distributed_target_items:
            return
        idx = len(self._distributed_target_items) - 1
        grp = self._distributed_target_items.pop()
        self._distributed_target_data.pop()

        # Clean up widgets and items
        prefix = f"scene.dt_{idx}"
        for k in [k for k in self._widgets if k.startswith(prefix)]:
            del self._widgets[k]
        for k in [k for k in self._items if k.startswith(prefix)]:
            del self._items[k]

        self._dt_group.removeChild(grp)
        self._update_dt_count_label()
        self.parameter_changed.emit("scene.distributed_targets", len(self._distributed_target_data))

    def _on_dt_refl_mode_changed(self, prefix: str, mode: str) -> None:
        is_uniform = mode == "uniform"
        self._set_visible(f"{prefix}.mean_rcs", is_uniform)
        self._set_visible(f"{prefix}.stddev_rcs", is_uniform)
        self._set_visible(f"{prefix}.file_path", not is_uniform)

    def _update_dt_count_label(self) -> None:
        n = len(self._distributed_target_data)
        self._dt_count_item.setText(1, str(n))

    def _open_point_target_editor(self) -> None:
        """Open the point target table dialog."""
        dlg = PointTargetDialog(self._target_data, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._target_data = dlg.get_targets()
            self._update_target_count_label()
            self.parameter_changed.emit("scene.targets", len(self._target_data))

    def _update_target_count_label(self) -> None:
        n = len(self._target_data)
        self._target_count_item.setText(1, f"{n} target{'s' if n != 1 else ''}")

    # -----------------------------------------------------------------
    # 7. Processing
    # -----------------------------------------------------------------

    _PROC_STEPS: list[tuple[str, str, bool]] = [
        ("image_formation", "Image Formation", False),   # required — no checkbox
        ("moco", "Motion Compensation", True),
        ("autofocus", "Autofocus", True),
        ("geocoding", "Geocoding", True),
        ("polarimetric_decomposition", "Polarimetric Decomp.", True),
    ]

    # Maps the processing step key to the ALGORITHM_SCHEMAS sub-dict key
    _SCHEMA_KEY_MAP: dict[str, str] = {
        "image_formation": "image_formation",
        "moco": "moco",
        "autofocus": "autofocus",
        "geocoding": "geocoding",
        "polarimetric_decomposition": "polarimetry",
    }

    def _build_processing(self) -> None:
        cat = _category_item("Processing")
        self._tree.addTopLevelItem(cat)
        self._items["processing"] = cat

        for step_key, label, optional in self._PROC_STEPS:
            item = _group_item(label)
            cat.addChild(item)
            self._items[f"processing.{step_key}"] = item

            schema_key = self._SCHEMA_KEY_MAP[step_key]
            algo_names = list(ALGORITHM_SCHEMAS.get(schema_key, {}).keys())
            default_algo = algo_names[0] if algo_names else ""

            if optional:
                # Checkbox on the group row, combo as first child
                cb = QCheckBox()
                cb.setChecked(False)
                self._tree.setItemWidget(item, 1, cb)
                self._widgets[f"processing.{step_key}_enabled"] = cb
                self._items[f"processing.{step_key}_enabled"] = item

                combo = _combo(algo_names, default_algo)
                combo_item = _param_item("Algorithm")
                item.addChild(combo_item)
                self._tree.setItemWidget(combo_item, 1, combo)
                key = f"processing.{step_key}"
                self._widgets[key] = combo
                self._items[f"processing.{step_key}_combo"] = combo_item

                # Toggle visibility of combo + params when checkbox changes
                cb.toggled.connect(
                    lambda checked, sk=step_key: self._on_proc_step_toggled(sk, checked)
                )

                # Connect combo change to rebuild child params
                combo.currentTextChanged.connect(
                    lambda text, sk=step_key: self._on_algo_changed(sk, text)
                )

                # Auto-enable perturbation + GPS when MoCo is enabled
                if step_key == "moco":
                    cb.toggled.connect(self._on_moco_toggled)

                # Initial state: unchecked, children hidden
                self._on_algo_changed(step_key, default_algo)
                self._on_proc_step_toggled(step_key, False)
            else:
                # Required step: just a combo, no checkbox
                combo = _combo(algo_names, default_algo)
                combo_item = _param_item("Algorithm")
                item.addChild(combo_item)
                self._tree.setItemWidget(combo_item, 1, combo)
                key = f"processing.{step_key}"
                self._widgets[key] = combo
                self._items[f"processing.{step_key}_combo"] = combo_item

                combo.currentTextChanged.connect(
                    lambda text, sk=step_key: self._on_algo_changed(sk, text)
                )
                self._on_algo_changed(step_key, default_algo)

    def _on_algo_changed(self, step_key: str, algo_name: str) -> None:
        """Remove old param children and create new ones from schema."""
        parent_item = self._items[f"processing.{step_key}"]

        # Remove all children except the combo item (always first child)
        while parent_item.childCount() > 1:
            child = parent_item.child(parent_item.childCount() - 1)
            # Unregister widgets
            for k in list(self._widgets.keys()):
                if k.startswith(f"processing.{step_key}_params."):
                    if self._items.get(k) is child:
                        del self._widgets[k]
                        del self._items[k]
                        break
            parent_item.removeChild(child)

        # Clean up all param widgets for this step
        prefix = f"processing.{step_key}_params."
        for k in [k for k in self._widgets if k.startswith(prefix)]:
            del self._widgets[k]
        for k in [k for k in self._items if k.startswith(prefix)]:
            del self._items[k]

        if algo_name == "(None)" or not algo_name:
            return

        schema_key = self._SCHEMA_KEY_MAP[step_key]
        params = ALGORITHM_SCHEMAS.get(schema_key, {}).get(algo_name, [])
        for pdef in params:
            pname = pdef["name"]
            plabel = pdef.get("label", pname)
            ptype = pdef.get("type", "float")
            pdefault = pdef.get("default", 0)
            full_key = f"processing.{step_key}_params.{pname}"

            if ptype == "bool":
                w = QCheckBox()
                w.setChecked(bool(pdefault))
                self._register(parent_item, full_key, plabel, w)
                self._connect_check(full_key, w)
            elif ptype == "int":
                w = _int_spin(
                    int(pdefault),
                    int(pdef.get("min", 0)),
                    int(pdef.get("max", 10_000_000)),
                )
                self._register(parent_item, full_key, plabel, w)
                self._connect_spin(full_key, w)
            elif ptype == "enum":
                choices = pdef.get("choices", [])
                w = _combo(choices, str(pdefault))
                self._register(parent_item, full_key, plabel, w)
                self._connect_combo(full_key, w)
            else:
                # float
                w = _plain_spin(
                    float(pdefault),
                    float(pdef.get("min", -1e15)),
                    float(pdef.get("max", 1e15)),
                    1.0,
                    f" {pdef['unit']}" if pdef.get("unit") else "",
                )
                self._register(parent_item, full_key, plabel, w)
                self._connect_spin(full_key, w)

    # =================================================================
    # Public API
    # =================================================================

    def get_all_parameters(self) -> dict:
        """Return complete parameter dict matching the project model structure."""

        # --- simulation ---
        auto_sr = self._w("radar.sample_rate_auto").isChecked()
        simulation = {
            "seed": self._w("simulation.seed").value(),
            "swath_range": (
                self._w("simulation.near_range").si_value(),
                self._w("simulation.far_range").si_value(),
            ),
            "sample_rate": None if auto_sr else self._w("radar.sample_rate").si_value(),
        }

        # --- sarmode (imaging geometry) ---
        sarmode = {
            "mode": self._w("imaging.mode").currentText(),
            "look_side": self._w("imaging.look_side").currentText(),
            "depression_angle": math.radians(self._w("imaging.depression_angle").value()),
            "squint_angle": math.radians(self._w("imaging.squint_angle").value()),
            "scene_center": [
                self._w("imaging.scene_center_x").si_value(),
                self._w("imaging.scene_center_y").si_value(),
                self._w("imaging.scene_center_z").si_value(),
            ],
            "n_subswaths": self._w("imaging.n_subswaths").value(),
            "burst_length": self._w("imaging.burst_length").value(),
        }

        # --- radar ---
        radar = {
            "carrier_freq": self._w("radar.carrier_freq").si_value(),
            "transmit_power": self._w("radar.transmit_power").si_value(),
            "receiver_gain_dB": self._w("radar.receiver_gain_dB").value(),
            "system_losses": self._w("radar.system_losses").value(),
            "noise_figure": self._w("radar.noise_figure").value(),
            "reference_temp": self._w("radar.reference_temp").value(),
            "polarization": self._w("radar.polarization").currentText(),
        }

        # --- antenna ---
        antenna = {
            "preset": self._w("antenna.preset").currentText(),
            "az_beamwidth": math.radians(self._w("antenna.az_beamwidth").value()),
            "el_beamwidth": math.radians(self._w("antenna.el_beamwidth").value()),
        }

        # --- waveform ---
        wtype = self._w("waveform.waveform_type").currentText()
        window_text = self._w("waveform.window").currentText()
        waveform: dict[str, Any] = {
            "waveform_type": wtype,
            "prf": self._w("waveform.prf").si_value(),
            "bandwidth": self._w("waveform.bandwidth").si_value(),
            "window": None if window_text == "(None)" else window_text,
        }
        if window_text == "kaiser":
            waveform["kaiser_beta"] = self._w("waveform.kaiser_beta").value()
        if wtype == "LFM":
            waveform["duty_cycle"] = self._w("waveform.duty_cycle").value()
        elif wtype == "FMCW":
            waveform["duty_cycle"] = self._w("waveform.fmcw_duty_cycle").value()
            waveform["ramp_type"] = self._w("waveform.ramp_type").currentText()

        if self._w("waveform.phase_noise_enabled").isChecked():
            waveform["phase_noise"] = {
                "flicker_fm_level": self._w("waveform.flicker_fm").value(),
                "white_fm_level": self._w("waveform.white_fm").value(),
                "flicker_pm_level": self._w("waveform.flicker_pm").value(),
                "white_floor": self._w("waveform.white_floor").value(),
            }
        else:
            waveform["phase_noise"] = None

        # --- platform ---
        fp_mode = self._w("platform.flight_path_mode").currentText()
        platform: dict[str, Any] = {
            "velocity": self._w("platform.velocity").si_value(),
            "altitude": self._w("platform.start_z").si_value(),
            "heading": [
                self._w("platform.heading_x").value(),
                self._w("platform.heading_y").value(),
                self._w("platform.heading_z").value(),
            ],
            "start_position": [
                self._w("platform.start_x").si_value(),
                self._w("platform.start_y").si_value(),
                self._w("platform.start_z").si_value(),
            ],
            "flight_path_mode": fp_mode,
        }
        if fp_mode == "start_stop":
            platform["stop_position"] = [
                self._w("platform.stop_x").si_value(),
                self._w("platform.stop_y").si_value(),
                self._w("platform.stop_z").si_value(),
            ]
        else:
            platform["flight_time"] = self._w("platform.flight_time").value()

        if self._w("platform.perturbation_enabled").isChecked():
            platform["perturbation"] = {
                "sigma_u": self._w("platform.sigma_u").value(),
                "sigma_v": self._w("platform.sigma_v").value(),
                "sigma_w": self._w("platform.sigma_w").value(),
            }
        else:
            platform["perturbation"] = None

        if self._w("platform.gps_enabled").isChecked():
            platform["gps"] = {
                "accuracy": self._w("platform.gps_accuracy").value(),
                "rate": self._w("platform.gps_rate").value(),
            }
        else:
            platform["gps"] = None

        if self._w("platform.imu_enabled").isChecked():
            platform["imu"] = {
                "accel_noise": self._w("platform.accel_noise").value(),
                "gyro_noise": self._w("platform.gyro_noise").value(),
                "rate": self._w("platform.imu_rate").value(),
            }
        else:
            platform["imu"] = None

        # --- scene ---
        distributed_targets = []
        for idx in range(len(self._distributed_target_data)):
            prefix = f"scene.dt_{idx}"
            refl_mode = self._w(f"{prefix}.refl_mode").currentText()
            dt = {
                "origin": [
                    self._w(f"{prefix}.origin_x").value(),
                    self._w(f"{prefix}.origin_y").value(),
                    self._w(f"{prefix}.origin_z").value(),
                ],
                "extent": [
                    self._w(f"{prefix}.dx").value(),
                    self._w(f"{prefix}.dy").value(),
                ],
                "cell_size": self._w(f"{prefix}.cell_size").value(),
                "reflectivity_mode": refl_mode,
            }
            if refl_mode == "uniform":
                dt["mean_rcs"] = self._w(f"{prefix}.mean_rcs").value()
                dt["stddev_rcs"] = self._w(f"{prefix}.stddev_rcs").value()
            else:
                dt["file_path"] = self._w(f"{prefix}.file_path").text()
            distributed_targets.append(dt)

        scene = {
            "origin_lat": self._w("scene.origin_lat").value(),
            "origin_lon": self._w("scene.origin_lon").value(),
            "origin_alt": self._w("scene.origin_alt").si_value(),
            "targets": list(self._target_data),
            "distributed_targets": distributed_targets,
        }

        # --- processing_config ---
        processing_config: dict[str, Any] = {}
        for step_key, _label, optional in self._PROC_STEPS:
            combo: QComboBox = self._w(f"processing.{step_key}")
            algo = combo.currentText()
            if optional:
                enabled_key = f"processing.{step_key}_enabled"
                cb = self._widgets.get(enabled_key)
                if cb is not None and not cb.isChecked():
                    processing_config[step_key] = None
                else:
                    processing_config[step_key] = algo
            else:
                processing_config[step_key] = algo

            # Collect algorithm-specific params
            params_prefix = f"processing.{step_key}_params."
            algo_params: dict[str, Any] = {}
            for k, widget in self._widgets.items():
                if not k.startswith(params_prefix):
                    continue
                pname = k[len(params_prefix):]
                if isinstance(widget, QCheckBox):
                    algo_params[pname] = widget.isChecked()
                elif isinstance(widget, QComboBox):
                    algo_params[pname] = widget.currentText()
                elif isinstance(widget, QSpinBox):
                    algo_params[pname] = widget.value()
                elif isinstance(widget, UnitSpinBox):
                    algo_params[pname] = widget.si_value()
                elif isinstance(widget, (QDoubleSpinBox, _CleanDoubleSpinBox)):
                    algo_params[pname] = widget.value()
            processing_config[f"{step_key}_params"] = algo_params

        return {
            "simulation": simulation,
            "sarmode": sarmode,
            "radar": radar,
            "antenna": antenna,
            "waveform": waveform,
            "platform": platform,
            "scene": scene,
            "processing_config": processing_config,
        }

    # -----------------------------------------------------------------
    # set_all_parameters
    # -----------------------------------------------------------------

    def set_all_parameters(self, params: dict) -> None:
        """Populate tree from a parameter dict."""

        # Block signals while bulk-setting to avoid cascading updates
        self._tree.blockSignals(True)
        try:
            self._set_simulation(params.get("simulation", {}))
            self._set_sarmode(params.get("sarmode", {}))
            self._set_radar(params.get("radar", {}))
            self._set_antenna(params.get("antenna", {}))
            self._set_waveform(params.get("waveform", {}))
            self._set_platform(params.get("platform", {}))
            self._set_scene(params.get("scene", {}))
            self._set_processing(params.get("processing_config", {}))
        finally:
            self._tree.blockSignals(False)

    def _set_simulation(self, p: dict) -> None:
        if not p:
            return
        if "seed" in p:
            self._w("simulation.seed").setValue(p["seed"])
        if "swath_range" in p:
            near, far = p["swath_range"]
            self._w("simulation.near_range").set_si_value(near)
            self._w("simulation.far_range").set_si_value(far)
        if "sample_rate" in p:
            sr = p["sample_rate"]
            if sr is None:
                self._w("radar.sample_rate_auto").setChecked(True)
            else:
                self._w("radar.sample_rate_auto").setChecked(False)
                self._w("radar.sample_rate").set_si_value(sr)

    def _set_sarmode(self, p: dict) -> None:
        if not p:
            return
        if "mode" in p:
            self._w("imaging.mode").setCurrentText(str(p["mode"]))
        if "look_side" in p:
            self._w("imaging.look_side").setCurrentText(str(p["look_side"]))
        if "depression_angle" in p:
            self._w("imaging.depression_angle").setValue(math.degrees(p["depression_angle"]))
        if "scene_center" in p:
            sc = p["scene_center"]
            if isinstance(sc, (list, tuple)) and len(sc) >= 3:
                self._w("imaging.scene_center_x").set_si_value(sc[0])
                self._w("imaging.scene_center_y").set_si_value(sc[1])
                self._w("imaging.scene_center_z").set_si_value(sc[2])
        if "squint_angle" in p:
            self._w("imaging.squint_angle").setValue(math.degrees(p["squint_angle"]))
        if "n_subswaths" in p:
            self._w("imaging.n_subswaths").setValue(p["n_subswaths"])
        if "burst_length" in p:
            self._w("imaging.burst_length").setValue(p["burst_length"])

    def _set_radar(self, p: dict) -> None:
        if not p:
            return
        if "carrier_freq" in p:
            self._w("radar.carrier_freq").set_si_value(p["carrier_freq"])
        if "transmit_power" in p:
            self._w("radar.transmit_power").set_si_value(p["transmit_power"])
        if "receiver_gain_dB" in p:
            self._w("radar.receiver_gain_dB").setValue(p["receiver_gain_dB"])
        if "system_losses" in p:
            self._w("radar.system_losses").setValue(p["system_losses"])
        if "noise_figure" in p:
            self._w("radar.noise_figure").setValue(p["noise_figure"])
        if "reference_temp" in p:
            self._w("radar.reference_temp").setValue(p["reference_temp"])
        if "polarization" in p:
            self._w("radar.polarization").setCurrentText(str(p["polarization"]))

    def _set_antenna(self, p: dict) -> None:
        if not p:
            return
        if "preset" in p:
            self._w("antenna.preset").setCurrentText(str(p["preset"]))
        if "az_beamwidth" in p:
            self._w("antenna.az_beamwidth").setValue(math.degrees(p["az_beamwidth"]))
        if "el_beamwidth" in p:
            self._w("antenna.el_beamwidth").setValue(math.degrees(p["el_beamwidth"]))

    def _set_waveform(self, p: dict) -> None:
        if not p:
            return
        if "prf" in p:
            self._w("waveform.prf").set_si_value(p["prf"])
        if "waveform_type" in p:
            self._w("waveform.waveform_type").setCurrentText(p["waveform_type"])
        if "bandwidth" in p:
            self._w("waveform.bandwidth").set_si_value(p["bandwidth"])
        if "duty_cycle" in p:
            wtype = self._w("waveform.waveform_type").currentText()
            if wtype == "FMCW":
                self._w("waveform.fmcw_duty_cycle").setValue(p["duty_cycle"])
            else:
                self._w("waveform.duty_cycle").setValue(p["duty_cycle"])
        if "ramp_type" in p:
            self._w("waveform.ramp_type").setCurrentText(str(p["ramp_type"]))
        if "window" in p:
            w = p["window"]
            self._w("waveform.window").setCurrentText("(None)" if w is None else str(w))
        if "kaiser_beta" in p:
            self._w("waveform.kaiser_beta").setValue(p["kaiser_beta"])
        if "phase_noise" in p:
            pn = p["phase_noise"]
            enabled = p.get("phase_noise_enabled", pn is not None)
            self._w("waveform.phase_noise_enabled").setChecked(enabled)
            if pn is not None:
                self._w("waveform.flicker_fm").setValue(pn.get("flicker_fm_level", -80.0))
                self._w("waveform.white_fm").setValue(pn.get("white_fm_level", -100.0))
                self._w("waveform.flicker_pm").setValue(pn.get("flicker_pm_level", -120.0))
                self._w("waveform.white_floor").setValue(pn.get("white_floor", -150.0))

    def _set_platform(self, p: dict) -> None:
        if not p:
            return
        if "flight_path_mode" in p:
            self._w("platform.flight_path_mode").setCurrentText(p["flight_path_mode"])
        if "start_position" in p:
            pos = p["start_position"]
            if len(pos) >= 3:
                self._w("platform.start_x").set_si_value(pos[0])
                self._w("platform.start_y").set_si_value(pos[1])
                self._w("platform.start_z").set_si_value(pos[2])
        if "stop_position" in p:
            pos = p["stop_position"]
            if len(pos) >= 3:
                self._w("platform.stop_x").set_si_value(pos[0])
                self._w("platform.stop_y").set_si_value(pos[1])
                self._w("platform.stop_z").set_si_value(pos[2])
        if "heading" in p:
            h = p["heading"]
            if isinstance(h, (list, tuple)) and len(h) >= 3:
                self._w("platform.heading_x").setValue(h[0])
                self._w("platform.heading_y").setValue(h[1])
                self._w("platform.heading_z").setValue(h[2])
            elif isinstance(h, (int, float)):
                self._w("platform.heading_x").setValue(math.sin(math.radians(h)))
                self._w("platform.heading_y").setValue(math.cos(math.radians(h)))
                self._w("platform.heading_z").setValue(0.0)
        if "velocity" in p:
            self._w("platform.velocity").set_si_value(p["velocity"])
        if "flight_time" in p:
            self._w("platform.flight_time").setValue(p["flight_time"])
        if "perturbation" in p:
            pt = p["perturbation"]
            enabled = p.get("perturbation_enabled", pt is not None)
            self._w("platform.perturbation_enabled").setChecked(enabled)
            if pt is not None:
                self._w("platform.sigma_u").setValue(pt.get("sigma_u", 1.0))
                self._w("platform.sigma_v").setValue(pt.get("sigma_v", 1.0))
                self._w("platform.sigma_w").setValue(pt.get("sigma_w", 0.5))
        if "gps" in p:
            g = p["gps"]
            enabled = p.get("gps_enabled", g is not None)
            self._w("platform.gps_enabled").setChecked(enabled)
            if g is not None:
                self._w("platform.gps_accuracy").setValue(g.get("accuracy", 0.002))
                self._w("platform.gps_rate").setValue(g.get("rate", 10.0))
        if "imu" in p:
            im = p["imu"]
            enabled = p.get("imu_enabled", im is not None)
            self._w("platform.imu_enabled").setChecked(enabled)
            if im is not None:
                self._w("platform.accel_noise").setValue(im.get("accel_noise", 0.0001))
                self._w("platform.gyro_noise").setValue(im.get("gyro_noise", 0.00001))
                self._w("platform.imu_rate").setValue(im.get("rate", 200.0))

    def _set_scene(self, p: dict) -> None:
        if not p:
            return
        if "origin_lat" in p:
            self._w("scene.origin_lat").setValue(p["origin_lat"])
        if "origin_lon" in p:
            self._w("scene.origin_lon").setValue(p["origin_lon"])
        if "origin_alt" in p:
            self._w("scene.origin_alt").set_si_value(p["origin_alt"])
        if "targets" in p:
            self._target_data = list(p["targets"])
            self._update_target_count_label()
        if "distributed_targets" in p:
            # Clear existing distributed targets
            while self._distributed_target_items:
                self._remove_distributed_target()
            # Add from data
            for dt in p["distributed_targets"]:
                self._add_distributed_target()
                idx = len(self._distributed_target_data) - 1
                prefix = f"scene.dt_{idx}"
                origin = dt.get("origin", [0, 0, 0])
                for i, axis in enumerate(("x", "y", "z")):
                    self._w(f"{prefix}.origin_{axis}").setValue(origin[i])
                extent = dt.get("extent", [100, 100])
                self._w(f"{prefix}.dx").setValue(extent[0])
                self._w(f"{prefix}.dy").setValue(extent[1])
                self._w(f"{prefix}.cell_size").setValue(dt.get("cell_size", 1.0))
                refl = dt.get("reflectivity_mode", "uniform")
                self._w(f"{prefix}.refl_mode").setCurrentText(refl)
                if refl == "uniform":
                    self._w(f"{prefix}.mean_rcs").setValue(dt.get("mean_rcs", 0.1))
                    self._w(f"{prefix}.stddev_rcs").setValue(dt.get("stddev_rcs", 0.01))
                else:
                    self._w(f"{prefix}.file_path").setText(dt.get("file_path", ""))

    def _set_processing(self, p: dict) -> None:
        if not p:
            return
        for step_key, _label, optional in self._PROC_STEPS:
            if step_key in p:
                algo = p[step_key]
                combo: QComboBox = self._w(f"processing.{step_key}")
                if optional:
                    enabled_key = f"processing.{step_key}_enabled"
                    cb = self._widgets.get(enabled_key)
                    if algo is None:
                        if cb is not None:
                            cb.setChecked(False)
                    else:
                        if cb is not None:
                            cb.setChecked(True)
                        combo.setCurrentText(str(algo))
                elif algo is not None:
                    combo.setCurrentText(str(algo))

            params_key = f"{step_key}_params"
            if params_key in p and p[params_key]:
                algo_params = p[params_key]
                for pname, pval in algo_params.items():
                    full_key = f"processing.{step_key}_params.{pname}"
                    w = self._widgets.get(full_key)
                    if w is None:
                        continue
                    if isinstance(w, QCheckBox):
                        w.setChecked(bool(pval))
                    elif isinstance(w, QComboBox):
                        w.setCurrentText(str(pval))
                    elif isinstance(w, QSpinBox):
                        w.setValue(int(pval))
                    elif isinstance(w, UnitSpinBox):
                        w.set_si_value(float(pval))
                    elif isinstance(w, (QDoubleSpinBox, _CleanDoubleSpinBox)):
                        w.setValue(float(pval))

    # -----------------------------------------------------------------
    # set_mode_constraints
    # -----------------------------------------------------------------

    def set_mode_constraints(self, mode: str) -> None:
        """Show/hide parameters based on SAR mode.

        - stripmap: hide scene_center, burst_length, n_subswaths
        - spotlight: show scene_center, hide n_subswaths, burst_length
        - scansar: show all
        """
        scene_center_keys = [
            "imaging.scene_center_x",
            "imaging.scene_center_y",
            "imaging.scene_center_z",
        ]
        scansar_keys = ["imaging.n_subswaths", "imaging.burst_length"]

        is_spotlight = mode == SARMode.SPOTLIGHT.value
        is_scansar = mode == SARMode.SCANMAR.value

        # Scene center: visible for spotlight and scansar
        self._set_group_visible(scene_center_keys, is_spotlight or is_scansar)

        # Subswaths & burst: visible only for scansar
        self._set_group_visible(scansar_keys, is_scansar)

    # -----------------------------------------------------------------
    # Filter / search
    # -----------------------------------------------------------------

    def filter(self, text: str) -> None:
        """Filter tree to show only matching parameters (case-insensitive)."""
        if not text:
            self.clear_filter()
            return
        text_lower = text.lower()
        for i in range(self._tree.topLevelItemCount()):
            cat = self._tree.topLevelItem(i)
            if cat is not None:
                self._filter_item(cat, text_lower)

    def clear_filter(self) -> None:
        """Restore all items to visible, then re-apply dynamic visibility rules."""
        for i in range(self._tree.topLevelItemCount()):
            cat = self._tree.topLevelItem(i)
            if cat is not None:
                self._show_all(cat)

        # Re-apply conditional visibility
        self._on_waveform_type_changed(self._w("waveform.waveform_type").currentText())
        self._on_window_changed(self._w("waveform.window").currentText())
        self._on_sample_rate_auto_toggled(self._w("radar.sample_rate_auto").isChecked())
        self._on_flight_path_mode_changed(self._w("platform.flight_path_mode").currentText())
        self._on_phase_noise_toggled(self._w("waveform.phase_noise_enabled").isChecked())
        self._on_perturbation_toggled(self._w("platform.perturbation_enabled").isChecked())
        self._on_gps_toggled(self._w("platform.gps_enabled").isChecked())
        self._on_imu_toggled(self._w("platform.imu_enabled").isChecked())
        for step_key, _label, optional in self._PROC_STEPS:
            if optional:
                cb = self._widgets.get(f"processing.{step_key}_enabled")
                if cb is not None:
                    self._on_proc_step_toggled(step_key, cb.isChecked())

    def _filter_item(self, item: QTreeWidgetItem, text: str) -> bool:
        """Recursively filter. Returns True if item or any child matches."""
        if item.childCount() == 0:
            # Leaf node — check column 0 text
            match = text in item.text(0).lower()
            item.setHidden(not match)
            return match

        any_child_visible = False
        for i in range(item.childCount()):
            child = item.child(i)
            if child is not None:
                if self._filter_item(child, text):
                    any_child_visible = True

        # Also check if the group/category name itself matches
        if text in item.text(0).lower():
            any_child_visible = True
            # Show all children
            self._show_all(item)

        item.setHidden(not any_child_visible)
        if any_child_visible:
            item.setExpanded(True)
        return any_child_visible

    def _show_all(self, item: QTreeWidgetItem) -> None:
        """Recursively unhide all descendants."""
        item.setHidden(False)
        for i in range(item.childCount()):
            child = item.child(i)
            if child is not None:
                self._show_all(child)

    def _on_filter_text_changed(self, text: str) -> None:
        self.filter(text)


__all__ = ["ParameterTreeWidget"]
