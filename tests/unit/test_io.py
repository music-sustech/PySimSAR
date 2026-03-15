"""Unit tests for HDF5 I/O and JSON config serialization (T061-T064)."""

from __future__ import annotations

import json
import os
import tempfile

import numpy as np
import pytest

from pySimSAR.core.types import RawData, PhaseHistoryData, SARImage
from pySimSAR.io.hdf5_format import write_hdf5, read_hdf5
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.sensors.nav_data import NavigationData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_h5(tmp_path):
    """Return a temporary HDF5 file path."""
    return str(tmp_path / "test_data.h5")


@pytest.fixture
def sample_raw_data():
    """Create sample RawData for testing."""
    rng = np.random.default_rng(42)
    echo = rng.standard_normal((64, 128)) + 1j * rng.standard_normal((64, 128))
    return RawData(
        echo=echo.astype(np.complex64),
        channel="hh",
        sample_rate=2e6,
        carrier_freq=9.6e9,
        bandwidth=100e6,
        prf=1000.0,
        waveform_name="LFM",
        sar_mode="stripmap",
    )


@pytest.fixture
def sample_trajectory():
    """Create sample Trajectory for testing."""
    n = 50
    time = np.linspace(0, 1.0, n)
    position = np.column_stack([
        np.zeros(n),
        np.linspace(0, 100, n),
        np.full(n, 2000.0),
    ])
    velocity = np.column_stack([
        np.zeros(n),
        np.full(n, 100.0),
        np.zeros(n),
    ])
    attitude = np.zeros((n, 3))
    return Trajectory(time=time, position=position, velocity=velocity, attitude=attitude)


@pytest.fixture
def sample_gps_nav():
    """Create sample GPS NavigationData."""
    n = 20
    time = np.linspace(0, 1.0, n)
    position = np.column_stack([
        np.zeros(n),
        np.linspace(0, 100, n),
        np.full(n, 2000.0),
    ])
    return NavigationData(time=time, position=position, source="gps")


@pytest.fixture
def sample_imu_nav():
    """Create sample IMU NavigationData."""
    n = 100
    time = np.linspace(0, 1.0, n)
    acceleration = np.random.default_rng(1).standard_normal((n, 3))
    angular_rate = np.random.default_rng(2).standard_normal((n, 3))
    return NavigationData(
        time=time, acceleration=acceleration, angular_rate=angular_rate, source="imu"
    )


@pytest.fixture
def sample_image():
    """Create sample SARImage for testing."""
    rng = np.random.default_rng(99)
    data = rng.standard_normal((32, 64)) + 1j * rng.standard_normal((32, 64))
    return SARImage(
        data=data.astype(np.complex64),
        pixel_spacing_range=0.5,
        pixel_spacing_azimuth=0.3,
        geometry="slant_range",
        algorithm="range_doppler",
        channel="hh",
    )


# ---------------------------------------------------------------------------
# T061: HDF5 write/read of RawData
# ---------------------------------------------------------------------------


class TestHDF5RawData:
    """Test HDF5 round-trip of RawData."""

    def test_single_channel_roundtrip(self, tmp_h5, sample_raw_data):
        """Single channel echo data survives HDF5 round-trip bit-exactly."""
        write_hdf5(tmp_h5, raw_data={"hh": sample_raw_data})
        result = read_hdf5(tmp_h5)

        assert "hh" in result["raw_data"]
        loaded = result["raw_data"]["hh"]
        assert np.array_equal(loaded.echo, sample_raw_data.echo)
        assert loaded.channel == sample_raw_data.channel
        assert loaded.sample_rate == sample_raw_data.sample_rate
        assert loaded.carrier_freq == sample_raw_data.carrier_freq
        assert loaded.bandwidth == sample_raw_data.bandwidth
        assert loaded.prf == sample_raw_data.prf
        assert loaded.waveform_name == sample_raw_data.waveform_name
        assert loaded.sar_mode == sample_raw_data.sar_mode

    def test_multi_channel_roundtrip(self, tmp_h5):
        """Quad-pol channels all round-trip correctly."""
        rng = np.random.default_rng(7)
        channels = {}
        for ch in ["hh", "hv", "vh", "vv"]:
            echo = rng.standard_normal((32, 64)) + 1j * rng.standard_normal((32, 64))
            channels[ch] = RawData(
                echo=echo.astype(np.complex128),
                channel=ch,
                sample_rate=4e6,
                carrier_freq=5.3e9,
                bandwidth=50e6,
                prf=500.0,
                waveform_name="FMCW",
                sar_mode="spotlight",
            )

        write_hdf5(tmp_h5, raw_data=channels)
        result = read_hdf5(tmp_h5)

        assert len(result["raw_data"]) == 4
        for ch in ["hh", "hv", "vh", "vv"]:
            assert np.array_equal(result["raw_data"][ch].echo, channels[ch].echo)

    def test_complex64_preserved(self, tmp_h5, sample_raw_data):
        """Complex64 dtype is preserved through round-trip."""
        assert sample_raw_data.echo.dtype == np.complex64
        write_hdf5(tmp_h5, raw_data={"hh": sample_raw_data})
        result = read_hdf5(tmp_h5)
        assert result["raw_data"]["hh"].echo.dtype == np.complex64


# ---------------------------------------------------------------------------
# T062: HDF5 write/read of NavigationData and Trajectory
# ---------------------------------------------------------------------------


class TestHDF5Navigation:
    """Test HDF5 round-trip of Trajectory and NavigationData."""

    def test_trajectory_roundtrip(self, tmp_h5, sample_trajectory):
        """Trajectory arrays round-trip bit-exactly."""
        write_hdf5(tmp_h5, trajectory=sample_trajectory)
        result = read_hdf5(tmp_h5)

        loaded = result["trajectory"]
        assert loaded is not None
        assert np.array_equal(loaded.time, sample_trajectory.time)
        assert np.array_equal(loaded.position, sample_trajectory.position)
        assert np.array_equal(loaded.velocity, sample_trajectory.velocity)
        assert np.array_equal(loaded.attitude, sample_trajectory.attitude)

    def test_gps_nav_roundtrip(self, tmp_h5, sample_gps_nav):
        """GPS NavigationData round-trips correctly."""
        write_hdf5(tmp_h5, navigation_data=[sample_gps_nav])
        result = read_hdf5(tmp_h5)

        assert len(result["navigation_data"]) == 1
        loaded = result["navigation_data"][0]
        assert loaded.source == "gps"
        assert np.array_equal(loaded.time, sample_gps_nav.time)
        assert np.array_equal(loaded.position, sample_gps_nav.position)
        assert loaded.acceleration is None

    def test_imu_nav_roundtrip(self, tmp_h5, sample_imu_nav):
        """IMU NavigationData round-trips correctly."""
        write_hdf5(tmp_h5, navigation_data=[sample_imu_nav])
        result = read_hdf5(tmp_h5)

        assert len(result["navigation_data"]) == 1
        loaded = result["navigation_data"][0]
        assert loaded.source == "imu"
        assert np.array_equal(loaded.time, sample_imu_nav.time)
        assert np.array_equal(loaded.acceleration, sample_imu_nav.acceleration)
        assert np.array_equal(loaded.angular_rate, sample_imu_nav.angular_rate)
        assert loaded.position is None

    def test_combined_nav_roundtrip(
        self, tmp_h5, sample_trajectory, sample_gps_nav, sample_imu_nav
    ):
        """Trajectory + GPS + IMU all stored and loaded together."""
        write_hdf5(
            tmp_h5,
            trajectory=sample_trajectory,
            navigation_data=[sample_gps_nav, sample_imu_nav],
        )
        result = read_hdf5(tmp_h5)

        assert result["trajectory"] is not None
        assert len(result["navigation_data"]) == 2
        sources = {nav.source for nav in result["navigation_data"]}
        assert sources == {"gps", "imu"}


# ---------------------------------------------------------------------------
# T063: HDF5 write/read of SARImage
# ---------------------------------------------------------------------------


class TestHDF5SARImage:
    """Test HDF5 round-trip of SARImage."""

    def test_image_roundtrip(self, tmp_h5, sample_image):
        """SARImage round-trips bit-exactly."""
        write_hdf5(tmp_h5, images={"rda_stripmap": sample_image})
        result = read_hdf5(tmp_h5)

        assert "rda_stripmap" in result["images"]
        loaded = result["images"]["rda_stripmap"]
        assert np.array_equal(loaded.data, sample_image.data)
        assert loaded.pixel_spacing_range == sample_image.pixel_spacing_range
        assert loaded.pixel_spacing_azimuth == sample_image.pixel_spacing_azimuth
        assert loaded.geometry == sample_image.geometry
        assert loaded.algorithm == sample_image.algorithm
        assert loaded.channel == sample_image.channel

    def test_image_with_geotransform(self, tmp_h5):
        """SARImage with geo_transform and projection_wkt round-trips."""
        img = SARImage(
            data=np.ones((10, 10), dtype=np.float32),
            pixel_spacing_range=1.0,
            pixel_spacing_azimuth=1.0,
            geometry="geographic",
            algorithm="omega_k",
            channel="single",
            geo_transform=np.array([0.0, 1.0, 0.0, 50.0, 0.0, -1.0]),
            projection_wkt='GEOGCS["WGS 84"]',
        )
        write_hdf5(tmp_h5, images={"geo_image": img})
        result = read_hdf5(tmp_h5)

        loaded = result["images"]["geo_image"]
        assert np.array_equal(loaded.data, img.data)
        assert np.array_equal(loaded.geo_transform, img.geo_transform)
        assert loaded.projection_wkt == img.projection_wkt

    def test_multiple_images(self, tmp_h5, sample_image):
        """Multiple images stored and loaded correctly."""
        img2 = SARImage(
            data=np.zeros((16, 32), dtype=np.float32),
            pixel_spacing_range=1.0,
            pixel_spacing_azimuth=1.5,
            geometry="ground_range",
            algorithm="chirp_scaling",
            channel="vv",
        )
        write_hdf5(tmp_h5, images={"rda": sample_image, "csa": img2})
        result = read_hdf5(tmp_h5)

        assert len(result["images"]) == 2
        assert "rda" in result["images"]
        assert "csa" in result["images"]


# ---------------------------------------------------------------------------
# T064: SimulationConfig and ProcessingConfig JSON serialization
# ---------------------------------------------------------------------------


class TestConfigSerialization:
    """Test JSON serialization of configs."""

    def test_processing_config_roundtrip(self):
        """ProcessingConfig serializes to JSON and deserializes back."""
        from pySimSAR.io.config import ProcessingConfig

        pc = ProcessingConfig(
            image_formation="range_doppler",
            moco="first_order",
            autofocus="pga",
            geocoding="slant_to_ground",
            polarimetric_decomposition="pauli",
            description="Test processing run",
        )
        json_str = pc.to_json()
        loaded = ProcessingConfig.from_json(json_str)

        assert loaded.image_formation == "range_doppler"
        assert loaded.moco == "first_order"
        assert loaded.autofocus == "pga"
        assert loaded.geocoding == "slant_to_ground"
        assert loaded.polarimetric_decomposition == "pauli"
        assert loaded.description == "Test processing run"

    def test_processing_config_optional_fields(self):
        """ProcessingConfig with optional fields set to None."""
        from pySimSAR.io.config import ProcessingConfig

        pc = ProcessingConfig(image_formation="omega_k")
        json_str = pc.to_json()
        loaded = ProcessingConfig.from_json(json_str)

        assert loaded.image_formation == "omega_k"
        assert loaded.moco is None
        assert loaded.autofocus is None
        assert loaded.geocoding is None
        assert loaded.polarimetric_decomposition is None

    def test_processing_config_requires_image_formation(self):
        """ProcessingConfig raises if image_formation is empty."""
        from pySimSAR.io.config import ProcessingConfig

        with pytest.raises(ValueError, match="image_formation"):
            ProcessingConfig(image_formation="")

    def test_simulation_config_to_json(self):
        """SimulationConfig serializes to valid JSON."""
        from pySimSAR.io.config import SimulationConfig
        from pySimSAR.core.scene import Scene
        from pySimSAR.core.radar import Radar, AntennaPattern
        from pySimSAR.waveforms.lfm import LFMWaveform

        scene = Scene(origin_lat=40.0, origin_lon=-74.0, origin_alt=0.0)
        wf = LFMWaveform(bandwidth=100e6, duty_cycle=0.1)

        def sinc_pattern(az, el):
            return 30.0

        antenna = AntennaPattern(
            pattern_2d=sinc_pattern,
            az_beamwidth=0.05, el_beamwidth=0.17, peak_gain_dB=30.0,
        )
        radar = Radar(
            carrier_freq=9.6e9, prf=1000.0, transmit_power=1000.0, antenna=antenna,
            waveform=wf, polarization="single", mode="stripmap",
            look_side="right", depression_angle=0.7,
        )
        cfg = SimulationConfig(
            scene=scene, radar=radar, n_pulses=256, seed=42,
            description="Test run",
        )
        json_str = cfg.to_json()
        data = json.loads(json_str)

        assert data["n_pulses"] == 256
        assert data["seed"] == 42
        assert data["description"] == "Test run"
        assert data["radar"]["carrier_freq"] == 9.6e9
        assert data["radar"]["waveform"] == "lfm"
        assert data["scene"]["origin_lat"] == 40.0
        assert data["scene"]["n_point_targets"] == 0

    def test_simulation_config_from_json(self):
        """SimulationConfig.from_json returns a dict."""
        from pySimSAR.io.config import SimulationConfig

        json_str = '{"n_pulses": 128, "seed": 7}'
        result = SimulationConfig.from_json(json_str)
        assert result["n_pulses"] == 128
        assert result["seed"] == 7

    def test_config_stored_in_hdf5(self, tmp_h5):
        """Config JSON strings are stored/loaded from HDF5."""
        from pySimSAR.io.config import ProcessingConfig

        pc = ProcessingConfig(image_formation="range_doppler")
        sim_json = '{"n_pulses": 256, "seed": 42}'

        write_hdf5(
            tmp_h5,
            simulation_config_json=sim_json,
            processing_config_json=pc.to_json(),
        )
        result = read_hdf5(tmp_h5)

        assert result["config"]["simulation_config"] == sim_json
        loaded_pc = ProcessingConfig.from_json(result["config"]["processing_config"])
        assert loaded_pc.image_formation == "range_doppler"


# ---------------------------------------------------------------------------
# Metadata tests
# ---------------------------------------------------------------------------


class TestHDF5Metadata:
    """Test metadata attributes in HDF5 files."""

    def test_metadata_written(self, tmp_h5):
        """Metadata group has required attributes."""
        write_hdf5(
            tmp_h5,
            origin_lat=40.0,
            origin_lon=-74.0,
            origin_alt=100.0,
        )
        result = read_hdf5(tmp_h5)

        meta = result["metadata"]
        assert "software_version" in meta
        assert "creation_date" in meta
        assert meta["coordinate_system"] == "ENU"
        assert meta["origin_lat"] == 40.0
        assert meta["origin_lon"] == -74.0
        assert meta["origin_alt"] == 100.0

    def test_empty_file_reads(self, tmp_h5):
        """An HDF5 file with only metadata reads without error."""
        write_hdf5(tmp_h5)
        result = read_hdf5(tmp_h5)

        assert result["raw_data"] == {}
        assert result["trajectory"] is None
        assert result["navigation_data"] == []
        assert result["images"] == {}


# ---------------------------------------------------------------------------
# T074: Convenience save/load methods
# ---------------------------------------------------------------------------


class TestConvenienceMethods:
    """Test save/load methods on RawData, SARImage, and SimulationResult."""

    def test_raw_data_save_load(self, tmp_h5, sample_raw_data):
        """RawData.save/load round-trips correctly."""
        sample_raw_data.save(tmp_h5)
        loaded = RawData.load(tmp_h5, channel="hh")
        assert np.array_equal(loaded.echo, sample_raw_data.echo)
        assert loaded.channel == "hh"

    def test_raw_data_load_first_channel(self, tmp_h5, sample_raw_data):
        """RawData.load without channel returns first channel."""
        sample_raw_data.save(tmp_h5)
        loaded = RawData.load(tmp_h5)
        assert np.array_equal(loaded.echo, sample_raw_data.echo)

    def test_raw_data_load_missing_channel(self, tmp_h5, sample_raw_data):
        """RawData.load raises KeyError for missing channel."""
        sample_raw_data.save(tmp_h5)
        with pytest.raises(KeyError):
            RawData.load(tmp_h5, channel="vv")

    def test_sar_image_save_load(self, tmp_h5, sample_image):
        """SARImage.save/load round-trips correctly."""
        sample_image.save(tmp_h5, name="test_img")
        loaded = SARImage.load(tmp_h5, name="test_img")
        assert np.array_equal(loaded.data, sample_image.data)
        assert loaded.algorithm == sample_image.algorithm

    def test_sar_image_load_first(self, tmp_h5, sample_image):
        """SARImage.load without name returns first image."""
        sample_image.save(tmp_h5)
        loaded = SARImage.load(tmp_h5)
        assert np.array_equal(loaded.data, sample_image.data)

    def test_simulation_result_save(self, tmp_h5):
        """SimulationResult.save writes HDF5 with raw data."""
        from pySimSAR.simulation.engine import SimulationResult

        rng = np.random.default_rng(42)
        echo = rng.standard_normal((32, 64)) + 1j * rng.standard_normal((32, 64))

        result = SimulationResult(
            echo={"single": echo.astype(np.complex64)},
            sample_rate=2e6,
        )
        result.save(tmp_h5)

        loaded = read_hdf5(tmp_h5)
        assert "single" in loaded["raw_data"]
        assert np.array_equal(loaded["raw_data"]["single"].echo, echo.astype(np.complex64))
