"""Contract test for HDF5 data format (T065).

Verifies SC-004: saving and reloading any data type produces
identical arrays (byte-for-byte via np.array_equal).
"""

from __future__ import annotations

import numpy as np
import pytest

from pySimSAR.core.types import RawData, SARImage
from pySimSAR.io.hdf5_format import read_hdf5, write_hdf5
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.sensors.nav_data import NavigationData


@pytest.fixture
def tmp_h5(tmp_path):
    return str(tmp_path / "contract_test.h5")


class TestDataFormatContract:
    """SC-004: Bit-exact round-trip fidelity for all data types."""

    def test_raw_data_bit_exact(self, tmp_h5):
        """RawData echo matrix is bit-exact after round-trip."""
        rng = np.random.default_rng(100)
        echo = (rng.standard_normal((128, 256)) + 1j * rng.standard_normal((128, 256))).astype(np.complex128)

        rd = RawData(
            echo=echo, channel="single", sample_rate=2e6,
            carrier_freq=9.6e9, bandwidth=100e6, prf=1000.0,
            waveform_name="LFM", sar_mode="stripmap",
        )
        write_hdf5(tmp_h5, raw_data={"single": rd})
        loaded = read_hdf5(tmp_h5)["raw_data"]["single"]
        assert np.array_equal(loaded.echo, echo), "RawData echo not bit-exact"

    def test_trajectory_bit_exact(self, tmp_h5):
        """Trajectory arrays are bit-exact after round-trip."""
        n = 100
        time = np.linspace(0, 2.0, n)
        pos = np.random.default_rng(1).standard_normal((n, 3))
        vel = np.random.default_rng(2).standard_normal((n, 3))
        att = np.random.default_rng(3).standard_normal((n, 3))

        traj = Trajectory(time=time, position=pos, velocity=vel, attitude=att)
        write_hdf5(tmp_h5, trajectory=traj)
        loaded = read_hdf5(tmp_h5)["trajectory"]

        assert np.array_equal(loaded.time, time)
        assert np.array_equal(loaded.position, pos)
        assert np.array_equal(loaded.velocity, vel)
        assert np.array_equal(loaded.attitude, att)

    def test_navigation_data_bit_exact(self, tmp_h5):
        """NavigationData arrays are bit-exact after round-trip."""
        n = 50
        rng = np.random.default_rng(42)
        time = np.linspace(0, 1.0, n)
        position = rng.standard_normal((n, 3))
        velocity = rng.standard_normal((n, 3))

        nav = NavigationData(
            time=time, position=position, velocity=velocity, source="gps"
        )
        write_hdf5(tmp_h5, navigation_data=[nav])
        loaded = read_hdf5(tmp_h5)["navigation_data"][0]

        assert np.array_equal(loaded.time, time)
        assert np.array_equal(loaded.position, position)
        assert np.array_equal(loaded.velocity, velocity)

    def test_sar_image_bit_exact(self, tmp_h5):
        """SARImage data is bit-exact after round-trip."""
        rng = np.random.default_rng(77)
        data = (rng.standard_normal((64, 128)) + 1j * rng.standard_normal((64, 128))).astype(np.complex64)

        img = SARImage(
            data=data, pixel_spacing_range=0.5, pixel_spacing_azimuth=0.3,
            geometry="slant_range", algorithm="range_doppler", channel="hh",
        )
        write_hdf5(tmp_h5, images={"test": img})
        loaded = read_hdf5(tmp_h5)["images"]["test"]

        assert np.array_equal(loaded.data, data), "SARImage data not bit-exact"
        assert loaded.data.dtype == np.complex64

    def test_full_file_roundtrip(self, tmp_h5):
        """All data types stored together and round-tripped bit-exactly."""
        rng = np.random.default_rng(999)
        n = 64

        # RawData
        echo = (rng.standard_normal((n, 128)) + 1j * rng.standard_normal((n, 128))).astype(np.complex64)
        rd = RawData(
            echo=echo, channel="hh", sample_rate=2e6,
            carrier_freq=9.6e9, bandwidth=100e6, prf=1000.0,
            waveform_name="LFM", sar_mode="stripmap",
        )

        # Trajectory
        time = np.linspace(0, 1.0, n)
        pos = rng.standard_normal((n, 3))
        vel = rng.standard_normal((n, 3))
        att = rng.standard_normal((n, 3))
        traj = Trajectory(time=time, position=pos, velocity=vel, attitude=att)

        # NavigationData
        gps = NavigationData(
            time=np.linspace(0, 1.0, 20),
            position=rng.standard_normal((20, 3)),
            source="gps",
        )

        # SARImage
        img_data = rng.standard_normal((32, 64)).astype(np.float32)
        img = SARImage(
            data=img_data, pixel_spacing_range=1.0, pixel_spacing_azimuth=1.0,
            geometry="ground_range", algorithm="chirp_scaling", channel="hh",
        )

        # Write everything
        write_hdf5(
            tmp_h5,
            raw_data={"hh": rd},
            trajectory=traj,
            navigation_data=[gps],
            images={"focused": img},
            simulation_config_json='{"test": true}',
            origin_lat=40.0, origin_lon=-74.0, origin_alt=50.0,
        )

        # Read and verify
        result = read_hdf5(tmp_h5)
        assert np.array_equal(result["raw_data"]["hh"].echo, echo)
        assert np.array_equal(result["trajectory"].time, time)
        assert np.array_equal(result["trajectory"].position, pos)
        assert len(result["navigation_data"]) == 1
        assert np.array_equal(result["images"]["focused"].data, img_data)
        assert result["config"]["simulation_config"] == '{"test": true}'
        assert result["metadata"]["origin_lat"] == 40.0

    def test_metadata_completeness(self, tmp_h5):
        """HDF5 file contains all required metadata attributes."""
        write_hdf5(
            tmp_h5,
            origin_lat=35.0, origin_lon=139.0, origin_alt=10.0,
        )
        result = read_hdf5(tmp_h5)
        meta = result["metadata"]

        required = [
            "software_version", "creation_date",
            "coordinate_system", "origin_lat", "origin_lon", "origin_alt",
        ]
        for key in required:
            assert key in meta, f"Missing metadata: {key}"
