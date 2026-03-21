"""Map Drift Autofocus (MDA) algorithm.

Splits the synthetic aperture into overlapping sub-apertures, measures
Doppler centroid drift between them, and fits a low-order polynomial
phase error model. Effective for linear and quadratic phase errors.

References
----------
Calloway, T.M. and Donohoe, G.W., "Subaperture Autofocus for Synthetic
Aperture Radar," IEEE Trans. Aerospace and Electronic Systems, 1994.
"""

from __future__ import annotations

import numpy as np

from pySimSAR.algorithms.base import AutofocusAlgorithm
from pySimSAR.core.types import PhaseHistoryData


class MapDriftAutofocus(AutofocusAlgorithm):
    """Map Drift Autofocus (MDA).

    Splits the aperture into overlapping sub-apertures, measures the
    Doppler centroid of each, and fits a low-order polynomial to the
    centroid drift. The integral of the centroid drift gives the phase
    error. Effective for linear and quadratic phase errors (defocus, drift).

    Parameters
    ----------
    max_iterations : int
        Maximum number of autofocus iterations.
    convergence_threshold : float
        Stop when max absolute phase correction < threshold (radians).
    n_subapertures : int
        Number of sub-apertures to split the azimuth into.
    poly_order : int
        Order of polynomial for phase error model (1=linear, 2=quadratic).
    """

    name = "mda"

    def __init__(
        self,
        max_iterations: int = 5,
        convergence_threshold: float = 0.01,
        n_subapertures: int = 4,
        poly_order: int = 2,
    ) -> None:
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self._n_subapertures = max(2, n_subapertures)
        self._poly_order = poly_order

    def focus(self, phase_history: object, azimuth_compressor: object) -> object:
        """Apply MDA autofocus to phase history data.

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
        """Estimate low-order phase error via Doppler centroid drift.

        Steps:
        1. Split azimuth into overlapping sub-apertures
        2. For each sub-aperture, compute Doppler centroid via
           phase-difference estimator
        3. Fit polynomial to centroid drift across sub-apertures
        4. Convert centroid drift to phase error via integration

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

        # Sub-aperture layout with ~50% overlap
        sub_len = max(4, 2 * n_az // (self._n_subapertures + 1))
        step = max(1, sub_len // 2)

        # Collect sub-aperture centers and their Doppler centroids
        centers = []
        centroids = []
        pos = 0
        while pos + sub_len <= n_az:
            end = pos + sub_len
            sub_data = data[pos:end, :]
            fc = self._doppler_centroid(sub_data, phase_history.prf)
            centers.append((pos + end) / 2.0)
            centroids.append(fc)
            pos += step

        if len(centers) < 2:
            return np.zeros(n_az)

        centers = np.array(centers)
        centroids = np.array(centroids)

        # Remove the mean centroid (we only care about drift)
        centroids -= np.mean(centroids)

        # Normalize azimuth coordinate
        t_norm = (centers - n_az / 2.0) / (n_az / 2.0)

        # Fit polynomial to centroid drift
        order = min(self._poly_order, len(centers) - 1)
        coeffs = np.polyfit(t_norm, centroids, deg=order)

        # Evaluate at all azimuth samples
        t_all = (np.arange(n_az) - n_az / 2.0) / (n_az / 2.0)
        centroid_fit = np.polyval(coeffs, t_all)

        # Convert Doppler centroid drift to phase error:
        # Instantaneous frequency f(n) = (1/2π) * dφ/dn
        # Phase error: φ(n) = 2π * Σ f(n) / PRF
        # where f(n) is the centroid offset at sample n
        phase_error = 2.0 * np.pi * np.cumsum(centroid_fit) / phase_history.prf

        # Remove mean
        phase_error -= np.mean(phase_error)

        return phase_error

    @staticmethod
    def _doppler_centroid(
        sub_data: np.ndarray,
        prf: float,
    ) -> float:
        """Estimate Doppler centroid via the phase-difference method.

        Uses the conjugate-product estimator averaged over range bins:
            f_c = PRF / (2π) * angle(Σ_r Σ_n s(n+1,r) * conj(s(n,r)))

        Parameters
        ----------
        sub_data : np.ndarray
            Sub-aperture data, shape (sub_len, n_range).
        prf : float
            Pulse repetition frequency.

        Returns
        -------
        float
            Estimated Doppler centroid in Hz.
        """
        # Conjugate product along azimuth, summed over range and azimuth
        conj_prod = np.sum(sub_data[1:, :] * np.conj(sub_data[:-1, :]))
        return prf / (2.0 * np.pi) * np.angle(conj_prod)


__all__ = ["MapDriftAutofocus"]
