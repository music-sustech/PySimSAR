"""Uniform clutter model."""

from __future__ import annotations

import numpy as np

from pySimSAR.clutter.base import ClutterModel
from pySimSAR.clutter.registry import clutter_model_registry


@clutter_model_registry.register
class UniformClutter(ClutterModel):
    """Uniform clutter model returning constant intensity values.

    Parameters
    ----------
    mean_intensity : float
        Constant intensity value for all cells. Must be >= 0.
    """

    name = "uniform"

    def __init__(self, mean_intensity: float = 1.0) -> None:
        if mean_intensity < 0:
            raise ValueError(
                f"mean_intensity must be >= 0, got {mean_intensity}"
            )
        self._mean_intensity = float(mean_intensity)

    @property
    def mean_intensity(self) -> float:
        """Constant intensity value."""
        return self._mean_intensity

    def generate(self, shape: tuple[int, ...], seed: int | None = None) -> np.ndarray:
        """Generate uniform clutter texture values.

        Parameters
        ----------
        shape : tuple[int, ...]
            Output array shape.
        seed : int | None
            Ignored for uniform model (output is deterministic).

        Returns
        -------
        np.ndarray
            Array filled with mean_intensity, with the given shape.
        """
        return np.full(shape, self._mean_intensity)


__all__ = ["UniformClutter"]
