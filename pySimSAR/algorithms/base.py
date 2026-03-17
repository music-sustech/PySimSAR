"""Algorithm abstract base classes for SAR processing."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from pySimSAR.core.types import ImageGeometry, SARMode


class ImageFormationAlgorithm(ABC):
    """Abstract base class for SAR image formation algorithms.

    Implements a two-step pipeline: range compression followed by
    azimuth compression, with an optional autofocus step between them.
    The ``process()`` method provides the complete end-to-end pipeline.
    """

    name: str = ""

    @classmethod
    def parameter_schema(cls) -> dict:
        """Declare expected parameters, types, defaults, and descriptions."""
        return {}

    @abstractmethod
    def process(self, raw_data: object, radar: object, trajectory: object) -> object:
        """Run the complete image formation pipeline.

        Parameters
        ----------
        raw_data : RawData
            Raw echo data.
        radar : Radar
            Radar configuration.
        trajectory : Trajectory
            Platform trajectory.

        Returns
        -------
        SARImage
            Focused SAR image.
        """

    @abstractmethod
    def range_compress(self, raw_data: object, radar: object) -> object:
        """Perform range compression.

        Parameters
        ----------
        raw_data : RawData
            Raw echo data.
        radar : Radar
            Radar configuration.

        Returns
        -------
        PhaseHistoryData
            Range-compressed phase history data.
        """

    @abstractmethod
    def azimuth_compress(
        self, phase_history: object, radar: object, trajectory: object
    ) -> object:
        """Perform azimuth compression.

        Parameters
        ----------
        phase_history : PhaseHistoryData
            Range-compressed data.
        radar : Radar
            Radar configuration.
        trajectory : Trajectory
            Platform trajectory.

        Returns
        -------
        SARImage
            Focused SAR image.
        """

    @abstractmethod
    def supported_modes(self) -> list[SARMode]:
        """Return the SAR modes supported by this algorithm.

        Returns
        -------
        list[SARMode]
            Supported SAR imaging modes.
        """


class AlgorithmModeError(Exception):
    """Raised when an algorithm does not support the requested SAR mode."""


class MotionCompensationAlgorithm(ABC):
    """Abstract base class for motion compensation algorithms.

    Corrects phase errors in raw data caused by platform motion
    deviations from the ideal flight path.
    """

    name: str = ""

    @classmethod
    def parameter_schema(cls) -> dict:
        """Declare expected parameters, types, defaults, and descriptions."""
        return {}

    @property
    @abstractmethod
    def order(self) -> int:
        """Compensation order (1 = first-order, 2 = second-order)."""

    @abstractmethod
    def compensate(
        self, raw_data: object, nav_data: object, reference_track: object
    ) -> object:
        """Apply motion compensation to raw data.

        Parameters
        ----------
        raw_data : RawData
            Raw echo data with motion-induced phase errors.
        nav_data : NavigationData
            Navigation sensor measurements.
        reference_track : Trajectory
            Reference (ideal) trajectory.

        Returns
        -------
        RawData
            Motion-compensated raw data.
        """


class AutofocusAlgorithm(ABC):
    """Abstract base class for autofocus algorithms.

    Estimates and corrects residual phase errors in phase history data
    after motion compensation. Operates between range and azimuth
    compression steps.
    """

    name: str = ""
    max_iterations: int = 10
    convergence_threshold: float = 0.01  # radians

    @classmethod
    def parameter_schema(cls) -> dict:
        """Declare expected parameters, types, defaults, and descriptions."""
        return {}

    @abstractmethod
    def focus(self, phase_history: object, azimuth_compressor: object) -> object:
        """Apply autofocus to phase history data.

        Parameters
        ----------
        phase_history : PhaseHistoryData
            Range-compressed phase history data.
        azimuth_compressor : callable
            Azimuth compression function from the image formation algorithm.

        Returns
        -------
        SARImage
            Focused SAR image with residual phase errors corrected.
        """

    def estimate_phase_error(self, phase_history: object) -> np.ndarray:
        """Estimate residual phase error from phase history data.

        Parameters
        ----------
        phase_history : PhaseHistoryData
            Range-compressed phase history data.

        Returns
        -------
        np.ndarray
            Estimated phase error in radians, shape (n_azimuth,).
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement estimate_phase_error"
        )


class ImageTransformationAlgorithm(ABC):
    """Abstract base class for image geometry transformations.

    Transforms SAR images from slant-range geometry to ground-range
    or geographic coordinates.
    """

    name: str = ""

    @classmethod
    def parameter_schema(cls) -> dict:
        """Declare expected parameters, types, defaults, and descriptions."""
        return {}

    @property
    @abstractmethod
    def output_geometry(self) -> ImageGeometry:
        """The output coordinate geometry of this transformation."""

    @abstractmethod
    def transform(self, image: object, radar: object, trajectory: object) -> object:
        """Transform image geometry.

        Parameters
        ----------
        image : SARImage
            Input SAR image in slant-range geometry.
        radar : Radar
            Radar configuration.
        trajectory : Trajectory
            Platform trajectory.

        Returns
        -------
        SARImage
            Image in the output coordinate geometry.
        """


class PolarimetricDecomposition(ABC):
    """Abstract base class for polarimetric decomposition algorithms.

    Decomposes quad-pol SAR data into scattering mechanism components.
    """

    name: str = ""

    @classmethod
    def parameter_schema(cls) -> dict:
        """Declare expected parameters, types, defaults, and descriptions."""
        return {}

    @property
    @abstractmethod
    def n_components(self) -> int:
        """Number of decomposition components produced."""

    @abstractmethod
    def decompose(
        self,
        image_hh: object,
        image_hv: object,
        image_vh: object,
        image_vv: object,
    ) -> dict[str, np.ndarray]:
        """Decompose quad-pol SAR data.

        Parameters
        ----------
        image_hh : SARImage
            HH-polarization image.
        image_hv : SARImage
            HV-polarization image.
        image_vh : SARImage
            VH-polarization image.
        image_vv : SARImage
            VV-polarization image.

        Returns
        -------
        dict[str, np.ndarray]
            Decomposition components, keyed by component name.
        """

    def validate_input(
        self,
        image_hh: object,
        image_hv: object,
        image_vh: object,
        image_vv: object,
    ) -> None:
        """Validate that all four polarization channels are present.

        Parameters
        ----------
        image_hh, image_hv, image_vh, image_vv : SARImage
            Quad-pol channel images.

        Raises
        ------
        ValueError
            If any channel is None or has mismatched dimensions.
        """
        channels = {"HH": image_hh, "HV": image_hv, "VH": image_vh, "VV": image_vv}
        for name, img in channels.items():
            if img is None:
                raise ValueError(f"Missing {name} polarization channel")


__all__ = [
    "ImageFormationAlgorithm",
    "AlgorithmModeError",
    "MotionCompensationAlgorithm",
    "AutofocusAlgorithm",
    "ImageTransformationAlgorithm",
    "PolarimetricDecomposition",
]
