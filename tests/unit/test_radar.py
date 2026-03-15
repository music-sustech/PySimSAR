"""Unit tests for AntennaPattern and Radar (T024, T025)."""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from pySimSAR.core.radar import AntennaPattern, C_LIGHT, K_BOLTZMANN, Radar
from pySimSAR.core.types import LookSide, PolarizationMode, SARMode
from pySimSAR.waveforms.base import Waveform


# ---------------------------------------------------------------------------
# Mock waveform for Radar tests
# ---------------------------------------------------------------------------

class MockWaveform(Waveform):
    """Minimal concrete waveform for testing."""

    name = "mock"

    def generate(self, prf: float, sample_rate: float) -> np.ndarray:
        return np.zeros(10, dtype=complex)

    def range_compress(
        self, echo: np.ndarray, prf: float, sample_rate: float
    ) -> np.ndarray:
        return echo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def array_pattern():
    """Create a simple 2D array antenna pattern."""
    az_angles = np.linspace(-0.1, 0.1, 21)
    el_angles = np.linspace(-0.05, 0.05, 11)
    az_grid, el_grid = np.meshgrid(az_angles, el_angles)
    # Simple sinc-like pattern peaking at (0, 0)
    pattern = 30.0 - 10.0 * (az_grid**2 + el_grid**2) / 0.01
    return AntennaPattern(
        pattern_2d=pattern,
        az_beamwidth=0.05,
        el_beamwidth=0.03,
        peak_gain_dB=30.0,
        az_angles=az_angles,
        el_angles=el_angles,
    )


@pytest.fixture()
def callable_pattern():
    """Create a callable antenna pattern."""

    def _gain(az: float, el: float) -> float:
        return 30.0 - 100.0 * (az**2 + el**2)

    return AntennaPattern(
        pattern_2d=_gain,
        az_beamwidth=0.05,
        el_beamwidth=0.03,
        peak_gain_dB=30.0,
    )


@pytest.fixture()
def mock_waveform():
    """Create a mock waveform with reasonable defaults."""
    return MockWaveform(bandwidth=50e6, duty_cycle=0.1)


@pytest.fixture()
def basic_radar(mock_waveform, array_pattern):
    """Create a basic Radar instance."""
    return Radar(
        carrier_freq=9.65e9,
        prf=1000.0,
        transmit_power=500.0,
        waveform=mock_waveform,
        antenna=array_pattern,
        polarization="single",
        mode="stripmap",
        look_side="right",
        depression_angle=0.7,
    )


# ---------------------------------------------------------------------------
# AntennaPattern tests (T024)
# ---------------------------------------------------------------------------

class TestAntennaPattern:
    """Tests for AntennaPattern."""

    def test_create_array_pattern(self, array_pattern):
        """Array pattern stores fields correctly."""
        assert array_pattern.az_beamwidth == 0.05
        assert array_pattern.el_beamwidth == 0.03
        assert array_pattern.peak_gain_dB == 30.0
        assert isinstance(array_pattern.pattern_2d, np.ndarray)
        assert array_pattern.az_angles is not None
        assert array_pattern.el_angles is not None

    def test_create_callable_pattern(self, callable_pattern):
        """Callable pattern stores fields correctly."""
        assert callable_pattern.az_beamwidth == 0.05
        assert callable_pattern.el_beamwidth == 0.03
        assert callable_pattern.peak_gain_dB == 30.0
        assert callable(callable_pattern.pattern_2d)

    def test_gain_array_interpolation(self, array_pattern):
        """gain() returns interpolated values for array patterns."""
        # At boresight the gain should be close to peak
        g = array_pattern.gain(0.0, 0.0)
        assert isinstance(g, float)
        assert g == pytest.approx(30.0, abs=1.0)

        # Off-boresight gain should be lower
        g_off = array_pattern.gain(0.05, 0.025)
        assert g_off < g

    def test_gain_callable_evaluation(self, callable_pattern):
        """gain() calls the callable for evaluation."""
        g = callable_pattern.gain(0.0, 0.0)
        assert g == pytest.approx(30.0)

        g_off = callable_pattern.gain(0.01, 0.01)
        expected = 30.0 - 100.0 * (0.01**2 + 0.01**2)
        assert g_off == pytest.approx(expected)

    def test_invalid_az_beamwidth(self):
        """Negative or zero az_beamwidth raises ValueError."""
        with pytest.raises(ValueError, match="az_beamwidth"):
            AntennaPattern(
                pattern_2d=lambda az, el: 0.0,
                az_beamwidth=0.0,
                el_beamwidth=0.03,
                peak_gain_dB=30.0,
            )
        with pytest.raises(ValueError, match="az_beamwidth"):
            AntennaPattern(
                pattern_2d=lambda az, el: 0.0,
                az_beamwidth=-0.01,
                el_beamwidth=0.03,
                peak_gain_dB=30.0,
            )

    def test_invalid_el_beamwidth(self):
        """Negative or zero el_beamwidth raises ValueError."""
        with pytest.raises(ValueError, match="el_beamwidth"):
            AntennaPattern(
                pattern_2d=lambda az, el: 0.0,
                az_beamwidth=0.05,
                el_beamwidth=0.0,
                peak_gain_dB=30.0,
            )

    def test_array_pattern_requires_angles(self):
        """Array pattern without angle vectors raises ValueError."""
        pattern = np.zeros((5, 10))
        with pytest.raises(ValueError, match="az_angles and el_angles"):
            AntennaPattern(
                pattern_2d=pattern,
                az_beamwidth=0.05,
                el_beamwidth=0.03,
                peak_gain_dB=30.0,
            )

    def test_array_pattern_shape_mismatch(self):
        """Mismatched pattern shape raises ValueError."""
        az = np.linspace(-0.1, 0.1, 10)
        el = np.linspace(-0.05, 0.05, 5)
        pattern = np.zeros((3, 7))  # wrong shape
        with pytest.raises(ValueError, match="shape"):
            AntennaPattern(
                pattern_2d=pattern,
                az_beamwidth=0.05,
                el_beamwidth=0.03,
                peak_gain_dB=30.0,
                az_angles=az,
                el_angles=el,
            )


# ---------------------------------------------------------------------------
# Radar tests (T025)
# ---------------------------------------------------------------------------

class TestRadar:
    """Tests for Radar."""

    def test_create_with_all_params(self, basic_radar):
        """Radar stores all parameters correctly."""
        r = basic_radar
        assert r.carrier_freq == 9.65e9
        assert r.prf == 1000.0
        assert r.transmit_power == 500.0
        assert r.noise_figure == 3.0
        assert r.system_losses == 2.0
        assert r.reference_temp == 290.0
        assert r.depression_angle == 0.7
        assert r.squint_angle == 0.0

    def test_bandwidth_property(self, basic_radar):
        """bandwidth delegates to waveform."""
        assert basic_radar.bandwidth == 50e6

    def test_pri_property(self, basic_radar):
        """pri is 1/prf."""
        assert basic_radar.pri == pytest.approx(1.0 / 1000.0)

    def test_wavelength_property(self, basic_radar):
        """wavelength = c / carrier_freq."""
        expected = C_LIGHT / 9.65e9
        assert basic_radar.wavelength == pytest.approx(expected)

    def test_noise_power_property(self, basic_radar):
        """noise_power = k * T * B * F (linear)."""
        f_linear = 10.0 ** (3.0 / 10.0)
        expected = K_BOLTZMANN * 290.0 * 50e6 * f_linear
        assert basic_radar.noise_power == pytest.approx(expected, rel=1e-10)

    def test_string_to_enum_conversion(self, mock_waveform, array_pattern):
        """String values for polarization/mode/look_side convert to enums."""
        r = Radar(
            carrier_freq=9.65e9,
            prf=1000.0,
            transmit_power=500.0,
            waveform=mock_waveform,
            antenna=array_pattern,
            polarization="dual",
            mode="spotlight",
            look_side="left",
            depression_angle=0.5,
        )
        assert r.polarization is PolarizationMode.DUAL
        assert r.mode is SARMode.SPOTLIGHT
        assert r.look_side is LookSide.LEFT

    def test_enum_passthrough(self, mock_waveform, array_pattern):
        """Enum instances pass through without conversion."""
        r = Radar(
            carrier_freq=9.65e9,
            prf=1000.0,
            transmit_power=500.0,
            waveform=mock_waveform,
            antenna=array_pattern,
            polarization=PolarizationMode.QUAD,
            mode=SARMode.SCANMAR,
            look_side=LookSide.RIGHT,
            depression_angle=0.5,
        )
        assert r.polarization is PolarizationMode.QUAD
        assert r.mode is SARMode.SCANMAR
        assert r.look_side is LookSide.RIGHT

    def test_invalid_carrier_freq(self, mock_waveform, array_pattern):
        """carrier_freq <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="carrier_freq"):
            Radar(
                carrier_freq=0,
                prf=1000.0,
                transmit_power=500.0,
                waveform=mock_waveform,
                antenna=array_pattern,
                polarization="single",
                mode="stripmap",
                look_side="right",
                depression_angle=0.5,
            )

    def test_invalid_prf(self, mock_waveform, array_pattern):
        """prf <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="prf"):
            Radar(
                carrier_freq=9.65e9,
                prf=-1.0,
                transmit_power=500.0,
                waveform=mock_waveform,
                antenna=array_pattern,
                polarization="single",
                mode="stripmap",
                look_side="right",
                depression_angle=0.5,
            )

    def test_invalid_transmit_power(self, mock_waveform, array_pattern):
        """transmit_power <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="transmit_power"):
            Radar(
                carrier_freq=9.65e9,
                prf=1000.0,
                transmit_power=0.0,
                waveform=mock_waveform,
                antenna=array_pattern,
                polarization="single",
                mode="stripmap",
                look_side="right",
                depression_angle=0.5,
            )

    def test_invalid_noise_figure(self, mock_waveform, array_pattern):
        """Negative noise_figure raises ValueError."""
        with pytest.raises(ValueError, match="noise_figure"):
            Radar(
                carrier_freq=9.65e9,
                prf=1000.0,
                transmit_power=500.0,
                waveform=mock_waveform,
                antenna=array_pattern,
                polarization="single",
                mode="stripmap",
                look_side="right",
                depression_angle=0.5,
                noise_figure=-1.0,
            )

    def test_invalid_depression_angle(self, mock_waveform, array_pattern):
        """depression_angle outside [0, pi/2] raises ValueError."""
        with pytest.raises(ValueError, match="depression_angle"):
            Radar(
                carrier_freq=9.65e9,
                prf=1000.0,
                transmit_power=500.0,
                waveform=mock_waveform,
                antenna=array_pattern,
                polarization="single",
                mode="stripmap",
                look_side="right",
                depression_angle=2.0,
            )

    def test_waveform_none_raises(self, array_pattern):
        """waveform=None raises ValueError."""
        with pytest.raises(ValueError, match="waveform"):
            Radar(
                carrier_freq=9.65e9,
                prf=1000.0,
                transmit_power=500.0,
                waveform=None,
                antenna=array_pattern,
                polarization="single",
                mode="stripmap",
                look_side="right",
                depression_angle=0.5,
            )

    def test_duty_cycle_warning(self, array_pattern):
        """Warn when waveform duration exceeds PRI."""
        # duty_cycle=0.9, prf=1.0 => duration=0.9, PRI=1.0 — OK
        # But duty_cycle=1.5 is invalid for Waveform, so use high duty + low prf trick:
        # duty_cycle=0.5, prf=0.4 => duration=0.5/0.4=1.25, PRI=1/0.4=2.5 — no warning
        # We need duration > PRI: duty_cycle=0.5, prf=1.0 => duration=0.5, PRI=1.0 — no
        # Actually: duration = duty_cycle / prf, PRI = 1/prf
        # duration > PRI => duty_cycle/prf > 1/prf => duty_cycle > 1
        # But Waveform caps duty_cycle at 1.0. So the warning can only trigger
        # if waveform.duration() is overridden. Let's just use a custom mock.
        class HighDutyWaveform(Waveform):
            name = "high_duty"

            def __init__(self):
                # Use max duty_cycle allowed
                super().__init__(bandwidth=50e6, duty_cycle=1.0)

            def duration(self, prf: float) -> float:
                # Override to return something > PRI
                return 2.0 / prf

            def generate(self, prf, sample_rate):
                return np.zeros(10, dtype=complex)

            def range_compress(self, echo, prf, sample_rate):
                return echo

        wf = HighDutyWaveform()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Radar(
                carrier_freq=9.65e9,
                prf=1000.0,
                transmit_power=500.0,
                waveform=wf,
                antenna=array_pattern,
                polarization="single",
                mode="stripmap",
                look_side="right",
                depression_angle=0.5,
            )
            assert len(w) == 1
            assert "duration" in str(w[0].message).lower() or "PRI" in str(
                w[0].message
            )
