"""Project creation wizard — guides users through SAR simulation setup."""
from __future__ import annotations
import math
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit,
    QSpinBox, QTextEdit, QVBoxLayout, QWizard, QWizardPage, QWidget,
)
from pySimSAR.gui.widgets.param_editor import UnitSpinBox, _plain_spin, _combo, _no_scroll_unless_focused

_FREQ = {"GHz": 1e9, "MHz": 1e6, "kHz": 1e3, "Hz": 1.0}
_DIST = {"km": 1e3, "m": 1.0}
_SPEED = {"m/s": 1.0, "km/h": 1.0 / 3.6}
_POWER = {"kW": 1e3, "W": 1.0, "mW": 1e-3}


class ProjectMetadataPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Project Metadata")
        self.setSubTitle("Name your project and select the SAR imaging mode.")
        form = QFormLayout(self)
        self._name = QLineEdit("New Project")
        self._description = QTextEdit()
        self._description.setMaximumHeight(60)
        self._mode = _combo(["stripmap", "spotlight", "scanmar"], "stripmap")
        form.addRow("Project Name:", self._name)
        form.addRow("Description:", self._description)
        form.addRow("SAR Mode:", self._mode)
        self.registerField("project_name*", self._name)

    def get_data(self) -> dict:
        return {
            "name": self._name.text(),
            "description": self._description.toPlainText(),
            "mode": self._mode.currentText(),
        }


class RadarConfigPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Radar Configuration")
        self.setSubTitle("Set the primary radar parameters.")
        form = QFormLayout(self)
        self._carrier_freq = UnitSpinBox(_FREQ, "GHz", value=9.65, minimum=0.001, maximum=999.0, step=0.01)
        self._prf = UnitSpinBox({"kHz": 1e3, "Hz": 1.0}, "Hz", value=1000.0, minimum=1.0, maximum=999999.0, step=100.0)
        self._transmit_power = UnitSpinBox(_POWER, "W", value=1000.0, minimum=0.01, maximum=999999.0, step=100.0)
        self._bandwidth = UnitSpinBox(_FREQ, "MHz", value=100.0, minimum=0.001, maximum=99999.0, step=1.0)
        self._depression = _plain_spin(45.0, 0.0, 90.0, 1.0, "°")
        form.addRow("Carrier Frequency:", self._carrier_freq)
        form.addRow("PRF:", self._prf)
        form.addRow("Transmit Power:", self._transmit_power)
        form.addRow("Bandwidth:", self._bandwidth)
        form.addRow("Depression Angle:", self._depression)

    def get_data(self) -> dict:
        return {
            "carrier_freq": self._carrier_freq.si_value(),
            "prf": self._prf.si_value(),
            "transmit_power": self._transmit_power.si_value(),
            "bandwidth": self._bandwidth.si_value(),
            "depression_angle": math.radians(self._depression.value()),
        }


class PlatformPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Platform Configuration")
        self.setSubTitle("Define the flight path.")
        form = QFormLayout(self)
        self._velocity = UnitSpinBox(_SPEED, "m/s", value=100.0, minimum=0.1, maximum=50000.0, step=10.0)
        self._altitude = UnitSpinBox(_DIST, "m", value=1000.0, minimum=1.0, maximum=100000.0, step=100.0)
        self._start_x = UnitSpinBox(_DIST, "m", value=0.0, minimum=-1e8, maximum=1e8, step=100.0)
        self._start_y = UnitSpinBox(_DIST, "m", value=-25.0, minimum=-1e8, maximum=1e8, step=100.0)
        self._stop_x = UnitSpinBox(_DIST, "m", value=0.0, minimum=-1e8, maximum=1e8, step=100.0)
        self._stop_y = UnitSpinBox(_DIST, "m", value=25.0, minimum=-1e8, maximum=1e8, step=100.0)
        form.addRow("Velocity:", self._velocity)
        form.addRow("Altitude:", self._altitude)
        form.addRow("Start X:", self._start_x)
        form.addRow("Start Y:", self._start_y)
        form.addRow("Stop X:", self._stop_x)
        form.addRow("Stop Y:", self._stop_y)

    def get_data(self) -> dict:
        alt = self._altitude.si_value()
        return {
            "velocity": self._velocity.si_value(),
            "altitude": alt,
            "start_position": [self._start_x.si_value(), self._start_y.si_value(), alt],
            "stop_position": [self._stop_x.si_value(), self._stop_y.si_value(), alt],
            "flight_path_mode": "start_stop",
            "heading": [0.0, 1.0, 0.0],
        }


class ScenePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Scene Configuration")
        self.setSubTitle("Set scene origin and swath range.")
        form = QFormLayout(self)
        self._origin_lat = _plain_spin(0.0, -90.0, 90.0, 0.01, "°")
        self._origin_lon = _plain_spin(0.0, -180.0, 180.0, 0.01, "°")
        self._near_range = UnitSpinBox(_DIST, "m", value=1350.0, minimum=0.0, maximum=1e8, step=100.0)
        self._far_range = UnitSpinBox(_DIST, "m", value=1500.0, minimum=0.0, maximum=1e8, step=100.0)
        form.addRow("Origin Latitude:", self._origin_lat)
        form.addRow("Origin Longitude:", self._origin_lon)
        form.addRow("Near Range:", self._near_range)
        form.addRow("Far Range:", self._far_range)

    def get_data(self) -> dict:
        return {
            "origin_lat": self._origin_lat.value(),
            "origin_lon": self._origin_lon.value(),
            "near_range": self._near_range.si_value(),
            "far_range": self._far_range.si_value(),
        }


class ProcessingPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Processing Configuration")
        self.setSubTitle("Select algorithms for the processing pipeline.")
        form = QFormLayout(self)
        self._image_formation = _combo(["range_doppler", "chirp_scaling", "omega_k"], "range_doppler")
        self._moco = _combo(["(None)", "first_order", "second_order"], "(None)")
        self._autofocus = _combo(["(None)", "pga", "min_entropy", "mda", "ppp"], "(None)")
        form.addRow("Image Formation:", self._image_formation)
        form.addRow("Motion Compensation:", self._moco)
        form.addRow("Autofocus:", self._autofocus)

    def get_data(self) -> dict:
        def _opt(combo):
            t = combo.currentText()
            return None if t == "(None)" else t
        return {
            "image_formation": self._image_formation.currentText(),
            "moco": _opt(self._moco),
            "autofocus": _opt(self._autofocus),
        }


class ProjectCreationWizard(QWizard):
    """Multi-step wizard for creating a new SAR simulation project."""

    wizard_completed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project Wizard")
        self.setMinimumSize(500, 400)

        self._metadata_page = ProjectMetadataPage()
        self._radar_page = RadarConfigPage()
        self._platform_page = PlatformPage()
        self._scene_page = ScenePage()
        self._processing_page = ProcessingPage()

        self.addPage(self._metadata_page)
        self.addPage(self._radar_page)
        self.addPage(self._platform_page)
        self.addPage(self._scene_page)
        self.addPage(self._processing_page)

    def get_parameters(self) -> dict:
        """Build a complete parameter dict from all wizard pages."""
        meta = self._metadata_page.get_data()
        radar_data = self._radar_page.get_data()
        platform_data = self._platform_page.get_data()
        scene_data = self._scene_page.get_data()
        proc_data = self._processing_page.get_data()

        return {
            "simulation": {
                "seed": 42,
                "swath_range": (scene_data["near_range"], scene_data["far_range"]),
                "sample_rate": None,
                "n_subswaths": 3,
                "burst_length": 20,
            },
            "radar": {
                "carrier_freq": radar_data["carrier_freq"],
                "transmit_power": radar_data["transmit_power"],
                "receiver_gain_dB": 30.0,
                "system_losses": 2.0,
                "noise_figure": 3.0,
                "squint_angle": 0.0,
                "reference_temp": 290.0,
                "polarization": "single",
                "mode": meta["mode"],
                "look_side": "right",
                "depression_angle": radar_data["depression_angle"],
            },
            "antenna": {
                "preset": "flat",
                "az_beamwidth": math.radians(10.0),
                "el_beamwidth": math.radians(10.0),
                "peak_gain_dB": 30.0,
            },
            "waveform": {
                "waveform_type": "LFM",
                "prf": radar_data["prf"],
                "bandwidth": radar_data["bandwidth"],
                "duty_cycle": 0.01,
                "window": None,
                "phase_noise": None,
            },
            "platform": {
                **platform_data,
                "perturbation": None,
                "gps": None,
                "imu": None,
            },
            "scene": {
                "origin_lat": scene_data["origin_lat"],
                "origin_lon": scene_data["origin_lon"],
                "origin_alt": 0.0,
                "scene_center": [0, 0, 0],
                "targets": [{"position": [1000, 0, 0], "rcs": 1.0}],
            },
            "processing_config": {
                **proc_data,
                "geocoding": None,
                "polarimetric_decomposition": None,
                "image_formation_params": {},
                "moco_params": {},
                "autofocus_params": {},
                "geocoding_params": {},
                "polarimetric_decomposition_params": {},
            },
        }

    def accept(self):
        params = self.get_parameters()
        self.wizard_completed.emit(params)
        super().accept()
