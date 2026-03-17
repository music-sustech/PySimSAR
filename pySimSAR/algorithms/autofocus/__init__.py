"""Autofocus algorithms for SAR.

Provides a registry of autofocus algorithms and default implementations:
- PhaseGradientAutofocus (PGA): dominant scatterer phase gradient estimation
- MapDriftAutofocus (MDA): sub-aperture Doppler centroid drift tracking
- MinimumEntropyAutofocus (MEA): entropy optimization with polynomial phase model
- ProminentPointProcessing (PPP): prominent scatterer phase history extraction
"""

from pySimSAR.algorithms.base import AutofocusAlgorithm
from pySimSAR.algorithms.registry import AlgorithmRegistry

autofocus_registry = AlgorithmRegistry(AutofocusAlgorithm, "autofocus")

# Register default algorithms
from pySimSAR.algorithms.autofocus.pga import PhaseGradientAutofocus
from pySimSAR.algorithms.autofocus.mda import MapDriftAutofocus
from pySimSAR.algorithms.autofocus.min_entropy import MinimumEntropyAutofocus
from pySimSAR.algorithms.autofocus.ppp import ProminentPointProcessing

autofocus_registry.register(PhaseGradientAutofocus)
autofocus_registry.register(MapDriftAutofocus)
autofocus_registry.register(MinimumEntropyAutofocus)
autofocus_registry.register(ProminentPointProcessing)

__all__ = [
    "autofocus_registry",
    "PhaseGradientAutofocus",
    "MapDriftAutofocus",
    "MinimumEntropyAutofocus",
    "ProminentPointProcessing",
]
