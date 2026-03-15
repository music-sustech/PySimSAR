"""Shared type definitions and enums for PySimSAR."""

from enum import Enum


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
