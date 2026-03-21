"""Minimum Entropy Autofocus (MEA) algorithm.

Iteratively adjusts polynomial phase correction coefficients to minimize
image entropy (maximize sharpness). Robust for distributed scenes without
strong point targets.

References
----------
Kragh, T.J., "Minimum-Entropy Autofocus for Synthetic Aperture Radar,"
PhD thesis, Washington University in St. Louis, 2006.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar

from pySimSAR.algorithms.base import AutofocusAlgorithm
from pySimSAR.core.types import PhaseHistoryData


class MinimumEntropyAutofocus(AutofocusAlgorithm):
    """Minimum Entropy Autofocus (MEA).

    Optimizes polynomial phase coefficients to minimize the entropy of
    the focused image. Lower entropy corresponds to a sharper, better
    focused image. Works well on distributed scenes where dominant
    scatterer methods (PGA, PPP) may struggle.

    Parameters
    ----------
    max_iterations : int
        Maximum number of outer autofocus iterations.
    convergence_threshold : float
        Stop when max absolute phase correction < threshold (radians).
    poly_order : int
        Order of polynomial phase model (2=quadratic, 3=cubic, etc.).
    """

    name = "min_entropy"

    def __init__(
        self,
        max_iterations: int = 10,
        convergence_threshold: float = 0.01,
        poly_order: int = 4,
    ) -> None:
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self._poly_order = poly_order

    def focus(self, phase_history: object, azimuth_compressor: object) -> object:
        """Apply minimum entropy autofocus to phase history data.

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
            gate_delay=getattr(phase_history, "gate_delay", 0.0),
        )

        for _ in range(self.max_iterations):
            phase_error = self.estimate_phase_error(phd)

            if np.max(np.abs(phase_error)) < self.convergence_threshold:
                break

            phd.data *= np.exp(-1j * phase_error)[:, np.newaxis]

        return azimuth_compressor(phd)

    def estimate_phase_error(self, phase_history: object) -> np.ndarray:
        """Estimate phase error by minimizing image entropy.

        Fits a polynomial phase model by optimizing coefficients to
        minimize the entropy of the azimuth-compressed image (computed
        column-wise via FFT for speed).

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
        n_az = data.shape[0]

        # Normalized azimuth coordinate [-1, 1]
        t = np.linspace(-1, 1, n_az)

        # Build polynomial basis (exclude order 0 and 1 — constant phase
        # is ambiguous, linear phase is a shift)
        orders = list(range(2, self._poly_order + 1))
        if not orders:
            return np.zeros(n_az)

        def _entropy_cost(coeffs: np.ndarray) -> float:
            """Compute image entropy for given polynomial coefficients."""
            phase = np.zeros(n_az)
            for i, order in enumerate(orders):
                phase += coeffs[i] * t**order

            corrected = data * np.exp(-1j * phase)[:, np.newaxis]

            # Fast azimuth compression via FFT (column-wise)
            image = np.fft.fftshift(np.fft.fft(corrected, axis=0), axes=0)
            magnitude = np.abs(image)
            power = magnitude**2
            total = np.sum(power)
            if total == 0:
                return 0.0
            p = power / total
            p = p[p > 0]
            return -np.sum(p * np.log(p))

        # Initial coefficients
        n_coeffs = len(orders)

        # Use coordinate-descent approach: optimize one coefficient at a
        # time via bounded scalar search. More robust than Nelder-Mead for
        # this problem since the entropy landscape can be flat in some
        # directions while steep in others.
        best_coeffs = np.zeros(n_coeffs)

        for _ in range(3):  # Multiple sweeps for interaction effects
            for i in range(n_coeffs):
                def _cost_1d(c: float) -> float:
                    trial = best_coeffs.copy()
                    trial[i] = c
                    return _entropy_cost(trial)

                res = minimize_scalar(
                    _cost_1d,
                    bounds=(-10.0, 10.0),
                    method="bounded",
                    options={"xatol": 0.01, "maxiter": 100},
                )
                best_coeffs[i] = res.x

        result_x = best_coeffs

        # Reconstruct phase error from optimal coefficients
        phase_error = np.zeros(n_az)
        for i, order in enumerate(orders):
            phase_error += result_x[i] * t**order

        # Remove mean
        phase_error -= np.mean(phase_error)

        return phase_error


__all__ = ["MinimumEntropyAutofocus"]
