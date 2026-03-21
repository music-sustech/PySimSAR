"""Slant-range to ground-range projection (flat earth model).

Projects SAR image pixel coordinates from slant-range geometry to
ground-range geometry by computing the ground-range for each slant-range
sample and resampling to a uniform ground-range grid.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.interpolate import interp1d

from pySimSAR.algorithms.base import ImageTransformationAlgorithm
from pySimSAR.core.types import ImageGeometry, SARImage


class SlantToGroundRange(ImageTransformationAlgorithm):
    """Project SAR image from slant-range to ground-range (flat earth).

    For each range sample at slant range R_s, the corresponding ground
    range is R_g = sqrt(R_s^2 - h^2), where h is the platform altitude.
    The image is resampled onto a uniform ground-range grid via
    interpolation.
    """

    name: str = "slant_to_ground"

    @property
    def output_geometry(self) -> ImageGeometry:
        return ImageGeometry.GROUND_RANGE

    def transform(
        self, image: object, radar: object, trajectory: object
    ) -> SARImage:
        """Transform image from slant-range to ground-range geometry.

        Parameters
        ----------
        image : SARImage
            Input image in slant-range/azimuth geometry.
        radar : Radar
            Radar configuration (provides depression angle).
        trajectory : Trajectory
            Platform trajectory (provides altitude).
        """
        # Mean platform altitude
        altitude = float(np.mean(trajectory.position[:, 2]))

        # Near slant range from depression angle
        near_slant = altitude / math.sin(radar.depression_angle)

        n_range, n_azimuth = image.data.shape
        slant_spacing = image.pixel_spacing_range

        # Slant range for each range bin
        slant_ranges = near_slant + np.arange(n_range) * slant_spacing

        # Ensure all slant ranges are >= altitude (valid geometry)
        slant_ranges = np.maximum(slant_ranges, altitude + 1e-6)

        # Ground range for each slant-range bin
        ground_ranges = np.sqrt(slant_ranges**2 - altitude**2)

        # Create uniform ground-range grid
        gr_min = ground_ranges[0]
        gr_max = ground_ranges[-1]

        # Compute average ground-range spacing
        # dRg/dRs = Rs / sqrt(Rs^2 - h^2) at mid-range
        mid_slant = slant_ranges[n_range // 2]
        mid_ground_spacing = slant_spacing * mid_slant / math.sqrt(
            mid_slant**2 - altitude**2
        )
        ground_spacing = mid_ground_spacing

        n_ground = int((gr_max - gr_min) / ground_spacing) + 1
        uniform_ground = np.linspace(gr_min, gr_min + (n_ground - 1) * ground_spacing, n_ground)

        # Interpolate each azimuth line from non-uniform ground-range
        # to uniform ground-range grid
        output = np.zeros((n_ground, n_azimuth), dtype=image.data.dtype)

        for az in range(n_azimuth):
            col = image.data[:, az]
            if np.iscomplexobj(col):
                interp_re = interp1d(
                    ground_ranges, col.real,
                    kind="linear", bounds_error=False, fill_value=0.0,
                )
                interp_im = interp1d(
                    ground_ranges, col.imag,
                    kind="linear", bounds_error=False, fill_value=0.0,
                )
                output[:, az] = interp_re(uniform_ground) + 1j * interp_im(uniform_ground)
            else:
                interp_fn = interp1d(
                    ground_ranges, col,
                    kind="linear", bounds_error=False, fill_value=0.0,
                )
                output[:, az] = interp_fn(uniform_ground)

        return SARImage(
            data=output,
            pixel_spacing_range=ground_spacing,
            pixel_spacing_azimuth=image.pixel_spacing_azimuth,
            geometry=ImageGeometry.GROUND_RANGE.value,
            algorithm=image.algorithm,
            channel=image.channel,
        )


__all__ = ["SlantToGroundRange"]
