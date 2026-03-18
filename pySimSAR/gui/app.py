"""Main application window for the PySimSAR GUI.

Wires together parameter editors, algorithm selector, visualization panels,
and the simulation controller into a single QMainWindow.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pySimSAR.gui.widgets.param_editor import (
    AntennaParamEditor,
    RadarParamEditor,
    WaveformParamEditor,
    PlatformParamEditor,
    SceneParamEditor,
    SimulationParamEditor,
)
from pySimSAR.gui.widgets.algorithm_selector import AlgorithmSelector
from pySimSAR.gui.panels.scene_3d import SceneViewerPanel
from pySimSAR.gui.panels.trajectory import TrajectoryViewerPanel
from pySimSAR.gui.panels.beam_animation import BeamAnimationPanel
from pySimSAR.gui.panels.image_viewer import ImageViewerPanel
from pySimSAR.gui.controllers.simulation_ctrl import SimulationController, ProjectModel
from pySimSAR.core.scene import Scene, PointTarget
from pySimSAR.core.radar import Radar, AntennaPattern, create_antenna_from_preset
from pySimSAR.core.platform import Platform
from pySimSAR.core.types import SARImage
from pySimSAR.waveforms.lfm import LFMWaveform
from pySimSAR.waveforms.fmcw import FMCWWaveform
from pySimSAR.waveforms.phase_noise import CompositePSDPhaseNoise
from pySimSAR.io.config import ProcessingConfig
from pySimSAR.motion.perturbation import DrydenTurbulence
from pySimSAR.sensors.gps import GPSSensor
from pySimSAR.sensors.gps_gaussian import GaussianGPSError
from pySimSAR.sensors.imu import IMUSensor
from pySimSAR.sensors.imu_white_noise import WhiteNoiseIMUError


class MainWindow(QMainWindow):
    """Main application window for PySimSAR.

    Layout
    ------
    Left sidebar: scrollable parameter editors and algorithm selector.
    Right area: tabbed visualization panels (3D Scene, Trajectory,
    Beam Animation, SAR Image).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("PySimSAR - SAR Signal Simulator")
        self.resize(1400, 900)

        self._controller: SimulationController | None = None
        self._model: ProjectModel | None = None

        # -- Build UI components --
        self._build_menu_bar()
        self._build_toolbar()
        self._build_status_bar()
        self._build_central_widget()

        # Show initial scene preview (platform trajectory)
        self._update_scene_preview()

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

        file_menu.addSeparator()

        self._action_exit = QAction("E&xit", self)
        self._action_exit.setShortcut("Ctrl+Q")
        self._action_exit.triggered.connect(self.close)
        file_menu.addAction(self._action_exit)

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
        self.statusBar().addPermanentWidget(self._progress_bar)
        self.statusBar().showMessage("Ready")

    def _build_central_widget(self) -> None:
        # -- Left sidebar: parameter editors inside a scroll area --
        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(4, 4, 4, 4)

        self._sim_editor = SimulationParamEditor()
        self._radar_editor = RadarParamEditor()
        self._antenna_editor = AntennaParamEditor()
        self._waveform_editor = WaveformParamEditor()
        self._platform_editor = PlatformParamEditor()
        self._scene_editor = SceneParamEditor()
        self._algorithm_selector = AlgorithmSelector()

        sidebar_layout.addWidget(self._sim_editor)
        sidebar_layout.addWidget(self._radar_editor)
        sidebar_layout.addWidget(self._antenna_editor)
        sidebar_layout.addWidget(self._waveform_editor)
        sidebar_layout.addWidget(self._platform_editor)
        sidebar_layout.addWidget(self._scene_editor)
        sidebar_layout.addWidget(self._algorithm_selector)
        sidebar_layout.addStretch()

        # Live-update scene preview when params change
        self._scene_editor.params_changed.connect(self._update_scene_preview)
        self._platform_editor.params_changed.connect(self._update_scene_preview)
        self._sim_editor.params_changed.connect(self._update_scene_preview)
        self._radar_editor.params_changed.connect(self._update_scene_preview)
        self._antenna_editor.params_changed.connect(self._update_scene_preview)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(sidebar_widget)
        scroll_area.setMinimumWidth(320)

        # -- Right area: tabbed visualization panels --
        self._tab_widget = QTabWidget()

        self._scene_panel = SceneViewerPanel()
        self._trajectory_panel = TrajectoryViewerPanel()
        self._beam_panel = BeamAnimationPanel()
        self._image_panel = ImageViewerPanel()

        self._tab_widget.addTab(self._scene_panel, "3D Scene")
        self._tab_widget.addTab(self._trajectory_panel, "Trajectory")
        self._tab_widget.addTab(self._beam_panel, "Beam Animation")
        self._tab_widget.addTab(self._image_panel, "SAR Image")

        # -- Splitter --
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(scroll_area)
        splitter.addWidget(self._tab_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 1020])

        self.setCentralWidget(splitter)

    # ==================================================================
    # Live scene preview
    # ==================================================================

    def _update_scene_preview(self) -> None:
        """Refresh the 3D scene panel with current targets and platform."""
        try:
            scene_params = self._scene_editor.get_params()
            scene = Scene(
                origin_lat=scene_params["origin_lat"],
                origin_lon=scene_params["origin_lon"],
                origin_alt=scene_params["origin_alt"],
            )
            for t in scene_params.get("targets", []):
                pos = np.array(t["position"], dtype=float)
                scene.add_target(PointTarget(position=pos, rcs=t["rcs"]))
            self._scene_panel.update_scene(scene)

            # Show platform start and projected trajectory
            plat_params = self._platform_editor.get_params()
            start = np.array(plat_params["start_position"], dtype=float)
            sim_params = self._sim_editor.get_params()
            radar_params = self._radar_editor.get_params()

            # Compute projected trajectory line
            n_pulses = sim_params["n_pulses"]
            prf = radar_params["prf"]
            velocity = plat_params["velocity"]
            heading_vec = np.array(plat_params["heading"], dtype=float)
            h_norm = np.linalg.norm(heading_vec)
            if h_norm < 1e-12:
                heading_vec = np.array([0.0, 1.0, 0.0])
            else:
                heading_vec = heading_vec / h_norm
            vel_vec = velocity * heading_vec
            heading_rad = float(np.arctan2(heading_vec[0], heading_vec[1]))
            dt = 1.0 / prf if prf > 0 else 0.001
            total_time = n_pulses * dt
            times = np.linspace(0, total_time, min(n_pulses, 500))
            traj = np.column_stack([
                start[0] + vel_vec[0] * times,
                start[1] + vel_vec[1] * times,
                start[2] + vel_vec[2] * times,
            ])
            self._scene_panel.update_platform(
                start_position=start,
                trajectory_positions=traj,
                depression_angle=math.degrees(radar_params["depression_angle"]),
                look_side=radar_params["look_side"],
                heading_rad=heading_rad,
            )
        except Exception:
            pass  # Non-critical, don't block the user

    # ==================================================================
    # Model building helpers
    # ==================================================================

    def _build_project_model(self) -> ProjectModel:
        """Collect parameters from all editors and construct a ProjectModel."""
        model = ProjectModel()

        # -- Scene --
        scene_params = self._scene_editor.get_params()
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
        wf_params = self._waveform_editor.get_params()
        # Build optional phase noise model
        phase_noise = None
        pn = wf_params.get("phase_noise")
        if pn is not None:
            phase_noise = CompositePSDPhaseNoise(
                flicker_fm_level=pn["flicker_fm_level"],
                white_fm_level=pn["white_fm_level"],
                flicker_pm_level=pn["flicker_pm_level"],
                white_floor=pn["white_floor"],
            )
        # Build optional window function
        window = wf_params.get("window")
        if window is not None:
            window = getattr(np, window, None)

        if wf_params["waveform_type"] == "LFM":
            waveform = LFMWaveform(
                bandwidth=wf_params["bandwidth"],
                duty_cycle=wf_params.get("duty_cycle", 0.01),
                phase_noise=phase_noise,
                window=window,
            )
        else:
            waveform = FMCWWaveform(
                bandwidth=wf_params["bandwidth"],
                duty_cycle=wf_params.get("duty_cycle", 1.0),
                ramp_type=wf_params.get("ramp_type", "up"),
                phase_noise=phase_noise,
                window=window,
            )

        # -- Antenna --
        ant_params = self._antenna_editor.get_params()
        antenna = create_antenna_from_preset(
            preset=ant_params["preset"],
            az_beamwidth=ant_params["az_beamwidth"],
            el_beamwidth=ant_params["el_beamwidth"],
            peak_gain_dB=ant_params["peak_gain_dB"],
        )

        # -- Radar --
        radar_params = self._radar_editor.get_params()
        model.radar = Radar(
            carrier_freq=radar_params["carrier_freq"],
            prf=radar_params["prf"],
            transmit_power=radar_params["transmit_power"],
            waveform=waveform,
            antenna=antenna,
            polarization=radar_params["polarization"],
            mode=radar_params["mode"],
            look_side=radar_params["look_side"],
            depression_angle=radar_params["depression_angle"],
            squint_angle=radar_params["squint_angle"],
            receiver_gain_dB=radar_params["receiver_gain_dB"],
            system_losses=radar_params["system_losses"],
            noise_figure=radar_params["noise_figure"],
            reference_temp=radar_params["reference_temp"],
        )

        # -- Platform --
        plat_params = self._platform_editor.get_params()
        start_pos = np.array(plat_params["start_position"], dtype=float)
        perturbation = None
        if plat_params.get("perturbation") is not None:
            p = plat_params["perturbation"]
            perturbation = DrydenTurbulence(
                sigma_u=p["sigma_u"],
                sigma_v=p["sigma_v"],
                sigma_w=p["sigma_w"],
            )
        sensors = []
        if plat_params.get("gps") is not None:
            g = plat_params["gps"]
            sensors.append(GPSSensor(
                accuracy_rms=g["accuracy"],
                update_rate=g["rate"],
                error_model=GaussianGPSError(sigma=g["accuracy"]),
            ))
        if plat_params.get("imu") is not None:
            i = plat_params["imu"]
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
            velocity=plat_params["velocity"],
            altitude=plat_params["altitude"],
            heading=np.array(plat_params["heading"], dtype=float),
            start_position=start_pos,
            perturbation=perturbation,
            sensors=sensors if sensors else None,
        )

        # -- Simulation --
        sim_params = self._sim_editor.get_params()
        model.n_pulses = sim_params["n_pulses"]
        model.seed = sim_params["seed"]
        model.swath_range = sim_params.get("swath_range")
        model.sample_rate = sim_params.get("sample_rate")
        model.scene_center = sim_params.get("scene_center")
        model.n_subswaths = sim_params.get("n_subswaths", 3)
        model.burst_length = sim_params.get("burst_length", 20)

        # -- Processing config --
        model.processing_config = self._algorithm_selector.get_config()

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
        self._controller.finished.connect(self._on_finished)
        self._controller.error.connect(self._on_error)

        # Update UI state
        self._action_run.setEnabled(False)
        self._tb_run.setEnabled(False)
        self._action_cancel.setEnabled(True)
        self._tb_cancel.setEnabled(True)
        self._progress_bar.setValue(0)
        self.statusBar().showMessage("Simulation running...")

        self._controller.start(self._model, run_pipeline=True)

    def _on_cancel(self) -> None:
        """Cancel the currently running simulation."""
        if self._controller is not None:
            self._controller.cancel()
        self.statusBar().showMessage("Cancellation requested...")

    def _on_progress(self, value: int) -> None:
        """Update the progress bar."""
        self._progress_bar.setValue(value)

    def _on_finished(self, model: ProjectModel) -> None:
        """Handle simulation completion: update all visualization panels."""
        self._model = model
        self._restore_run_state()
        self._progress_bar.setValue(100)
        self.statusBar().showMessage("Simulation complete.")

        # Update visualization panels with results
        self._update_panels(model)

    def _on_error(self, message: str) -> None:
        """Handle simulation error."""
        self._restore_run_state()
        self._progress_bar.setValue(0)
        self.statusBar().showMessage("Simulation failed.")
        QMessageBox.critical(self, "Simulation Error", message)

    def _restore_run_state(self) -> None:
        """Re-enable the Run button and disable Cancel after simulation ends."""
        self._action_run.setEnabled(True)
        self._tb_run.setEnabled(True)
        self._action_cancel.setEnabled(False)
        self._tb_cancel.setEnabled(False)

    def _update_panels(self, model: ProjectModel) -> None:
        """Push simulation/pipeline results into the visualization panels."""
        # Scene + platform (re-add both so platform isn't lost)
        self._update_scene_preview()

        # Trajectories
        if model.simulation_result is not None:
            sim = model.simulation_result
            ideal_traj = getattr(sim, "ideal_trajectory", None)
            true_traj = getattr(sim, "true_trajectory", None)
            self._trajectory_panel.update_trajectories(ideal_traj, true_traj)

            # Beam animation
            if true_traj is not None and model.radar is not None:
                try:
                    self._beam_panel.setup(true_traj, model.radar)
                except Exception:
                    pass  # Non-critical

        # SAR Image (show the first available image from pipeline results)
        if model.pipeline_result is not None:
            images = model.pipeline_result.images
            if images:
                # images is a dict; show the first one
                first_key = next(iter(images))
                first_image = images[first_key]
                self._image_panel.update_image(first_image)
                self._tab_widget.setCurrentWidget(self._image_panel)

    # ==================================================================
    # File menu actions
    # ==================================================================

    def _on_new_project(self) -> None:
        """Reset all editors and panels to defaults."""
        # Reset editors to default values
        self._sim_editor.set_params({
            "n_pulses": 512, "seed": 42, "swath_range": (1350.0, 1500.0),
            "sample_rate": None, "scene_center": [0, 0, 0],
            "n_subswaths": 3, "burst_length": 20,
        })
        self._radar_editor.set_params({
            "carrier_freq": 9.65e9,
            "prf": 1000.0,
            "transmit_power": 1000.0,
            "receiver_gain_dB": 30.0,
            "system_losses": 2.0,
            "noise_figure": 3.0,
            "squint_angle": 0.0,
            "reference_temp": 290.0,
            "polarization": "single",
            "mode": "stripmap",
            "look_side": "right",
            "depression_angle": 0.7854,
        })
        self._antenna_editor.set_params({
            "preset": "flat",
            "az_beamwidth": math.radians(10.0),
            "el_beamwidth": math.radians(10.0),
            "peak_gain_dB": 30.0,
        })
        self._waveform_editor.set_params({
            "waveform_type": "LFM",
            "bandwidth": 100e6,
            "duty_cycle": 0.01,
            "window": None,
            "phase_noise": None,
        })
        self._platform_editor.set_params({
            "velocity": 100.0,
            "heading": [0.0, 1.0, 0.0],
            "start_position": [0.0, -25.0, 1000.0],
            "perturbation": None,
            "gps": None,
            "imu": None,
        })
        self._scene_editor.set_params({
            "origin_lat": 0.0,
            "origin_lon": 0.0,
            "origin_alt": 0.0,
            "targets": [{"position": [1000, 0, 0], "rcs": 1.0}],
        })

        # Clear panels
        self._scene_panel.clear()
        self._trajectory_panel.clear()
        self._beam_panel.clear()
        self._image_panel.clear()

        # Reset state
        self._model = None
        self._progress_bar.setValue(0)
        self.statusBar().showMessage("New project created.")

    def _on_import_hdf5(self) -> None:
        """Open a file dialog to import an HDF5 file for processing-only."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import HDF5 File",
            "",
            "HDF5 Files (*.h5 *.hdf5);;All Files (*)",
        )
        if not filepath:
            return

        try:
            model = ProjectModel()
            model.import_from_hdf5(filepath)
            model.processing_config = self._algorithm_selector.get_config()
            self._model = model
            self.statusBar().showMessage(f"Imported: {Path(filepath).name}")
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import HDF5 file:\n{exc}",
            )

    def _on_save_project(self) -> None:
        """Save the current project state to an HDF5 file."""
        if self._model is None:
            QMessageBox.information(
                self,
                "Save Project",
                "No project to save. Run a simulation or import data first.",
            )
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            "",
            "HDF5 Files (*.h5 *.hdf5);;All Files (*)",
        )
        if not filepath:
            return

        try:
            self._model.save_project(filepath)
            self.statusBar().showMessage(f"Saved: {Path(filepath).name}")
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save project:\n{exc}",
            )


# ======================================================================
# Application entry points
# ======================================================================


def launch() -> MainWindow:
    """Create the QApplication (if needed) and show the MainWindow.

    Returns the MainWindow instance for programmatic access.
    """
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
