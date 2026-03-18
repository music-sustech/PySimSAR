"""Platform configuration for airborne/UAV SAR."""

from __future__ import annotations

from typing import Any

import numpy as np

from pySimSAR.motion.trajectory import Trajectory


class Platform:
    """Aircraft/UAV platform configuration.

    Parameters
    ----------
    velocity : float
        Nominal platform speed in m/s. Must be > 0.
    altitude : float
        Nominal flight altitude in meters (ENU z). Must be > 0.
    heading : float | array-like
        Flight direction.  Accepts either:

        * A scalar (radians) — legacy convention where 0 = North (+Y)
          and pi/2 = East (+X).  Converted internally to a 3-D unit
          vector ``[sin(h), cos(h), 0]``.
        * A 3-element direction vector ``[hx, hy, hz]`` which is
          normalised internally.  Magnitude is ignored (only direction
          matters); speed is controlled by *velocity*.
    start_position : np.ndarray | None
        Starting position in ENU meters, shape (3,).
        If None, defaults to [0, 0, altitude].
    perturbation : MotionPerturbation | None
        Motion perturbation model (optional).
    sensors : list | None
        Attached navigation sensors (GPS/IMU). Defaults to empty list.
    """

    def __init__(
        self,
        velocity: float,
        altitude: float,
        heading: float | np.ndarray = 0.0,
        start_position: np.ndarray | None = None,
        perturbation: Any | None = None,
        sensors: list | None = None,
    ) -> None:
        if velocity <= 0:
            raise ValueError(f"velocity must be > 0, got {velocity}")
        if altitude <= 0:
            raise ValueError(f"altitude must be > 0, got {altitude}")

        self.velocity = float(velocity)
        self.altitude = float(altitude)

        # Accept scalar (legacy radians) or 3-D direction vector
        h = np.asarray(heading, dtype=float)
        if h.ndim == 0:
            # Scalar → legacy angle convention
            angle = float(h) % (2 * np.pi)
            self._heading_vec = np.array(
                [np.sin(angle), np.cos(angle), 0.0]
            )
            self.heading = angle  # keep for backwards compat
        else:
            norm = float(np.linalg.norm(h))
            if norm < 1e-12:
                raise ValueError("heading vector must be non-zero")
            self._heading_vec = h / norm
            # Derive scalar heading for backwards compat (yaw angle)
            self.heading = float(
                np.arctan2(self._heading_vec[0], self._heading_vec[1])
            ) % (2 * np.pi)

        if start_position is not None:
            self.start_position = np.asarray(start_position, dtype=float)
        else:
            self.start_position = np.array([0.0, 0.0, float(altitude)])

        self.perturbation = perturbation
        self.sensors: list = sensors if sensors is not None else []

    @property
    def heading_vector(self) -> np.ndarray:
        """Unit direction vector for the flight path (read-only)."""
        return self._heading_vec.copy()

    def _heading_to_velocity_vector(self) -> np.ndarray:
        """Return the velocity vector (speed × heading direction)."""
        return self.velocity * self._heading_vec

    def generate_ideal_trajectory(
        self, n_pulses: int, prf: float
    ) -> Trajectory:
        """Generate an ideal (straight-line, constant altitude) trajectory.

        Parameters
        ----------
        n_pulses : int
            Number of pulses/time samples.
        prf : float
            Pulse repetition frequency in Hz.

        Returns
        -------
        Trajectory
            Ideal trajectory with constant velocity and zero attitude offsets.
        """
        pri = 1.0 / prf
        vel_vec = self._heading_to_velocity_vector()

        time = np.arange(n_pulses) * pri
        position = np.outer(time, vel_vec) + self.start_position
        velocity = np.tile(vel_vec, (n_pulses, 1))
        attitude = np.zeros((n_pulses, 3))
        # Set yaw to heading
        attitude[:, 2] = self.heading

        return Trajectory(
            time=time,
            position=position,
            velocity=velocity,
            attitude=attitude,
        )

    def generate_perturbed_trajectory(
        self,
        n_pulses: int,
        prf: float,
        seed: int = 42,
    ) -> Trajectory:
        """Generate a perturbed trajectory using the motion perturbation model.

        If no perturbation model is set, returns the ideal trajectory.

        Parameters
        ----------
        n_pulses : int
            Number of pulses/time samples.
        prf : float
            Pulse repetition frequency in Hz.
        seed : int
            Random seed for reproducibility.

        Returns
        -------
        Trajectory
            Perturbed trajectory with turbulence-induced deviations.
        """
        ideal = self.generate_ideal_trajectory(n_pulses, prf)

        if self.perturbation is None:
            return ideal

        pri = 1.0 / prf
        dv = self.perturbation.generate(
            n_samples=n_pulses,
            dt=pri,
            velocity=self.velocity,
            altitude=self.altitude,
            seed=seed,
        )

        # Perturbed velocity = ideal + perturbation
        perturbed_velocity = ideal.velocity + dv

        # Integrate velocity perturbations to get position offsets
        dpos = np.zeros_like(ideal.position)
        for i in range(3):
            dpos[:, i] = np.cumsum(dv[:, i]) * pri

        perturbed_position = ideal.position + dpos

        # Approximate attitude perturbations from velocity perturbations
        # Small-angle approximation: delta_angle ~ delta_v / V
        perturbed_attitude = ideal.attitude.copy()
        perturbed_attitude[:, 0] += dv[:, 1] / self.velocity   # roll from lateral
        perturbed_attitude[:, 1] += -dv[:, 2] / self.velocity  # pitch from vertical
        perturbed_attitude[:, 2] += dv[:, 0] / self.velocity   # yaw from longitudinal

        return Trajectory(
            time=ideal.time,
            position=perturbed_position,
            velocity=perturbed_velocity,
            attitude=perturbed_attitude,
        )

    def __repr__(self) -> str:
        hv = self._heading_vec
        return (
            f"Platform(velocity={self.velocity}, altitude={self.altitude}, "
            f"heading=[{hv[0]:.3f}, {hv[1]:.3f}, {hv[2]:.3f}])"
        )


__all__ = ["Platform"]
