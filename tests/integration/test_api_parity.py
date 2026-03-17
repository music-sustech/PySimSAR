"""T132 – API parity: every GUI action has a Python API equivalent (FR-013).

Validates that configure, run, visualize, import, save/load operations
are all accessible programmatically without any GUI dependency.
"""

from __future__ import annotations

import numpy as np
import pytest

from pySimSAR.core.scene import Scene, PointTarget
from pySimSAR.core.radar import Radar, create_antenna_from_preset
from pySimSAR.core.platform import Platform
from pySimSAR.core.types import RawData, SARImage
from pySimSAR.io.config import ProcessingConfig, SimulationConfig
from pySimSAR.io.hdf5_format import write_hdf5, read_hdf5, import_data
from pySimSAR.simulation.engine import SimulationEngine
from pySimSAR.pipeline.runner import PipelineRunner
from pySimSAR.waveforms.lfm import LFMWaveform
from pySimSAR.motion.trajectory import Trajectory


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture()
def bandwidth():
    return 50e6


@pytest.fixture()
def waveform(bandwidth):
    return LFMWaveform(bandwidth=bandwidth, duty_cycle=0.1)


@pytest.fixture()
def antenna():
    return create_antenna_from_preset(
        "flat",
        az_beamwidth=np.radians(3.0),
        el_beamwidth=np.radians(5.0),
        peak_gain_dB=30.0,
    )


@pytest.fixture()
def scene():
    s = Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=0.0)
    s.add_target(PointTarget(position=np.array([0.0, 0.0, 0.0]), rcs=1.0))
    s.add_target(PointTarget(position=np.array([100.0, 0.0, 0.0]), rcs=10.0))
    return s


@pytest.fixture()
def radar(waveform, antenna):
    return Radar(
        carrier_freq=9.65e9,
        prf=500.0,
        transmit_power=1000.0,
        waveform=waveform,
        antenna=antenna,
        polarization="single",
        mode="stripmap",
        look_side="right",
        depression_angle=np.radians(45.0),
    )


@pytest.fixture()
def sim_result(scene, radar, bandwidth):
    engine = SimulationEngine(
        scene=scene,
        radar=radar,
        n_pulses=64,
        platform_start=np.array([0.0, -5000.0, 2000.0]),
        platform_velocity=np.array([0.0, 100.0, 0.0]),
        seed=42,
        sample_rate=2 * bandwidth,
    )
    return engine.run()


# --------------------------------------------------------------------------
# 1. Configure — all configuration objects can be created programmatically
# --------------------------------------------------------------------------

class TestConfigureAPI:
    """GUI action: configure scene, radar, platform, processing."""

    def test_scene_creation(self):
        scene = Scene(origin_lat=34.0, origin_lon=-118.0, origin_alt=100.0)
        scene.add_target(PointTarget(
            position=np.array([50.0, 50.0, 0.0]), rcs=5.0,
        ))
        assert len(scene.point_targets) == 1
        assert scene.origin_lat == 34.0

    def test_radar_creation(self, waveform, antenna):
        radar = Radar(
            carrier_freq=5.4e9,
            prf=1000.0,
            transmit_power=500.0,
            waveform=waveform,
            antenna=antenna,
            polarization="single",
            mode="stripmap",
            look_side="left",
            depression_angle=np.radians(30.0),
        )
        assert radar.carrier_freq == 5.4e9
        assert radar.bandwidth == waveform.bandwidth

    def test_platform_creation(self):
        platform = Platform(velocity=100.0, altitude=5000.0, heading=0.0)
        assert platform.velocity == 100.0
        assert platform.altitude == 5000.0

    def test_processing_config_creation(self):
        config = ProcessingConfig(
            image_formation="range_doppler",
            moco=None,
            autofocus=None,
        )
        assert config.image_formation == "range_doppler"

    def test_simulation_config_creation(self, scene, radar):
        sim_cfg = SimulationConfig(
            scene=scene, radar=radar, n_pulses=128, seed=0,
            description="API parity test",
        )
        assert sim_cfg.n_pulses == 128
        assert sim_cfg.seed == 0
        assert sim_cfg.description == "API parity test"


# --------------------------------------------------------------------------
# 2. Run simulation — SimulationEngine.run() programmatic access
# --------------------------------------------------------------------------

class TestRunSimulationAPI:
    """GUI action: run a simulation to produce raw echo data."""

    def test_simulation_engine_run(self, sim_result):
        assert "single" in sim_result.echo
        echo = sim_result.echo["single"]
        assert echo.ndim == 2
        assert echo.shape[0] == 64  # n_pulses
        assert echo.dtype == complex

    def test_simulation_result_has_positions(self, sim_result):
        assert sim_result.positions.shape == (64, 3)
        assert sim_result.velocities.shape == (64, 3)
        assert sim_result.pulse_times.shape == (64,)

    def test_simulation_result_has_gate_delay(self, sim_result):
        assert isinstance(sim_result.gate_delay, float)
        assert sim_result.gate_delay >= 0.0

    def test_simulation_with_platform(self, scene, radar):
        platform = Platform(velocity=100.0, altitude=3000.0, heading=0.0)
        engine = SimulationEngine(
            scene=scene, radar=radar, n_pulses=32, platform=platform, seed=7,
        )
        result = engine.run()
        assert "single" in result.echo
        assert result.echo["single"].shape[0] == 32


# --------------------------------------------------------------------------
# 3. Run pipeline — PipelineRunner.run() programmatic access
# --------------------------------------------------------------------------

class TestRunPipelineAPI:
    """GUI action: process raw data through the imaging pipeline."""

    def test_pipeline_runner(self, sim_result, radar):
        config = ProcessingConfig(image_formation="range_doppler")
        runner = PipelineRunner(config)

        # Build RawData dict from simulation result
        raw_data = {}
        for ch, echo in sim_result.echo.items():
            raw_data[ch] = RawData(
                echo=echo,
                channel=ch,
                sample_rate=sim_result.sample_rate,
                carrier_freq=radar.carrier_freq,
                bandwidth=radar.bandwidth,
                prf=radar.prf,
                waveform_name=radar.waveform.name,
                sar_mode="stripmap",
                gate_delay=sim_result.gate_delay,
            )

        # Build a simple trajectory for the pipeline
        traj = Trajectory(
            time=sim_result.pulse_times,
            position=sim_result.positions,
            velocity=sim_result.velocities,
            attitude=np.zeros((64, 3)),
        )

        result = runner.run(raw_data, radar=radar, trajectory=traj)
        assert "single" in result.images
        img = result.images["single"]
        assert isinstance(img, SARImage)
        assert img.data.ndim == 2
        assert "image_formation" in result.steps_applied[0]


# --------------------------------------------------------------------------
# 4. Import — import_data() programmatic access
# --------------------------------------------------------------------------

class TestImportAPI:
    """GUI action: import an existing HDF5 file for processing."""

    def test_import_data(self, tmp_path, sim_result, radar):
        filepath = tmp_path / "import_test.h5"
        sim_result.save(str(filepath), radar=radar)

        imported = import_data(str(filepath))
        assert "raw_data" in imported
        assert len(imported["raw_data"]) > 0
        assert "radar_params" in imported

        first_rd = next(iter(imported["raw_data"].values()))
        assert isinstance(first_rd, RawData)
        assert first_rd.carrier_freq == radar.carrier_freq

    def test_import_no_raw_data_raises(self, tmp_path):
        filepath = tmp_path / "empty.h5"
        # Write file with only an image, no raw data
        img = SARImage(
            data=np.zeros((10, 10), dtype=complex),
            pixel_spacing_range=1.0,
            pixel_spacing_azimuth=1.0,
        )
        write_hdf5(str(filepath), images={"test": img})
        with pytest.raises(ValueError, match="No raw data"):
            import_data(str(filepath))


# --------------------------------------------------------------------------
# 5. Save / Load — write_hdf5 / read_hdf5 round-trip
# --------------------------------------------------------------------------

class TestSaveLoadAPI:
    """GUI action: save results and reload them."""

    def test_raw_data_round_trip(self, tmp_path, sim_result, radar):
        filepath = tmp_path / "roundtrip_raw.h5"
        sim_result.save(str(filepath), radar=radar)

        loaded = read_hdf5(str(filepath))
        assert "single" in loaded["raw_data"]
        rd = loaded["raw_data"]["single"]
        original = sim_result.echo["single"]
        np.testing.assert_array_equal(rd.echo, original)
        assert rd.carrier_freq == radar.carrier_freq
        assert rd.bandwidth == radar.bandwidth
        assert rd.prf == radar.prf

    def test_image_round_trip(self, tmp_path):
        filepath = tmp_path / "roundtrip_img.h5"
        original_data = np.random.default_rng(0).standard_normal((32, 64)) + \
            1j * np.random.default_rng(1).standard_normal((32, 64))
        img = SARImage(
            data=original_data,
            pixel_spacing_range=0.5,
            pixel_spacing_azimuth=1.0,
            algorithm="range_doppler",
            geometry="slant_range",
            channel="single",
        )
        write_hdf5(str(filepath), images={"focused": img})

        loaded = read_hdf5(str(filepath))
        assert "focused" in loaded["images"]
        loaded_img = loaded["images"]["focused"]
        np.testing.assert_array_equal(loaded_img.data, original_data)
        assert loaded_img.pixel_spacing_range == 0.5
        assert loaded_img.pixel_spacing_azimuth == 1.0
        assert loaded_img.algorithm == "range_doppler"

    def test_raw_data_save_load_convenience(self, tmp_path, sim_result, radar):
        """RawData.save() / RawData.load() convenience methods."""
        filepath = tmp_path / "convenience_raw.h5"
        rd = RawData(
            echo=sim_result.echo["single"],
            channel="single",
            sample_rate=sim_result.sample_rate,
            carrier_freq=radar.carrier_freq,
            bandwidth=radar.bandwidth,
            prf=radar.prf,
            waveform_name="lfm",
            sar_mode="stripmap",
        )
        rd.save(str(filepath))
        loaded = RawData.load(str(filepath), channel="single")
        np.testing.assert_array_equal(loaded.echo, rd.echo)

    def test_sar_image_save_load_convenience(self, tmp_path):
        """SARImage.save() / SARImage.load() convenience methods."""
        filepath = tmp_path / "convenience_img.h5"
        data = np.ones((8, 8), dtype=complex)
        img = SARImage(data=data, pixel_spacing_range=1.0, pixel_spacing_azimuth=1.0)
        img.save(str(filepath), name="my_image")
        loaded = SARImage.load(str(filepath), name="my_image")
        np.testing.assert_array_equal(loaded.data, data)


# --------------------------------------------------------------------------
# 6. Visualize (data access) — image data accessible for custom plotting
# --------------------------------------------------------------------------

class TestVisualizeDataAccessAPI:
    """GUI action: visualize a SAR image.

    The Python API equivalent is direct access to SARImage.data and
    metadata, enabling any custom matplotlib / other visualization.
    """

    def test_sar_image_data_access(self):
        data = np.random.default_rng(99).standard_normal((16, 16)) + \
            1j * np.random.default_rng(100).standard_normal((16, 16))
        img = SARImage(
            data=data,
            pixel_spacing_range=0.75,
            pixel_spacing_azimuth=1.5,
            geometry="slant_range",
            algorithm="omega_k",
            channel="hh",
        )

        # Amplitude image (what a GUI would display)
        amplitude = np.abs(img.data)
        assert amplitude.shape == (16, 16)
        assert amplitude.dtype == np.float64

        # Phase image
        phase = np.angle(img.data)
        assert phase.shape == (16, 16)

        # dB scale
        amplitude_db = 20 * np.log10(amplitude + 1e-30)
        assert np.all(np.isfinite(amplitude_db))

        # Metadata for axis labeling
        assert img.pixel_spacing_range == 0.75
        assert img.pixel_spacing_azimuth == 1.5
        assert img.geometry == "slant_range"
        assert img.channel == "hh"

    def test_pipeline_result_images_are_accessible(self, sim_result, radar):
        """Pipeline output images expose .data for visualization."""
        config = ProcessingConfig(image_formation="range_doppler")
        runner = PipelineRunner(config)

        raw_data = {}
        for ch, echo in sim_result.echo.items():
            raw_data[ch] = RawData(
                echo=echo,
                channel=ch,
                sample_rate=sim_result.sample_rate,
                carrier_freq=radar.carrier_freq,
                bandwidth=radar.bandwidth,
                prf=radar.prf,
                waveform_name=radar.waveform.name,
                sar_mode="stripmap",
                gate_delay=sim_result.gate_delay,
            )

        traj = Trajectory(
            time=sim_result.pulse_times,
            position=sim_result.positions,
            velocity=sim_result.velocities,
            attitude=np.zeros((64, 3)),
        )

        result = runner.run(raw_data, radar=radar, trajectory=traj)
        for ch, img in result.images.items():
            # All data needed for visualization is available
            assert img.data.ndim == 2
            assert img.pixel_spacing_range > 0
            assert img.pixel_spacing_azimuth > 0
            assert isinstance(img.geometry, str)
            assert isinstance(img.algorithm, str)
