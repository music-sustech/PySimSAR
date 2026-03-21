"""Frequency Modulated Continuous Wave (FMCW) waveform implementation."""

from __future__ import annotations

import numpy as np

from pySimSAR.core.types import RampType
from pySimSAR.waveforms.base import Waveform
from pySimSAR.waveforms.registry import waveform_registry


@waveform_registry.register
class FMCWWaveform(Waveform):
    """FMCW radar waveform with configurable ramp type.

    Generates a continuous-wave frequency-modulated signal. Range compression
    uses dechirp (stretch) processing: multiply echo by conjugate of the
    transmit signal and take the FFT.

    Parameters
    ----------
    bandwidth : float
        Waveform bandwidth in Hz.
    duty_cycle : float
        Fraction of PRI occupied by the waveform (default 1.0 for CW).
    ramp_type : str
        Frequency ramp shape: ``"up"``, ``"down"``, or ``"triangle"``.
    phase_noise : PhaseNoiseModel | None
        Optional phase noise model.
    window : Callable[[int], np.ndarray] | None
        Optional window function for sidelobe control.
    """

    name = "fmcw"

    def __init__(
        self,
        bandwidth: float,
        duty_cycle: float = 1.0,
        ramp_type: RampType | str = "up",
        phase_noise=None,
        window=None,
        prf: float | None = None,
    ) -> None:
        if isinstance(ramp_type, str):
            try:
                ramp_type = RampType(ramp_type.lower())
            except ValueError:
                valid = [r.value for r in RampType]
                raise ValueError(
                    f"ramp_type must be one of {valid}, got '{ramp_type}'"
                )
        super().__init__(
            bandwidth=bandwidth,
            duty_cycle=duty_cycle,
            phase_noise=phase_noise,
            window=window,
            prf=prf,
        )
        self._ramp_type = ramp_type
        self._tx_signal: np.ndarray | None = None

    @property
    def ramp_type(self) -> RampType:
        """Frequency ramp type."""
        return self._ramp_type

    def generate(self, prf: float, sample_rate: float) -> np.ndarray:
        """Generate an FMCW waveform signal.

        Parameters
        ----------
        prf : float
            Pulse repetition frequency in Hz.
        sample_rate : float
            Sampling rate in Hz.

        Returns
        -------
        np.ndarray
            Complex-valued FMCW samples, shape (n_samples,).
        """
        duration = self.duration(prf)
        n_samples = int(duration * sample_rate)
        t = np.arange(n_samples) / sample_rate

        if self._ramp_type == RampType.UP:
            K = self.bandwidth / duration
            signal = np.exp(1j * np.pi * K * t**2)
        elif self._ramp_type == RampType.DOWN:
            K = self.bandwidth / duration
            signal = np.exp(-1j * np.pi * K * t**2)
        else:  # triangle
            n_half = n_samples // 2
            n_second = n_samples - n_half
            K_half = 2.0 * self.bandwidth / duration

            t_up = np.arange(n_half) / sample_rate
            signal_up = np.exp(1j * np.pi * K_half * t_up**2)

            t_down = np.arange(n_second) / sample_rate
            signal_down = np.exp(-1j * np.pi * K_half * t_down**2)

            signal = np.concatenate([signal_up, signal_down])

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

        Uses the same approach as LFM: conj(FFT(ref)) * FFT(echo) in the
        frequency domain, which correctly handles echoes at any delay
        regardless of waveform duration.

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


__all__ = ["FMCWWaveform"]
