"""Windowed-sinc interpolation for RCMC in SAR image formation."""

from __future__ import annotations

import numpy as np


def sinc_interp(row: np.ndarray, src_positions: np.ndarray,
                order: int = 8) -> np.ndarray:
    """Lanczos-windowed sinc interpolation for complex 1-D data.

    Vectorised implementation: builds a (N, 2*order) index matrix and
    evaluates all kernels in one shot, avoiding per-sample Python loops.

    Parameters
    ----------
    row : (N,) complex array
        Input data.
    src_positions : (N,) float array
        Fractional source positions to sample from *row*.
    order : int
        Number of taps on each side of the interpolation point
        (total kernel width = 2 * order).

    Returns
    -------
    (N,) complex array
    """
    n = len(row)
    width = 2 * order  # kernel width

    # Integer base index for each output sample
    base = np.floor(src_positions).astype(np.intp)  # (N,)

    # Tap offsets: -order+1, -order+2, ..., 0, ..., order
    offsets = np.arange(-order + 1, order + 1)  # (width,)

    # Index matrix: (N, width)
    idx = base[:, np.newaxis] + offsets[np.newaxis, :]  # (N, width)

    # Delta matrix: fractional distance from each tap
    delta = src_positions[:, np.newaxis] - idx  # (N, width)

    # Lanczos-windowed sinc kernel
    kernel = np.sinc(delta) * np.sinc(delta / order)  # (N, width)

    # Clamp indices to valid range and zero kernel for out-of-bounds taps
    valid = (idx >= 0) & (idx < n)
    kernel[~valid] = 0.0
    idx_clamped = np.clip(idx, 0, n - 1)

    # Gather data and apply kernel
    samples = row[idx_clamped]  # (N, width) complex
    out = np.sum(kernel * samples, axis=1)  # (N,)

    return out
