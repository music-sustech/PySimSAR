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

When n_iterations > 1, the range swath is partitioned into blocks,
each focused with its own local reference range.  This reduces
range-dependent residual errors for wide-swath or high-squint
geometries.

Supports stripmap and scan-SAR modes.
"""

from __future__ import annotations

import numpy as np

from pySimSAR.algorithms.base import ImageFormationAlgorithm
from pySimSAR.algorithms.image_formation._rcmc_interp import sinc_interp
from pySimSAR.core.radar import C_LIGHT
from pySimSAR.core.types import PhaseHistoryData, SARImage, SARMode


class ChirpScalingAlgorithm(ImageFormationAlgorithm):
    """Chirp Scaling image formation algorithm.

    Performs RCMC using bulk phase correction in 2D frequency domain
    at a reference range, then residual interpolation-based correction.

    Parameters
    ----------
    n_iterations : int
        Number of range-block iterations.  When 1 (default), a single
        reference range (swath centre) is used for the entire swath.
        When > 1, the range swath is partitioned into *n_iterations*
        blocks, each focused with its own local reference range.  This
        reduces range-dependent residual phase errors for wide-swath or
        high-squint geometries.
    """

    name = "chirp_scaling"

    def __init__(self, n_iterations: int = 1) -> None:
        self.n_iterations = max(1, int(n_iterations))

    def supported_modes(self) -> list[SARMode]:
        return [SARMode.STRIPMAP, SARMode.SCANMAR]

    def process(self, raw_data, radar, trajectory) -> SARImage:
        phd = self.range_compress(raw_data, radar)
        return self.azimuth_compress(phd, radar, trajectory)

    def range_compress(self, raw_data, radar) -> PhaseHistoryData:
        """Range compression using the waveform's matched filter."""
        echo = raw_data.echo

        radar.waveform.generate(radar.waveform.prf, raw_data.sample_rate)

        compressed = radar.waveform.range_compress(
            echo, radar.waveform.prf, raw_data.sample_rate
        )

        return PhaseHistoryData(
            data=compressed,
            sample_rate=raw_data.sample_rate,
            prf=radar.waveform.prf,
            carrier_freq=radar.carrier_freq,
            bandwidth=radar.bandwidth,
            channel=raw_data.channel,
            gate_delay=raw_data.gate_delay,
        )

    def azimuth_compress(self, phase_history, radar, trajectory) -> SARImage:
        """Azimuth compression with CSA-style RCMC.

        When *n_iterations* == 1 the entire swath is processed with a
        single reference range.  When > 1 the swath is split into
        *n_iterations* blocks, each focused at its local reference
        range, and the results are stitched back together.
        """
        data = phase_history.data  # (n_azimuth, n_range)
        n_az, n_rng = data.shape

        wavelength = C_LIGHT / phase_history.carrier_freq
        prf = phase_history.prf
        sample_rate = phase_history.sample_rate
        V = np.mean(np.linalg.norm(trajectory.velocity, axis=1))
        f_eta = np.fft.fftfreq(n_az, d=1.0 / prf)
        range_bin_spacing = C_LIGHT / (2.0 * sample_rate)
        near_range = phase_history.gate_delay * C_LIGHT / 2.0

        D_f_eta = np.sqrt(
            np.maximum(1.0 - (wavelength * f_eta / (2.0 * V)) ** 2, 0.01)
        )

        # Determine range-block boundaries
        n_iter = min(self.n_iterations, n_rng)
        block_edges = np.linspace(0, n_rng, n_iter + 1, dtype=int)

        # Azimuth FFT (shared across all blocks)
        data_rd = np.fft.fft(data, axis=0)

        # Output array
        focused_rd = np.zeros_like(data_rd)

        for blk in range(n_iter):
            b_start = int(block_edges[blk])
            b_end = int(block_edges[blk + 1])
            if b_end <= b_start:
                continue

            # Local reference range: centre of this block
            mid_bin = (b_start + b_end) / 2.0
            R_ref = max(near_range + mid_bin * range_bin_spacing, 1.0)

            # --- Bulk RCMC in 2D frequency domain for this block ---
            block_rd = data_rd[:, b_start:b_end].copy()
            block_2d = np.fft.fft(block_rd, axis=1)
            f_tau_blk = np.fft.fftfreq(b_end - b_start, d=1.0 / sample_rate)

            for k in range(n_az):
                a_k = 1.0 / D_f_eta[k] - 1.0
                if abs(a_k) < 1e-10:
                    continue
                phase_rcmc = 4.0 * np.pi * R_ref * a_k * f_tau_blk / C_LIGHT
                block_2d[k, :] *= np.exp(1j * phase_rcmc)

            block_rd = np.fft.ifft(block_2d, axis=1)

            # --- Residual RCMC via interpolation ---
            near_range_bins = near_range / range_bin_spacing
            block_rd = self._apply_residual_rcmc(
                block_rd, f_eta, wavelength, V, R_ref,
                range_bin_spacing, n_az, b_end - b_start,
                near_range_bins=near_range_bins + b_start,
            )

            # --- Azimuth matched filtering ---
            for rng_bin in range(b_end - b_start):
                R0 = near_range + (b_start + rng_bin) * range_bin_spacing
                if R0 < 1.0:
                    continue
                K_a = -2.0 * V**2 / (wavelength * R0)
                H_az = np.exp(1j * np.pi * f_eta**2 / K_a)
                block_rd[:, rng_bin] *= H_az

            focused_rd[:, b_start:b_end] = block_rd

        # Azimuth IFFT to focused image
        focused = np.fft.ifft(focused_rd, axis=0)

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
        range R0 is ``(R0 - R_ref) * a(f_eta)``.  This is corrected per
        Doppler line using linear interpolation.

        Parameters
        ----------
        near_range_bins : float
            Absolute range offset of the first column in *data_rd*,
            expressed in range-bin units.
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

            R_ref_bin = R_ref / range_bin_spacing
            abs_bins = near_range_bins + range_bins
            src_positions = abs_bins / D_k - R_ref_bin * a_k - near_range_bins

            row = data_rd[k, :]
            data_corrected[k, :] = sinc_interp(row, src_positions, 8)

        return data_corrected


__all__ = ["ChirpScalingAlgorithm"]
