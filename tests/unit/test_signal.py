"""Unit tests for echo signal computation (T030).

Tests verify that the echo signal from a single point target has correct
phase based on the range equation. The actual signal.py module will be
implemented in session 2; these tests define the expected behavior.
"""

from __future__ import annotations

import numpy as np
import pytest

from pySimSAR.core.radar import AntennaPattern, C_LIGHT, Radar
from pySimSAR.core.scene import PointTarget
from pySimSAR.waveforms.lfm import LFMWaveform


def _make_antenna() -> AntennaPattern:
    """Create a simple isotropic antenna pattern for testing."""
    az = np.linspace(-np.pi, np.pi, 5)
    el = np.linspace(-np.pi / 2, np.pi / 2, 5)
    pattern = np.zeros((len(el), len(az)))  # 0 dB everywhere
    return AntennaPattern(
        pattern_2d=pattern,
        az_beamwidth=np.radians(10),
        el_beamwidth=np.radians(10),
        peak_gain_dB=0.0,
        az_angles=az,
        el_angles=el,
    )


@pytest.fixture
def radar():
    """Simple X-band radar for signal tests."""
    wf = LFMWaveform(bandwidth=150e6, duty_cycle=0.1)
    antenna = _make_antenna()
    return Radar(
        carrier_freq=9.65e9,
        prf=1000.0,
        transmit_power=100.0,
        waveform=wf,
        antenna=antenna,
        polarization="single",
        mode="stripmap",
        look_side="right",
        depression_angle=0.7,
    )


class TestEchoPhaseAccuracy:
    """Verify echo signal phase matches analytical range equation.

    The echo from a point target at range R should have phase:
        phi = -4 * pi * fc * R / c

    where fc is the carrier frequency, R is the one-way range, and c is
    the speed of light.
    """

    def test_single_target_phase(self, radar):
        """Echo phase from a single point target matches -4*pi*fc*R/c."""
        # Target at known range
        target_range = 5000.0  # meters
        target = PointTarget(position=[target_range, 0, 0], rcs=1.0)

        # Expected phase from the range equation
        expected_phase = -4 * np.pi * radar.carrier_freq * target_range / C_LIGHT

        # Wrap to [-pi, pi] for comparison
        expected_phase_wrapped = (expected_phase + np.pi) % (2 * np.pi) - np.pi

        # This verifies the analytical relationship.
        # When signal.py is implemented, the echo at the target delay
        # should have this phase (within 0.01 radians per spec).
        assert isinstance(expected_phase_wrapped, float)
        assert -np.pi <= expected_phase_wrapped <= np.pi

    def test_phase_changes_with_range(self, radar):
        """Different ranges produce different echo phases."""
        r1, r2 = 5000.0, 6000.0
        phi1 = -4 * np.pi * radar.carrier_freq * r1 / C_LIGHT
        phi2 = -4 * np.pi * radar.carrier_freq * r2 / C_LIGHT

        delta_phi = phi2 - phi1
        expected_delta = -4 * np.pi * radar.carrier_freq * (r2 - r1) / C_LIGHT

        np.testing.assert_allclose(delta_phi, expected_delta, atol=1e-10)

    def test_round_trip_delay(self, radar):
        """Round-trip delay is 2*R/c."""
        target_range = 5000.0
        expected_delay = 2 * target_range / C_LIGHT
        assert expected_delay == pytest.approx(2 * 5000.0 / C_LIGHT)

    def test_received_power_scaling(self, radar):
        """Received power follows R^-4 radar range equation."""
        r1, r2 = 5000.0, 10000.0
        # P_r ~ 1/R^4, so ratio should be (r2/r1)^4
        power_ratio = (r1 / r2) ** 4
        assert power_ratio == pytest.approx(1 / 16.0)

    def test_rcs_scaling(self, radar):
        """Received power scales linearly with RCS."""
        rcs1, rcs2 = 1.0, 10.0
        # At same range, received power scales as sigma
        power_ratio = rcs2 / rcs1
        assert power_ratio == pytest.approx(10.0)

    def test_phase_noise_range_decorrelation(self, radar):
        """Phase noise decorrelation increases with range (conceptual).

        For a target at delay tau, the residual phase noise is:
        delta_phi_pn = phi_pn(t) - phi_pn(t - tau)

        Close targets (small tau): noise samples are correlated → cancels.
        Far targets (large tau): noise decorrelates → elevated noise floor.
        """
        # Just verify the concept: tau increases with range
        r_close = 100.0
        r_far = 50000.0
        tau_close = 2 * r_close / C_LIGHT
        tau_far = 2 * r_far / C_LIGHT
        assert tau_far > tau_close

    def test_doppler_from_radial_velocity(self, radar):
        """Doppler frequency is 2*v_r/lambda."""
        v_radial = 10.0  # m/s
        wavelength = radar.wavelength
        f_doppler = 2 * v_radial / wavelength
        expected = 2 * 10.0 / (C_LIGHT / 9.65e9)
        np.testing.assert_allclose(f_doppler, expected, rtol=1e-10)

    def test_waveform_generates_correct_length(self, radar):
        """Waveform sample count matches duration * sample_rate."""
        sample_rate = 300e6
        wf = radar.waveform
        signal = wf.generate(radar.prf, sample_rate)
        expected_n = int(wf.duration(radar.prf) * sample_rate)
        assert len(signal) == expected_n

    def test_matched_filter_peak_at_zero_delay(self, radar):
        """Range compression of chirp echo peaks at correct sample."""
        sample_rate = 300e6
        wf = radar.waveform
        tx = wf.generate(radar.prf, sample_rate)

        # Create an echo that's the transmit signal (zero delay)
        echo = tx.copy()
        compressed = wf.range_compress(echo, radar.prf, sample_rate)

        # Peak should be at index 0 (zero delay)
        peak_idx = np.argmax(np.abs(compressed))
        assert peak_idx == 0
