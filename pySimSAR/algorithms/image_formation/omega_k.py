"""Omega-K (Wavenumber Domain) Algorithm for SAR image formation.

Implements the Omega-K algorithm for SAR image formation with exact
Range Cell Migration Correction (RCMC) based on the wavenumber domain
migration function D(f_eta).

The Omega-K algorithm uses the exact migration factor
D(f_eta) = sqrt(1 - (lambda*f_eta/(2V))^2) derived from the 2D
wavenumber analysis (K_Y = sqrt(K_R^2 - K_x^2)). This enables
accurate processing for both stripmap and spotlight modes, where
the wider Doppler bandwidth of spotlight data requires the full
wavenumber relationship.

Processing steps:
1. Range compression via the waveform's matched filter
2. Azimuth FFT to range-Doppler domain
3. RCMC via interpolation using the exact wavenumber migration
4. Azimuth matched filtering in range-Doppler domain
5. Azimuth IFFT to focused image

Supports stripmap and spotlight modes.
"""

from __future__ import annotations

import numpy as np

from pySimSAR.algorithms.base import ImageFormationAlgorithm
from pySimSAR.core.radar import C_LIGHT
from pySimSAR.core.types import PhaseHistoryData, SARImage, SARMode


class OmegaKAlgorithm(ImageFormationAlgorithm):
    """Omega-K (Wavenumber Domain) image formation algorithm.

    Uses the exact wavenumber domain migration factor for RCMC,
    supporting both stripmap and spotlight modes. The wider Doppler
    bandwidth of spotlight mode requires the exact D(f_eta) relationship
    (not the narrowband approximation), which is derived from the
    Omega-K wavenumber analysis K_Y = sqrt(K_R^2 - K_x^2).

    Supports stripmap and spotlight modes.
    """

    name = "omega_k"

    def __init__(self) -> None:
        pass

    def supported_modes(self) -> list[SARMode]:
        return [SARMode.STRIPMAP, SARMode.SPOTLIGHT]

    def process(self, raw_data, radar, trajectory) -> SARImage:
        phd = self.range_compress(raw_data, radar)
        return self.azimuth_compress(phd, radar, trajectory)

    def range_compress(self, raw_data, radar) -> PhaseHistoryData:
        """Range compression using the waveform's matched filter."""
        echo = raw_data.echo

        radar.waveform.generate(radar.prf, raw_data.sample_rate)

        compressed = radar.waveform.range_compress(
            echo, radar.prf, raw_data.sample_rate
        )

        return PhaseHistoryData(
            data=compressed,
            sample_rate=raw_data.sample_rate,
            prf=radar.prf,
            carrier_freq=radar.carrier_freq,
            bandwidth=radar.bandwidth,
            channel=raw_data.channel,
            gate_delay=raw_data.gate_delay,
        )

    def azimuth_compress(self, phase_history, radar, trajectory) -> SARImage:
        """Azimuth compression with exact wavenumber-domain RCMC.

        Uses the full D(f_eta) = sqrt(1 - (lambda*f_eta/(2V))^2) from
        the wavenumber domain analysis for RCMC, followed by azimuth
        matched filtering.
        """
        data = phase_history.data  # (n_azimuth, n_range)
        n_az, n_rng = data.shape

        wavelength = C_LIGHT / phase_history.carrier_freq
        prf = phase_history.prf

        # Effective platform velocity (mean speed)
        V = np.mean(np.linalg.norm(trajectory.velocity, axis=1))

        # Doppler frequency axis
        f_eta = np.fft.fftfreq(n_az, d=1.0 / prf)

        # Range bin spacing (two-way)
        range_bin_spacing = C_LIGHT / (2.0 * phase_history.sample_rate)

        # Azimuth FFT → range-Doppler domain
        data_rd = np.fft.fft(data, axis=0)

        # Near range from gate delay (bin 0 corresponds to this slant range)
        near_range = phase_history.gate_delay * C_LIGHT / 2.0
        near_range_bins = near_range / range_bin_spacing

        # RCMC using exact wavenumber migration factor
        data_rd = self._apply_rcmc(
            data_rd, f_eta, wavelength, V, range_bin_spacing, n_az, n_rng,
            near_range_bins=near_range_bins,
        )

        # Azimuth matched filtering per range bin
        for rng_bin in range(n_rng):
            R0 = near_range + rng_bin * range_bin_spacing
            if R0 < 1.0:
                continue

            # Azimuth FM rate: K_a = -2V^2 / (lambda * R0)
            K_a = -2.0 * V ** 2 / (wavelength * R0)

            # Azimuth matched filter: H_az = exp(j*pi*f_eta^2 / K_a)
            H_az = np.exp(1j * np.pi * f_eta ** 2 / K_a)
            data_rd[:, rng_bin] *= H_az

        # Azimuth IFFT → focused image
        focused = np.fft.ifft(data_rd, axis=0)

        # Pixel spacings
        range_spacing = C_LIGHT / (2.0 * phase_history.sample_rate)
        azimuth_spacing = V / prf

        return SARImage(
            data=focused,
            pixel_spacing_range=range_spacing,
            pixel_spacing_azimuth=azimuth_spacing,
            geometry="slant_range",
            algorithm=self.name,
            channel=phase_history.channel,
            near_range=near_range,
        )

    def _apply_rcmc(
        self,
        data_rd: np.ndarray,
        f_eta: np.ndarray,
        wavelength: float,
        V: float,
        range_bin_spacing: float,
        n_az: int,
        n_rng: int,
        near_range_bins: float = 0.0,
    ) -> np.ndarray:
        """Apply RCMC using exact wavenumber domain migration factor.

        For each Doppler line, computes the migration factor
        D(f_eta) = sqrt(1 - (lambda*f_eta/(2V))^2) from the wavenumber
        relation K_Y = sqrt(K_R^2 - K_x^2), and corrects the range
        position via interpolation.

        Processes from a clean copy to avoid cross-contamination.

        Parameters
        ----------
        near_range_bins : float
            Near range offset in bin units (gate_delay * c/2 / range_bin_spacing).
        """
        data_corrected = data_rd.copy()
        range_bins = np.arange(n_rng, dtype=float)

        for k in range(n_az):
            arg = wavelength * f_eta[k] / (2.0 * V)
            if abs(arg) >= 0.99:
                continue

            D_k = np.sqrt(1.0 - arg ** 2)
            if abs(D_k - 1.0) < 1e-10:
                continue

            # Each target at absolute range bin (near_range_bins + b) has
            # migrated to (near_range_bins + b)/D_k. Convert back to
            # array-relative coordinates.
            abs_bins = near_range_bins + range_bins
            src_positions = abs_bins / D_k - near_range_bins

            row = data_rd[k, :]
            data_corrected[k, :] = np.interp(
                src_positions, range_bins, row.real
            ) + 1j * np.interp(
                src_positions, range_bins, row.imag
            )

        return data_corrected


__all__ = ["OmegaKAlgorithm"]
