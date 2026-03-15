"""Waveform abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pySimSAR.waveforms.phase_noise import PhaseNoiseModel


class Waveform(ABC):
    """Abstract base class for radar waveform implementations.

    A waveform defines how the radar transmit signal is generated and
    how received echoes are range-compressed. Implementations must provide
    ``generate()`` for transmit signal synthesis and ``range_compress()``
    for matched filtering or dechirp processing.

    Parameters
    ----------
    bandwidth : float
        Waveform bandwidth in Hz.
    duty_cycle : float
        Fraction of PRI occupied by the waveform (0, 1].
    phase_noise : PhaseNoiseModel | None
        Optional phase noise model applied to the generated waveform.
    window : Callable[[int], np.ndarray] | None
        Optional window function for range compression sidelobe control.
        Signature: window(n) -> np.ndarray of shape (n,).
    """

    name: str = ""

    def __init__(
        self,
        bandwidth: float,
        duty_cycle: float,
        phase_noise: PhaseNoiseModel | None = None,
        window: Callable[[int], np.ndarray] | None = None,
    ) -> None:
        if bandwidth <= 0:
            raise ValueError(f"bandwidth must be positive, got {bandwidth}")
        if not 0 < duty_cycle <= 1:
            raise ValueError(f"duty_cycle must be in (0, 1], got {duty_cycle}")

        self._bandwidth = bandwidth
        self._duty_cycle = duty_cycle
        self._phase_noise = phase_noise
        self._window = window

    @property
    def bandwidth(self) -> float:
        """Waveform bandwidth in Hz."""
        return self._bandwidth

    @property
    def duty_cycle(self) -> float:
        """Fraction of PRI occupied by the waveform."""
        return self._duty_cycle

    @property
    def phase_noise(self) -> PhaseNoiseModel | None:
        """Phase noise model, or None."""
        return self._phase_noise

    @property
    def window(self) -> Callable[[int], np.ndarray] | None:
        """Window function for range compression."""
        return self._window

    def duration(self, prf: float) -> float:
        """Compute waveform duration from duty cycle and PRF.

        Parameters
        ----------
        prf : float
            Pulse repetition frequency in Hz.

        Returns
        -------
        float
            Waveform duration in seconds (duty_cycle / prf).
        """
        if prf <= 0:
            raise ValueError(f"prf must be positive, got {prf}")
        return self._duty_cycle / prf

    @abstractmethod
    def generate(self, prf: float, sample_rate: float) -> np.ndarray:
        """Generate the transmit waveform samples.

        Parameters
        ----------
        prf : float
            Pulse repetition frequency in Hz (determines duration).
        sample_rate : float
            Sampling rate in Hz.

        Returns
        -------
        np.ndarray
            Complex-valued waveform samples, shape (n_samples,).
        """

    @abstractmethod
    def range_compress(
        self, echo: np.ndarray, prf: float, sample_rate: float
    ) -> np.ndarray:
        """Range-compress received echo data.

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


__all__ = ["Waveform"]
