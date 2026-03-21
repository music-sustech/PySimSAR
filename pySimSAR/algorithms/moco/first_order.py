"""First-Order Motion Compensation (MoCo) for SAR.

Applies a bulk (range-independent) phase correction for each pulse based on
the slant-range deviation between the measured platform position and a
reference straight-line track fitted from the navigation data.

Algorithm:
    1. Fit a straight-line reference track through GPS positions (least-squares).
    2. For each pulse n:
        dR(n) = |scene_center - nav_pos(n)| - |scene_center - ref_pos(n)|
        Phase correction: exp(+j * 4*pi/lambda * dR(n))
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter

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

    The reference track is a straight-line least-squares fit through the
    GPS-measured positions — no knowledge of the "ideal" trajectory is
    required.

    Parameters
    ----------
    scene_center : np.ndarray | None
        Reference ground point for range error computation, shape (3,).
        If None, estimated from the fitted reference trajectory geometry
        as the broadside ground point at mid-aperture.
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
        reference_track: Trajectory | None = None,
    ) -> RawData:
        """Apply first-order motion compensation.

        Parameters
        ----------
        raw_data : RawData
            Raw echo data with motion-induced phase errors.
            Echo shape: (n_azimuth, n_range).
        nav_data : NavigationData
            Navigation sensor measurements with measured positions.
        reference_track : Trajectory | None
            Explicit reference trajectory. If None (the normal case),
            a straight-line track is fitted from the GPS positions.

        Returns
        -------
        RawData
            Motion-compensated raw data with bulk phase errors corrected.
        """
        echo = raw_data.echo.copy()
        n_az, n_rg = echo.shape

        wavelength = C_LIGHT / raw_data.carrier_freq

        # Get measured positions aligned to pulse times
        nav_pos = self._align_nav_positions(n_az, raw_data.prf, nav_data)

        # Smooth GPS positions to remove measurement noise while
        # preserving the low-frequency motion errors we want to correct.
        smoothed_pos = self._smooth_positions(nav_pos)

        # Determine reference positions
        if reference_track is not None:
            ref_pos = self._align_ref_positions(
                n_az, raw_data.prf, reference_track
            )
        else:
            # Fit a straight-line reference from GPS data
            ref_pos = self._fit_straight_line(smoothed_pos)

        # Reference velocities (numerical differentiation of ref_pos)
        dt = 1.0 / raw_data.prf
        ref_vel = np.gradient(ref_pos, dt, axis=0)

        # Determine scene center
        if self._scene_center is not None:
            scene_center = self._scene_center
        else:
            scene_center = self._estimate_scene_center(ref_pos, ref_vel)

        # Compute range errors using smoothed positions (not raw GPS)
        delta_r = self._compute_range_errors(ref_pos, smoothed_pos, scene_center)

        # Apply phase correction: exp(+j * 4*pi/lambda * dR)
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
            gate_delay=raw_data.gate_delay,
        )

    # ------------------------------------------------------------------
    # Position alignment
    # ------------------------------------------------------------------

    @staticmethod
    def _align_nav_positions(
        n_az: int,
        prf: float,
        nav_data: NavigationData,
    ) -> np.ndarray:
        """Interpolate GPS positions to pulse times, shape (n_az, 3)."""
        if nav_data.position is None:
            raise ValueError("NavigationData must contain position measurements")
        pulse_times = np.arange(n_az) / prf
        if len(nav_data.time) == n_az:
            return nav_data.position.copy()
        interp = interp1d(
            nav_data.time,
            nav_data.position,
            axis=0,
            kind="linear",
            fill_value="extrapolate",
        )
        return interp(pulse_times)

    @staticmethod
    def _align_ref_positions(
        n_az: int,
        prf: float,
        reference_track: Trajectory,
    ) -> np.ndarray:
        """Get reference trajectory positions at pulse times, shape (n_az, 3)."""
        if len(reference_track) == n_az:
            return reference_track.position.copy()
        pulse_times = np.arange(n_az) / prf
        return np.column_stack(
            [reference_track.interpolate_position(t) for t in pulse_times]
        ).T

    # ------------------------------------------------------------------
    # GPS smoothing
    # ------------------------------------------------------------------

    @staticmethod
    def _smooth_positions(positions: np.ndarray) -> np.ndarray:
        """Smooth GPS positions with a Savitzky-Golay filter.

        Removes high-frequency measurement noise while preserving the
        low-frequency platform motion that MoCo needs to correct.

        Parameters
        ----------
        positions : np.ndarray
            Raw GPS positions, shape (N, 3).

        Returns
        -------
        np.ndarray
            Smoothed positions, shape (N, 3).
        """
        n = len(positions)
        # Window must be odd and <= n; use ~5% of aperture, min 5
        window = max(5, n // 20) | 1  # ensure odd
        window = min(window, n if n % 2 == 1 else n - 1)
        if window < 5:
            return positions.copy()
        poly_order = min(3, window - 1)
        smoothed = np.empty_like(positions)
        for axis in range(3):
            smoothed[:, axis] = savgol_filter(
                positions[:, axis], window, poly_order
            )
        return smoothed

    # ------------------------------------------------------------------
    # Straight-line reference fit
    # ------------------------------------------------------------------

    @staticmethod
    def _fit_straight_line(positions: np.ndarray) -> np.ndarray:
        """Fit a straight-line trajectory through measured positions.

        Performs a least-squares linear fit: pos(n) = p0 + v * t(n),
        independently for each axis.

        Parameters
        ----------
        positions : np.ndarray
            Measured positions, shape (N, 3).

        Returns
        -------
        np.ndarray
            Fitted straight-line positions, shape (N, 3).
        """
        n = len(positions)
        t = np.arange(n, dtype=float)
        # Design matrix: [1, t]
        A = np.column_stack([np.ones(n), t])
        # Solve for each axis: coeffs shape (2, 3)
        coeffs, _, _, _ = np.linalg.lstsq(A, positions, rcond=None)
        return A @ coeffs

    # ------------------------------------------------------------------
    # Scene center estimation
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Range error computation
    # ------------------------------------------------------------------

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
