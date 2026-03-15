"""IMU error model abstract base class and sensor configuration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pySimSAR.motion.trajectory import Trajectory
    from pySimSAR.sensors.nav_data import NavigationData


class IMUErrorModel(ABC):
    """Abstract base class for IMU measurement error models.

    IMU error models add realistic noise to acceleration and angular rate
    measurements from the true platform dynamics.
    """

    name: str = ""

    @abstractmethod
    def apply(
        self,
        true_acceleration: np.ndarray,
        true_angular_rate: np.ndarray,
        time: np.ndarray,
        seed: int | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Apply IMU measurement errors to true dynamics.

        Parameters
        ----------
        true_acceleration : np.ndarray
            True acceleration in m/s^2, shape (n_samples, 3).
        true_angular_rate : np.ndarray
            True angular rate in rad/s, shape (n_samples, 3).
        time : np.ndarray
            Time stamps in seconds, shape (n_samples,).
        seed : int | None
            Random seed for reproducibility.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            (noisy_acceleration, noisy_angular_rate), each shape (n_samples, 3).
        """


class IMUSensor:
    """Inertial measurement unit configuration.

    Parameters
    ----------
    accel_noise_density : float
        Accelerometer noise density (VRW) in m/s^2/sqrt(Hz). Must be >= 0.
    gyro_noise_density : float
        Gyroscope noise density (ARW) in rad/s/sqrt(Hz). Must be >= 0.
    sample_rate : float
        IMU output rate in Hz. Must be > 0.
    error_model : IMUErrorModel
        Error generation model.
    """

    def __init__(
        self,
        accel_noise_density: float,
        gyro_noise_density: float,
        sample_rate: float,
        error_model: IMUErrorModel,
    ) -> None:
        if accel_noise_density < 0:
            raise ValueError(
                f"accel_noise_density must be >= 0, got {accel_noise_density}"
            )
        if gyro_noise_density < 0:
            raise ValueError(
                f"gyro_noise_density must be >= 0, got {gyro_noise_density}"
            )
        if sample_rate <= 0:
            raise ValueError(f"sample_rate must be > 0, got {sample_rate}")

        self.accel_noise_density = float(accel_noise_density)
        self.gyro_noise_density = float(gyro_noise_density)
        self.sample_rate = float(sample_rate)
        self.error_model = error_model

    def generate_measurements(
        self,
        trajectory: Trajectory,
        seed: int | None = None,
    ) -> NavigationData:
        """Generate IMU measurements from a true trajectory.

        Samples the trajectory at the IMU sample rate, computes true
        accelerations and angular rates, and applies the error model.

        Parameters
        ----------
        trajectory : Trajectory
            True platform trajectory.
        seed : int | None
            Random seed for reproducibility.

        Returns
        -------
        NavigationData
            IMU acceleration and angular rate measurements.
        """
        from pySimSAR.sensors.nav_data import NavigationData

        t_start = trajectory.time[0]
        t_end = trajectory.time[-1]
        dt = 1.0 / self.sample_rate
        sample_times = np.arange(t_start, t_end + dt / 2, dt)

        # Compute true accelerations via finite differences of velocity
        true_velocities = np.zeros((len(sample_times), 3))
        for i, t in enumerate(sample_times):
            true_velocities[i] = trajectory.interpolate_velocity(t)

        # Acceleration = dv/dt (finite differences)
        true_accel = np.zeros_like(true_velocities)
        if len(sample_times) > 1:
            true_accel[1:] = np.diff(true_velocities, axis=0) / dt
            true_accel[0] = true_accel[1]  # extrapolate first sample

        # Angular rate: approximate from attitude changes
        # For simplicity, use finite differences of interpolated attitude
        from scipy.interpolate import interp1d

        att_interp = np.zeros((len(sample_times), 3))
        for axis in range(3):
            f = interp1d(
                trajectory.time,
                trajectory.attitude[:, axis],
                kind="linear",
                fill_value="extrapolate",
            )
            att_interp[:, axis] = f(sample_times)

        true_gyro = np.zeros_like(att_interp)
        if len(sample_times) > 1:
            true_gyro[1:] = np.diff(att_interp, axis=0) / dt
            true_gyro[0] = true_gyro[1]

        # Apply error model
        noisy_accel, noisy_gyro = self.error_model.apply(
            true_accel, true_gyro, sample_times, seed=seed
        )

        return NavigationData(
            time=sample_times,
            acceleration=noisy_accel,
            angular_rate=noisy_gyro,
            source="imu",
        )

    def __repr__(self) -> str:
        return (
            f"IMUSensor(sample_rate={self.sample_rate}Hz, "
            f"accel_nd={self.accel_noise_density}, "
            f"gyro_nd={self.gyro_noise_density})"
        )


__all__ = ["IMUErrorModel", "IMUSensor"]
