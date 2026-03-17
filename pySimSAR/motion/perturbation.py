"""Motion perturbation models for platform trajectory."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class MotionPerturbation(ABC):
    """Abstract base class for motion perturbation models."""

    @abstractmethod
    def generate(
        self,
        n_samples: int,
        dt: float,
        velocity: float,
        altitude: float,
        seed: int | None = None,
    ) -> np.ndarray:
        """Generate velocity perturbation time series.

        Parameters
        ----------
        n_samples : int
            Number of time samples.
        dt : float
            Time step in seconds.
        velocity : float
            Platform airspeed in m/s.
        altitude : float
            Platform altitude in meters.
        seed : int | None
            Random seed for reproducibility.

        Returns
        -------
        np.ndarray
            Velocity perturbations [du, dv, dw] in m/s, shape (n_samples, 3).
        """


class DrydenTurbulence(MotionPerturbation):
    """Dryden wind turbulence model (MIL-HDBK-1797).

    Generates coloured noise by filtering white noise through transfer
    functions that match the Dryden turbulence power spectral density.

    Parameters
    ----------
    sigma_u : float
        Longitudinal turbulence intensity in m/s. Must be >= 0.
    sigma_v : float
        Lateral turbulence intensity in m/s. Must be >= 0.
    sigma_w : float
        Vertical turbulence intensity in m/s. Must be >= 0.
    """

    def __init__(
        self,
        sigma_u: float = 1.0,
        sigma_v: float = 1.0,
        sigma_w: float = 0.5,
    ) -> None:
        if sigma_u < 0:
            raise ValueError(f"sigma_u must be >= 0, got {sigma_u}")
        if sigma_v < 0:
            raise ValueError(f"sigma_v must be >= 0, got {sigma_v}")
        if sigma_w < 0:
            raise ValueError(f"sigma_w must be >= 0, got {sigma_w}")

        self.sigma_u = sigma_u
        self.sigma_v = sigma_v
        self.sigma_w = sigma_w

    def generate(
        self,
        n_samples: int,
        dt: float,
        velocity: float,
        altitude: float,
        seed: int | None = None,
    ) -> np.ndarray:
        """Generate Dryden turbulence velocity perturbations.

        Uses MIL-HDBK-1797 transfer functions for low-altitude model.

        Parameters
        ----------
        n_samples : int
            Number of time samples.
        dt : float
            Time step in seconds.
        velocity : float
            Platform airspeed in m/s.
        altitude : float
            Platform altitude in meters.
        seed : int | None
            Random seed for reproducibility.

        Returns
        -------
        np.ndarray
            Velocity perturbations [du, dv, dw], shape (n_samples, 3).
        """
        if self.sigma_u == 0.0 and self.sigma_v == 0.0 and self.sigma_w == 0.0:
            return np.zeros((n_samples, 3))

        rng = np.random.default_rng(seed)

        # Dryden scale lengths (low altitude, MIL-HDBK-1797)
        h = max(altitude, 10.0)  # avoid division by zero
        L_u = h / (0.177 + 0.000823 * h) ** 1.2
        L_v = L_u
        L_w = h

        V = velocity
        perturbation = np.zeros((n_samples, 3))

        # IFFT spectral shaping with Gaussian random amplitudes.
        # For each rfft bin k with frequency f_k:
        #   Two-sided PSD S(f_k) is the Dryden spectrum.
        #   X[k] has E[|X[k]|^2] = N^2 * S(f_k) * df
        # irfft produces a signal whose variance matches the PSD integral.
        freqs = np.fft.rfftfreq(n_samples, d=dt)
        n_rfft = len(freqs)
        df = 1.0 / (n_samples * dt)

        for axis, (sigma, L) in enumerate(
            [(self.sigma_u, L_u), (self.sigma_v, L_v), (self.sigma_w, L_w)]
        ):
            if sigma == 0.0:
                continue

            # Dryden two-sided PSD as function of cyclic frequency f (Hz)
            f_norm = 2.0 * np.pi * L * freqs / V

            if axis == 0:
                # Longitudinal: S(f) = sigma^2 * 2*L/(pi*V) / (1 + (2*pi*L*f/V)^2)
                # |H(jw)|^2 where H(s) = sigma*sqrt(2*L/V) / (1 + L/V*s)
                K = sigma * np.sqrt(2.0 * L / V)
                psd = K**2 / (1.0 + f_norm**2)
            else:
                # Lateral/Vertical: second-order Dryden
                K = sigma * np.sqrt(L / V)
                psd = K**2 * (1.0 + 3.0 * f_norm**2) / (1.0 + f_norm**2) ** 2

            # Gaussian random amplitudes with correct power per bin
            target_power = n_samples**2 * psd * df
            spectrum = np.zeros(n_rfft, dtype=complex)

            # DC must be zero — perturbations are zero-mean by definition.
            # A nonzero DC produces a constant velocity offset that integrates
            # into linear position drift, masking the oscillatory turbulence.
            spectrum[0] = 0.0
            # Nyquist: real-valued
            spectrum[-1] = rng.normal(0, np.sqrt(target_power[-1]))

            # Interior bins: complex Gaussian
            std_per_component = np.sqrt(target_power[1:-1] / 2.0)
            spectrum[1:-1] = (
                rng.normal(0, std_per_component)
                + 1j * rng.normal(0, std_per_component)
            )

            perturbation[:, axis] = np.fft.irfft(spectrum, n=n_samples)

        return perturbation

    def __repr__(self) -> str:
        return (
            f"DrydenTurbulence(sigma_u={self.sigma_u}, "
            f"sigma_v={self.sigma_v}, sigma_w={self.sigma_w})"
        )


__all__ = ["MotionPerturbation", "DrydenTurbulence"]
