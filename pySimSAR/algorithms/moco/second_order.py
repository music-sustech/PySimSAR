"""Second-Order Motion Compensation (MoCo) for SAR.

Extends first-order MoCo with a range-dependent phase correction that
accounts for the variation of the motion-induced phase error across
different range bins.

Algorithm:
    1. First-order: bulk phase correction per pulse (scene center reference)
    2. Residual: for each range bin R, correct the residual phase error
       arising from the quadratic approximation of the path difference:
           dR_residual(n, R) ≈ (dp_perp^2) * (1/(2R) - 1/(2R_ref))
       where dp_perp is the cross-track + vertical deviation magnitude.
"""

from __future__ import annotations

import numpy as np

from pySimSAR.algorithms.base import MotionCompensationAlgorithm
from pySimSAR.algorithms.moco.first_order import FirstOrderMoCo
from pySimSAR.core.radar import C_LIGHT
from pySimSAR.core.types import RawData
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.sensors.nav_data import NavigationData


class SecondOrderMoCo(MotionCompensationAlgorithm):
    """Second-order (range-dependent) motion compensation.

    Extends first-order MoCo by applying an additional range-dependent
    phase correction for the quadratic residual term.

    Parameters
    ----------
    scene_center : np.ndarray | None
        Reference ground point, shape (3,). Passed through to
        FirstOrderMoCo. If None, auto-estimated from trajectory.
    """

    name = "second_order"

    def __init__(self, scene_center: np.ndarray | None = None) -> None:
        self._scene_center = (
            np.asarray(scene_center, dtype=float)
            if scene_center is not None
            else None
        )

    @property
    def order(self) -> int:
        return 2

    def compensate(
        self,
        raw_data: RawData,
        nav_data: NavigationData,
        reference_track: Trajectory,
    ) -> RawData:
        """Apply second-order motion compensation.

        Parameters
        ----------
        raw_data : RawData
            Raw echo data, shape (n_azimuth, n_range).
        nav_data : NavigationData
            Navigation sensor measurements.
        reference_track : Trajectory
            Reference (ideal) trajectory.

        Returns
        -------
        RawData
            Motion-compensated raw data with range-dependent correction.
        """
        # Step 1: Apply first-order (bulk) correction
        first_order = FirstOrderMoCo(scene_center=self._scene_center)
        compensated_1st = first_order.compensate(raw_data, nav_data, reference_track)

        # Step 2: Range-dependent residual correction
        echo = compensated_1st.echo.copy()
        n_az, n_rg = echo.shape
        wavelength = C_LIGHT / raw_data.carrier_freq

        # Get aligned positions
        ref_pos, nav_pos = first_order._align_positions(
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

        # Determine scene center (same as first-order used)
        if self._scene_center is not None:
            scene_center = self._scene_center
        else:
            scene_center = FirstOrderMoCo._estimate_scene_center(ref_pos, ref_vel)

        # Reference slant range (from ideal trajectory to scene center)
        R_ref = np.linalg.norm(scene_center - ref_pos, axis=1)  # (n_az,)

        # Position deviation
        dp = nav_pos - ref_pos  # (n_az, 3)

        # Compute cross-track and vertical components of deviation
        along = ref_vel.copy()
        along[:, 2] = 0.0
        at_norm = np.linalg.norm(along, axis=1, keepdims=True)
        at_norm = np.maximum(at_norm, 1e-10)
        along /= at_norm

        # Cross-track unit vector (right-looking)
        z_hat = np.array([0.0, 0.0, 1.0])
        cross = np.cross(along, z_hat)
        ct_norm = np.linalg.norm(cross, axis=1, keepdims=True)
        ct_norm = np.maximum(ct_norm, 1e-10)
        cross /= ct_norm

        dx_cross = np.sum(dp * cross, axis=1)  # (n_az,)
        dz = dp[:, 2]  # (n_az,)

        # Quadratic deviation magnitude squared
        dp_perp_sq = dx_cross**2 + dz**2  # (n_az,)

        # Range bin slant ranges (approximate)
        range_bin_spacing = C_LIGHT / (2.0 * raw_data.sample_rate)
        # Near range estimate: use reference slant range minus half swath
        R_ref_mean = np.mean(R_ref)
        half_swath = n_rg * range_bin_spacing / 2.0
        R_near = max(R_ref_mean - half_swath, R_ref_mean * 0.5)
        R_bins = R_near + np.arange(n_rg) * range_bin_spacing  # (n_rg,)

        # Residual range error (quadratic term):
        #   dR_res(n, r) = dp_perp_sq(n) * (1/(2*R(r)) - 1/(2*R_ref(n)))
        inv_R_bins = 1.0 / (2.0 * R_bins)  # (n_rg,)
        inv_R_ref = 1.0 / (2.0 * R_ref)  # (n_az,)

        delta_r_residual = dp_perp_sq[:, np.newaxis] * (
            inv_R_bins[np.newaxis, :] - inv_R_ref[:, np.newaxis]
        )

        # Apply range-dependent phase correction
        phase_correction = np.exp(
            1j * 4.0 * np.pi / wavelength * delta_r_residual
        )
        echo *= phase_correction

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


__all__ = ["SecondOrderMoCo"]
