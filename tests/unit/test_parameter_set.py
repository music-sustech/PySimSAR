"""Unit tests for parameter set I/O (T096l-T096o)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from pySimSAR.io.parameter_set import (
    resolve_refs,
    load_parameter_set,
    build_simulation,
    save_parameter_set,
)


@pytest.fixture()
def tmp_project(tmp_path):
    """Create a minimal project directory for testing."""
    # Waveform
    waveform = {
        "type": "lfm",
        "bandwidth_hz": 150e6,
        "duty_cycle": 0.1,
        "window": None,
        "phase_noise": None,
    }
    _write(tmp_path / "waveform.json", waveform)

    # Antenna
    antenna = {
        "type": "preset",
        "preset": "flat",
        "az_beamwidth_deg": 3.0,
        "el_beamwidth_deg": 10.0,
        "peak_gain_dB": 30.0,
    }
    _write(tmp_path / "antenna.json", antenna)

    # Radar
    radar = {
        "carrier_freq_hz": 9.65e9,
        "prf_hz": 1000.0,
        "transmit_power_w": 1000.0,
        "receiver_gain_dB": 0.0,
        "noise_figure_dB": 3.0,
        "system_losses_dB": 2.0,
        "reference_temp_K": 290.0,
        "polarization": "single",
        "mode": "stripmap",
        "look_side": "right",
        "depression_angle_deg": 45.0,
        "squint_angle_deg": 0.0,
        "waveform": {"$ref": "waveform.json"},
        "antenna": {"$ref": "antenna.json"},
    }
    _write(tmp_path / "radar.json", radar)

    # Scene
    scene = {
        "origin_lat_deg": 34.05,
        "origin_lon_deg": -118.25,
        "origin_alt_m": 0.0,
        "point_targets": [
            {
                "position_m": [2000, 0, 0],
                "rcs_m2": 1.0,
                "rcs_model": {"type": "static"},
                "velocity_mps": None,
            }
        ],
    }
    _write(tmp_path / "scene.json", scene)

    # Platform
    platform = {
        "velocity_mps": 100.0,
        "altitude_m": 2000.0,
        "heading_deg": 0.0,
        "start_position_m": [0, -12.8, 2000],
        "perturbation": None,
        "sensors": None,
    }
    _write(tmp_path / "platform.json", platform)

    # Project
    project = {
        "format_version": "1.0",
        "name": "Test Project",
        "description": "Unit test project",
        "scene": {"$ref": "scene.json"},
        "radar": {"$ref": "radar.json"},
        "platform": {"$ref": "platform.json"},
        "simulation": {
            "n_pulses": 256,
            "seed": 42,
            "sample_rate_hz": None,
            "scene_center_m": None,
        },
    }
    _write(tmp_path / "project.json", project)

    return tmp_path


def _write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# T096l: resolve_refs tests
# ---------------------------------------------------------------------------

class TestResolveRefs:
    """Tests for $ref and $data resolution."""

    def test_ref_loads_json(self, tmp_path):
        """$ref loads and replaces with contents of referenced file."""
        _write(tmp_path / "child.json", {"key": "value"})
        data = {"nested": {"$ref": "child.json"}}
        result = resolve_refs(data, tmp_path)
        assert result["nested"] == {"key": "value"}

    def test_ref_recursive(self, tmp_path):
        """$ref works recursively."""
        _write(tmp_path / "grandchild.json", {"deep": 42})
        _write(tmp_path / "child.json", {"gc": {"$ref": "grandchild.json"}})
        data = {"nested": {"$ref": "child.json"}}
        result = resolve_refs(data, tmp_path)
        assert result["nested"]["gc"]["deep"] == 42

    def test_ref_sibling_keys_error(self, tmp_path):
        """$ref with sibling keys raises ValueError."""
        _write(tmp_path / "child.json", {"key": "value"})
        data = {"nested": {"$ref": "child.json", "extra": "bad"}}
        with pytest.raises(ValueError, match="sibling keys"):
            resolve_refs(data, tmp_path)

    def test_ref_circular_detection(self, tmp_path):
        """Circular $ref raises ValueError."""
        _write(tmp_path / "a.json", {"next": {"$ref": "b.json"}})
        _write(tmp_path / "b.json", {"next": {"$ref": "a.json"}})
        data = {"start": {"$ref": "a.json"}}
        with pytest.raises(ValueError, match="Circular"):
            resolve_refs(data, tmp_path)

    def test_data_npy(self, tmp_path):
        """$data loads .npy file."""
        arr = np.array([1.0, 2.0, 3.0])
        np.save(str(tmp_path / "test.npy"), arr)
        data = {"arr": {"$data": "test.npy"}}
        result = resolve_refs(data, tmp_path)
        np.testing.assert_array_equal(result["arr"], arr)

    def test_data_npz(self, tmp_path):
        """$data loads .npz file as dict."""
        a = np.array([1, 2])
        b = np.array([3, 4])
        np.savez(str(tmp_path / "test.npz"), a=a, b=b)
        data = {"arrays": {"$data": "test.npz"}}
        result = resolve_refs(data, tmp_path)
        assert isinstance(result["arrays"], dict)
        np.testing.assert_array_equal(result["arrays"]["a"], a)
        np.testing.assert_array_equal(result["arrays"]["b"], b)

    def test_data_csv(self, tmp_path):
        """$data loads .csv file."""
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        np.savetxt(str(tmp_path / "test.csv"), arr, delimiter=",")
        data = {"table": {"$data": "test.csv"}}
        result = resolve_refs(data, tmp_path)
        np.testing.assert_array_almost_equal(result["table"], arr)

    def test_data_sibling_keys_error(self, tmp_path):
        """$data with sibling keys raises ValueError."""
        np.save(str(tmp_path / "test.npy"), np.array([1.0]))
        data = {"arr": {"$data": "test.npy", "extra": "bad"}}
        with pytest.raises(ValueError, match="sibling keys"):
            resolve_refs(data, tmp_path)

    def test_list_resolution(self, tmp_path):
        """Lists are resolved recursively."""
        _write(tmp_path / "item.json", {"v": 1})
        data = [{"$ref": "item.json"}, "plain"]
        result = resolve_refs(data, tmp_path)
        assert result[0] == {"v": 1}
        assert result[1] == "plain"


# ---------------------------------------------------------------------------
# T096m: load_parameter_set tests
# ---------------------------------------------------------------------------

class TestLoadParameterSet:
    """Tests for load_parameter_set."""

    def test_loads_from_directory(self, tmp_project):
        """Loads project.json from a directory."""
        params = load_parameter_set(tmp_project)
        assert params["format_version"] == "1.0"
        assert params["name"] == "Test Project"

    def test_loads_from_file(self, tmp_project):
        """Loads from a direct file path."""
        params = load_parameter_set(tmp_project / "project.json")
        assert params["format_version"] == "1.0"

    def test_refs_resolved(self, tmp_project):
        """$ref entries are resolved."""
        params = load_parameter_set(tmp_project)
        # Scene should be resolved
        assert "point_targets" in params["scene"]
        # Radar waveform should be resolved
        assert params["radar"]["waveform"]["type"] == "lfm"

    def test_unit_suffix_stripping(self, tmp_project):
        """Unit suffixes stripped from keys."""
        params = load_parameter_set(tmp_project)
        radar = params["radar"]
        assert "carrier_freq" in radar
        assert "carrier_freq_hz" not in radar

    def test_degree_to_radian_conversion(self, tmp_project):
        """_deg keys converted to radians (except geographic)."""
        params = load_parameter_set(tmp_project)
        radar = params["radar"]
        # depression_angle should be in radians
        assert "depression_angle" in radar
        assert radar["depression_angle"] == pytest.approx(np.radians(45.0))

    def test_geographic_coords_not_converted(self, tmp_project):
        """origin_lat_deg and origin_lon_deg stay in degrees."""
        params = load_parameter_set(tmp_project)
        scene = params["scene"]
        # These should remain as degrees (key is still origin_lat_deg)
        assert scene.get("origin_lat_deg") == 34.05 or scene.get("origin_lat") == 34.05

    def test_missing_format_version_raises(self, tmp_path):
        """Missing format_version raises ValueError."""
        _write(tmp_path / "project.json", {"name": "bad"})
        with pytest.raises(ValueError, match="format_version"):
            load_parameter_set(tmp_path)


# ---------------------------------------------------------------------------
# T096n: build_simulation tests
# ---------------------------------------------------------------------------

class TestBuildSimulation:
    """Tests for build_simulation."""

    def test_builds_all_objects(self, tmp_project):
        """build_simulation returns all required objects."""
        params = load_parameter_set(tmp_project)
        sim = build_simulation(params)
        assert sim["scene"] is not None
        assert sim["radar"] is not None
        assert sim["platform"] is not None
        assert sim["engine_kwargs"] is not None

    def test_scene_has_targets(self, tmp_project):
        """Scene contains the configured point targets."""
        params = load_parameter_set(tmp_project)
        sim = build_simulation(params)
        assert len(sim["scene"].point_targets) == 1
        np.testing.assert_array_almost_equal(
            sim["scene"].point_targets[0].position, [2000, 0, 0]
        )

    def test_radar_configured(self, tmp_project):
        """Radar has correct carrier frequency."""
        params = load_parameter_set(tmp_project)
        sim = build_simulation(params)
        assert sim["radar"].carrier_freq == pytest.approx(9.65e9)

    def test_engine_kwargs(self, tmp_project):
        """Engine kwargs contain n_pulses and seed."""
        params = load_parameter_set(tmp_project)
        sim = build_simulation(params)
        assert sim["engine_kwargs"]["n_pulses"] == 256
        assert sim["engine_kwargs"]["seed"] == 42

    def test_window_factory_hamming(self, tmp_project):
        """Window name 'hamming' resolves to callable."""
        # Modify waveform to use hamming
        wf = {"type": "lfm", "bandwidth_hz": 150e6, "duty_cycle": 0.1,
              "window": "hamming", "phase_noise": None}
        _write(tmp_project / "waveform.json", wf)
        params = load_parameter_set(tmp_project)
        sim = build_simulation(params)
        assert sim["radar"].waveform.window is not None

    def test_scansar_alias(self, tmp_project):
        """'scansar' is accepted as alias for 'scanmar'."""
        radar_json = json.loads((tmp_project / "radar.json").read_text())
        radar_json["mode"] = "scansar"
        _write(tmp_project / "radar.json", radar_json)
        params = load_parameter_set(tmp_project)
        sim = build_simulation(params)
        from pySimSAR.core.types import SARMode
        assert sim["radar"].mode == SARMode.SCANMAR


# ---------------------------------------------------------------------------
# T096o: save_parameter_set tests
# ---------------------------------------------------------------------------

class TestSaveParameterSet:
    """Tests for save_parameter_set."""

    def test_round_trip(self, tmp_project, tmp_path):
        """Save then load produces equivalent objects."""
        params = load_parameter_set(tmp_project)
        sim = build_simulation(params)

        save_dir = tmp_path / "saved_project"
        save_parameter_set(
            save_dir,
            scene=sim["scene"],
            radar=sim["radar"],
            platform=sim["platform"],
            n_pulses=sim["engine_kwargs"]["n_pulses"],
            seed=sim["engine_kwargs"]["seed"],
            name="Round-trip test",
        )

        # Reload
        params2 = load_parameter_set(save_dir)
        sim2 = build_simulation(params2)

        assert len(sim2["scene"].point_targets) == len(sim["scene"].point_targets)
        assert sim2["radar"].carrier_freq == pytest.approx(sim["radar"].carrier_freq)
        assert sim2["engine_kwargs"]["n_pulses"] == sim["engine_kwargs"]["n_pulses"]

    def test_creates_project_json(self, tmp_project, tmp_path):
        """Save creates project.json."""
        params = load_parameter_set(tmp_project)
        sim = build_simulation(params)

        save_dir = tmp_path / "output"
        save_parameter_set(
            save_dir,
            scene=sim["scene"],
            radar=sim["radar"],
            platform=sim["platform"],
            n_pulses=256,
            seed=42,
        )

        assert (save_dir / "project.json").exists()
        assert (save_dir / "scene.json").exists()
        assert (save_dir / "radar.json").exists()

    def test_inline_vs_bulk_threshold(self, tmp_path):
        """<= 20 targets: inline. > 20 targets: .npy files."""
        from pySimSAR.core.scene import PointTarget, Scene
        from pySimSAR.core.radar import Radar, create_antenna_from_preset
        from pySimSAR.waveforms.lfm import LFMWaveform

        # Create scene with 25 targets
        scene = Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=0.0)
        for i in range(25):
            scene.add_target(PointTarget(position=[i * 10, 0, 0], rcs=1.0))

        wf = LFMWaveform(bandwidth=150e6, duty_cycle=0.1)
        ant = create_antenna_from_preset("flat", np.radians(3.0), np.radians(10.0), 30.0)
        radar = Radar(
            carrier_freq=9.65e9, prf=1000.0, transmit_power=1000.0,
            waveform=wf, antenna=ant, polarization="single",
            mode="stripmap", look_side="right", depression_angle=np.radians(45.0),
        )

        save_dir = tmp_path / "bulk"
        save_parameter_set(
            save_dir, scene=scene, radar=radar, platform=None,
            n_pulses=256, seed=42,
        )

        # Should have .npy files for bulk targets
        assert (save_dir / "scene_point_targets_positions.npy").exists()
        assert (save_dir / "scene_point_targets_rcs.npy").exists()

    def test_processing_config_saved(self, tmp_project, tmp_path):
        """Processing config is saved when provided."""
        from pySimSAR.io.config import ProcessingConfig
        params = load_parameter_set(tmp_project)
        sim = build_simulation(params)

        pc = ProcessingConfig(
            image_formation="range_doppler",
            moco="first_order",
            autofocus="pga",
        )

        save_dir = tmp_path / "with_proc"
        save_parameter_set(
            save_dir,
            scene=sim["scene"],
            radar=sim["radar"],
            platform=sim["platform"],
            n_pulses=256,
            seed=42,
            processing_config=pc,
        )

        assert (save_dir / "processing.json").exists()
        project = json.loads((save_dir / "project.json").read_text())
        assert "processing" in project
