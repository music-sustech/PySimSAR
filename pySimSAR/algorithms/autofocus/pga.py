"""Phase Gradient Autofocus (PGA) algorithm.

Estimates and corrects residual phase errors using dominant scatterer
selection and phase gradient estimation. Iterates until convergence.

The standard PGA loop (Wahl et al. 1994):
    1. Azimuth-compress the phase history to get an image
    2. Select dominant scatterers from the focused image
    3. Centre-shift and window each in image domain (adaptive mainlobe window)
    4. FFT to Doppler domain, estimate phase gradient, integrate
    5. Correct the Doppler-domain phase history and repeat

References
----------
Wahl, D.E., Eichel, P.H., Ghiglia, D.C., and Jakowatz, C.V.,
"Phase Gradient Autofocus--A Robust Tool for High Resolution SAR Phase
Correction," IEEE Trans. Aerospace and Electronic Systems, 1994.
"""

from __future__ import annotations

import numpy as np

from pySimSAR.algorithms.base import AutofocusAlgorithm
from pySimSAR.core.types import PhaseHistoryData


class PhaseGradientAutofocus(AutofocusAlgorithm):
    """Phase Gradient Autofocus (PGA).

    Selects dominant scatterers per range bin from a focused image,
    extracts their azimuth phase histories, estimates the phase gradient,
    and integrates to obtain a phase error correction.

    Parameters
    ----------
    max_iterations : int
        Maximum number of autofocus iterations.
    convergence_threshold : float
        Stop when max absolute phase correction < threshold (radians).
    n_dominant : int
        Number of dominant range bins to use for gradient estimation.
        0 = auto (n_range // 4).
    window_fraction : float
        Maximum fraction of azimuth extent used for windowing (0, 1].
        The actual window is the smaller of this and an adaptive
        mainlobe-width estimate per range bin.
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def focus(self, phase_history: object, azimuth_compressor: object) -> object:
        """Apply PGA autofocus to phase history data.

        Uses image sharpness (intensity kurtosis) as a quality guard:
        if a correction degrades focus, the iteration is undone and the
        best image seen so far is returned.  This prevents divergence on
        multi-target scenes where scatterer interference can bias the
        phase-gradient estimate.

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

        best_image = None
        best_sharpness = -np.inf

        for _ in range(self.max_iterations):
            # Step 1: Focus with current phase history
            image = azimuth_compressor(phd)
            sharpness = self._image_sharpness(image.data)

            # Quality guard: if the last correction degraded the image,
            # stop and return the best image seen so far.
            if sharpness < best_sharpness:
                return best_image

            best_image = image
            best_sharpness = sharpness

            # Step 2: Estimate phase error from the focused image
            phase_error = self._estimate_phase_error_from_image(image.data)

            if np.max(np.abs(phase_error)) < self.convergence_threshold:
                return image

            # Step 3: Correct the phase history in the slow-time domain.
            # The phase error is physically a slow-time phenomenon (platform
            # motion).  Although estimated via Doppler-domain gradients, the
            # N-point array maps approximately to the N slow-time samples
            # under the stationary-phase relationship.
            phd.data *= np.exp(-1j * phase_error)[:, np.newaxis]

        # Final focus after last correction
        image = azimuth_compressor(phd)
        sharpness = self._image_sharpness(image.data)
        if sharpness >= best_sharpness:
            return image
        return best_image

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _image_sharpness(data: np.ndarray) -> float:
        """Image sharpness via intensity kurtosis (higher = better focus)."""
        power = np.abs(data) ** 2
        total = np.sum(power)
        if total == 0:
            return 0.0
        return float(np.sum(power * power)) / (total * total)

    def _estimate_phase_error_from_image(
        self, image_data: np.ndarray
    ) -> np.ndarray:
        """Estimate residual phase error from a focused image.

        Steps:
        1. Select dominant scatterers (highest peak range bins)
        2. For each, circular-shift to centre the peak
        3. Adaptive window around mainlobe (first-null width)
        4. FFT back to Doppler domain
        5. Phase gradient via conjugate product
        6. Remove centering-induced linear phase bias
        7. Average gradients, integrate to get phase error

        The adaptive window keeps only the mainlobe of each dominant
        scatterer, excluding sidelobes and nearby targets.  The FFT then
        provides a full N-point Doppler spectrum for gradient estimation,
        where a well-focused scatterer has nearly flat phase (matched
        filter removed the chirp).

        Parameters
        ----------
        image_data : np.ndarray
            Focused image, shape (n_azimuth, n_range). May be complex.

        Returns
        -------
        np.ndarray
            Phase error estimate in Doppler domain, shape (n_azimuth,),
            in radians.
        """
        n_az, n_rng = image_data.shape

        # Number of dominant range bins
        n_dom = self._n_dominant if self._n_dominant > 0 else max(1, n_rng // 4)
        n_dom = min(n_dom, n_rng)

        # Select range bins with strongest peak response
        peak_power = np.max(np.abs(image_data) ** 2, axis=0)
        dominant_bins = np.argsort(peak_power)[-n_dom:]

        # Maximum window half-width (from configured fraction)
        max_win_half = max(1, int(n_az * self._window_fraction / 2))

        # Accumulate weighted phase gradients
        gradient_sum = np.zeros(n_az, dtype=complex)
        weight_sum = np.zeros(n_az)

        for rng_bin in dominant_bins:
            col = image_data[:, rng_bin]

            # Find azimuth peak and circularly shift to centre
            peak_idx = np.argmax(np.abs(col))
            shift = n_az // 2 - peak_idx
            col_shifted = np.roll(col, shift)

            # Adaptive window: measure the mainlobe half-width as the
            # distance from the peak to where the magnitude drops below
            # half the peak (-6 dB).  Use twice that as the window
            # half-width to cover approximately the first-null width.
            center = n_az // 2
            mag = np.abs(col_shifted)
            peak_mag = mag[center]
            if peak_mag == 0:
                continue

            ml_hw = 1
            half_threshold = peak_mag * 0.5
            for i in range(center + 1, min(center + max_win_half, n_az)):
                if mag[i] < half_threshold:
                    ml_hw = i - center
                    break
            else:
                ml_hw = max_win_half // 2

            # Window half-width: 2× mainlobe half-width, clamped
            win_half = min(max(2 * ml_hw, 3), max_win_half)

            window = np.zeros(n_az)
            lo = max(0, center - win_half)
            hi = min(n_az, center + win_half)
            window[lo:hi] = 1.0
            col_windowed = col_shifted * window

            # FFT to Doppler domain — image was formed by IFFT of the
            # matched-filtered Doppler data, so FFT inverts that.
            doppler = np.fft.fft(col_windowed)

            # Phase gradient: d[k] * conj(d[k-1])
            grad = doppler[1:] * np.conj(doppler[:-1])

            # Magnitude weighting
            dmag = np.abs(doppler)
            w = dmag[:-1] * dmag[1:]

            # Pad to full length
            grad_full = np.concatenate([[0.0 + 0j], grad])
            w_full = np.concatenate([[0.0], w])

            # Remove centering-induced linear phase from gradient.
            # Circular shift by 'shift' in image adds exp(-j*2π*k*shift/N)
            # in Doppler; the conjugate product picks up a constant factor
            # exp(-j*2π*shift/N).  Multiply by the conjugate to cancel it,
            # ensuring gradients from scatterers at different azimuth
            # positions add coherently.
            grad_full *= np.exp(1j * 2.0 * np.pi * shift / n_az)

            gradient_sum += grad_full
            weight_sum += w_full

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
