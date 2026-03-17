"""Geocoding algorithms for SAR image coordinate transformation.

Provides a registry of geocoding algorithms and default implementations:
- SlantToGroundRange: flat-earth slant-to-ground range projection
- Georeferencing: pixel-to-lat/lon mapping using trajectory and radar geometry
"""

from pySimSAR.algorithms.base import ImageTransformationAlgorithm
from pySimSAR.algorithms.registry import AlgorithmRegistry

geocoding_registry = AlgorithmRegistry(ImageTransformationAlgorithm, "geocoding")

# Register default algorithms
from pySimSAR.algorithms.geocoding.slant_to_ground import SlantToGroundRange
from pySimSAR.algorithms.geocoding.georeferencing import Georeferencing

geocoding_registry.register(SlantToGroundRange)
geocoding_registry.register(Georeferencing)

__all__ = [
    "geocoding_registry",
    "SlantToGroundRange",
    "Georeferencing",
]
