"""PySimSAR — a modular SAR signal simulator and processing toolkit.

Provides classes for scene definition, radar configuration, raw signal
simulation, image formation, and data I/O in a single convenient namespace.
"""

# Core data types
# Platform
from pySimSAR.core.platform import Platform

# Radar and antenna
from pySimSAR.core.radar import AntennaPattern, Radar, create_antenna_from_preset

# Scene model
from pySimSAR.core.scene import DistributedTarget, PointTarget, Scene
from pySimSAR.core.types import PhaseHistoryData, RawData, SARImage

# Configuration
from pySimSAR.io.config import ProcessingConfig, SimulationConfig

# HDF5 I/O
from pySimSAR.io.hdf5_format import import_data, read_hdf5, write_hdf5

# Processing pipeline
from pySimSAR.pipeline.runner import PipelineResult, PipelineRunner

# Simulation engine
from pySimSAR.simulation.engine import SimulationEngine, SimulationResult

__all__ = [
    # Core types
    "RawData",
    "SARImage",
    "PhaseHistoryData",
    # Scene
    "Scene",
    "PointTarget",
    "DistributedTarget",
    # Radar
    "Radar",
    "AntennaPattern",
    "create_antenna_from_preset",
    # Platform
    "Platform",
    # Simulation
    "SimulationEngine",
    "SimulationResult",
    # Pipeline
    "PipelineRunner",
    "PipelineResult",
    # Config
    "SimulationConfig",
    "ProcessingConfig",
    # I/O
    "write_hdf5",
    "read_hdf5",
    "import_data",
]
