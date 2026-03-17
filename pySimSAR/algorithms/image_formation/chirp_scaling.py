"""Chirp Scaling Algorithm (CSA) for SAR image formation.

Implements the Chirp Scaling algorithm with:
1. Range compression via the waveform's matched filter
2. Azimuth FFT to range-Doppler domain
3. Range Cell Migration Correction (RCMC)
4. Azimuth matched filtering in Doppler domain
5. Azimuth IFFT to focused image

The CSA performs RCMC using a two-stage approach:
- Bulk RCMC via phase multiplication in 2D frequency domain at a
  reference range (corrects all range bins by the same amount)
- Residual RCMC via interpolation for range-dependent correction

Supports stripmap and scan-SAR modes.
"""

from __future__ import annotations

import numpy as np

from pySimSAR.algorithms.base import ImageFormationAlgorithm
from pySimSAR.core.radar import C_LIGHT
from pySimSAR.core.types import PhaseHistoryData, SARImage, SARMode


class ChirpScalingAlgorithm(ImageFormationAlgorithm):
    """Chirp Scaling image formation algorithm.

    Performs RCMC using bulk phase correction in 2D frequency domain
    at a reference range, then residual interpolation-based correction.

    Supports stripmap and scan-SAR modes.
    """

    name = "chirp_scaling"

    def __init__(self) -> None:
        pass

    def supported_modes(self) -> list[SARMode]:
        return [SARMode.STRIPMAP, SARMode.SCANMAR]

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
        """Azimuth compression with CSA-style RCMC.

        Uses bulk RCMC in 2D frequency domain at a reference range,
        then residual interpolation correction for range-dependent
        migration, followed by azimuth matched filtering.
        """
        data = phase_history.data  # (n_azimuth, n_range)
        n_az, n_rng = data.shape

        wavelength = C_LIGHT / phase_history.carrier_freq
        prf = phase_history.prf
        sample_rate = phase_history.sample_rate

        # Effective platform velocity (mean speed)
        V = np.mean(np.linalg.norm(trajectory.velocity, axis=1))

        # Doppler frequency axis
        f_eta = np.fft.fftfreq(n_az, d=1.0 / prf)

        # Range frequency axis
        f_tau = np.fft.fftfreq(n_rng, d=1.0 / sample_rate)

        # Range bin spacing (two-way)
        range_bin_spacing = C_LIGHT / (2.0 * sample_rate)

        # Near range from gate delay (bin 0 corresponds to this slant range)
        near_range = phase_history.gate_delay * C_LIGHT / 2.0

        # Reference range from peak of range power profile
        range_power = np.sum(np.abs(data) ** 2, axis=0)
        R_ref_bin = float(np.argmax(range_power))
        R_ref = max(near_range + R_ref_bin * range_bin_spacing, 1.0)

        # Migration factor D(f_eta) = sqrt(1 - (lambda*f_eta/(2V))^2)
        D_f_eta = np.sqrt(
            np.maximum(1.0 - (wavelength * f_eta / (2.0 * V)) ** 2, 0.01)
        )

        # === Step 1: Azimuth FFT to range-Doppler domain ===
        data_rd = np.fft.fft(data, axis=0)

        # === Step 2: Bulk RCMC in 2D frequency domain ===
        # Correct migration at the reference range via phase multiply
        data_2d = np.fft.fft(data_rd, axis=1)
        for k in range(n_az):
            a_k = 1.0 / D_f_eta[k] - 1.0
            if abs(a_k) < 1e-10:
                continue
            phase_rcmc = 4.0 * np.pi * R_ref * a_k * f_tau / C_LIGHT
            data_2d[k, :] *= np.exp(1j * phase_rcmc)
        data_rd = np.fft.ifft(data_2d, axis=1)

        # === Step 3: Residual RCMC via interpolation ===
        # After bulk correction at R_ref, residual migration is
        # (R0 - R_ref) * a(f_eta) per range bin. Correct via interpolation.
        near_range_bins = near_range / range_bin_spacing
        data_rd = self._apply_residual_rcmc(
            data_rd, f_eta, wavelength, V, R_ref,
            range_bin_spacing, n_az, n_rng,
            near_range_bins=near_range_bins,
        )

        # === Step 4: Azimuth matched filtering ===
        for rng_bin in range(n_rng):
            R0 = near_range + rng_bin * range_bin_spacing
            if R0 < 1.0:
                continue

            K_a = -2.0 * V**2 / (wavelength * R0)
            H_az = np.exp(1j * np.pi * f_eta**2 / K_a)
            data_rd[:, rng_bin] *= H_az

        # === Step 5: Azimuth IFFT to focused image ===
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

    def _apply_residual_rcmc(
        self,
        data_rd: np.ndarray,
        f_eta: np.ndarray,
        wavelength: float,
        V: float,
        R_ref: float,
        range_bin_spacing: float,
        n_az: int,
        n_rng: int,
        near_range_bins: float = 0.0,
    ) -> np.ndarray:
        """Apply residual RCMC correction via interpolation.

        After bulk RCMC at R_ref, the residual migration for a target at
        range R0 is (R0 - R_ref) * a(f_eta). This is corrected per
        Doppler line using interpolation.

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
            a_k = 1.0 / D_k - 1.0
            if abs(a_k) < 1e-10:
                continue

            # After bulk correction at R_ref, the residual shift for
            # absolute range bin (near_range_bins + b) is:
            # ((near_range_bins + b) * rbs - R_ref) * a_k / rbs bins
            # Total source position in array coords:
            # (near_range_bins + b) / D_k - R_ref_bin * a_k - near_range_bins
            R_ref_bin = R_ref / range_bin_spacing
            abs_bins = near_range_bins + range_bins
            src_positions = abs_bins / D_k - R_ref_bin * a_k - near_range_bins

            row = data_rd[k, :]
            data_corrected[k, :] = np.interp(
                src_positions, range_bins, row.real
            ) + 1j * np.interp(
                src_positions, range_bins, row.imag
            )

        return data_corrected


__all__ = ["ChirpScalingAlgorithm"]
