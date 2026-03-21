"""Shared test fixtures for PySimSAR tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pySimSAR.core.types import RawData
from pySimSAR.io.parameter_set import build_simulation, load_parameter_set
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.simulation.engine import SimulationEngine

# ---------------------------------------------------------------------------
# Example project directories
# ---------------------------------------------------------------------------

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
GOLDEN_DIR = EXAMPLES_DIR / "golden"
SCENARIOS_DIR = EXAMPLES_DIR / "scenarios"

# Auto-discover scenario directories
SCENARIO_NAMES = sorted(
    d.name
    for d in SCENARIOS_DIR.iterdir()
    if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
) if SCENARIOS_DIR.exists() else []


# ---------------------------------------------------------------------------
# Scenario helpers
# ---------------------------------------------------------------------------

def _make_trajectory(pulse_times, positions, velocities) -> Trajectory:
    """Create a Trajectory with zero attitude."""
    attitude = np.zeros((len(pulse_times), 3))
    return Trajectory(
        time=pulse_times,
        position=positions,
        velocity=velocities,
        attitude=attitude,
    )


def run_scenario(name: str, cache: dict) -> dict:
    """Load, build, and run a scenario, caching the result."""
    if name in cache:
        return cache[name]

    case_dir = SCENARIOS_DIR / name
    params = load_parameter_set(case_dir)
    sim = build_simulation(params)

    engine = SimulationEngine(
        scene=sim["scene"],
        radar=sim["radar"],
        platform=sim["platform"],
        **sim["engine_kwargs"],
    )
    result = engine.run()

    channel = list(result.echo.keys())[0]
    echo = result.echo[channel]
    raw = RawData(
        echo=echo,
        channel=channel,
        sample_rate=result.sample_rate,
        carrier_freq=sim["radar"].carrier_freq,
        bandwidth=sim["radar"].bandwidth,
        prf=sim["radar"].waveform.prf,
        waveform_name=sim["radar"].waveform.name,
        sar_mode=sim["radar"].mode.value,
        gate_delay=result.gate_delay,
    )

    trajectory = _make_trajectory(
        result.pulse_times, result.positions, result.velocities,
    )

    ideal_traj = None
    if result.ideal_trajectory is not None:
        ideal_traj = _make_trajectory(
            result.pulse_times,
            result.ideal_trajectory.position,
            result.ideal_trajectory.velocity,
        )

    plat_data = params.get("platform", {})
    has_perturbation = plat_data.get("perturbation") is not None
    has_moco = sim["processing_config"] is not None and sim["processing_config"].moco is not None

    nav_data = None
    if result.navigation_data:
        for nd in result.navigation_data:
            if nd.position is not None:
                nav_data = nd
                break
        if nav_data is None:
            nav_data = result.navigation_data[0]

    entry = {
        "sim_objects": sim,
        "sim_result": result,
        "raw_data": {channel: raw},
        "trajectory": trajectory,
        "ideal_trajectory": ideal_traj,
        "nav_data": nav_data,
        "has_perturbation": has_perturbation,
        "has_moco": has_moco,
    }
    cache[name] = entry
    return entry


@pytest.fixture(scope="session")
def scenario_cache():
    """Session-scoped cache for simulation results keyed by scenario name."""
    return {}


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
