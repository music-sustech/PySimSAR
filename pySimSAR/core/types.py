"""Shared type definitions and enums for PySimSAR."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class PolarizationMode(str, Enum):
    """Radar polarization mode."""

    SINGLE = "single"
    DUAL = "dual"
    QUAD = "quad"


class SARMode(str, Enum):
    """SAR imaging mode."""

    STRIPMAP = "stripmap"
    SPOTLIGHT = "spotlight"
    SCANMAR = "scanmar"


class LookSide(str, Enum):
    """Radar look direction relative to flight track."""

    LEFT = "left"
    RIGHT = "right"


class RampType(str, Enum):
    """FMCW frequency ramp direction."""

    UP = "up"
    DOWN = "down"
    TRIANGLE = "triangle"


class PolarizationChannel(str, Enum):
    """Polarization channel label."""

    SINGLE = "single"
    HH = "hh"
    HV = "hv"
    VH = "vh"
    VV = "vv"


class ImageGeometry(str, Enum):
    """SAR image coordinate geometry."""

    SLANT_RANGE = "slant_range"
    GROUND_RANGE = "ground_range"
    GEOGRAPHIC = "geographic"


class SimulationState(str, Enum):
    """Simulation configuration state."""

    CREATED = "created"
    VALIDATED = "validated"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Data entities for I/O (Phase 5)
# ---------------------------------------------------------------------------


@dataclass
class RawData:
    """Simulated raw SAR echo data for a single polarization channel.

    Attributes
    ----------
    echo : np.ndarray
        Complex echo matrix, shape (n_range, n_azimuth).
    channel : str
        Polarization channel name (e.g. "single", "hh").
    sample_rate : float
        Range sampling rate in Hz.
    carrier_freq : float
        Radar carrier frequency in Hz.
    bandwidth : float
        Waveform bandwidth in Hz.
    prf : float
        Pulse repetition frequency in Hz.
    waveform_name : str
        Name of the waveform used (e.g. "LFM", "FMCW").
    sar_mode : str
        SAR mode string (e.g. "stripmap", "spotlight", "scanmar").
    """

    echo: np.ndarray
    channel: str
    sample_rate: float
    carrier_freq: float
    bandwidth: float
    prf: float
    waveform_name: str = ""
    sar_mode: str = "stripmap"

    def __post_init__(self) -> None:
        self.echo = np.asarray(self.echo)
        if self.echo.ndim != 2:
            raise ValueError(
                f"echo must be 2-D (n_range, n_azimuth), got shape {self.echo.shape}"
            )

    def save(self, filepath: str | object, **kwargs) -> None:
        """Save this RawData to an HDF5 file."""
        from pySimSAR.io.hdf5_format import write_hdf5

        write_hdf5(filepath, raw_data={self.channel: self}, **kwargs)

    @staticmethod
    def load(filepath: str | object, channel: str | None = None) -> RawData:
        """Load RawData from an HDF5 file.

        If channel is None, returns the first channel found.
        """
        from pySimSAR.io.hdf5_format import read_hdf5

        data = read_hdf5(filepath)
        rd = data["raw_data"]
        if not rd:
            raise ValueError(f"No raw data found in {filepath}")
        if channel is not None:
            if channel not in rd:
                raise KeyError(f"Channel '{channel}' not found in {filepath}")
            return rd[channel]
        return next(iter(rd.values()))


@dataclass
class PhaseHistoryData:
    """Range-compressed phase history for autofocus / azimuth compression.

    Attributes
    ----------
    data : np.ndarray
        Complex phase history matrix, shape (n_range, n_azimuth).
    sample_rate : float
        Range sampling rate in Hz.
    prf : float
        Pulse repetition frequency in Hz.
    carrier_freq : float
        Carrier frequency in Hz.
    bandwidth : float
        Waveform bandwidth in Hz.
    channel : str
        Polarization channel name.
    """

    data: np.ndarray
    sample_rate: float
    prf: float
    carrier_freq: float
    bandwidth: float
    channel: str = "single"

    def __post_init__(self) -> None:
        self.data = np.asarray(self.data)
        if self.data.ndim != 2:
            raise ValueError(
                f"data must be 2-D (n_range, n_azimuth), got shape {self.data.shape}"
            )


@dataclass
class SARImage:
    """Focused SAR image product.

    Attributes
    ----------
    data : np.ndarray
        Image pixel data, shape (n_rows, n_cols). Complex or real.
    pixel_spacing_range : float
        Range pixel spacing in meters.
    pixel_spacing_azimuth : float
        Azimuth pixel spacing in meters.
    geometry : str
        Coordinate geometry: "slant_range", "ground_range", or "geographic".
    algorithm : str
        Name of the image formation algorithm used.
    channel : str
        Polarization channel name.
    geo_transform : np.ndarray | None
        Affine geo-transform, shape (6,). None if not georeferenced.
    projection_wkt : str | None
        WKT projection string. None if not georeferenced.
    """

    data: np.ndarray
    pixel_spacing_range: float
    pixel_spacing_azimuth: float
    geometry: str = "slant_range"
    algorithm: str = ""
    channel: str = "single"
    geo_transform: np.ndarray | None = None
    projection_wkt: str | None = None

    def __post_init__(self) -> None:
        self.data = np.asarray(self.data)
        if self.data.ndim != 2:
            raise ValueError(
                f"data must be 2-D (n_rows, n_cols), got shape {self.data.shape}"
            )

    def save(self, filepath: str | object, name: str = "image", **kwargs) -> None:
        """Save this SARImage to an HDF5 file."""
        from pySimSAR.io.hdf5_format import write_hdf5

        write_hdf5(filepath, images={name: self}, **kwargs)

    @staticmethod
    def load(filepath: str | object, name: str | None = None) -> SARImage:
        """Load SARImage from an HDF5 file.

        If name is None, returns the first image found.
        """
        from pySimSAR.io.hdf5_format import read_hdf5

        data = read_hdf5(filepath)
        imgs = data["images"]
        if not imgs:
            raise ValueError(f"No images found in {filepath}")
        if name is not None:
            if name not in imgs:
                raise KeyError(f"Image '{name}' not found in {filepath}")
            return imgs[name]
        return next(iter(imgs.values()))
