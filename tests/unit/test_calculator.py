"""Tests for SARCalculator derived-value computation."""

from __future__ import annotations

import math

import pytest

from pySimSAR.core.calculator import CalculatedResult, SARCalculator

C = 299792458.0
K_B = 1.380649e-23


# ------------------------------------------------------------------ fixtures


@pytest.fixture
def calculator() -> SARCalculator:
    return SARCalculator()


@pytest.fixture
def params_xband() -> dict:
    """X-band airborne stripmap configuration."""
    return {
        "carrier_freq": 9.65e9,
        "prf": 1000.0,
        "bandwidth": 100e6,
        "duty_cycle": 0.01,
        "transmit_power": 1000.0,
        "az_beamwidth": math.radians(10.0),
        "el_beamwidth": math.radians(10.0),

        "depression_angle": math.radians(45.0),
        "velocity": 100.0,
        "altitude": 1000.0,
        "noise_figure": 3.0,
        "system_losses": 2.0,
        "receiver_gain_dB": 30.0,
        "reference_temp": 290.0,
        "mode": "stripmap",
        "near_range": 1350.0,
        "far_range": 1500.0,
    }


@pytest.fixture
def params_cband() -> dict:
    """C-band spaceborne stripmap configuration."""
    return {
        "carrier_freq": 5.405e9,
        "prf": 1700.0,
        "bandwidth": 50e6,
        "duty_cycle": 0.05,
        "transmit_power": 5000.0,
        "az_beamwidth": math.radians(0.3),
        "el_beamwidth": math.radians(5.0),
        "depression_angle": math.radians(30.0),
        "velocity": 7500.0,
        "altitude": 700000.0,
        "noise_figure": 2.5,
        "system_losses": 3.0,
        "receiver_gain_dB": 0.0,
        "reference_temp": 290.0,
        "mode": "stripmap",
        "near_range": 800000.0,
        "far_range": 850000.0,
    }


@pytest.fixture
def params_wband() -> dict:
    """W-band UAV FMCW configuration."""
    return {
        "carrier_freq": 77e9,
        "prf": 5000.0,
        "bandwidth": 2e9,
        "duty_cycle": 1.0,
        "transmit_power": 0.01,
        "az_beamwidth": math.radians(3.0),
        "el_beamwidth": math.radians(10.0),
        "depression_angle": math.radians(60.0),
        "velocity": 30.0,
        "altitude": 100.0,
        "noise_figure": 8.0,
        "system_losses": 5.0,
        "receiver_gain_dB": 20.0,
        "reference_temp": 290.0,
        "mode": "stripmap",
        "near_range": 100.0,
        "far_range": 200.0,
    }


# ----------------------------------------------- Config 1: X-band airborne


class TestXBandAirborne:
    """Verify derived values for X-band airborne stripmap."""

    def test_wavelength(self, calculator: SARCalculator, params_xband: dict) -> None:
        result = calculator.compute(params_xband)
        expected = C / 9.65e9  # ~0.031066 m
        assert result["wavelength"].value == pytest.approx(expected, rel=1e-4)
        assert result["wavelength"].unit == "m"

    def test_pulse_width(self, calculator: SARCalculator, params_xband: dict) -> None:
        result = calculator.compute(params_xband)
        expected = 0.01 / 1000.0  # 1e-5 s
        assert result["pulse_width"].value == pytest.approx(expected, rel=1e-4)
        assert result["pulse_width"].unit == "s"

    def test_range_resolution(self, calculator: SARCalculator, params_xband: dict) -> None:
        result = calculator.compute(params_xband)
        expected = C / (2.0 * 100e6)  # ~1.499 m
        assert result["range_resolution"].value == pytest.approx(expected, rel=1e-4)
        assert result["range_resolution"].unit == "m"

    def test_azimuth_resolution(self, calculator: SARCalculator, params_xband: dict) -> None:
        result = calculator.compute(params_xband)
        wl = C / 9.65e9
        antenna_length = wl / math.radians(10.0)  # ~0.178 m
        expected = antenna_length / 2.0  # ~0.089 m
        assert result["azimuth_resolution"].value == pytest.approx(expected, rel=1e-4)
        assert result["azimuth_resolution"].unit == "m"

    def test_unambiguous_range(self, calculator: SARCalculator, params_xband: dict) -> None:
        result = calculator.compute(params_xband)
        expected = C / (2.0 * 1000.0)  # ~149896.229 m
        assert result["unambiguous_range"].value == pytest.approx(expected, rel=1e-4)
        assert result["unambiguous_range"].unit == "m"
        # far_range=1500 is well below unambiguous_range; no warning expected
        assert result["unambiguous_range"].warning is None

    def test_unambiguous_doppler(self, calculator: SARCalculator, params_xband: dict) -> None:
        result = calculator.compute(params_xband)
        wl = C / 9.65e9
        expected = wl * 1000.0 / 4.0
        assert result["unambiguous_doppler"].value == pytest.approx(expected, rel=1e-4)

    def test_swath_width_ground(self, calculator: SARCalculator, params_xband: dict) -> None:
        result = calculator.compute(params_xband)
        expected = (1500.0 - 1350.0) / math.sin(math.radians(45.0))
        assert result["swath_width_ground"].value == pytest.approx(expected, rel=1e-4)
        assert result["swath_width_ground"].unit == "m"


# ----------------------------------------------- Config 2: C-band spaceborne


class TestCBandSpaceborne:
    """Verify derived values for C-band spaceborne stripmap."""

    def test_wavelength(self, calculator: SARCalculator, params_cband: dict) -> None:
        result = calculator.compute(params_cband)
        expected = C / 5.405e9  # ~0.05547 m
        assert result["wavelength"].value == pytest.approx(expected, rel=1e-4)

    def test_pulse_width(self, calculator: SARCalculator, params_cband: dict) -> None:
        result = calculator.compute(params_cband)
        expected = 0.05 / 1700.0  # ~2.941e-5 s
        assert result["pulse_width"].value == pytest.approx(expected, rel=1e-4)

    def test_range_resolution(self, calculator: SARCalculator, params_cband: dict) -> None:
        result = calculator.compute(params_cband)
        expected = C / (2.0 * 50e6)  # ~2.998 m
        assert result["range_resolution"].value == pytest.approx(expected, rel=1e-4)

    def test_azimuth_resolution(self, calculator: SARCalculator, params_cband: dict) -> None:
        result = calculator.compute(params_cband)
        wl = C / 5.405e9
        antenna_length = wl / math.radians(0.3)  # ~10.59 m
        expected = antenna_length / 2.0  # ~5.30 m
        assert result["azimuth_resolution"].value == pytest.approx(expected, rel=1e-4)

    def test_unambiguous_range(self, calculator: SARCalculator, params_cband: dict) -> None:
        result = calculator.compute(params_cband)
        expected = C / (2.0 * 1700.0)  # ~88173.1 m
        assert result["unambiguous_range"].value == pytest.approx(expected, rel=1e-4)
        # far_range=850000 >> unambiguous_range ~88173 => warning expected
        assert result["unambiguous_range"].warning is not None
        assert "range ambiguity" in result["unambiguous_range"].warning.lower()

    def test_synthetic_aperture(self, calculator: SARCalculator, params_cband: dict) -> None:
        result = calculator.compute(params_cband)
        wl = C / 5.405e9
        antenna_length = wl / math.radians(0.3)
        mid_range = (800000.0 + 850000.0) / 2.0
        expected = wl * mid_range / antenna_length
        assert result["synthetic_aperture"].value == pytest.approx(expected, rel=1e-4)


# ------------------------------------------------ Config 3: W-band UAV FMCW


class TestWBandUAV:
    """Verify derived values for W-band UAV FMCW."""

    def test_wavelength(self, calculator: SARCalculator, params_wband: dict) -> None:
        result = calculator.compute(params_wband)
        expected = C / 77e9  # ~0.003893 m
        assert result["wavelength"].value == pytest.approx(expected, rel=1e-4)

    def test_pulse_width(self, calculator: SARCalculator, params_wband: dict) -> None:
        result = calculator.compute(params_wband)
        expected = 1.0 / 5000.0  # 2e-4 s (FMCW: 100% duty cycle)
        assert result["pulse_width"].value == pytest.approx(expected, rel=1e-4)

    def test_range_resolution(self, calculator: SARCalculator, params_wband: dict) -> None:
        result = calculator.compute(params_wband)
        expected = C / (2.0 * 2e9)  # ~0.07495 m
        assert result["range_resolution"].value == pytest.approx(expected, rel=1e-4)

    def test_azimuth_resolution(self, calculator: SARCalculator, params_wband: dict) -> None:
        result = calculator.compute(params_wband)
        wl = C / 77e9
        antenna_length = wl / math.radians(3.0)  # ~0.0743 m
        expected = antenna_length / 2.0  # ~0.0372 m
        assert result["azimuth_resolution"].value == pytest.approx(expected, rel=1e-4)

    def test_unambiguous_range(self, calculator: SARCalculator, params_wband: dict) -> None:
        result = calculator.compute(params_wband)
        expected = C / (2.0 * 5000.0)  # ~29979.2 m
        assert result["unambiguous_range"].value == pytest.approx(expected, rel=1e-4)
        # far_range=200 << unambiguous_range; no warning
        assert result["unambiguous_range"].warning is None

    def test_doppler_bandwidth(self, calculator: SARCalculator, params_wband: dict) -> None:
        result = calculator.compute(params_wband)
        wl = C / 77e9
        antenna_length = wl / math.radians(3.0)
        az_res = antenna_length / 2.0
        expected = 2.0 * 30.0 / az_res
        assert result["doppler_bandwidth"].value == pytest.approx(expected, rel=1e-4)
        assert result["doppler_bandwidth"].unit == "Hz"


# ------------------------------------------------ Warning generation


class TestWarnings:
    """Verify that warnings fire under the correct conditions."""

    def test_unambiguous_range_warning_when_far_range_exceeds(
        self, calculator: SARCalculator, params_xband: dict
    ) -> None:
        """Set far_range beyond unambiguous range to trigger warning."""
        params_xband["far_range"] = 200000.0  # > C/(2*1000) ~ 149896 m
        result = calculator.compute(params_xband)
        assert result["unambiguous_range"].warning is not None
        assert "range ambiguity" in result["unambiguous_range"].warning.lower()

    def test_unambiguous_doppler_warning_when_velocity_exceeds(
        self, calculator: SARCalculator, params_xband: dict
    ) -> None:
        """Set velocity beyond unambiguous Doppler to trigger warning."""
        wl = C / 9.65e9
        unamb_doppler = wl * 1000.0 / 4.0  # ~7.77 m/s
        params_xband["velocity"] = unamb_doppler + 10.0  # exceeds limit
        result = calculator.compute(params_xband)
        assert result["unambiguous_doppler"].warning is not None
        assert "doppler ambiguity" in result["unambiguous_doppler"].warning.lower()

    def test_no_warning_when_within_limits(
        self, calculator: SARCalculator, params_xband: dict
    ) -> None:
        """Default X-band config should have no warnings on unambiguous_range."""
        result = calculator.compute(params_xband)
        assert result["unambiguous_range"].warning is None

    def test_nesz_warning_when_sensitivity_poor(
        self, calculator: SARCalculator, params_wband: dict
    ) -> None:
        """W-band UAV has very low power; NESZ may be above -10 dB."""
        result = calculator.compute(params_wband)
        nesz = result["nesz"]
        if nesz.value > -10.0:
            assert nesz.warning is not None
            assert "nesz" in nesz.warning.lower()


# ------------------------------------------------ Missing optional params


class TestMissingOptionalParams:
    """Quantities that require optional params should be absent when those params are missing."""

    def test_swath_width_ground_skipped_without_ranges(
        self, calculator: SARCalculator, params_xband: dict
    ) -> None:
        del params_xband["near_range"]
        del params_xband["far_range"]
        result = calculator.compute(params_xband)
        assert "swath_width_ground" not in result

    def test_n_range_samples_skipped_without_ranges(
        self, calculator: SARCalculator, params_xband: dict
    ) -> None:
        del params_xband["near_range"]
        del params_xband["far_range"]
        result = calculator.compute(params_xband)
        assert "n_range_samples" not in result

    def test_flight_time_skipped_without_flight_time_or_positions(
        self, calculator: SARCalculator, params_xband: dict
    ) -> None:
        # Ensure no flight_time, start_position, or stop_position
        params_xband.pop("flight_time", None)
        params_xband.pop("start_position", None)
        params_xband.pop("stop_position", None)
        result = calculator.compute(params_xband)
        assert "flight_time" not in result
        assert "n_pulses" not in result
        assert "track_length" not in result

    def test_flight_time_present_when_provided(
        self, calculator: SARCalculator, params_xband: dict
    ) -> None:
        params_xband["flight_time"] = 60.0
        result = calculator.compute(params_xband)
        assert "flight_time" in result
        assert result["flight_time"].value == pytest.approx(60.0, rel=1e-4)
        assert "n_pulses" in result
        assert result["n_pulses"].value == pytest.approx(60000.0, rel=1e-4)
        assert "track_length" in result
        assert result["track_length"].value == pytest.approx(6000.0, rel=1e-4)

    def test_flight_time_derived_from_positions(
        self, calculator: SARCalculator, params_xband: dict
    ) -> None:
        params_xband["start_position"] = (0.0, 0.0, 0.0)
        params_xband["stop_position"] = (300.0, 400.0, 0.0)
        # distance = 500 m, velocity = 100 m/s => flight_time = 5 s
        result = calculator.compute(params_xband)
        assert "flight_time" in result
        assert result["flight_time"].value == pytest.approx(5.0, rel=1e-4)


# ------------------------------------------------ compute_single


class TestComputeSingle:
    """Verify compute_single returns the same values and handles errors."""

    def test_single_matches_bulk(
        self, calculator: SARCalculator, params_xband: dict
    ) -> None:
        bulk = calculator.compute(params_xband)
        for key in ("wavelength", "pulse_width", "range_resolution", "azimuth_resolution"):
            single = calculator.compute_single(key, params_xband)
            assert single.value == pytest.approx(bulk[key].value, rel=1e-10)
            assert single.unit == bulk[key].unit

    def test_unknown_key_raises(self, calculator: SARCalculator, params_xband: dict) -> None:
        with pytest.raises(KeyError, match="Unknown derived quantity"):
            calculator.compute_single("nonexistent_key", params_xband)


# ------------------------------------------------ CalculatedResult dataclass


class TestCalculatedResult:
    def test_default_warning_is_none(self) -> None:
        r = CalculatedResult(value=1.0, unit="m")
        assert r.warning is None

    def test_fields_stored(self) -> None:
        r = CalculatedResult(value=42.0, unit="dB", warning="test warning")
        assert r.value == 42.0
        assert r.unit == "dB"
        assert r.warning == "test warning"
