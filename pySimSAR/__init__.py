"""PySimSAR — a modular SAR signal simulator and processing toolkit.

Provides classes for scene definition, radar configuration, raw signal
simulation, image formation, and data I/O in a single convenient namespace.
"""

# Core data types
from pySimSAR.core.types import RawData, SARImage, PhaseHistoryData

# Scene model
from pySimSAR.core.scene import Scene, PointTarget, DistributedTarget

# Radar and antenna
from pySimSAR.core.radar import Radar, AntennaPattern, create_antenna_from_preset

# Platform
from pySimSAR.core.platform import Platform

# Simulation engine
from pySimSAR.simulation.engine import SimulationEngine, SimulationResult

# Processing pipeline
from pySimSAR.pipeline.runner import PipelineRunner, PipelineResult

# Configuration
from pySimSAR.io.config import SimulationConfig, ProcessingConfig

# HDF5 I/O
from pySimSAR.io.hdf5_format import write_hdf5, read_hdf5, import_data

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
