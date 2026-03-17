"""RCS (Radar Cross Section) fluctuation models.

Provides a pluggable interface for point target RCS statistical behavior.
The default StaticRCS model returns the base RCS unchanged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class RCSModel(ABC):
    """Abstract base class for point target RCS fluctuation models."""

    name: str = ""

    @abstractmethod
    def apply(self, rcs: float | np.ndarray, seed: int | None = None) -> float | np.ndarray:
        """Apply statistical fluctuation to the base RCS value.

        Parameters
        ----------
        rcs : float | np.ndarray
            Base RCS value (scalar or 2x2 scattering matrix).
        seed : int | None
            Random seed for reproducibility.

        Returns
        -------
        float | np.ndarray
            Fluctuated RCS value, same type as input.
        """

    @classmethod
    def parameter_schema(cls) -> dict:
        """Declare parameters for JSON serialization."""
        return {}


class StaticRCS(RCSModel):
    """Non-fluctuating RCS model. Returns the base RCS unchanged."""

    name = "static"

    def apply(self, rcs: float | np.ndarray, seed: int | None = None) -> float | np.ndarray:
        return rcs


__all__ = ["RCSModel", "StaticRCS"]
