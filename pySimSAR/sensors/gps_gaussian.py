"""Gaussian GPS error model — simple additive white Gaussian noise."""

from __future__ import annotations

import numpy as np

from pySimSAR.sensors.gps import GPSErrorModel
from pySimSAR.sensors.registry import gps_error_registry


class GaussianGPSError(GPSErrorModel):
    """Simple additive white Gaussian noise GPS error model.

    Adds independent Gaussian noise to each position axis with
    configurable RMS. No temporal correlation.

    Parameters
    ----------
    accuracy_rms : float
        Position accuracy RMS per axis in meters. Must be > 0.
    """

    name = "gaussian"

    def __init__(self, accuracy_rms: float) -> None:
        if accuracy_rms <= 0:
            raise ValueError(f"accuracy_rms must be > 0, got {accuracy_rms}")
        self.accuracy_rms = float(accuracy_rms)

    def apply(
        self,
        true_positions: np.ndarray,
        time: np.ndarray,
        seed: int | None = None,
    ) -> np.ndarray:
        rng = np.random.default_rng(seed)
        noise = rng.normal(0.0, self.accuracy_rms, size=true_positions.shape)
        return true_positions + noise

    def __repr__(self) -> str:
        return f"GaussianGPSError(accuracy_rms={self.accuracy_rms})"


# Register with the GPS error registry
gps_error_registry.register(GaussianGPSError)

__all__ = ["GaussianGPSError"]
