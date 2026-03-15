"""First-Order Motion Compensation (MoCo) for SAR.

Applies a bulk (range-independent) phase correction for each pulse based on
the slant-range deviation between the measured platform position and
the reference (ideal) trajectory, computed to a scene center reference point.

Algorithm:
    For each pulse n:
        1. dR(n) = |scene_center - nav_pos(n)| - |scene_center - ref_pos(n)|
        2. Phase correction: exp(+j * 4*pi/lambda * dR(n))
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import interp1d

from pySimSAR.algorithms.base import MotionCompensationAlgorithm
from pySimSAR.core.radar import C_LIGHT
from pySimSAR.core.types import RawData
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.sensors.nav_data import NavigationData


class FirstOrderMoCo(MotionCompensationAlgorithm):
    """First-order (bulk) motion compensation.

    Corrects the range-independent component of motion-induced phase
    error by computing the slant-range deviation to a reference point
    for each pulse and applying a uniform phase shift across all range bins.

    Parameters
    ----------
    scene_center : np.ndarray | None
        Reference ground point for range error computation, shape (3,).
        If None, estimated from the reference trajectory geometry as
        the broadside ground point at the mid-aperture position.
    """

    name = "first_order"

    def __init__(self, scene_center: np.ndarray | None = None) -> None:
        self._scene_center = (
            np.asarray(scene_center, dtype=float)
            if scene_center is not None
            else None
        )

    @property
    def order(self) -> int:
        return 1

    def compensate(
        self,
        raw_data: RawData,
        nav_data: NavigationData,
        reference_track: Trajectory,
    ) -> RawData:
        """Apply first-order motion compensation.

        Parameters
        ----------
        raw_data : RawData
            Raw echo data with motion-induced phase errors.
            Echo shape: (n_azimuth, n_range).
        nav_data : NavigationData
            Navigation sensor measurements with measured positions.
        reference_track : Trajectory
            Reference (ideal) trajectory.

        Returns
        -------
        RawData
            Motion-compensated raw data with bulk phase errors corrected.
        """
        echo = raw_data.echo.copy()
        n_az, n_rg = echo.shape

        wavelength = C_LIGHT / raw_data.carrier_freq

        # Get positions aligned to pulse times
        ref_pos, nav_pos = self._align_positions(
            n_az, raw_data.prf, nav_data, reference_track
        )

        # Get reference velocities
        if len(reference_track) == n_az:
            ref_vel = reference_track.velocity
        else:
            pulse_times = np.arange(n_az) / raw_data.prf
            ref_vel = np.column_stack(
                [reference_track.interpolate_velocity(t) for t in pulse_times]
            ).T

        # Determine scene center
        if self._scene_center is not None:
            scene_center = self._scene_center
        else:
            scene_center = self._estimate_scene_center(ref_pos, ref_vel)

        # Compute range errors for each pulse
        delta_r = self._compute_range_errors(ref_pos, nav_pos, scene_center)

        # Apply phase correction: exp(+j * 4*pi/lambda * dR)
        # The echo phase is -4*pi/lambda * R (see compute_echo_phase).
        # When R increases by dR, the phase decreases by 4*pi/lambda * dR.
        # To compensate, we add +4*pi/lambda * dR.
        phase_correction = np.exp(1j * 4.0 * np.pi / wavelength * delta_r)

        # Apply the same correction to all range bins in each pulse
        echo *= phase_correction[:, np.newaxis]

        return RawData(
            echo=echo,
            channel=raw_data.channel,
            sample_rate=raw_data.sample_rate,
            carrier_freq=raw_data.carrier_freq,
            bandwidth=raw_data.bandwidth,
            prf=raw_data.prf,
            waveform_name=raw_data.waveform_name,
            sar_mode=raw_data.sar_mode,
        )

    def _align_positions(
        self,
        n_az: int,
        prf: float,
        nav_data: NavigationData,
        reference_track: Trajectory,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get reference and measured positions aligned to pulse times.

        Returns
        -------
        tuple of (ref_positions, nav_positions)
            Both shape (n_az, 3).
        """
        pulse_times = np.arange(n_az) / prf

        # Reference positions
        if len(reference_track) == n_az:
            ref_pos = reference_track.position
        else:
            ref_pos = np.column_stack(
                [reference_track.interpolate_position(t) for t in pulse_times]
            ).T

        # Measured positions from nav data
        if nav_data.position is not None and len(nav_data.time) == n_az:
            nav_pos = nav_data.position
        elif nav_data.position is not None:
            interp = interp1d(
                nav_data.time,
                nav_data.position,
                axis=0,
                kind="linear",
                fill_value="extrapolate",
            )
            nav_pos = interp(pulse_times)
        else:
            raise ValueError("NavigationData must contain position measurements")

        return ref_pos, nav_pos

    @staticmethod
    def _estimate_scene_center(
        ref_pos: np.ndarray,
        ref_vel: np.ndarray,
    ) -> np.ndarray:
        """Estimate a scene center from the reference trajectory.

        Places the scene center on the ground in the cross-track
        direction from the mid-aperture position, at a ground range
        equal to the platform altitude (approximately 45-degree look).

        Parameters
        ----------
        ref_pos : np.ndarray
            Reference positions, shape (n_az, 3).
        ref_vel : np.ndarray
            Reference velocities, shape (n_az, 3).

        Returns
        -------
        np.ndarray
            Estimated scene center, shape (3,).
        """
        mid = len(ref_pos) // 2
        pos_mid = ref_pos[mid]
        vel_mid = ref_vel[mid]

        # Along-track direction (horizontal)
        along = vel_mid.copy()
        along[2] = 0.0
        norm = np.linalg.norm(along)
        if norm > 0:
            along /= norm

        # Cross-track (right-looking): along x z_hat
        cross = np.cross(along, np.array([0.0, 0.0, 1.0]))
        norm = np.linalg.norm(cross)
        if norm > 0:
            cross /= norm

        altitude = pos_mid[2]
        ground_range = max(altitude, 1000.0)

        sc = pos_mid.copy()
        sc += cross * ground_range
        sc[2] = 0.0
        return sc

    @staticmethod
    def _compute_range_errors(
        ref_pos: np.ndarray,
        nav_pos: np.ndarray,
        scene_center: np.ndarray,
    ) -> np.ndarray:
        """Compute slant-range error to scene center for each pulse.

        Parameters
        ----------
        ref_pos : np.ndarray
            Reference positions, shape (n_az, 3).
        nav_pos : np.ndarray
            Measured positions, shape (n_az, 3).
        scene_center : np.ndarray
            Reference ground point, shape (3,).

        Returns
        -------
        np.ndarray
            Range error per pulse, shape (n_az,).
        """
        r_ref = np.linalg.norm(scene_center - ref_pos, axis=1)
        r_nav = np.linalg.norm(scene_center - nav_pos, axis=1)
        return r_nav - r_ref


__all__ = ["FirstOrderMoCo"]
