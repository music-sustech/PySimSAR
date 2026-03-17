"""Prominent Point Processing (PPP) autofocus algorithm.

Identifies isolated prominent scatterers in range-compressed data,
extracts their azimuth phase histories, and estimates motion errors
from phase deviations relative to the expected model.

References
----------
Eichel, P.H. and Jakowatz, C.V., "Phase-gradient autofocus for SAR
phase correction: explanation and demonstration of algorithmic steps,"
Proc. SPIE, 1989.
"""

from __future__ import annotations

import numpy as np

from pySimSAR.algorithms.base import AutofocusAlgorithm
from pySimSAR.core.types import PhaseHistoryData, SARImage


class ProminentPointProcessing(AutofocusAlgorithm):
    """Prominent Point Processing (PPP) autofocus.

    Identifies prominent scatterers in the range-compressed domain by
    their energy contrast, extracts their azimuth phase histories,
    removes the expected quadratic phase (matched filter), and averages
    the residual phase across selected scatterers to estimate the
    common phase error.

    Parameters
    ----------
    max_iterations : int
        Maximum number of autofocus iterations.
    convergence_threshold : float
        Stop when max absolute phase correction < threshold (radians).
    n_scatterers : int
        Number of prominent scatterers to use. 0 = auto (top 25%).
    contrast_threshold : float
        Minimum energy contrast ratio (peak / median) for scatterer
        selection. Scatterers below this threshold are rejected.
    """

    name = "ppp"

    def __init__(
        self,
        max_iterations: int = 10,
        convergence_threshold: float = 0.01,
        n_scatterers: int = 0,
        contrast_threshold: float = 3.0,
    ) -> None:
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self._n_scatterers = n_scatterers
        self._contrast_threshold = contrast_threshold

    def focus(self, phase_history: object, azimuth_compressor: object) -> object:
        """Apply PPP autofocus to phase history data.

        Parameters
        ----------
        phase_history : PhaseHistoryData
            Range-compressed phase history data, shape (n_azimuth, n_range).
        azimuth_compressor : callable
            Callable(PhaseHistoryData) -> SARImage.

        Returns
        -------
        SARImage
            Focused image after autofocus correction.
        """
        phd = PhaseHistoryData(
            data=phase_history.data.copy(),
            sample_rate=phase_history.sample_rate,
            prf=phase_history.prf,
            carrier_freq=phase_history.carrier_freq,
            bandwidth=phase_history.bandwidth,
            channel=phase_history.channel,
        )

        for _ in range(self.max_iterations):
            phase_error = self.estimate_phase_error(phd)

            if np.max(np.abs(phase_error)) < self.convergence_threshold:
                break

            phd.data *= np.exp(-1j * phase_error)[:, np.newaxis]

        return azimuth_compressor(phd)

    def estimate_phase_error(self, phase_history: object) -> np.ndarray:
        """Estimate phase error from prominent scatterer phase histories.

        Steps:
        1. Compute per-range-bin energy across azimuth
        2. Select prominent scatterers by energy contrast
        3. For each selected scatterer, extract azimuth phase history
        4. Remove expected linear phase trend (best-fit line)
        5. Average residual phases across scatterers (weighted by energy)
        6. Return the common residual phase error

        Parameters
        ----------
        phase_history : PhaseHistoryData
            Range-compressed data, shape (n_azimuth, n_range).

        Returns
        -------
        np.ndarray
            Phase error estimate, shape (n_azimuth,), in radians.
        """
        data = phase_history.data  # (n_azimuth, n_range)
        n_az, n_rng = data.shape

        # Per-range-bin energy
        energy = np.sum(np.abs(data) ** 2, axis=0)  # (n_range,)

        # How many scatterers to use
        n_sel = self._n_scatterers if self._n_scatterers > 0 else max(1, n_rng // 4)
        n_sel = min(n_sel, n_rng)

        # Sort by energy descending
        sorted_bins = np.argsort(energy)[::-1]

        # Filter by contrast: energy must be > contrast_threshold * median
        median_energy = np.median(energy)
        if median_energy > 0:
            contrast_mask = energy[sorted_bins] > self._contrast_threshold * median_energy
        else:
            contrast_mask = np.ones(n_rng, dtype=bool)

        selected = sorted_bins[contrast_mask][:n_sel]

        if len(selected) == 0:
            return np.zeros(n_az)

        # Azimuth index for trend removal
        n_idx = np.arange(n_az, dtype=float)

        # Accumulate weighted residual phase
        phase_sum = np.zeros(n_az)
        weight_total = 0.0

        for rng_bin in selected:
            col = data[:, rng_bin]
            phase = np.unwrap(np.angle(col))

            # Remove linear trend (expected Doppler phase ramp)
            # Fit and subtract a line: phase = a*n + b
            coeffs = np.polyfit(n_idx, phase, 1)
            trend = np.polyval(coeffs, n_idx)
            residual = phase - trend

            # Remove mean of residual
            residual -= np.mean(residual)

            # Weight by range-bin energy
            w = energy[rng_bin]
            phase_sum += w * residual
            weight_total += w

        if weight_total > 0:
            phase_error = phase_sum / weight_total
        else:
            phase_error = np.zeros(n_az)

        # Remove mean
        phase_error -= np.mean(phase_error)

        return phase_error


__all__ = ["ProminentPointProcessing"]
