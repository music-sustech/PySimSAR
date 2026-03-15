"""White noise IMU error model — additive white Gaussian noise."""

from __future__ import annotations

import numpy as np

from pySimSAR.sensors.imu import IMUErrorModel
from pySimSAR.sensors.registry import imu_error_registry


class WhiteNoiseIMUError(IMUErrorModel):
    """Additive white Gaussian noise IMU error model.

    Adds independent Gaussian noise to accelerometer and gyroscope outputs
    with configurable noise density. No bias drift or scale factor error.

    The noise standard deviation is: noise_density * sqrt(sample_rate),
    where sample_rate = 1/dt is inferred from the time array.

    Parameters
    ----------
    accel_noise_density : float
        Accelerometer noise density (VRW) in m/s^2/sqrt(Hz). Must be >= 0.
    gyro_noise_density : float
        Gyroscope noise density (ARW) in rad/s/sqrt(Hz). Must be >= 0.
    """

    name = "white_noise"

    def __init__(
        self,
        accel_noise_density: float,
        gyro_noise_density: float,
    ) -> None:
        if accel_noise_density < 0:
            raise ValueError(
                f"accel_noise_density must be >= 0, got {accel_noise_density}"
            )
        if gyro_noise_density < 0:
            raise ValueError(
                f"gyro_noise_density must be >= 0, got {gyro_noise_density}"
            )

        self.accel_noise_density = float(accel_noise_density)
        self.gyro_noise_density = float(gyro_noise_density)

    def apply(
        self,
        true_acceleration: np.ndarray,
        true_angular_rate: np.ndarray,
        time: np.ndarray,
        seed: int | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        rng = np.random.default_rng(seed)

        # Infer sample rate from time array
        if len(time) > 1:
            dt = np.mean(np.diff(time))
            sample_rate = 1.0 / dt
        else:
            sample_rate = 1.0

        # Noise sigma = noise_density * sqrt(sample_rate)
        accel_sigma = self.accel_noise_density * np.sqrt(sample_rate)
        gyro_sigma = self.gyro_noise_density * np.sqrt(sample_rate)

        noisy_accel = true_acceleration + rng.normal(
            0.0, accel_sigma, size=true_acceleration.shape
        )
        noisy_gyro = true_angular_rate + rng.normal(
            0.0, gyro_sigma, size=true_angular_rate.shape
        )

        return noisy_accel, noisy_gyro

    def __repr__(self) -> str:
        return (
            f"WhiteNoiseIMUError(accel_nd={self.accel_noise_density}, "
            f"gyro_nd={self.gyro_noise_density})"
        )


# Register with the IMU error registry
imu_error_registry.register(WhiteNoiseIMUError)

__all__ = ["WhiteNoiseIMUError"]
