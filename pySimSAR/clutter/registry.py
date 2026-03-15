"""Clutter model registry."""

from pySimSAR.algorithms.registry import AlgorithmRegistry
from pySimSAR.clutter.base import ClutterModel

clutter_model_registry = AlgorithmRegistry(ClutterModel, "clutter_model")

__all__ = ["clutter_model_registry"]
