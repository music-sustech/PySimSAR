"""Phase Gradient Autofocus (PGA) algorithm.

Estimates and corrects residual phase errors using dominant scatterer
selection and phase gradient estimation. Iterates until convergence.

References
----------
Wahl, D.E., Eichel, P.H., Ghiglia, D.C., and Jakowatz, C.V.,
"Phase Gradient Autofocus—A Robust Tool for High Resolution SAR Phase
Correction," IEEE Trans. Aerospace and Electronic Systems, 1994.
"""

from __future__ import annotations

import numpy as np

from pySimSAR.algorithms.base import AutofocusAlgorithm
from pySimSAR.core.types import PhaseHistoryData, SARImage


class PhaseGradientAutofocus(AutofocusAlgorithm):
    """Phase Gradient Autofocus (PGA).

    Selects dominant scatterers per range bin, estimates the azimuth
    phase gradient, and integrates to obtain a phase error correction.
    Best for scenes with strong isolated scatterers.

    Parameters
    ----------
    max_iterations : int
        Maximum number of autofocus iterations.
    convergence_threshold : float
        Stop when max absolute phase correction < threshold (radians).
    n_dominant : int
        Number of dominant range bins to use for gradient estimation.
    window_fraction : float
        Fraction of azimuth extent used for windowing around peak (0, 1].
    """

    name = "pga"

    def __init__(
        self,
        max_iterations: int = 10,
        convergence_threshold: float = 0.01,
        n_dominant: int = 0,
        window_fraction: float = 0.5,
    ) -> None:
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self._n_dominant = n_dominant
        self._window_fraction = window_fraction

    def focus(self, phase_history: object, azimuth_compressor: object) -> object:
        """Apply PGA autofocus to phase history data.

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

            # Apply correction: multiply each azimuth line
            phd.data *= np.exp(-1j * phase_error)[:, np.newaxis]

        return azimuth_compressor(phd)

    def estimate_phase_error(self, phase_history: object) -> np.ndarray:
        """Estimate residual phase error via phase gradient method.

        Steps:
        1. Select dominant scatterers (highest energy range bins)
        2. For each selected range bin, circularly shift to center the peak
        3. Apply window around the peak
        4. Compute phase gradient (finite difference of phase)
        5. Average gradients across selected bins
        6. Integrate to obtain phase error, remove mean

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

        # Number of dominant range bins to use
        n_dom = self._n_dominant if self._n_dominant > 0 else max(1, n_rng // 4)
        n_dom = min(n_dom, n_rng)

        # Select dominant range bins by total energy
        energy_per_bin = np.sum(np.abs(data) ** 2, axis=0)
        dominant_bins = np.argsort(energy_per_bin)[-n_dom:]

        # Window half-width in azimuth samples
        win_half = max(1, int(n_az * self._window_fraction / 2))

        # Accumulate weighted phase gradients
        gradient_sum = np.zeros(n_az, dtype=complex)
        weight_sum = np.zeros(n_az)

        for rng_bin in dominant_bins:
            col = data[:, rng_bin]

            # Find azimuth peak and circularly shift to center
            peak_idx = np.argmax(np.abs(col))
            shift = n_az // 2 - peak_idx
            col_shifted = np.roll(col, shift)

            # Apply window around center
            window = np.zeros(n_az)
            center = n_az // 2
            lo = max(0, center - win_half)
            hi = min(n_az, center + win_half)
            window[lo:hi] = 1.0
            col_windowed = col_shifted * window

            # Phase gradient: d/dn [angle(s(n))] via complex conjugate product
            # grad(n) = s(n) * conj(s(n-1)) — phase of this is the gradient
            grad = col_windowed[1:] * np.conj(col_windowed[:-1])

            # Magnitude weighting (higher SNR bins get more weight)
            mag = np.abs(col_windowed)
            w = mag[:-1] * mag[1:]

            # Pad to full length (prepend zero for the first sample)
            grad_full = np.concatenate([[0.0 + 0j], grad])
            w_full = np.concatenate([[0.0], w])

            # Undo the circular shift
            gradient_sum += np.roll(grad_full, -shift)
            weight_sum += np.roll(w_full, -shift)

        # Weighted average of phase gradients
        valid = weight_sum > 0
        avg_gradient = np.zeros(n_az)
        avg_gradient[valid] = np.angle(gradient_sum[valid])

        # Integrate gradient to get phase error
        phase_error = np.cumsum(avg_gradient)

        # Remove mean (constant phase is ambiguous)
        phase_error -= np.mean(phase_error)

        return phase_error


__all__ = ["PhaseGradientAutofocus"]
