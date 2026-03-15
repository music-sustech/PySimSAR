"""Trajectory data class for time-stamped platform state history."""

from __future__ import annotations

import numpy as np
from scipy import interpolate


class Trajectory:
    """Time-stamped platform state history.

    Stores position, velocity, and attitude arrays at discrete time steps.
    Two trajectory instances exist per simulation: the "ideal" (nominal)
    trajectory and the "true" (perturbed) trajectory.

    Parameters
    ----------
    time : np.ndarray
        Time stamps in seconds, shape (N,). Must be monotonically increasing.
    position : np.ndarray
        ENU positions in meters, shape (N, 3).
    velocity : np.ndarray
        ENU velocities in m/s, shape (N, 3).
    attitude : np.ndarray
        Euler angles [roll, pitch, yaw] in radians, shape (N, 3).
    """

    def __init__(
        self,
        time: np.ndarray,
        position: np.ndarray,
        velocity: np.ndarray,
        attitude: np.ndarray,
    ) -> None:
        time = np.asarray(time, dtype=float)
        position = np.asarray(position, dtype=float)
        velocity = np.asarray(velocity, dtype=float)
        attitude = np.asarray(attitude, dtype=float)

        n = len(time)
        if position.shape != (n, 3) or velocity.shape != (n, 3) or attitude.shape != (n, 3):
            raise ValueError(
                f"All arrays must have consistent lengths. "
                f"time={n}, position={position.shape}, "
                f"velocity={velocity.shape}, attitude={attitude.shape}"
            )

        if n > 1 and np.any(np.diff(time) <= 0):
            raise ValueError("time must be monotonically increasing")

        self.time = time
        self.position = position
        self.velocity = velocity
        self.attitude = attitude

    def interpolate_position(self, t: float) -> np.ndarray:
        """Interpolate position at an arbitrary time.

        Parameters
        ----------
        t : float
            Query time in seconds.

        Returns
        -------
        np.ndarray
            Interpolated ENU position, shape (3,).
        """
        result = np.empty(3)
        for i in range(3):
            f = interpolate.interp1d(
                self.time, self.position[:, i],
                kind="linear", fill_value="extrapolate",
            )
            result[i] = float(f(t))
        return result

    def interpolate_velocity(self, t: float) -> np.ndarray:
        """Interpolate velocity at an arbitrary time.

        Parameters
        ----------
        t : float
            Query time in seconds.

        Returns
        -------
        np.ndarray
            Interpolated ENU velocity, shape (3,).
        """
        result = np.empty(3)
        for i in range(3):
            f = interpolate.interp1d(
                self.time, self.velocity[:, i],
                kind="linear", fill_value="extrapolate",
            )
            result[i] = float(f(t))
        return result

    def __len__(self) -> int:
        return len(self.time)

    def __repr__(self) -> str:
        return (
            f"Trajectory(n_samples={len(self)}, "
            f"t=[{self.time[0]:.4f}, {self.time[-1]:.4f}]s)"
        )


__all__ = ["Trajectory"]
