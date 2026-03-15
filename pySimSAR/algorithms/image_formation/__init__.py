"""Image formation algorithm registry and default implementations."""

from pySimSAR.algorithms.base import ImageFormationAlgorithm
from pySimSAR.algorithms.registry import AlgorithmRegistry

image_formation_registry = AlgorithmRegistry(
    ImageFormationAlgorithm, "image_formation"
)

# Register default algorithms
from pySimSAR.algorithms.image_formation.range_doppler import RangeDopplerAlgorithm
from pySimSAR.algorithms.image_formation.chirp_scaling import ChirpScalingAlgorithm
from pySimSAR.algorithms.image_formation.omega_k import OmegaKAlgorithm

image_formation_registry.register(RangeDopplerAlgorithm)
image_formation_registry.register(ChirpScalingAlgorithm)
image_formation_registry.register(OmegaKAlgorithm)

__all__ = [
    "image_formation_registry",
    "RangeDopplerAlgorithm",
    "ChirpScalingAlgorithm",
    "OmegaKAlgorithm",
]
