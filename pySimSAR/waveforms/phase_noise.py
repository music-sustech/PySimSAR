"""Phase noise model abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class PhaseNoiseModel(ABC):
    """Abstract base class for oscillator phase noise models.

    Phase noise corrupts the transmitted and received waveforms, causing
    range-dependent decorrelation. Close-range targets see correlated
    phase noise (which cancels in range compression), while far-range
    targets experience an elevated noise floor.
    """

    name: str = ""

    @abstractmethod
    def generate(
        self, n_samples: int, sample_rate: float, seed: int | None = None
    ) -> np.ndarray:
        """Generate phase noise samples.

        Parameters
        ----------
        n_samples : int
            Number of samples to generate.
        sample_rate : float
            Sampling rate in Hz.
        seed : int | None
            Random seed for reproducibility.

        Returns
        -------
        np.ndarray
            Phase noise samples in radians, shape (n_samples,).
        """


class CompositePSDPhaseNoise(PhaseNoiseModel):
    """Composite power spectral density phase noise model.

    Models oscillator phase noise as a sum of four standard noise processes:
    flicker FM (1/f^3), white FM (1/f^2), flicker PM (1/f), and white PM
    (flat floor). Each component level is specified in dBc/Hz.

    Parameters
    ----------
    flicker_fm_level : float
        Flicker FM noise level in dBc/Hz at 1 Hz offset (default -80).
    white_fm_level : float
        White FM noise level in dBc/Hz at 1 Hz offset (default -100).
    flicker_pm_level : float
        Flicker PM noise level in dBc/Hz at 1 Hz offset (default -120).
    white_floor : float
        White phase noise floor in dBc/Hz (default -150).
    """

    name = "composite_psd"

    def __init__(
        self,
        flicker_fm_level: float = -80.0,
        white_fm_level: float = -100.0,
        flicker_pm_level: float = -120.0,
        white_floor: float = -150.0,
    ) -> None:
        self._flicker_fm_level = flicker_fm_level
        self._white_fm_level = white_fm_level
        self._flicker_pm_level = flicker_pm_level
        self._white_floor = white_floor

    def generate(
        self, n_samples: int, sample_rate: float, seed: int | None = None
    ) -> np.ndarray:
        """Generate phase noise samples shaped by the composite PSD.

        Parameters
        ----------
        n_samples : int
            Number of samples to generate.
        sample_rate : float
            Sampling rate in Hz.
        seed : int | None
            Random seed for reproducibility.

        Returns
        -------
        np.ndarray
            Phase noise samples in radians, shape (n_samples,).
        """
        f = np.fft.rfftfreq(n_samples, 1.0 / sample_rate)
        # Avoid division by zero at DC
        f[0] = f[1]

        # Build composite PSD in linear power
        psd = (
            10.0 ** (self._flicker_fm_level / 10.0) / f**3
            + 10.0 ** (self._white_fm_level / 10.0) / f**2
            + 10.0 ** (self._flicker_pm_level / 10.0) / f
            + 10.0 ** (self._white_floor / 10.0)
        )

        # Generate shaped noise in frequency domain
        rng = np.random.default_rng(seed)
        amplitude = np.sqrt(psd * sample_rate / 2.0)
        noise_freq = amplitude * (
            rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))
        )

        # Transform to time domain
        phase_noise = np.fft.irfft(noise_freq, n=n_samples)
        return phase_noise


__all__ = ["PhaseNoiseModel", "CompositePSDPhaseNoise"]
