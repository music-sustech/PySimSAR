"""Navigation data container for sensor measurements."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

_VALID_SOURCES = {"gps", "imu", "fused"}


@dataclass
class NavigationData:
    """Sensor-measured navigation state (with errors).

    Attributes
    ----------
    time : np.ndarray
        Measurement timestamps in seconds, shape (M,).
    position : np.ndarray | None
        Measured positions (GPS) in ENU meters, shape (M, 3).
    velocity : np.ndarray | None
        Measured velocities in m/s, shape (M, 3).
    acceleration : np.ndarray | None
        Measured accelerations (IMU) in m/s^2, shape (M, 3).
    angular_rate : np.ndarray | None
        Measured angular rates (IMU) in rad/s, shape (M, 3).
    source : str
        Sensor source: "gps", "imu", or "fused".
    """

    time: np.ndarray = field(default_factory=lambda: np.empty(0))
    position: np.ndarray | None = None
    velocity: np.ndarray | None = None
    acceleration: np.ndarray | None = None
    angular_rate: np.ndarray | None = None
    source: str = "gps"

    def __post_init__(self) -> None:
        self.time = np.asarray(self.time, dtype=float)

        if self.source not in _VALID_SOURCES:
            raise ValueError(
                f"source must be one of {_VALID_SOURCES}, got '{self.source}'"
            )

        n = len(self.time)
        if n > 1 and np.any(np.diff(self.time) <= 0):
            raise ValueError("time must be monotonically increasing")

        for name, arr in [
            ("position", self.position),
            ("velocity", self.velocity),
            ("acceleration", self.acceleration),
            ("angular_rate", self.angular_rate),
        ]:
            if arr is not None:
                arr = np.asarray(arr, dtype=float)
                if arr.shape != (n, 3):
                    raise ValueError(
                        f"{name} shape {arr.shape} inconsistent with "
                        f"time length {n}, expected ({n}, 3)"
                    )
                setattr(self, name, arr)


__all__ = ["NavigationData"]
