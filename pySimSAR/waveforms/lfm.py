"""Linear Frequency Modulated (LFM) waveform implementation."""

from __future__ import annotations

import numpy as np

from pySimSAR.waveforms.base import Waveform
from pySimSAR.waveforms.registry import waveform_registry


@waveform_registry.register
class LFMWaveform(Waveform):
    """Pulsed linear frequency modulated (chirp) waveform.

    Generates a baseband LFM chirp signal with quadratic phase:
    ``s(t) = exp(j * pi * K * t^2)`` where ``K = bandwidth / duration``
    is the chirp slope in Hz/s.

    Range compression is performed via frequency-domain matched filtering.

    Parameters
    ----------
    bandwidth : float
        Waveform bandwidth in Hz.
    duty_cycle : float
        Fraction of PRI occupied by the pulse. Must be < 1.0 for pulsed
        operation.
    phase_noise : PhaseNoiseModel | None
        Optional phase noise model.
    window : Callable[[int], np.ndarray] | None
        Optional window function for sidelobe control.
    """

    name = "lfm"

    def __init__(
        self,
        bandwidth: float,
        duty_cycle: float = 0.1,
        phase_noise=None,
        window=None,
    ) -> None:
        if duty_cycle >= 1.0:
            raise ValueError(
                f"duty_cycle must be < 1.0 for pulsed LFM, got {duty_cycle}"
            )
        super().__init__(
            bandwidth=bandwidth,
            duty_cycle=duty_cycle,
            phase_noise=phase_noise,
            window=window,
        )
        self._tx_signal: np.ndarray | None = None

    def generate(self, prf: float, sample_rate: float) -> np.ndarray:
        """Generate a baseband LFM chirp signal.

        Parameters
        ----------
        prf : float
            Pulse repetition frequency in Hz.
        sample_rate : float
            Sampling rate in Hz.

        Returns
        -------
        np.ndarray
            Complex-valued chirp samples, shape (n_samples,).
        """
        duration = self.duration(prf)
        n_samples = int(duration * sample_rate)
        t = np.arange(n_samples) / sample_rate

        K = self.bandwidth / duration  # chirp slope (Hz/s)
        signal = np.exp(1j * np.pi * K * t**2)

        if self.phase_noise is not None:
            pn = self.phase_noise.generate(n_samples, sample_rate)
            signal = signal * np.exp(1j * pn)

        if self.window is not None:
            signal = signal * self.window(n_samples)

        self._tx_signal = signal
        return signal

    def range_compress(
        self, echo: np.ndarray, prf: float, sample_rate: float
    ) -> np.ndarray:
        """Range-compress echo data via frequency-domain matched filtering.

        Parameters
        ----------
        echo : np.ndarray
            Raw echo data, shape (n_range_samples,) or (n_pulses, n_range_samples).
        prf : float
            Pulse repetition frequency in Hz.
        sample_rate : float
            Sampling rate in Hz.

        Returns
        -------
        np.ndarray
            Range-compressed data, same shape as input.
        """
        if self._tx_signal is None:
            raise RuntimeError(
                "Must call generate() before range_compress()."
            )

        ref = self._tx_signal

        if echo.ndim == 1:
            n = len(echo)
            ref_fft = np.conj(np.fft.fft(ref, n=n))
            if self.window is not None:
                ref_fft = ref_fft * self.window(n)
            return np.fft.ifft(np.fft.fft(echo, n=n) * ref_fft)
        elif echo.ndim == 2:
            n = echo.shape[1]
            ref_fft = np.conj(np.fft.fft(ref, n=n))
            if self.window is not None:
                ref_fft = ref_fft * self.window(n)
            return np.fft.ifft(
                np.fft.fft(echo, n=n, axis=1) * ref_fft[np.newaxis, :],
                axis=1,
            )
        else:
            raise ValueError(f"echo must be 1D or 2D, got {echo.ndim}D")


__all__ = ["LFMWaveform"]
