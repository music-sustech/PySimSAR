"""GPS error model abstract base class and sensor configuration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pySimSAR.motion.trajectory import Trajectory
    from pySimSAR.sensors.nav_data import NavigationData


class GPSErrorModel(ABC):
    """Abstract base class for GPS measurement error models.

    GPS error models add realistic position measurement errors to
    the true platform trajectory, simulating GPS sensor imperfections.
    """

    name: str = ""

    @abstractmethod
    def apply(
        self,
        true_positions: np.ndarray,
        time: np.ndarray,
        seed: int | None = None,
    ) -> np.ndarray:
        """Apply GPS measurement errors to true positions.

        Parameters
        ----------
        true_positions : np.ndarray
            True platform positions in ENU coordinates, shape (n_samples, 3).
        time : np.ndarray
            Time stamps in seconds, shape (n_samples,).
        seed : int | None
            Random seed for reproducibility.

        Returns
        -------
        np.ndarray
            Noisy GPS position measurements, shape (n_samples, 3).
        """


class GPSSensor:
    """GPS navigation sensor configuration.

    Parameters
    ----------
    accuracy_rms : float
        Position accuracy RMS in meters. Must be > 0.
    update_rate : float
        Output rate in Hz. Must be > 0.
    error_model : GPSErrorModel
        Error generation model.
    outage_intervals : list[tuple[float, float]] | None
        Time intervals with no GPS output. Each tuple is (start, end).
    """

    def __init__(
        self,
        accuracy_rms: float,
        update_rate: float,
        error_model: GPSErrorModel,
        outage_intervals: list[tuple[float, float]] | None = None,
    ) -> None:
        if accuracy_rms <= 0:
            raise ValueError(f"accuracy_rms must be > 0, got {accuracy_rms}")
        if update_rate <= 0:
            raise ValueError(f"update_rate must be > 0, got {update_rate}")

        self.accuracy_rms = float(accuracy_rms)
        self.update_rate = float(update_rate)
        self.error_model = error_model
        self.outage_intervals: list[tuple[float, float]] = (
            outage_intervals if outage_intervals is not None else []
        )

    def generate_measurements(
        self,
        trajectory: Trajectory,
        seed: int | None = None,
    ) -> NavigationData:
        """Generate GPS measurements from a true trajectory.

        Samples the trajectory at the GPS update rate, applies the error
        model, and masks outage intervals.

        Parameters
        ----------
        trajectory : Trajectory
            True platform trajectory.
        seed : int | None
            Random seed for reproducibility.

        Returns
        -------
        NavigationData
            GPS position measurements.
        """
        from pySimSAR.sensors.nav_data import NavigationData

        # Sample at GPS update rate
        t_start = trajectory.time[0]
        t_end = trajectory.time[-1]
        dt = 1.0 / self.update_rate
        sample_times = np.arange(t_start, t_end + dt / 2, dt)

        # Interpolate true positions at sample times
        true_positions = np.zeros((len(sample_times), 3))
        for i, t in enumerate(sample_times):
            true_positions[i] = trajectory.interpolate_position(t)

        # Apply error model
        noisy_positions = self.error_model.apply(true_positions, sample_times, seed=seed)

        # Mask outage intervals
        valid = np.ones(len(sample_times), dtype=bool)
        for start, end in self.outage_intervals:
            valid &= ~((sample_times >= start) & (sample_times <= end))

        return NavigationData(
            time=sample_times[valid],
            position=noisy_positions[valid],
            source="gps",
        )

    def __repr__(self) -> str:
        return (
            f"GPSSensor(accuracy_rms={self.accuracy_rms}, "
            f"update_rate={self.update_rate}Hz)"
        )


__all__ = ["GPSErrorModel", "GPSSensor"]
