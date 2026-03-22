"""Navigation helper functions for SAR motion compensation.

Shared utilities for aligning, smoothing, and fitting GPS-derived
platform positions.  Used by MoCo algorithms and the processing
pipeline to reconstruct reference trajectories.
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter

from pySimSAR.sensors.nav_data import NavigationData


def align_nav_positions(
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


def smooth_positions(positions: np.ndarray) -> np.ndarray:
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


def fit_straight_line(positions: np.ndarray) -> np.ndarray:
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


__all__ = ["align_nav_positions", "smooth_positions", "fit_straight_line"]
