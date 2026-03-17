"""Range-Doppler Algorithm (RDA) for SAR image formation.

Implements the classic Range-Doppler algorithm with:
1. Range compression via the waveform's matched filter
2. Range Cell Migration Correction (RCMC) via sinc interpolation
3. Azimuth compression via matched filtering in Doppler domain
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import interp1d

from pySimSAR.algorithms.base import ImageFormationAlgorithm
from pySimSAR.core.radar import C_LIGHT
from pySimSAR.core.types import PhaseHistoryData, SARImage, SARMode


class RangeDopplerAlgorithm(ImageFormationAlgorithm):
    """Range-Doppler image formation algorithm.

    The Range-Doppler algorithm operates in the range-Doppler domain:
    - Range compression in fast-time (frequency-domain matched filter)
    - Azimuth FFT to range-Doppler domain
    - Range Cell Migration Correction (RCMC) via interpolation
    - Azimuth matched filtering in Doppler domain
    - Azimuth IFFT to focused image

    Supports stripmap mode only.

    Parameters
    ----------
    apply_rcmc : bool
        Whether to apply Range Cell Migration Correction (default True).
    rcmc_interp_order : int
        Interpolation order for RCMC (default 8 for sinc-like).
    """

    name = "range_doppler"

    def __init__(
        self,
        apply_rcmc: bool = True,
        rcmc_interp_order: int = 8,
    ) -> None:
        self._apply_rcmc = apply_rcmc
        self._rcmc_interp_order = rcmc_interp_order

    def supported_modes(self) -> list[SARMode]:
        return [SARMode.STRIPMAP]

    def process(self, raw_data, radar, trajectory) -> SARImage:
        phd = self.range_compress(raw_data, radar)
        return self.azimuth_compress(phd, radar, trajectory)

    def range_compress(self, raw_data, radar) -> PhaseHistoryData:
        """Range compression using the waveform's matched filter.

        Parameters
        ----------
        raw_data : RawData
            Raw echo data with shape (n_azimuth, n_range).
        radar : Radar
            Radar configuration (provides waveform and PRF).

        Returns
        -------
        PhaseHistoryData
            Range-compressed phase history.
        """
        echo = raw_data.echo  # (n_azimuth, n_range)

        # Ensure waveform has generated its reference signal
        radar.waveform.generate(radar.prf, raw_data.sample_rate)

        # Apply waveform range compression (handles 2D: axis=1)
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
        """Azimuth compression in Range-Doppler domain.

        Parameters
        ----------
        phase_history : PhaseHistoryData
            Range-compressed data, shape (n_azimuth, n_range).
        radar : Radar
            Radar configuration.
        trajectory : Trajectory
            Platform trajectory (provides velocity).

        Returns
        -------
        SARImage
            Focused SAR image.
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

        # Near range from gate delay (bin 0 corresponds to this slant range)
        near_range = phase_history.gate_delay * C_LIGHT / 2.0

        # Azimuth FFT -> Range-Doppler domain
        data_rd = np.fft.fft(data, axis=0)

        # RCMC: correct range cell migration per Doppler line
        if self._apply_rcmc:
            near_range_bins = near_range / range_bin_spacing
            data_rd = self._apply_rcmc_correction(
                data_rd, f_eta, wavelength, V, range_bin_spacing, n_az, n_rng,
                near_range_bins=near_range_bins,
            )

        # Azimuth matched filtering per range bin
        for rng_bin in range(n_rng):
            R0 = near_range + rng_bin * range_bin_spacing
            if R0 < 1.0:
                continue

            # Azimuth FM rate: K_a = -2V^2 / (lambda * R0)
            K_a = -2.0 * V**2 / (wavelength * R0)

            # Azimuth matched filter: H_az = exp(j*pi*f_eta^2 / K_a)
            H_az = np.exp(1j * np.pi * f_eta**2 / K_a)
            data_rd[:, rng_bin] *= H_az

        # Azimuth IFFT -> focused image
        focused = np.fft.ifft(data_rd, axis=0)

        # Pixel spacings
        range_spacing = C_LIGHT / (2.0 * phase_history.bandwidth)
        azimuth_spacing = V / prf

        return SARImage(
            data=focused,
            pixel_spacing_range=range_spacing,
            pixel_spacing_azimuth=azimuth_spacing,
            geometry="slant_range",
            algorithm=self.name,
            channel=phase_history.channel,
        )

    def _apply_rcmc_correction(
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
        """Apply Range Cell Migration Correction in range-Doppler domain.

        Processes per Doppler line (row-wise) from a clean copy to avoid
        cross-contamination between range bins.

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

            D_k = np.sqrt(1.0 - arg**2)
            if abs(D_k - 1.0) < 1e-10:
                # No migration at zero Doppler
                continue

            # Source positions: target at absolute range bin (near + b) migrates
            # by factor 1/D_k. Convert back to array-relative coordinates.
            abs_bins = near_range_bins + range_bins
            src_positions = abs_bins / D_k - near_range_bins

            # Interpolate from original data to correct the migration
            row = data_rd[k, :]
            data_corrected[k, :] = np.interp(
                src_positions, range_bins, row.real
            ) + 1j * np.interp(
                src_positions, range_bins, row.imag
            )

        return data_corrected


__all__ = ["RangeDopplerAlgorithm"]
