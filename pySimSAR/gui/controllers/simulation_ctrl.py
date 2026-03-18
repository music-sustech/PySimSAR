"""Simulation controller and project model for the PySimSAR GUI.

SimulationController runs simulation + processing in a background QThread.
ProjectModel manages project state: scene, radar, configs, results.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from pySimSAR.core.platform import Platform
from pySimSAR.core.radar import Radar
from pySimSAR.core.scene import Scene
from pySimSAR.core.types import RawData, SARImage
from pySimSAR.io.config import ProcessingConfig, SimulationConfig
from pySimSAR.io.hdf5_format import import_data, read_hdf5, write_hdf5
from pySimSAR.pipeline.runner import PipelineResult, PipelineRunner
from pySimSAR.simulation.engine import SimulationEngine, SimulationResult


# ---------------------------------------------------------------------------
# ProjectModel
# ---------------------------------------------------------------------------


class ProjectModel:
    """Holds all state for a simulation project.

    Attributes
    ----------
    scene : Scene | None
    radar : Radar | None
    platform : Platform | None
    n_pulses : int
    seed : int
    processing_config : ProcessingConfig | None
    simulation_result : SimulationResult | None
    pipeline_result : PipelineResult | None
    filepath : Path | None
        Path to the project file on disk (None if unsaved).
    """

    def __init__(self) -> None:
        self.scene: Scene | None = None
        self.radar: Radar | None = None
        self.platform: Platform | None = None
        self.n_pulses: int = 512
        self.seed: int = 42
        self.swath_range: tuple[float, float] | None = (1350.0, 1500.0)
        self.sample_rate: float | None = None
        self.scene_center: list[float] | None = None
        self.n_subswaths: int = 3
        self.burst_length: int = 20
        self.processing_config: ProcessingConfig | None = None
        self.simulation_result: SimulationResult | None = None
        self.pipeline_result: PipelineResult | None = None
        self.filepath: Path | None = None
        self._imported_data: dict | None = None

    # -- convenience properties -------------------------------------------

    @property
    def has_simulation(self) -> bool:
        """True if simulation results are available."""
        return self.simulation_result is not None

    @property
    def has_pipeline(self) -> bool:
        """True if pipeline results are available."""
        return self.pipeline_result is not None

    @property
    def is_imported(self) -> bool:
        """True if this project was created via HDF5 import."""
        return self._imported_data is not None

    # -- raw data accessor ------------------------------------------------

    def get_raw_data(self) -> dict[str, RawData] | None:
        """Return raw data dict suitable for PipelineRunner.

        Converts SimulationResult echo arrays into RawData when the
        project was created via simulation. Returns the imported raw_data
        dict when created via import.
        """
        if self._imported_data is not None:
            return self._imported_data.get("raw_data")
        if self.simulation_result is None or self.radar is None:
            return None
        sim = self.simulation_result
        raw: dict[str, RawData] = {}
        for ch_name, echo in sim.echo.items():
            raw[ch_name] = RawData(
                echo=echo,
                channel=ch_name,
                sample_rate=sim.sample_rate,
                carrier_freq=self.radar.carrier_freq,
                bandwidth=self.radar.bandwidth,
                prf=self.radar.prf,
                waveform_name=self.radar.waveform.name,
                sar_mode=self.radar.mode.value,
                gate_delay=sim.gate_delay,
            )
        return raw

    # -- workflows --------------------------------------------------------

    def create_simulation_config(self) -> SimulationConfig:
        """Build a SimulationConfig from the current model state.

        Raises
        ------
        ValueError
            If scene or radar are not set.
        """
        if self.scene is None:
            raise ValueError("Scene is required")
        if self.radar is None:
            raise ValueError("Radar is required")
        return SimulationConfig(
            scene=self.scene,
            radar=self.radar,
            n_pulses=self.n_pulses,
            seed=self.seed,
            platform=self.platform,
        )

    def import_from_hdf5(self, filepath: str | Path) -> None:
        """Import an existing HDF5 file for processing-only workflow.

        Populates ``_imported_data`` with raw_data, trajectory, etc.
        Clears any prior simulation result.

        Parameters
        ----------
        filepath : str | Path
            Path to the HDF5 file.
        """
        self._imported_data = import_data(filepath)
        self.simulation_result = None
        self.pipeline_result = None
        self.filepath = Path(filepath)

    def save_project(self, filepath: str | Path) -> None:
        """Persist the current project state to an HDF5 file.

        Parameters
        ----------
        filepath : str | Path
            Destination path.
        """
        filepath = Path(filepath)
        raw_data = self.get_raw_data()
        trajectory = None
        nav_data = None
        images = None

        if self.simulation_result is not None:
            trajectory = self.simulation_result.true_trajectory
            nav_data = self.simulation_result.navigation_data

        if self._imported_data is not None:
            trajectory = trajectory or self._imported_data.get("trajectory")
            nav_data = nav_data or self._imported_data.get("navigation_data")

        if self.pipeline_result is not None:
            images = self.pipeline_result.images

        sim_json = None
        proc_json = None
        if self.scene is not None and self.radar is not None:
            try:
                cfg = self.create_simulation_config()
                sim_json = cfg.to_json()
            except Exception:
                pass
        if self.processing_config is not None:
            try:
                proc_json = self.processing_config.to_json()
            except Exception:
                pass

        write_hdf5(
            filepath,
            raw_data=raw_data,
            trajectory=trajectory,
            navigation_data=nav_data,
            images=images,
            simulation_config_json=sim_json,
            processing_config_json=proc_json,
        )
        self.filepath = filepath

    def load_project(self, filepath: str | Path) -> None:
        """Load a previously saved project from HDF5.

        Restores raw data, trajectory, images, and configs.

        Parameters
        ----------
        filepath : str | Path
            Path to the project HDF5 file.
        """
        filepath = Path(filepath)
        data = read_hdf5(filepath)

        # Restore raw data as imported data
        if data.get("raw_data"):
            self._imported_data = {
                "raw_data": data["raw_data"],
                "trajectory": data.get("trajectory"),
                "navigation_data": data.get("navigation_data", []),
            }

        # Restore images into a PipelineResult if present
        if data.get("images"):
            self.pipeline_result = PipelineResult(
                images=data["images"],
                steps_applied=["loaded_from_file"],
            )
        else:
            self.pipeline_result = None

        # Restore configs if serialized
        config_block = data.get("config", {})
        if config_block.get("processing_config"):
            try:
                self.processing_config = ProcessingConfig.from_json(
                    config_block["processing_config"]
                )
            except Exception:
                pass

        self.simulation_result = None
        self.filepath = filepath

    def reset(self) -> None:
        """Clear all project state."""
        self.__init__()


# ---------------------------------------------------------------------------
# SimulationWorker (runs inside QThread)
# ---------------------------------------------------------------------------


class _SimulationWorker(QObject):
    """Executes simulation and pipeline processing on a background thread."""

    progress = pyqtSignal(int)
    finished = pyqtSignal(object)  # SimulationResult or PipelineResult
    error = pyqtSignal(str)

    def __init__(self, model: ProjectModel, run_pipeline: bool = True) -> None:
        super().__init__()
        self._model = model
        self._run_pipeline = run_pipeline
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            self._execute()
        except Exception as exc:
            self.error.emit(f"{type(exc).__name__}: {exc}")

    def _execute(self) -> None:
        model = self._model

        # -- Phase 1: Simulation (skip if imported) -----------------------
        if not model.is_imported:
            self.progress.emit(5)
            if self._cancelled:
                return

            engine_kwargs = dict(
                scene=model.scene,
                radar=model.radar,
                n_pulses=model.n_pulses,
                seed=model.seed,
                platform=model.platform,
                swath_range=model.swath_range,
            )
            if model.sample_rate is not None:
                engine_kwargs["sample_rate"] = model.sample_rate
            if model.scene_center is not None:
                engine_kwargs["scene_center"] = np.array(model.scene_center)
            if model.radar is not None and model.radar.mode.value == "scanmar":
                engine_kwargs["n_subswaths"] = model.n_subswaths
                engine_kwargs["burst_length"] = model.burst_length
            engine = SimulationEngine(**engine_kwargs)

            self.progress.emit(10)
            if self._cancelled:
                return

            sim_result = engine.run()
            model.simulation_result = sim_result
            self.progress.emit(50)

            if self._cancelled:
                return

        # -- Phase 2: Processing pipeline ---------------------------------
        if self._run_pipeline and model.processing_config is not None:
            raw_data = model.get_raw_data()
            if raw_data is None:
                self.error.emit("No raw data available for processing")
                return

            if self._cancelled:
                return

            self.progress.emit(60)

            trajectory = None
            nav_data = None
            ideal_trajectory = None

            if model.simulation_result is not None:
                trajectory = model.simulation_result.true_trajectory
                nav_data = model.simulation_result.navigation_data
                ideal_trajectory = model.simulation_result.ideal_trajectory
            elif model._imported_data is not None:
                trajectory = model._imported_data.get("trajectory")
                nav_data = model._imported_data.get("navigation_data")

            runner = PipelineRunner(model.processing_config)

            if self._cancelled:
                return

            self.progress.emit(70)
            pipeline_result = runner.run(
                raw_data,
                model.radar,
                trajectory,
                nav_data=nav_data,
                ideal_trajectory=ideal_trajectory,
            )
            model.pipeline_result = pipeline_result
            self.progress.emit(95)

        self.progress.emit(100)
        self.finished.emit(model)


# ---------------------------------------------------------------------------
# SimulationController
# ---------------------------------------------------------------------------


class SimulationController(QObject):
    """Runs simulation and processing in a background thread.

    Signals
    -------
    progress(int)
        Progress percentage (0-100).
    finished(ProjectModel)
        Emitted when processing completes successfully.
    error(str)
        Emitted when an error occurs.
    """

    progress = pyqtSignal(int)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _SimulationWorker | None = None

    @property
    def is_running(self) -> bool:
        """True if a simulation is currently in progress."""
        return self._thread is not None and self._thread.isRunning()

    def start(self, model: ProjectModel, run_pipeline: bool = True) -> None:
        """Launch simulation in a background thread.

        Parameters
        ----------
        model : ProjectModel
            Project model containing scene, radar, and config.
        run_pipeline : bool
            If True, also run the processing pipeline after simulation.
        """
        if self.is_running:
            self.error.emit("Simulation already running")
            return

        self._thread = QThread()
        self._worker = _SimulationWorker(model, run_pipeline)
        self._worker.moveToThread(self._thread)

        # Connect signals
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._thread.start()

    def cancel(self) -> None:
        """Request cancellation of the running simulation."""
        if self._worker is not None:
            self._worker.cancel()

    def _on_finished(self, model: ProjectModel) -> None:
        self._cleanup()
        self.finished.emit(model)

    def _on_error(self, msg: str) -> None:
        self._cleanup()
        self.error.emit(msg)

    def _cleanup(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
        self._worker = None
