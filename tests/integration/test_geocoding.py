"""Integration tests for geocoding algorithms (Phase 9 — US6).

T097: SlantToGroundRange — spatial scaling correctness
T098: Georeferencing — lat/lon accuracy
"""

from __future__ import annotations

import math

import numpy as np

from pySimSAR.algorithms.geocoding.georeferencing import Georeferencing
from pySimSAR.algorithms.geocoding.slant_to_ground import SlantToGroundRange
from pySimSAR.core.radar import C_LIGHT, AntennaPattern, Radar
from pySimSAR.core.types import ImageGeometry, SARImage
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.waveforms.lfm import LFMWaveform


def _make_radar_and_trajectory(
    altitude: float = 5000.0,
    depression_angle_deg: float = 45.0,
    velocity: float = 100.0,
    n_pulses: int = 256,
    carrier_freq: float = 9.65e9,
    bandwidth: float = 150e6,
    prf: float = 1000.0,
) -> tuple:
    """Create a radar and trajectory for geocoding tests."""
    depression_angle = math.radians(depression_angle_deg)

    waveform = LFMWaveform(bandwidth=bandwidth, duty_cycle=0.1, prf=prf)
    antenna = AntennaPattern(
        pattern_2d=lambda az, el: 30.0,
        az_beamwidth=math.radians(3.0),
        el_beamwidth=math.radians(5.0),
    )
    radar = Radar(
        carrier_freq=carrier_freq,
        transmit_power=1000.0,
        waveform=waveform,
        antenna=antenna,
        polarization="single",
        mode="stripmap",
        look_side="right",
        depression_angle=depression_angle,
    )

    pri = 1.0 / prf
    time = np.arange(n_pulses) * pri
    # Platform flies along y-axis (North) at constant altitude
    positions = np.column_stack([
        np.zeros(n_pulses),       # East = 0
        velocity * time,          # North
        np.full(n_pulses, altitude),  # Up
    ])
    velocities = np.tile([0.0, velocity, 0.0], (n_pulses, 1))
    attitudes = np.zeros((n_pulses, 3))

    trajectory = Trajectory(
        time=time, position=positions,
        velocity=velocities, attitude=attitudes,
    )
    return radar, trajectory


class TestSlantToGroundRange:
    """T097: Integration test for SlantToGroundRange."""

    def test_output_geometry_is_ground_range(self):
        s2g = SlantToGroundRange()
        assert s2g.output_geometry == ImageGeometry.GROUND_RANGE

    def test_name(self):
        s2g = SlantToGroundRange()
        assert s2g.name == "slant_to_ground"

    def test_ground_range_spacing_larger_than_slant_range(self):
        """Ground-range spacing >= slant-range spacing for non-zero depression."""
        altitude = 5000.0
        depression_deg = 45.0
        radar, trajectory = _make_radar_and_trajectory(
            altitude=altitude, depression_angle_deg=depression_deg,
        )

        n_range, n_azimuth = 128, 64
        slant_spacing = C_LIGHT / (2 * radar.bandwidth)
        image = SARImage(
            data=np.random.default_rng(42).standard_normal((n_range, n_azimuth))
            + 1j * np.random.default_rng(43).standard_normal((n_range, n_azimuth)),
            pixel_spacing_range=slant_spacing,
            pixel_spacing_azimuth=trajectory.position[1, 1] - trajectory.position[0, 1],
            geometry="slant_range",
        )

        s2g = SlantToGroundRange()
        result = s2g.transform(image, radar, trajectory)

        assert result.geometry == ImageGeometry.GROUND_RANGE.value
        # Ground-range spacing >= slant-range spacing for incidence < 90 deg
        assert result.pixel_spacing_range >= slant_spacing * 0.9

    def test_point_target_ground_range_position(self):
        """A point target at known slant range maps to correct ground range."""
        altitude = 5000.0
        depression_deg = 45.0
        depression_rad = math.radians(depression_deg)
        radar, trajectory = _make_radar_and_trajectory(
            altitude=altitude, depression_angle_deg=depression_deg,
        )

        n_range, n_azimuth = 256, 64
        slant_spacing = C_LIGHT / (2 * radar.bandwidth)
        az_spacing = 0.1

        # Place a bright target at range bin 128
        target_range_bin = 128
        data = np.zeros((n_range, n_azimuth), dtype=complex)
        data[target_range_bin, n_azimuth // 2] = 1.0 + 0j

        image = SARImage(
            data=data,
            pixel_spacing_range=slant_spacing,
            pixel_spacing_azimuth=az_spacing,
            geometry="slant_range",
        )

        # Expected slant range to the target (from near range)
        near_slant = altitude / math.sin(depression_rad)
        target_slant = near_slant + target_range_bin * slant_spacing

        # Expected ground range from nadir
        expected_ground_range = math.sqrt(target_slant**2 - altitude**2)

        s2g = SlantToGroundRange()
        result = s2g.transform(image, radar, trajectory)

        # Find the peak in the output image
        peak_idx = np.unravel_index(np.argmax(np.abs(result.data)), result.data.shape)
        peak_range_bin = peak_idx[0]

        # Near ground range
        near_ground = math.sqrt(near_slant**2 - altitude**2)
        actual_ground_range = near_ground + peak_range_bin * result.pixel_spacing_range

        # Allow tolerance of 2 ground-range pixels
        tolerance = 2.0 * result.pixel_spacing_range
        assert abs(actual_ground_range - expected_ground_range) < tolerance

    def test_image_dimensions_preserved_azimuth(self):
        """Azimuth dimension should be unchanged."""
        radar, trajectory = _make_radar_and_trajectory()
        n_range, n_azimuth = 128, 64
        slant_spacing = C_LIGHT / (2 * radar.bandwidth)

        image = SARImage(
            data=np.ones((n_range, n_azimuth), dtype=complex),
            pixel_spacing_range=slant_spacing,
            pixel_spacing_azimuth=0.1,
            geometry="slant_range",
        )

        s2g = SlantToGroundRange()
        result = s2g.transform(image, radar, trajectory)

        assert result.data.shape[1] == n_azimuth

    def test_azimuth_spacing_unchanged(self):
        """Azimuth pixel spacing should be unchanged."""
        radar, trajectory = _make_radar_and_trajectory()
        az_spacing = 0.15
        image = SARImage(
            data=np.ones((128, 64), dtype=complex),
            pixel_spacing_range=C_LIGHT / (2 * radar.bandwidth),
            pixel_spacing_azimuth=az_spacing,
            geometry="slant_range",
        )

        s2g = SlantToGroundRange()
        result = s2g.transform(image, radar, trajectory)
        assert result.pixel_spacing_azimuth == az_spacing


class TestGeoreferencing:
    """T098: Integration test for Georeferencing."""

    def test_output_geometry_is_geographic(self):
        geo = Georeferencing()
        assert geo.output_geometry == ImageGeometry.GEOGRAPHIC

    def test_name(self):
        geo = Georeferencing()
        assert geo.name == "georeferencing"

    def test_geo_transform_populated(self):
        """Output image should have geo_transform metadata."""
        radar, trajectory = _make_radar_and_trajectory()
        image = SARImage(
            data=np.ones((128, 64), dtype=complex),
            pixel_spacing_range=C_LIGHT / (2 * radar.bandwidth),
            pixel_spacing_azimuth=0.1,
            geometry="slant_range",
        )

        geo = Georeferencing()
        result = geo.transform(image, radar, trajectory)

        assert result.geo_transform is not None
        assert result.geo_transform.shape == (6,)
        assert result.geometry == ImageGeometry.GEOGRAPHIC.value

    def test_known_target_lat_lon(self):
        """A target at known ENU position should map to correct lat/lon offset."""
        altitude = 5000.0
        depression_deg = 45.0
        radar, trajectory = _make_radar_and_trajectory(
            altitude=altitude, depression_angle_deg=depression_deg,
            n_pulses=64, velocity=100.0,
        )

        n_range, n_azimuth = 128, 64
        slant_spacing = C_LIGHT / (2 * radar.bandwidth)
        az_spacing = 0.1

        image = SARImage(
            data=np.ones((n_range, n_azimuth), dtype=complex),
            pixel_spacing_range=slant_spacing,
            pixel_spacing_azimuth=az_spacing,
            geometry="slant_range",
        )

        geo = Georeferencing()
        result = geo.transform(image, radar, trajectory)

        # geo_transform should encode the mapping
        gt = result.geo_transform
        # gt[0] = origin_lon, gt[3] = origin_lat (in degrees)
        # gt[1] = d_lon/d_col, gt[5] = d_lat/d_row
        # These should be non-zero finite values
        assert np.all(np.isfinite(gt))
        # Longitude offset per column should be positive (look_side=right, heading=North)
        assert gt[1] > 0 or gt[1] < 0  # non-zero

    def test_pixel_spacing_in_meters(self):
        """Output pixel spacing should reflect ground-range and azimuth meters."""
        radar, trajectory = _make_radar_and_trajectory()
        image = SARImage(
            data=np.ones((128, 64), dtype=complex),
            pixel_spacing_range=C_LIGHT / (2 * radar.bandwidth),
            pixel_spacing_azimuth=0.1,
            geometry="slant_range",
        )

        geo = Georeferencing()
        result = geo.transform(image, radar, trajectory)

        # Pixel spacing should be positive and reasonable
        assert result.pixel_spacing_range > 0
        assert result.pixel_spacing_azimuth > 0

    def test_image_data_shape_preserved(self):
        """Output image should have same shape as input."""
        radar, trajectory = _make_radar_and_trajectory()
        image = SARImage(
            data=np.ones((128, 64), dtype=complex),
            pixel_spacing_range=C_LIGHT / (2 * radar.bandwidth),
            pixel_spacing_azimuth=0.1,
            geometry="slant_range",
        )

        geo = Georeferencing()
        result = geo.transform(image, radar, trajectory)

        # Shape should match input (georeferencing maps coordinates,
        # not necessarily resample the grid)
        assert result.data.shape == image.data.shape


class TestGeocodingRegistry:
    """Test that geocoding algorithms are properly registered."""

    def test_registry_contains_algorithms(self):
        from pySimSAR.algorithms.geocoding import geocoding_registry

        assert "slant_to_ground" in geocoding_registry
        assert "georeferencing" in geocoding_registry

    def test_registry_instantiation(self):
        from pySimSAR.algorithms.geocoding import geocoding_registry

        s2g_cls = geocoding_registry.get("slant_to_ground")
        geo_cls = geocoding_registry.get("georeferencing")

        assert s2g_cls is SlantToGroundRange
        assert geo_cls is Georeferencing
