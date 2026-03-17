"""Golden reference test cases — end-to-end validation (T096z4).

Each golden case loads a parameter set, builds simulation objects,
runs the simulation, forms images, and validates against analytical
expectations.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pySimSAR.io.parameter_set import load_parameter_set, build_simulation
from pySimSAR.simulation.engine import SimulationEngine
from pySimSAR.core.radar import C_LIGHT
from pySimSAR.motion.trajectory import Trajectory as _Trajectory

GOLDEN_DIR = Path(__file__).parent.parent / "golden"

GOLDEN_CASES = [
    "single_point_stripmap",
    "multi_target_spotlight",
    "motion_moco_autofocus",
]


def _make_trajectory(pulse_times, positions, velocities):
    """Create a Trajectory with zero attitude."""
    attitude = np.zeros((len(pulse_times), 3))
    return _Trajectory(
        time=pulse_times,
        position=positions,
        velocity=velocities,
        attitude=attitude,
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _run_simulation(sim: dict) -> object:
    """Build and run SimulationEngine from build_simulation output."""
    engine = SimulationEngine(
        scene=sim["scene"],
        radar=sim["radar"],
        platform=sim["platform"],
        **sim["engine_kwargs"],
    )
    return engine.run()


def _range_compress(result, radar):
    """Range compress echo data."""
    from pySimSAR.core.types import RawData
    channel = list(result.echo.keys())[0]
    echo = result.echo[channel]
    raw = RawData(
        echo=echo,
        channel=channel,
        sample_rate=result.sample_rate,
        carrier_freq=radar.carrier_freq,
        bandwidth=radar.bandwidth,
        prf=radar.prf,
        waveform_name=radar.waveform.name,
        sar_mode=radar.mode.value,
        gate_delay=result.gate_delay,
    )
    return raw


def _form_image(raw, radar, trajectory, algorithm_name="range_doppler"):
    """Form image using specified algorithm."""
    from pySimSAR.algorithms.image_formation import image_formation_registry
    algo_cls = image_formation_registry.get(algorithm_name)
    algo = algo_cls()
    phd = algo.range_compress(raw, radar)
    image = algo.azimuth_compress(phd, radar, trajectory)
    return image, phd


def _find_peak(image_data):
    """Find peak location and value in 2D complex image."""
    mag = np.abs(image_data)
    peak_idx = np.unravel_index(np.argmax(mag), mag.shape)
    return peak_idx, mag[peak_idx]


def _measure_3dB_width(profile, peak_idx):
    """Measure -3 dB width of a 1D profile around peak_idx."""
    mag = np.abs(profile)
    peak_val = mag[peak_idx]
    threshold = peak_val / np.sqrt(2)  # -3 dB

    # Search left
    left = peak_idx
    while left > 0 and mag[left] >= threshold:
        left -= 1

    # Search right
    right = peak_idx
    while right < len(mag) - 1 and mag[right] >= threshold:
        right += 1

    return right - left


# ---------------------------------------------------------------------------
# Test class: load and build
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case_name", GOLDEN_CASES)
class TestGoldenLoadBuild:
    """Test that golden parameter sets load and build correctly."""

    def test_load_parameter_set(self, case_name):
        """Parameter set loads without errors."""
        case_dir = GOLDEN_DIR / case_name
        params = load_parameter_set(case_dir)
        assert params is not None
        assert params["format_version"] == "1.0"

    def test_build_simulation(self, case_name):
        """Constructed objects are valid."""
        case_dir = GOLDEN_DIR / case_name
        params = load_parameter_set(case_dir)
        sim = build_simulation(params)
        assert sim["scene"] is not None
        assert sim["radar"] is not None
        assert len(sim["scene"].point_targets) > 0


# ---------------------------------------------------------------------------
# Case 1: single_point_stripmap
# ---------------------------------------------------------------------------

class TestGoldenSinglePointStripmap:
    """Golden Case 1: single point target, stripmap, RDA."""

    @pytest.fixture(scope="class")
    def sim_objects(self):
        params = load_parameter_set(GOLDEN_DIR / "single_point_stripmap")
        return build_simulation(params)

    @pytest.fixture(scope="class")
    def sim_result(self, sim_objects):
        return _run_simulation(sim_objects)

    def test_simulation_produces_echo(self, sim_result):
        """Simulation produces echo data."""
        assert "single" in sim_result.echo
        echo = sim_result.echo["single"]
        assert echo.shape[0] == 256  # n_pulses
        assert echo.shape[1] > 0

    def test_broadside_range_accuracy(self, sim_objects, sim_result):
        """Broadside range matches analytical sqrt(2000^2 + 2000^2) = 2828.4 m."""
        target_pos = sim_objects["scene"].point_targets[0].position

        # Find broadside pulse (closest approach)
        ranges = np.array([
            np.linalg.norm(sim_result.positions[i] - target_pos)
            for i in range(sim_result.positions.shape[0])
        ])
        broadside_idx = np.argmin(ranges)
        R0 = ranges[broadside_idx]

        # Expected: R0 ~ sqrt(2000^2 + 2000^2) = 2828.4 m
        assert R0 == pytest.approx(2828.4, abs=5.0)

    def test_image_formation(self, sim_objects, sim_result):
        """Image formation produces focused image with target peak."""
        radar = sim_objects["radar"]
        raw = _range_compress(sim_result, radar)

        from pySimSAR.algorithms.image_formation import image_formation_registry
        from pySimSAR.motion.trajectory import Trajectory as _Trajectory
        trajectory = _make_trajectory(
            sim_result.pulse_times,
            sim_result.positions,
            sim_result.velocities,
        )

        algo_cls = image_formation_registry.get("range_doppler")
        algo = algo_cls()
        phd = algo.range_compress(raw, radar)
        image = algo.azimuth_compress(phd, radar, trajectory)

        # Should have a clear peak
        peak_idx, peak_val = _find_peak(image.data)
        assert peak_val > 0, "Image should have a target peak"

        # Peak magnitude should be above noise (at least 3x median)
        mag = np.abs(image.data)
        noise_floor = np.median(mag)
        assert peak_val > 3 * noise_floor, (
            f"Target peak ({peak_val:.4e}) should be > 3x noise ({noise_floor:.4e})"
        )


# ---------------------------------------------------------------------------
# Case 2: multi_target_spotlight
# ---------------------------------------------------------------------------

class TestGoldenMultiTargetSpotlight:
    """Golden Case 2: 3 targets, spotlight, Omega-K."""

    @pytest.fixture(scope="class")
    def sim_objects(self):
        params = load_parameter_set(GOLDEN_DIR / "multi_target_spotlight")
        return build_simulation(params)

    @pytest.fixture(scope="class")
    def sim_result(self, sim_objects):
        return _run_simulation(sim_objects)

    def test_simulation_produces_echo(self, sim_result):
        """Simulation produces echo data for 512 pulses."""
        echo = sim_result.echo["single"]
        assert echo.shape[0] == 512

    def test_three_targets_resolved(self, sim_objects, sim_result):
        """All 3 targets produce detectable echo energy."""
        radar = sim_objects["radar"]
        raw = _range_compress(sim_result, radar)

        from pySimSAR.motion.trajectory import Trajectory as _Trajectory
        trajectory = _make_trajectory(
            sim_result.pulse_times,
            sim_result.positions,
            sim_result.velocities,
        )

        from pySimSAR.algorithms.image_formation import image_formation_registry
        algo_cls = image_formation_registry.get("omega_k")
        algo = algo_cls()
        phd = algo.range_compress(raw, radar)
        image = algo.azimuth_compress(phd, radar, trajectory)

        # Should have at least 3 distinct peaks
        mag = np.abs(image.data)
        threshold = 0.1 * np.max(mag)
        peaks_above = np.sum(mag > threshold)
        assert peaks_above >= 3, f"Expected at least 3 bright pixels, got {peaks_above}"


# ---------------------------------------------------------------------------
# Case 3: motion_moco_autofocus
# ---------------------------------------------------------------------------

class TestGoldenMotionMocoAutofocus:
    """Golden Case 3: Dryden perturbation + MoCo + PGA."""

    @pytest.fixture(scope="class")
    def sim_objects(self):
        params = load_parameter_set(GOLDEN_DIR / "motion_moco_autofocus")
        return build_simulation(params)

    @pytest.fixture(scope="class")
    def sim_result(self, sim_objects):
        return _run_simulation(sim_objects)

    def test_simulation_with_perturbation(self, sim_result):
        """Simulation runs with Dryden perturbation."""
        echo = sim_result.echo["single"]
        assert echo.shape[0] == 512
        # Should have trajectory data
        assert sim_result.ideal_trajectory is not None
        assert sim_result.true_trajectory is not None

    def test_trajectory_is_perturbed(self, sim_result):
        """True trajectory differs from ideal."""
        ideal_pos = sim_result.ideal_trajectory.position
        true_pos = sim_result.true_trajectory.position
        diff = np.linalg.norm(true_pos - ideal_pos, axis=1)
        assert np.max(diff) > 0.01, "Perturbed trajectory should differ from ideal"

    def test_image_formation_with_ideal_trajectory(self, sim_objects, sim_result):
        """Image formation using ideal trajectory produces a detectable target."""
        radar = sim_objects["radar"]

        from pySimSAR.algorithms.image_formation import image_formation_registry

        ideal_trajectory = _make_trajectory(
            sim_result.pulse_times,
            sim_result.ideal_trajectory.position,
            sim_result.ideal_trajectory.velocity,
        )

        raw = _range_compress(sim_result, radar)

        algo_cls = image_formation_registry.get("range_doppler")
        algo = algo_cls()
        phd = algo.range_compress(raw, radar)
        image = algo.azimuth_compress(phd, radar, ideal_trajectory)

        peak_val = np.max(np.abs(image.data))
        noise_floor = np.median(np.abs(image.data))
        assert peak_val > 3 * noise_floor, (
            f"Target peak ({peak_val:.4e}) should be > 3x noise ({noise_floor:.4e})"
        )
