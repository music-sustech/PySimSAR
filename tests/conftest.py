"""Shared test fixtures for PySimSAR tests."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def rng():
    """Deterministic random number generator for reproducible tests."""
    return np.random.default_rng(seed=42)


@pytest.fixture
def simple_scene_params():
    """Parameters for a simple 3-point-target scene."""
    return {
        "origin_lat": 40.0,
        "origin_lon": -105.0,
        "origin_alt": 1600.0,
        "targets": [
            {"position": np.array([0.0, 0.0, 0.0]), "rcs": 1.0},
            {"position": np.array([100.0, 0.0, 0.0]), "rcs": 0.5},
            {"position": np.array([0.0, 200.0, 0.0]), "rcs": 0.8},
        ],
    }


@pytest.fixture
def xband_radar_params():
    """Parameters for an X-band pulsed radar."""
    return {
        "carrier_freq": 9.65e9,
        "prf": 1000.0,
        "transmit_power": 100.0,
        "noise_figure": 3.0,
        "system_losses": 2.0,
        "reference_temp": 290.0,
        "polarization": "single",
        "mode": "stripmap",
        "look_side": "right",
        "depression_angle": 0.7,
        "squint_angle": 0.0,
    }


@pytest.fixture
def lfm_waveform_params():
    """Parameters for an LFM waveform."""
    return {
        "bandwidth": 150e6,
        "duty_cycle": 0.1,
    }


@pytest.fixture
def fmcw_waveform_params():
    """Parameters for an FMCW waveform (W-band)."""
    return {
        "bandwidth": 1e9,
        "duty_cycle": 0.8,
        "ramp_type": "up",
    }


@pytest.fixture
def platform_params():
    """Parameters for a straight-line airborne platform."""
    return {
        "velocity": 100.0,
        "altitude": 2000.0,
        "heading": 0.0,
        "start_position": np.array([-500.0, -5000.0, 2000.0]),
    }


@pytest.fixture
def gps_sensor_params():
    """Parameters for a GPS sensor."""
    return {
        "accuracy_rms": 0.02,
        "update_rate": 10.0,
    }


@pytest.fixture
def imu_sensor_params():
    """Parameters for an IMU sensor."""
    return {
        "accel_noise_density": 0.0002,
        "gyro_noise_density": 5e-6,
        "sample_rate": 200.0,
    }
