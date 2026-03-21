"""Main application window for the PySimSAR GUI.

Layout (post-overhaul):
  Left panel:  ParameterTreeWidget (scrollable inline-editing tree)
  Right panel: Visualization tabs (top) + Calculated values panel (bottom)
  Bottom:      Full-width status bar with progress
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pySimSAR.core.flight_path import compute_flight_path
from pySimSAR.core.platform import Platform
from pySimSAR.core.radar import Radar, create_antenna_from_preset
from pySimSAR.core.scene import PointTarget, Scene
from pySimSAR.core.types import SARModeConfig
from pySimSAR.gui.controllers.simulation_ctrl import ProjectModel, SimulationController
from pySimSAR.gui.panels.azimuth_profile import AzimuthProfilePanel
from pySimSAR.gui.panels.beam_animation import BeamAnimationPanel
from pySimSAR.gui.panels.doppler_spectrum import DopplerSpectrumPanel
from pySimSAR.gui.panels.image_viewer import ImageViewerPanel
from pySimSAR.gui.panels.phase_history import PhaseHistoryPanel
from pySimSAR.gui.panels.polarimetry import PolarimetryPanel
from pySimSAR.gui.panels.range_profile import RangeProfilePanel
from pySimSAR.gui.panels.scene_3d import SceneViewerPanel
from pySimSAR.gui.panels.trajectory import TrajectoryViewerPanel
from pySimSAR.gui.widgets.calc_panel import CalculatedValuesPanel
from pySimSAR.gui.widgets.param_tree import ParameterTreeWidget
from pySimSAR.gui.widgets.preset_browser import PresetBrowserDialog
from pySimSAR.gui.wizards.import_wizard import ImportWizard
from pySimSAR.gui.wizards.project_wizard import ProjectCreationWizard
from pySimSAR.io.archive import pack_project, unpack_project
from pySimSAR.io.config import ProcessingConfig
from pySimSAR.io.parameter_set import load_default_gui_params, make_window
from pySimSAR.io.user_data import UserDataDir
from pySimSAR.motion.perturbation import DrydenTurbulence
from pySimSAR.sensors.gps import GPSSensor
from pySimSAR.sensors.gps_gaussian import GaussianGPSError
from pySimSAR.sensors.imu import IMUSensor
from pySimSAR.sensors.imu_white_noise import WhiteNoiseIMUError
from pySimSAR.waveforms.fmcw import FMCWWaveform
from pySimSAR.waveforms.lfm import LFMWaveform
from pySimSAR.waveforms.phase_noise import CompositePSDPhaseNoise


class PreferencesDialog(QDialog):
    """Application preferences dialog."""

    def __init__(self, prefs: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._tooltips = QCheckBox()
        self._tooltips.setChecked(prefs.get("tooltips_enabled", True))
        form.addRow("Show tooltips:", self._tooltips)

        self._colormap = QComboBox()
        self._colormap.addItems(["gray", "viridis", "plasma", "inferno", "magma", "jet"])
        self._colormap.setCurrentText(prefs.get("default_colormap", "gray"))
        form.addRow("Default colormap:", self._colormap)

        from pySimSAR.gui.widgets.param_editor import _plain_spin
        self._dynamic_range = _plain_spin(
            prefs.get("default_dynamic_range_dB", 40.0), 10.0, 120.0, 5.0, " dB"
        )
        form.addRow("Default dynamic range:", self._dynamic_range)

        from PyQt6.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_preferences(self) -> dict:
        return {
            "tooltips_enabled": self._tooltips.isChecked(),
            "default_colormap": self._colormap.currentText(),
            "default_dynamic_range_dB": self._dynamic_range.value(),
        }


class MainWindow(QMainWindow):
    """Main application window for PySimSAR.

    Layout
    ------
    Left:   ParameterTreeWidget (scrollable, inline-editing parameter tree)
    Right:  QSplitter(vertical)
              Top:    QTabWidget with visualization panels
              Bottom: CalculatedValuesPanel
    Bottom: Status bar with progress bar
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("PySimSAR - SAR Signal Simulator")
        self.resize(1400, 900)

        self._controller: SimulationController | None = None
        self._model: ProjectModel | None = None
        self._user_data = UserDataDir()
        self._user_data.ensure_structure()
        self._preferences = self._user_data.load_preferences()

        # -- Build UI components --
        self._build_menu_bar()
        self._build_toolbar()
        self._build_status_bar()
        self._build_central_widget()

        # Wire parameter tree signals
        self._param_tree.parameter_changed.connect(self._on_parameter_changed)

        # Load default project into the parameter tree
        try:
            default_params = load_default_gui_params()
            self._param_tree.set_all_parameters(default_params)
        except Exception:
            pass  # Fall back to widget-level defaults

        # Initial scene preview + calc panel update
        self._update_scene_preview()
        self._update_calc_panel()

    # ==================================================================
    # UI construction
    # ==================================================================

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        # -- File menu --
        file_menu = menu_bar.addMenu("&File")

        self._action_new = QAction("&New Project", self)
        self._action_new.setShortcut("Ctrl+N")
        self._action_new.triggered.connect(self._on_new_project)
        file_menu.addAction(self._action_new)

        self._action_import = QAction("&Import HDF5...", self)
        self._action_import.setShortcut("Ctrl+I")
        self._action_import.triggered.connect(self._on_import_hdf5)
        file_menu.addAction(self._action_import)

        self._action_save = QAction("&Save Project...", self)
        self._action_save.setShortcut("Ctrl+S")
        self._action_save.triggered.connect(self._on_save_project)
        file_menu.addAction(self._action_save)

        self._action_open = QAction("&Open Project...", self)
        self._action_open.setShortcut("Ctrl+O")
        self._action_open.triggered.connect(self._on_open_project)
        file_menu.addAction(self._action_open)

        file_menu.addSeparator()

        self._action_exit = QAction("E&xit", self)
        self._action_exit.setShortcut("Ctrl+Q")
        self._action_exit.triggered.connect(self.close)
        file_menu.addAction(self._action_exit)

        # -- Edit menu --
        edit_menu = menu_bar.addMenu("&Edit")

        self._action_prefs = QAction("&Preferences...", self)
        self._action_prefs.triggered.connect(self._on_preferences)
        edit_menu.addAction(self._action_prefs)

        # -- Tools menu --
        tools_menu = menu_bar.addMenu("&Tools")

        self._action_presets = QAction("Preset &Browser...", self)
        self._action_presets.triggered.connect(self._on_preset_browser)
        tools_menu.addAction(self._action_presets)

        # -- Simulation menu --
        sim_menu = menu_bar.addMenu("&Simulation")

        self._action_run = QAction("&Run", self)
        self._action_run.setShortcut("F5")
        self._action_run.triggered.connect(self._on_run)
        sim_menu.addAction(self._action_run)

        self._action_cancel = QAction("&Cancel", self)
        self._action_cancel.setShortcut("Shift+F5")
        self._action_cancel.setEnabled(False)
        self._action_cancel.triggered.connect(self._on_cancel)
        sim_menu.addAction(self._action_cancel)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._tb_run = toolbar.addAction("Run")
        self._tb_run.triggered.connect(self._on_run)

        self._tb_cancel = toolbar.addAction("Cancel")
        self._tb_cancel.setEnabled(False)
        self._tb_cancel.triggered.connect(self._on_cancel)

    def _build_status_bar(self) -> None:
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFixedWidth(250)

        self._mem_label = QLabel()
        self._mem_label.setFixedWidth(200)
        self._mem_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._update_memory_label()

        self._mem_timer = QTimer(self)
        self._mem_timer.timeout.connect(self._update_memory_label)
        self._mem_timer.start(2000)

        self.statusBar().addPermanentWidget(self._mem_label)
        self.statusBar().addPermanentWidget(self._progress_bar)
        self.statusBar().showMessage("Ready")

    def _update_memory_label(self) -> None:
        """Update the status bar memory usage label using OS process info."""
        mem = self._get_rss_bytes()
        if mem < 0:
            self._mem_label.setText("Memory Usage: N/A")
            return
        self._mem_label.setText(f"Memory Usage: {mem / 1024 ** 3:.2f} GB")

    @staticmethod
    def _get_rss_bytes() -> int:
        """Return process RSS in bytes (cross-platform)."""
        # 1. psutil — works on all platforms if installed
        try:
            import psutil
            return psutil.Process(os.getpid()).memory_info().rss
        except Exception:
            pass
        # 2. Platform-specific fallbacks (no third-party deps)
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                    _fields_ = [
                        ("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t),
                    ]
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
                k32.GetCurrentProcess.restype = wintypes.HANDLE
                k32.GetCurrentProcess.argtypes = []
                k32.K32GetProcessMemoryInfo.argtypes = [
                    wintypes.HANDLE,
                    ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                    wintypes.DWORD,
                ]
                k32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
                handle = k32.GetCurrentProcess()
                if k32.K32GetProcessMemoryInfo(
                    handle, ctypes.byref(counters), counters.cb
                ):
                    return counters.WorkingSetSize
            except Exception:
                pass
        elif sys.platform == "linux":
            # /proc/pid/statm gives RSS in pages
            try:
                with open(f"/proc/{os.getpid()}/statm") as f:
                    pages = int(f.read().split()[1])
                return pages * os.sysconf("SC_PAGE_SIZE")
            except Exception:
                pass
        # 3. resource module — works on macOS and Linux (fallback for both)
        try:
            import resource
            ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # macOS reports bytes; Linux reports kilobytes
            if sys.platform == "darwin":
                return ru
            return ru * 1024
        except Exception:
            pass
        return -1

    def _build_central_widget(self) -> None:
        # -- Left panel: ParameterTreeWidget --
        self._param_tree = ParameterTreeWidget()
        self._param_tree.setMinimumWidth(360)

        # -- Right panel: viz tabs (top) + calc panel (bottom) --
        self._tab_widget = QTabWidget()

        self._scene_panel = SceneViewerPanel()
        self._trajectory_panel = TrajectoryViewerPanel()
        self._beam_panel = BeamAnimationPanel()
        self._image_panel = ImageViewerPanel()

        self._phase_history_panel = PhaseHistoryPanel()
        self._range_profile_panel = RangeProfilePanel()
        self._azimuth_profile_panel = AzimuthProfilePanel()
        self._doppler_panel = DopplerSpectrumPanel()
        self._polarimetry_panel = PolarimetryPanel()

        self._tab_widget.addTab(self._scene_panel, "3D Scene")
        self._tab_widget.addTab(self._trajectory_panel, "Trajectory")
        self._tab_widget.addTab(self._beam_panel, "Beam Animation")
        self._tab_widget.addTab(self._image_panel, "SAR Image")
        self._tab_widget.addTab(self._phase_history_panel, "Phase History")
        self._tab_widget.addTab(self._range_profile_panel, "Range Profile")
        self._tab_widget.addTab(self._azimuth_profile_panel, "Azimuth Profile")
        self._tab_widget.addTab(self._doppler_panel, "Doppler Spectrum")
        self._tab_widget.addTab(self._polarimetry_panel, "Polarimetry")

        self._calc_panel = CalculatedValuesPanel()

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.addWidget(self._tab_widget)
        right_splitter.addWidget(self._calc_panel)
        right_splitter.setStretchFactor(0, 4)
        right_splitter.setStretchFactor(1, 0)
        right_splitter.setSizes([650, 160])

        # -- Main horizontal splitter --
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self._param_tree)
        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([400, 1000])

        self.setCentralWidget(main_splitter)

    # ==================================================================
    # Parameter change handling
    # ==================================================================

    def _on_parameter_changed(self, key: str, value: object) -> None:
        """Handle any parameter change from the tree."""
        self._update_scene_preview()
        self._update_calc_panel()

    def _update_calc_panel(self) -> None:
        """Recompute calculated values from current tree params."""
        try:
            all_p = self._param_tree.get_all_parameters()
            # Build flat params dict for calculator
            radar = all_p.get("radar", {})
            sarmode = all_p.get("sarmode", {})
            antenna = all_p.get("antenna", {})
            waveform = all_p.get("waveform", {})
            platform = all_p.get("platform", {})
            simulation = all_p.get("simulation", {})

            calc_params = {
                "carrier_freq": radar.get("carrier_freq", 9.65e9),
                "prf": waveform.get("prf", 1000.0),
                "bandwidth": waveform.get("bandwidth", 100e6),
                "duty_cycle": waveform.get("duty_cycle", 0.01),
                "transmit_power": radar.get("transmit_power", 1.0),
                "az_beamwidth": antenna.get("az_beamwidth", math.radians(10.0)),
                "el_beamwidth": antenna.get("el_beamwidth", math.radians(10.0)),
                                "depression_angle": sarmode.get("depression_angle", math.radians(45.0)),
                "velocity": platform.get("velocity", 100.0),
                "altitude": platform.get("altitude", 1000.0),
                "noise_figure": radar.get("noise_figure", 3.0),
                "system_losses": radar.get("system_losses", 2.0),
                "receiver_gain_dB": radar.get("receiver_gain_dB", 30.0),
                "reference_temp": radar.get("reference_temp", 290.0),
                "mode": sarmode.get("mode", "stripmap"),
            }

            # Swath range
            swath = simulation.get("swath_range")
            if swath is not None:
                calc_params["near_range"] = swath[0]
                calc_params["far_range"] = swath[1]

            # Flight path
            fp_mode = platform.get("flight_path_mode", "start_stop")
            start = platform.get("start_position")
            if fp_mode == "start_stop":
                stop = platform.get("stop_position")
                if start and stop:
                    calc_params["start_position"] = start
                    calc_params["stop_position"] = stop
            else:
                ft = platform.get("flight_time")
                if ft:
                    calc_params["flight_time"] = ft

            self._calc_panel.update(calc_params)
        except Exception:
            pass

    # ==================================================================
    # Live scene preview
    # ==================================================================

    def _update_scene_preview(self) -> None:
        """Refresh the 3D scene panel with current targets and platform."""
        try:
            all_p = self._param_tree.get_all_parameters()
            scene_params = all_p["scene"]
            sarmode_params = all_p["sarmode"]
            waveform_params = all_p["waveform"]
            platform_params = all_p["platform"]

            scene = Scene(
                origin_lat=scene_params["origin_lat"],
                origin_lon=scene_params["origin_lon"],
                origin_alt=scene_params["origin_alt"],
            )
            for t in scene_params.get("targets", []):
                pos = np.array(t["position"], dtype=float)
                scene.add_target(PointTarget(position=pos, rcs=t["rcs"]))
            self._scene_panel.update_scene(scene)

            # Compute projected trajectory
            start = np.array(platform_params["start_position"], dtype=float)
            velocity = platform_params["velocity"]
            heading_vec = np.array(platform_params["heading"], dtype=float)
            h_norm = np.linalg.norm(heading_vec)
            if h_norm < 1e-12:
                heading_vec = np.array([0.0, 1.0, 0.0])
            else:
                heading_vec = heading_vec / h_norm
            vel_vec = velocity * heading_vec
            heading_rad = float(np.arctan2(heading_vec[0], heading_vec[1]))

            # Derive n_pulses from flight path
            prf = waveform_params.get("prf", 1000.0)
            fp_mode = platform_params.get("flight_path_mode", "start_stop")
            if fp_mode == "start_stop" and "stop_position" in platform_params:
                stop = np.array(platform_params["stop_position"], dtype=float)
                dist = np.linalg.norm(stop - start)
                total_time = dist / velocity if velocity > 0 else 1.0
            elif "flight_time" in platform_params:
                total_time = platform_params["flight_time"]
            else:
                # Fallback: use a default
                total_time = 5.0

            n_pulses = max(2, int(prf * total_time))
            times = np.linspace(0, total_time, min(n_pulses, 500))
            traj = np.column_stack([
                start[0] + vel_vec[0] * times,
                start[1] + vel_vec[1] * times,
                start[2] + vel_vec[2] * times,
            ])
            self._scene_panel.update_platform(
                start_position=start,
                trajectory_positions=traj,
                depression_angle=math.degrees(sarmode_params["depression_angle"]),
                look_side=sarmode_params["look_side"],
                heading_rad=heading_rad,
            )
        except Exception:
            pass  # Non-critical

    # ==================================================================
    # Model building helpers
    # ==================================================================

    def _build_project_model(self) -> ProjectModel:
        """Collect parameters from tree and construct a ProjectModel."""
        model = ProjectModel()
        all_p = self._param_tree.get_all_parameters()
        scene_params = all_p["scene"]
        sarmode_params = all_p["sarmode"]
        radar_params = all_p["radar"]
        antenna_params = all_p["antenna"]
        waveform_params = all_p["waveform"]
        platform_params = all_p["platform"]
        simulation_params = all_p["simulation"]
        proc_params = all_p["processing_config"]

        # -- Scene --
        scene = Scene(
            origin_lat=scene_params["origin_lat"],
            origin_lon=scene_params["origin_lon"],
            origin_alt=scene_params["origin_alt"],
        )
        for t in scene_params.get("targets", []):
            pos = np.array(t["position"], dtype=float)
            vel = t.get("velocity")
            if vel is not None:
                vel = np.array(vel, dtype=float)
            scene.add_target(PointTarget(position=pos, rcs=t["rcs"], velocity=vel))
        model.scene = scene

        # -- Waveform --
        wf_params = waveform_params
        phase_noise = None
        pn = wf_params.get("phase_noise")
        if pn is not None:
            phase_noise = CompositePSDPhaseNoise(
                flicker_fm_level=pn["flicker_fm_level"],
                white_fm_level=pn["white_fm_level"],
                flicker_pm_level=pn["flicker_pm_level"],
                white_floor=pn["white_floor"],
            )
        window_params = {}
        if "kaiser_beta" in wf_params:
            window_params["beta"] = wf_params["kaiser_beta"]
        window = make_window(wf_params.get("window"), window_params)

        prf = wf_params.get("prf", 1000.0)
        if wf_params["waveform_type"] == "LFM":
            waveform = LFMWaveform(
                bandwidth=wf_params["bandwidth"],
                duty_cycle=wf_params.get("duty_cycle", 0.01),
                phase_noise=phase_noise,
                window=window,
                prf=prf,
            )
        else:
            waveform = FMCWWaveform(
                bandwidth=wf_params["bandwidth"],
                duty_cycle=wf_params.get("duty_cycle", 1.0),
                ramp_type=wf_params.get("ramp_type", "up"),
                phase_noise=phase_noise,
                window=window,
                prf=prf,
            )

        # -- Antenna --
        antenna = create_antenna_from_preset(
            preset=antenna_params["preset"],
            az_beamwidth=antenna_params["az_beamwidth"],
            el_beamwidth=antenna_params["el_beamwidth"],
        )

        # -- SAR Imaging config --
        sar_mode_config = SARModeConfig(
            mode=sarmode_params["mode"],
            look_side=sarmode_params["look_side"],
            depression_angle=sarmode_params["depression_angle"],
            squint_angle=sarmode_params.get("squint_angle", 0.0),
            scene_center=np.array(sarmode_params.get("scene_center", [0, 0, 0]), dtype=float),
            n_subswaths=sarmode_params.get("n_subswaths", 3),
            burst_length=sarmode_params.get("burst_length", 20),
        )

        # -- Radar --
        model.radar = Radar(
            carrier_freq=radar_params["carrier_freq"],
            transmit_power=radar_params["transmit_power"],
            waveform=waveform,
            antenna=antenna,
            polarization=radar_params["polarization"],
            receiver_gain_dB=radar_params["receiver_gain_dB"],
            system_losses=radar_params["system_losses"],
            noise_figure=radar_params["noise_figure"],
            reference_temp=radar_params["reference_temp"],
            sar_mode_config=sar_mode_config,
        )

        # -- Platform --
        plat = platform_params
        start_pos = np.array(plat["start_position"], dtype=float)
        perturbation = None
        if plat.get("perturbation") is not None:
            p = plat["perturbation"]
            perturbation = DrydenTurbulence(
                sigma_u=p["sigma_u"],
                sigma_v=p["sigma_v"],
                sigma_w=p["sigma_w"],
            )
        sensors = []
        if plat.get("gps") is not None:
            g = plat["gps"]
            sensors.append(GPSSensor(
                accuracy_rms=g["accuracy"],
                update_rate=g["rate"],
                error_model=GaussianGPSError(accuracy_rms=g["accuracy"]),
            ))
        if plat.get("imu") is not None:
            i = plat["imu"]
            sensors.append(IMUSensor(
                accel_noise_density=i["accel_noise"],
                gyro_noise_density=i["gyro_noise"],
                sample_rate=i["rate"],
                error_model=WhiteNoiseIMUError(
                    accel_noise_density=i["accel_noise"],
                    gyro_noise_density=i["gyro_noise"],
                ),
            ))
        model.platform = Platform(
            velocity=plat["velocity"],
            altitude=plat["altitude"],
            heading=np.array(plat["heading"], dtype=float),
            start_position=start_pos,
            perturbation=perturbation,
            sensors=sensors if sensors else None,
        )

        # -- Simulation (n_pulses derived from flight path) --
        fp_mode = plat.get("flight_path_mode", "start_stop")
        prf = waveform_params.get("prf", 1000.0)
        if fp_mode == "start_stop" and "stop_position" in plat:
            try:
                fp = compute_flight_path(
                    start_position=plat["start_position"],
                    stop_position=plat["stop_position"],
                    velocity=plat["velocity"],
                    prf=prf,
                )
                model.n_pulses = fp.n_pulses or 512
            except Exception:
                model.n_pulses = 512
        elif "flight_time" in plat:
            model.n_pulses = max(1, int(prf * plat["flight_time"]))
        else:
            model.n_pulses = 512

        model.seed = simulation_params["seed"]
        model.swath_range = simulation_params.get("swath_range")
        model.sample_rate = simulation_params.get("sample_rate")
        model.sar_mode_config = sar_mode_config

        # -- Processing config --
        pc = proc_params
        model.processing_config = ProcessingConfig(
            image_formation=pc.get("image_formation", "range_doppler"),
            image_formation_params=pc.get("image_formation_params", {}),
            moco=pc.get("moco"),
            moco_params=pc.get("moco_params", {}),
            autofocus=pc.get("autofocus"),
            autofocus_params=pc.get("autofocus_params", {}),
            geocoding=pc.get("geocoding"),
            polarimetric_decomposition=pc.get("polarimetric_decomposition"),
        )

        return model

    # ==================================================================
    # Simulation control
    # ==================================================================

    def _on_run(self) -> None:
        """Collect parameters, build the model, and start the simulation."""
        if self._controller is not None and self._controller.is_running:
            self.statusBar().showMessage("Simulation already running.")
            return

        try:
            self._model = self._build_project_model()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Parameter Error",
                f"Failed to build project model:\n{exc}",
            )
            return

        self._controller = SimulationController(self)
        self._controller.progress.connect(self._on_progress)
        self._controller.stage.connect(self._on_stage)
        self._controller.finished.connect(self._on_finished)
        self._controller.error.connect(self._on_error)

        self._action_run.setEnabled(False)
        self._tb_run.setEnabled(False)
        self._action_cancel.setEnabled(True)
        self._tb_cancel.setEnabled(True)
        self._progress_bar.setValue(0)
        self.statusBar().showMessage("Simulation running...")

        self._controller.start(self._model, run_pipeline=True)

    def _on_cancel(self) -> None:
        if self._controller is not None:
            self._controller.cancel()
        self.statusBar().showMessage("Cancellation requested...")

    def _on_progress(self, value: int) -> None:
        self._progress_bar.setValue(value)

    def _on_stage(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _on_finished(self, model: ProjectModel) -> None:
        self._model = model
        self._restore_run_state()
        self._progress_bar.setValue(100)
        self.statusBar().showMessage("Simulation complete.")
        self._update_panels(model)

    def _on_error(self, message: str) -> None:
        self._restore_run_state()
        self._progress_bar.setValue(0)
        self.statusBar().showMessage("Simulation failed.")
        QMessageBox.critical(self, "Simulation Error", message)

    def _restore_run_state(self) -> None:
        self._action_run.setEnabled(True)
        self._tb_run.setEnabled(True)
        self._action_cancel.setEnabled(False)
        self._tb_cancel.setEnabled(False)

    def _update_panels(self, model: ProjectModel) -> None:
        """Push simulation/pipeline results into the visualization panels."""
        self._update_scene_preview()

        if model.simulation_result is not None:
            sim = model.simulation_result
            ideal_traj = getattr(sim, "ideal_trajectory", None)
            true_traj = getattr(sim, "true_trajectory", None)
            self._trajectory_panel.update_trajectories(ideal_traj, true_traj)

            if true_traj is not None and model.radar is not None:
                try:
                    self._beam_panel.setup(true_traj, model.radar)
                except Exception:
                    pass

        if model.pipeline_result is not None:
            pr = model.pipeline_result
            images = pr.images
            if images:
                first_key = next(iter(images))
                first_image = images[first_key]
                self._image_panel.update_image(first_image)
                self._range_profile_panel.update(first_image)
                self._azimuth_profile_panel.update(first_image)
                self._tab_widget.setCurrentWidget(self._image_panel)

            # Phase history (intermediate result)
            if pr.phase_history:
                first_phd = next(iter(pr.phase_history.values()))
                self._phase_history_panel.update(first_phd)

            # Doppler spectrum (from raw data reference)
            if pr.raw_data_ref:
                first_rd = next(iter(pr.raw_data_ref.values()))
                self._doppler_panel.update(first_rd, model.radar)

            # Polarimetric decomposition
            if pr.decomposition:
                self._polarimetry_panel.update(pr.decomposition)

    # ==================================================================
    # File menu actions
    # ==================================================================

    def _on_new_project(self) -> None:
        """Launch the project creation wizard."""
        wizard = ProjectCreationWizard(self)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            params = wizard.get_parameters()
            self._param_tree.set_all_parameters(params)

            # Clear panels
            self._scene_panel.clear()
            self._trajectory_panel.clear()
            self._beam_panel.clear()
            self._image_panel.clear()
            self._phase_history_panel.clear()
            self._range_profile_panel.clear()
            self._azimuth_profile_panel.clear()
            self._doppler_panel.clear()
            self._polarimetry_panel.clear()
            self._calc_panel.clear()

            self._model = None
            self._progress_bar.setValue(0)
            self.statusBar().showMessage("New project created.")

            self._update_scene_preview()
            self._update_calc_panel()

    def _on_import_hdf5(self) -> None:
        """Launch import wizard for HDF5 data."""
        wizard = ImportWizard(self)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            filepath = wizard.get_filepath()
            if not filepath:
                return
            try:
                model = ProjectModel()
                model.import_from_hdf5(filepath)
                pc = self._param_tree.get_all_parameters()["processing_config"]
                model.processing_config = ProcessingConfig(
                    image_formation=pc.get("image_formation", "range_doppler"),
                    image_formation_params=pc.get("image_formation_params", {}),
                    moco=pc.get("moco"),
                    moco_params=pc.get("moco_params", {}),
                    autofocus=pc.get("autofocus"),
                    autofocus_params=pc.get("autofocus_params", {}),
                    geocoding=pc.get("geocoding"),
                    polarimetric_decomposition=pc.get("polarimetric_decomposition"),
                )
                self._model = model
                self.statusBar().showMessage(f"Imported: {Path(filepath).name}")
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "Import Error",
                    f"Failed to import HDF5 file:\n{exc}",
                )

    def _on_save_project(self) -> None:
        """Save the current project state to HDF5 or .pysimsar archive."""
        if self._model is None:
            QMessageBox.information(
                self,
                "Save Project",
                "No project to save. Run a simulation or import data first.",
            )
            return

        filepath, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            "",
            "HDF5 Files (*.h5 *.hdf5);;PySimSAR Archive (*.pysimsar);;All Files (*)",
        )
        if not filepath:
            return

        try:
            fp = Path(filepath)
            if fp.suffix == ".pysimsar":
                # Save HDF5 to temp dir, then pack
                import tempfile
                with tempfile.TemporaryDirectory() as tmpdir:
                    h5_path = Path(tmpdir) / "project.h5"
                    self._model.save_project(str(h5_path))
                    # Save current parameters as JSON
                    import json
                    params = self._param_tree.get_all_parameters()
                    params_path = Path(tmpdir) / "parameters.json"
                    with open(params_path, "w", encoding="utf-8") as f:
                        json.dump(params, f, indent=2, default=str)
                    pack_project(tmpdir, fp)
            else:
                self._model.save_project(filepath)
            self.statusBar().showMessage(f"Saved: {fp.name}")
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save project:\n{exc}",
            )

    def _on_open_project(self) -> None:
        """Open a project from JSON directory, HDF5, or .pysimsar archive."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            "",
            "All Project Files (*.json *.h5 *.hdf5 *.pysimsar);;"
            "JSON Project (project.json);;"
            "HDF5 Files (*.h5 *.hdf5);;"
            "PySimSAR Archive (*.pysimsar);;"
            "All Files (*)",
        )
        if not filepath:
            return

        try:
            fp = Path(filepath)
            if fp.suffix == ".json":
                # JSON project directory — load via parameter_set
                from pySimSAR.io.parameter_set import (
                    load_parameter_set,
                    project_to_gui_params,
                )
                params = load_parameter_set(fp)
                gui_params = project_to_gui_params(params)
                # Convert swath_range from list to tuple
                sim = gui_params.get("simulation", {})
                if "swath_range" in sim and isinstance(sim["swath_range"], list):
                    sim["swath_range"] = tuple(sim["swath_range"])
                self._param_tree.set_all_parameters(gui_params)
                self._build_project_model()
            elif fp.suffix == ".pysimsar":
                import json
                import tempfile
                tmpdir = tempfile.mkdtemp(prefix="pysimsar_")
                unpack_project(fp, tmpdir)
                # Load parameters if available
                params_path = Path(tmpdir) / "parameters.json"
                if params_path.exists():
                    with open(params_path, encoding="utf-8") as f:
                        params = json.load(f)
                    # Convert swath_range from list to tuple
                    sim = params.get("simulation", {})
                    if "swath_range" in sim and isinstance(sim["swath_range"], list):
                        sim["swath_range"] = tuple(sim["swath_range"])
                    self._param_tree.set_all_parameters(params)
                # Load HDF5 data if present
                h5_path = Path(tmpdir) / "project.h5"
                if h5_path.exists():
                    model = ProjectModel()
                    model.import_from_hdf5(str(h5_path))
                    self._model = model
            else:
                model = ProjectModel()
                model.import_from_hdf5(filepath)
                self._model = model

            self.statusBar().showMessage(f"Opened: {fp.name}")
            self._update_scene_preview()
            self._update_calc_panel()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Open Error",
                f"Failed to open project:\n{exc}",
            )

    def _on_preferences(self) -> None:
        """Open the preferences dialog."""
        dlg = PreferencesDialog(self._preferences, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._preferences.update(dlg.get_preferences())
            self._user_data.save_preferences(self._preferences)
            self.statusBar().showMessage("Preferences saved.")

    def _on_preset_browser(self) -> None:
        """Open the preset browser dialog."""
        dlg = PresetBrowserDialog(self)
        dlg.preset_applied.connect(self._on_preset_applied)
        dlg.exec()

    def _on_preset_applied(self, params: dict) -> None:
        """Apply a preset to the parameter tree."""
        self._param_tree.set_all_parameters(params)
        self._update_scene_preview()
        self._update_calc_panel()
        self.statusBar().showMessage("Preset applied.")


# ======================================================================
# Application entry points
# ======================================================================


def launch() -> MainWindow:
    """Create the QApplication (if needed) and show the MainWindow."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    return window


def main() -> None:
    """Entry point: launch the application and run the event loop."""
    app = QApplication.instance()
    created_app = False
    if app is None:
        app = QApplication(sys.argv)
        created_app = True

    window = MainWindow()
    window.show()

    if created_app:
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
