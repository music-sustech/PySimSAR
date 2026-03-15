"""Clutter model abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class ClutterModel(ABC):
    """Abstract base class for ground clutter texture models.

    Clutter models generate multiplicative texture values that modulate
    the reflectivity of distributed targets. Values must be non-negative.
    """

    name: str = ""

    @abstractmethod
    def generate(self, shape: tuple[int, ...], seed: int | None = None) -> np.ndarray:
        """Generate clutter texture values.

        Parameters
        ----------
        shape : tuple[int, ...]
            Output array shape.
        seed : int | None
            Random seed for reproducibility.

        Returns
        -------
        np.ndarray
            Clutter texture values >= 0, with the given shape.
        """


__all__ = ["ClutterModel"]
