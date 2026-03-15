"""Unit tests for LFMWaveform, FMCWWaveform, and CompositePSDPhaseNoise.

Covers tasks T026 (LFM waveform), T027 (FMCW waveform), T028 (composite
phase noise model).
"""

from __future__ import annotations

import numpy as np
import pytest

from pySimSAR.waveforms.lfm import LFMWaveform
from pySimSAR.waveforms.fmcw import FMCWWaveform
from pySimSAR.waveforms.phase_noise import CompositePSDPhaseNoise


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def lfm():
    return LFMWaveform(bandwidth=100e6, duty_cycle=0.1)


@pytest.fixture()
def fmcw_up():
    return FMCWWaveform(bandwidth=50e6, duty_cycle=1.0, ramp_type="up")


@pytest.fixture()
def fmcw_down():
    return FMCWWaveform(bandwidth=50e6, duty_cycle=1.0, ramp_type="down")


@pytest.fixture()
def fmcw_triangle():
    return FMCWWaveform(bandwidth=50e6, duty_cycle=1.0, ramp_type="triangle")


PRF = 1000.0
SAMPLE_RATE = 200e6


# ===================================================================
# T026: LFMWaveform tests
# ===================================================================

class TestLFMWaveformGenerate:
    """Test LFM chirp generation."""

    def test_returns_complex_array(self, lfm):
        signal = lfm.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        assert isinstance(signal, np.ndarray)
        assert np.iscomplexobj(signal)

    def test_correct_length(self, lfm):
        signal = lfm.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        expected = int(lfm.duration(PRF) * SAMPLE_RATE)
        assert len(signal) == expected

    def test_is_1d(self, lfm):
        signal = lfm.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        assert signal.ndim == 1

    def test_duration_equals_duty_cycle_over_prf(self, lfm):
        assert lfm.duration(PRF) == pytest.approx(0.1 / PRF)

    def test_chirp_slope(self, lfm):
        """K = bandwidth / duration."""
        duration = lfm.duration(PRF)
        K_expected = lfm.bandwidth / duration
        # Verify via instantaneous frequency: d(phase)/dt at t should be 2*pi*K*t
        signal = lfm.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        n = len(signal)
        t = np.arange(n) / SAMPLE_RATE
        phase = np.unwrap(np.angle(signal))
        # Numerical derivative of phase
        dt = 1.0 / SAMPLE_RATE
        inst_freq = np.diff(phase) / (2 * np.pi * dt)
        # At midpoint, instantaneous freq should be approximately K * t_mid
        mid = n // 2
        t_mid = t[mid]
        assert inst_freq[mid] == pytest.approx(K_expected * t_mid, rel=0.01)

    def test_phase_is_quadratic(self, lfm):
        """Phase of signal should follow pi*K*t^2."""
        signal = lfm.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        duration = lfm.duration(PRF)
        K = lfm.bandwidth / duration
        n = len(signal)
        t = np.arange(n) / SAMPLE_RATE
        expected_phase = np.pi * K * t**2
        actual_phase = np.unwrap(np.angle(signal))
        # Check at several points (beginning, quarter, mid)
        for idx in [0, n // 4, n // 2]:
            # Allow phase offset but slope should match
            assert actual_phase[idx] == pytest.approx(
                expected_phase[idx], abs=0.1
            )

    def test_duty_cycle_must_be_less_than_one(self):
        with pytest.raises(ValueError, match="duty_cycle"):
            LFMWaveform(bandwidth=100e6, duty_cycle=1.0)

    def test_with_phase_noise(self):
        pn = CompositePSDPhaseNoise()
        lfm_pn = LFMWaveform(bandwidth=100e6, duty_cycle=0.1, phase_noise=pn)
        signal = lfm_pn.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        assert np.iscomplexobj(signal)
        assert len(signal) == int(lfm_pn.duration(PRF) * SAMPLE_RATE)

    def test_with_window(self):
        lfm_win = LFMWaveform(
            bandwidth=100e6, duty_cycle=0.1, window=np.hamming
        )
        signal = lfm_win.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        n = len(signal)
        # Amplitude should be tapered by the window
        amp = np.abs(signal)
        # Edges should be smaller than center
        assert amp[0] < amp[n // 2]
        assert amp[-1] < amp[n // 2]


class TestLFMWaveformRangeCompress:
    """Test LFM matched-filter range compression."""

    def test_must_call_generate_first(self, lfm):
        echo = np.ones(100, dtype=complex)
        with pytest.raises(RuntimeError, match="generate"):
            lfm.range_compress(echo, prf=PRF, sample_rate=SAMPLE_RATE)

    def test_compress_chirp_echo_1d(self, lfm):
        """Compressing a chirp echo with itself should produce a peak."""
        signal = lfm.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        # Echo is just the transmit signal (zero delay)
        result = lfm.range_compress(signal, prf=PRF, sample_rate=SAMPLE_RATE)
        assert result.ndim == 1
        # Peak should be at index 0 (zero delay)
        peak_idx = np.argmax(np.abs(result))
        assert peak_idx == 0
        # Peak should be significantly larger than sidelobes
        peak_val = np.abs(result[peak_idx])
        mean_val = np.mean(np.abs(result))
        assert peak_val > 5 * mean_val

    def test_compress_2d_echo(self, lfm):
        """2D echo (multiple pulses) should compress each row."""
        signal = lfm.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        echo = np.tile(signal, (4, 1))
        result = lfm.range_compress(echo, prf=PRF, sample_rate=SAMPLE_RATE)
        assert result.ndim == 2
        assert result.shape[0] == 4
        # Each pulse should have peak at index 0
        for i in range(4):
            assert np.argmax(np.abs(result[i])) == 0

    def test_compress_with_window(self):
        lfm_win = LFMWaveform(
            bandwidth=100e6, duty_cycle=0.1, window=np.hamming
        )
        signal = lfm_win.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        result = lfm_win.range_compress(
            signal, prf=PRF, sample_rate=SAMPLE_RATE
        )
        assert result.ndim == 1
        # Should still produce a peak
        peak_val = np.abs(result).max()
        assert peak_val > 0


class TestLFMWaveformRegistry:
    """Test LFM registration."""

    def test_registered_in_waveform_registry(self):
        from pySimSAR.waveforms.registry import waveform_registry

        assert "lfm" in waveform_registry
        assert waveform_registry.get("lfm") is LFMWaveform


# ===================================================================
# T027: FMCWWaveform tests
# ===================================================================

class TestFMCWWaveformGenerate:
    """Test FMCW signal generation."""

    def test_up_ramp_returns_complex(self, fmcw_up):
        signal = fmcw_up.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        assert np.iscomplexobj(signal)

    def test_correct_length(self, fmcw_up):
        signal = fmcw_up.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        expected = int(fmcw_up.duration(PRF) * SAMPLE_RATE)
        assert len(signal) == expected

    def test_down_ramp_signal(self, fmcw_down):
        signal = fmcw_down.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        assert np.iscomplexobj(signal)
        assert len(signal) == int(fmcw_down.duration(PRF) * SAMPLE_RATE)

    def test_triangle_ramp_correct_length(self, fmcw_triangle):
        signal = fmcw_triangle.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        expected = int(fmcw_triangle.duration(PRF) * SAMPLE_RATE)
        assert len(signal) == expected

    def test_triangle_two_half_structure(self, fmcw_triangle):
        """Triangle ramp should have up-chirp in first half, down in second."""
        signal = fmcw_triangle.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        n = len(signal)
        n_half = n // 2

        # Phase of first half should be increasing (positive chirp)
        phase_first = np.unwrap(np.angle(signal[:n_half]))
        # Phase of second half should be decreasing (negative chirp)
        phase_second = np.unwrap(np.angle(signal[n_half:]))

        # Instantaneous frequency of first half should be positive
        diff_first = np.diff(phase_first)
        assert np.mean(diff_first) > 0
        # Instantaneous frequency of second half should be negative
        diff_second = np.diff(phase_second)
        assert np.mean(diff_second) < 0

    def test_invalid_ramp_type_rejected(self):
        with pytest.raises(ValueError, match="ramp_type"):
            FMCWWaveform(bandwidth=50e6, ramp_type="invalid")

    def test_ramp_type_property(self, fmcw_up):
        assert fmcw_up.ramp_type == "up"

    def test_with_phase_noise(self):
        pn = CompositePSDPhaseNoise()
        fmcw = FMCWWaveform(
            bandwidth=50e6, duty_cycle=1.0, ramp_type="up", phase_noise=pn
        )
        signal = fmcw.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        assert np.iscomplexobj(signal)

    def test_with_window(self):
        fmcw = FMCWWaveform(
            bandwidth=50e6, duty_cycle=1.0, ramp_type="up", window=np.hamming
        )
        signal = fmcw.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        amp = np.abs(signal)
        n = len(signal)
        assert amp[0] < amp[n // 2]


class TestFMCWWaveformRangeCompress:
    """Test FMCW dechirp range compression."""

    def test_must_call_generate_first(self, fmcw_up):
        echo = np.ones(100, dtype=complex)
        with pytest.raises(RuntimeError, match="generate"):
            fmcw_up.range_compress(echo, prf=PRF, sample_rate=SAMPLE_RATE)

    def test_dechirp_1d(self, fmcw_up):
        """Dechirp of tx with itself should give a peak at DC."""
        signal = fmcw_up.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        result = fmcw_up.range_compress(
            signal, prf=PRF, sample_rate=SAMPLE_RATE
        )
        assert result.ndim == 1
        # Peak should be dominant
        peak_val = np.abs(result).max()
        mean_val = np.mean(np.abs(result))
        assert peak_val > 5 * mean_val

    def test_dechirp_2d(self, fmcw_up):
        signal = fmcw_up.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        echo = np.tile(signal, (3, 1))
        result = fmcw_up.range_compress(
            echo, prf=PRF, sample_rate=SAMPLE_RATE
        )
        assert result.ndim == 2
        assert result.shape[0] == 3

    def test_dechirp_with_window(self):
        fmcw = FMCWWaveform(
            bandwidth=50e6, duty_cycle=1.0, ramp_type="up", window=np.hamming
        )
        signal = fmcw.generate(prf=PRF, sample_rate=SAMPLE_RATE)
        result = fmcw.range_compress(
            signal, prf=PRF, sample_rate=SAMPLE_RATE
        )
        assert result.ndim == 1


class TestFMCWWaveformRegistry:
    """Test FMCW registration."""

    def test_registered_in_waveform_registry(self):
        from pySimSAR.waveforms.registry import waveform_registry

        assert "fmcw" in waveform_registry
        assert waveform_registry.get("fmcw") is FMCWWaveform


# ===================================================================
# T028: CompositePSDPhaseNoise tests
# ===================================================================

class TestCompositePSDPhaseNoise:
    """Test composite PSD phase noise generation."""

    def test_returns_real_array(self):
        pn = CompositePSDPhaseNoise()
        samples = pn.generate(n_samples=1024, sample_rate=SAMPLE_RATE)
        assert isinstance(samples, np.ndarray)
        assert not np.iscomplexobj(samples)

    def test_correct_length(self):
        pn = CompositePSDPhaseNoise()
        for n in [512, 1024, 2048]:
            samples = pn.generate(n_samples=n, sample_rate=SAMPLE_RATE)
            assert len(samples) == n

    def test_seed_reproducibility(self):
        pn = CompositePSDPhaseNoise()
        s1 = pn.generate(n_samples=1024, sample_rate=SAMPLE_RATE, seed=42)
        s2 = pn.generate(n_samples=1024, sample_rate=SAMPLE_RATE, seed=42)
        np.testing.assert_array_equal(s1, s2)

    def test_different_seeds_differ(self):
        pn = CompositePSDPhaseNoise()
        s1 = pn.generate(n_samples=1024, sample_rate=SAMPLE_RATE, seed=42)
        s2 = pn.generate(n_samples=1024, sample_rate=SAMPLE_RATE, seed=99)
        assert not np.array_equal(s1, s2)

    def test_psd_spectral_shape(self):
        """Output PSD should decay with frequency (dominated by 1/f^3 at low f)."""
        pn = CompositePSDPhaseNoise(
            flicker_fm_level=-60.0,
            white_fm_level=-120.0,
            flicker_pm_level=-140.0,
            white_floor=-160.0,
        )
        # Generate a long sequence for PSD estimation
        n = 8192
        sr = 1e6
        samples = pn.generate(n_samples=n, sample_rate=sr, seed=123)
        # Estimate PSD via periodogram
        spectrum = np.abs(np.fft.rfft(samples)) ** 2 / n
        freqs = np.fft.rfftfreq(n, 1.0 / sr)
        # Low-frequency power should be higher than high-frequency power
        n_freq = len(freqs)
        low_band = spectrum[1 : n_freq // 10]
        high_band = spectrum[n_freq // 2 :]
        assert np.mean(low_band) > np.mean(high_band)

    def test_custom_levels(self):
        """Custom levels should produce different noise than defaults."""
        pn_default = CompositePSDPhaseNoise()
        pn_custom = CompositePSDPhaseNoise(
            flicker_fm_level=-60.0,
            white_fm_level=-80.0,
            flicker_pm_level=-100.0,
            white_floor=-120.0,
        )
        s_default = pn_default.generate(
            n_samples=1024, sample_rate=SAMPLE_RATE, seed=42
        )
        s_custom = pn_custom.generate(
            n_samples=1024, sample_rate=SAMPLE_RATE, seed=42
        )
        # Higher noise levels should produce larger variance
        assert np.var(s_custom) > np.var(s_default)

    def test_name_attribute(self):
        pn = CompositePSDPhaseNoise()
        assert pn.name == "composite_psd"

    def test_registered_in_phase_noise_registry(self):
        # Trigger registration by importing the waveforms package
        import pySimSAR.waveforms  # noqa: F401
        from pySimSAR.waveforms.registry import phase_noise_registry

        assert "composite_psd" in phase_noise_registry
        assert phase_noise_registry.get("composite_psd") is CompositePSDPhaseNoise
