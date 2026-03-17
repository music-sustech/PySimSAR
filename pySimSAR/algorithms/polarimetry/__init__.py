"""Polarimetric decomposition algorithms for quad-pol SAR data.

Provides a registry of decomposition algorithms and default implementations:
- PauliDecomposition: 3-component Pauli basis (surface, double-bounce, volume)
- FreemanDurdenDecomposition: model-based 3-component
- YamaguchiDecomposition: 4-component with helix scattering
- CloudePottierDecomposition: eigenvalue-based H/A/Alpha
"""

from pySimSAR.algorithms.base import PolarimetricDecomposition
from pySimSAR.algorithms.registry import AlgorithmRegistry

polarimetry_registry = AlgorithmRegistry(PolarimetricDecomposition, "polarimetry")

# Register default algorithms
from pySimSAR.algorithms.polarimetry.pauli import PauliDecomposition
from pySimSAR.algorithms.polarimetry.freeman_durden import FreemanDurdenDecomposition
from pySimSAR.algorithms.polarimetry.yamaguchi import YamaguchiDecomposition
from pySimSAR.algorithms.polarimetry.cloude_pottier import CloudePottierDecomposition

polarimetry_registry.register(PauliDecomposition)
polarimetry_registry.register(FreemanDurdenDecomposition)
polarimetry_registry.register(YamaguchiDecomposition)
polarimetry_registry.register(CloudePottierDecomposition)

__all__ = [
    "polarimetry_registry",
    "PauliDecomposition",
    "FreemanDurdenDecomposition",
    "YamaguchiDecomposition",
    "CloudePottierDecomposition",
]
