"""Motion compensation algorithms for SAR.

Provides a registry of MoCo algorithms and default implementations:
- FirstOrderMoCo: bulk phase correction to scene center
- SecondOrderMoCo: range-dependent correction with residual terms
"""

from pySimSAR.algorithms.base import MotionCompensationAlgorithm
from pySimSAR.algorithms.registry import AlgorithmRegistry

moco_registry = AlgorithmRegistry(MotionCompensationAlgorithm, "moco")

# Register default algorithms
from pySimSAR.algorithms.moco.first_order import FirstOrderMoCo
from pySimSAR.algorithms.moco.second_order import SecondOrderMoCo

moco_registry.register(FirstOrderMoCo)
moco_registry.register(SecondOrderMoCo)

__all__ = [
    "moco_registry",
    "FirstOrderMoCo",
    "SecondOrderMoCo",
]
