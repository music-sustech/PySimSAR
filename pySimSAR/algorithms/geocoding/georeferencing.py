"""Georeferencing: pixel-to-lat/lon mapping using trajectory and radar geometry.

Maps SAR image pixels from slant-range/azimuth coordinates to geographic
(latitude/longitude) coordinates using the platform trajectory, radar
depression angle, and look direction.
"""

from __future__ import annotations

import math

import numpy as np

from pySimSAR.algorithms.base import ImageTransformationAlgorithm
from pySimSAR.core.coordinates import enu_to_geodetic
from pySimSAR.core.types import ImageGeometry, LookSide, SARImage


class Georeferencing(ImageTransformationAlgorithm):
    """Map SAR image pixels to lat/lon using trajectory and radar geometry.

    Computes the ground position of each pixel by projecting the slant-range
    vector from the platform position to the ground (flat earth assumption),
    then converts the ENU ground positions to geodetic (lat/lon) coordinates.

    The output SARImage retains the same pixel data but gains a geo_transform
    array encoding the affine mapping from pixel indices to geographic
    coordinates (GDAL-style):
        [origin_lon, d_lon/d_col, d_lon/d_row,
         origin_lat, d_lat/d_col, d_lat/d_row]

    Parameters
    ----------
    scene_origin_lat : float
        Scene origin latitude in degrees (default 0.0).
    scene_origin_lon : float
        Scene origin longitude in degrees (default 0.0).
    scene_origin_alt : float
        Scene origin altitude in meters (default 0.0).
    """

    name: str = "georeferencing"

    def __init__(
        self,
        scene_origin_lat: float = 0.0,
        scene_origin_lon: float = 0.0,
        scene_origin_alt: float = 0.0,
    ) -> None:
        self._ref_lat = scene_origin_lat
        self._ref_lon = scene_origin_lon
        self._ref_alt = scene_origin_alt

    @property
    def output_geometry(self) -> ImageGeometry:
        return ImageGeometry.GEOGRAPHIC

    def transform(
        self, image: object, radar: object, trajectory: object
    ) -> SARImage:
        """Transform image coordinates to geographic (lat/lon).

        Parameters
        ----------
        image : SARImage
            Input image in slant-range geometry.
        radar : Radar
            Radar parameters (depression angle, look side).
        trajectory : Trajectory
            Platform trajectory in ENU coordinates.
        """
        n_range, n_azimuth = image.data.shape

        # Mean platform altitude
        altitude = float(np.mean(trajectory.position[:, 2]))

        # Near slant range
        near_slant = altitude / math.sin(radar.depression_angle)

        # Compute corner ground positions in ENU
        # For each corner pixel, determine the ground position
        corners_enu = []
        for az_idx, rng_idx in [(0, 0), (0, n_range - 1),
                                (n_azimuth - 1, 0), (n_azimuth - 1, n_range - 1)]:
            enu = self._pixel_to_enu(
                rng_idx, az_idx, near_slant, image, radar, trajectory,
            )
            corners_enu.append(enu)

        # Convert corners to geodetic
        corners_geo = []
        for enu in corners_enu:
            lat, lon, _ = enu_to_geodetic(
                enu, self._ref_lat, self._ref_lon, self._ref_alt,
            )
            corners_geo.append((lat, lon))

        # Compute ground-range pixel spacing (slant to ground projection)
        mid_slant = near_slant + (n_range // 2) * image.pixel_spacing_range
        mid_slant = max(mid_slant, altitude + 1e-6)
        ground_range_spacing = image.pixel_spacing_range * mid_slant / math.sqrt(
            mid_slant**2 - altitude**2
        )

        # Compute geo_transform (affine mapping from pixel to lat/lon)
        # Use the four corners to estimate the affine parameters
        origin_lat = corners_geo[0][0]
        origin_lon = corners_geo[0][1]

        # d_lon per range pixel (column) and d_lat per azimuth pixel (row)
        if n_range > 1:
            d_lon_per_col = (corners_geo[1][1] - corners_geo[0][1]) / (n_range - 1)
            d_lat_per_col = (corners_geo[1][0] - corners_geo[0][0]) / (n_range - 1)
        else:
            d_lon_per_col = 0.0
            d_lat_per_col = 0.0

        if n_azimuth > 1:
            d_lon_per_row = (corners_geo[2][1] - corners_geo[0][1]) / (n_azimuth - 1)
            d_lat_per_row = (corners_geo[2][0] - corners_geo[0][0]) / (n_azimuth - 1)
        else:
            d_lon_per_row = 0.0
            d_lat_per_row = 0.0

        geo_transform = np.array([
            origin_lon, d_lon_per_col, d_lon_per_row,
            origin_lat, d_lat_per_col, d_lat_per_row,
        ])

        return SARImage(
            data=image.data.copy(),
            pixel_spacing_range=ground_range_spacing,
            pixel_spacing_azimuth=image.pixel_spacing_azimuth,
            geometry=ImageGeometry.GEOGRAPHIC.value,
            algorithm=image.algorithm,
            channel=image.channel,
            geo_transform=geo_transform,
        )

    def _pixel_to_enu(
        self,
        range_idx: int,
        azimuth_idx: int,
        near_slant: float,
        image: object,
        radar: object,
        trajectory: object,
    ) -> np.ndarray:
        """Compute the ENU ground position for a given pixel.

        Projects the slant-range vector from the platform to the ground
        using flat-earth geometry.
        """
        # Platform position at this azimuth line
        n_traj = len(trajectory.time)
        n_azimuth = image.data.shape[1]

        if n_azimuth > 1 and n_traj > 1:
            # Map azimuth index to trajectory time
            t = trajectory.time[0] + azimuth_idx * (
                trajectory.time[-1] - trajectory.time[0]
            ) / (n_azimuth - 1)
            platform_pos = trajectory.interpolate_position(t)
        else:
            platform_pos = trajectory.position[0]

        # Slant range for this range bin
        slant_range = near_slant + range_idx * image.pixel_spacing_range
        altitude = platform_pos[2]
        slant_range = max(slant_range, altitude + 1e-6)

        # Ground range from nadir
        ground_range = math.sqrt(slant_range**2 - altitude**2)

        # Look direction in the across-track plane
        # Platform heading from velocity vector
        vel = trajectory.velocity[min(azimuth_idx, n_traj - 1)]
        heading = math.atan2(vel[0], vel[1])  # atan2(East, North)

        # Cross-track direction depends on look_side
        if radar.look_side == LookSide.RIGHT:
            cross_track_angle = heading + math.pi / 2
        else:
            cross_track_angle = heading - math.pi / 2

        # Ground position
        ground_east = platform_pos[0] + ground_range * math.sin(cross_track_angle)
        ground_north = platform_pos[1] + ground_range * math.cos(cross_track_angle)

        return np.array([ground_east, ground_north, 0.0])


__all__ = ["Georeferencing"]
