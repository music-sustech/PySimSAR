"""Scene model: point targets, distributed targets, and scene container."""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

import numpy as np

if TYPE_CHECKING:
    from pySimSAR.clutter.base import ClutterModel


class PointTarget:
    """A single point scatterer in the scene.

    Parameters
    ----------
    position : np.ndarray
        ENU coordinates [x, y, z] in meters, shape (3,).
    rcs : float | np.ndarray
        Radar cross section. Scalar for single-pol, complex 2x2 scattering
        matrix for quad-pol.
    velocity : np.ndarray | None
        Optional target velocity [vx, vy, vz] in m/s, shape (3,).
    """

    def __init__(
        self,
        position: np.ndarray,
        rcs: float | np.ndarray,
        velocity: np.ndarray | None = None,
    ) -> None:
        position = np.asarray(position, dtype=float)
        if position.shape != (3,):
            raise ValueError(
                f"position must have shape (3,), got {position.shape}"
            )
        if not np.all(np.isfinite(position)):
            raise ValueError("position must contain only finite values")
        self._position = position

        if isinstance(rcs, np.ndarray):
            if rcs.shape != (2, 2):
                raise ValueError(
                    f"array rcs must have shape (2, 2), got {rcs.shape}"
                )
            self._rcs = rcs
        else:
            rcs_val = float(rcs)
            if rcs_val <= 0:
                raise ValueError(f"scalar rcs must be > 0, got {rcs_val}")
            self._rcs = rcs_val

        if velocity is not None:
            velocity = np.asarray(velocity, dtype=float)
            if velocity.shape != (3,):
                raise ValueError(
                    f"velocity must have shape (3,), got {velocity.shape}"
                )
            if not np.all(np.isfinite(velocity)):
                raise ValueError("velocity must contain only finite values")
        self._velocity = velocity

    @property
    def position(self) -> np.ndarray:
        """ENU coordinates [x, y, z] in meters."""
        return self._position

    @property
    def rcs(self) -> float | np.ndarray:
        """Radar cross section (scalar or 2x2 scattering matrix)."""
        return self._rcs

    @property
    def velocity(self) -> np.ndarray | None:
        """Target velocity in m/s, or None."""
        return self._velocity


class DistributedTarget:
    """A gridded distributed scattering region.

    Parameters
    ----------
    origin : np.ndarray
        ENU position of the grid corner, shape (3,).
    extent : np.ndarray
        Grid size [dx, dy] in meters, shape (2,). Must be > 0.
    cell_size : float
        Grid cell spacing in meters. Must be > 0.
    reflectivity : np.ndarray | None
        Reflectivity magnitude per cell, shape (ny, nx). Values >= 0.
        May be None if clutter_model is provided.
    scattering_matrix : np.ndarray | None
        Per-cell polarimetric scattering matrix, shape (ny, nx, 2, 2).
    elevation : np.ndarray | None
        Per-cell elevation offset, shape (ny, nx).
    clutter_model : ClutterModel | None
        If provided, can override reflectivity at simulation time.
    """

    def __init__(
        self,
        origin: np.ndarray,
        extent: np.ndarray,
        cell_size: float,
        reflectivity: np.ndarray | None = None,
        scattering_matrix: np.ndarray | None = None,
        elevation: np.ndarray | None = None,
        clutter_model: ClutterModel | None = None,
    ) -> None:
        origin = np.asarray(origin, dtype=float)
        if origin.shape != (3,):
            raise ValueError(
                f"origin must have shape (3,), got {origin.shape}"
            )
        self._origin = origin

        extent = np.asarray(extent, dtype=float)
        if extent.shape != (2,):
            raise ValueError(
                f"extent must have shape (2,), got {extent.shape}"
            )
        if np.any(extent <= 0):
            raise ValueError(f"extent values must be > 0, got {extent}")
        self._extent = extent

        if cell_size <= 0:
            raise ValueError(f"cell_size must be > 0, got {cell_size}")
        self._cell_size = float(cell_size)

        # Derive grid dimensions
        self._nx = int(extent[0] / cell_size)
        self._ny = int(extent[1] / cell_size)

        if reflectivity is not None:
            reflectivity = np.asarray(reflectivity, dtype=float)
            if reflectivity.shape != (self._ny, self._nx):
                raise ValueError(
                    f"reflectivity shape {reflectivity.shape} does not match "
                    f"grid dimensions ({self._ny}, {self._nx})"
                )
            if np.any(reflectivity < 0):
                raise ValueError("reflectivity values must be >= 0")
        elif clutter_model is None:
            raise ValueError(
                "either reflectivity or clutter_model must be provided"
            )
        self._reflectivity = reflectivity

        if scattering_matrix is not None:
            scattering_matrix = np.asarray(scattering_matrix)
            expected = (self._ny, self._nx, 2, 2)
            if scattering_matrix.shape != expected:
                raise ValueError(
                    f"scattering_matrix shape {scattering_matrix.shape} "
                    f"does not match expected {expected}"
                )
        self._scattering_matrix = scattering_matrix

        if elevation is not None:
            elevation = np.asarray(elevation, dtype=float)
            if elevation.shape != (self._ny, self._nx):
                raise ValueError(
                    f"elevation shape {elevation.shape} does not match "
                    f"grid dimensions ({self._ny}, {self._nx})"
                )
        self._elevation = elevation

        self._clutter_model = clutter_model

    @property
    def origin(self) -> np.ndarray:
        """ENU position of the grid corner."""
        return self._origin

    @property
    def extent(self) -> np.ndarray:
        """Grid size [dx, dy] in meters."""
        return self._extent

    @property
    def cell_size(self) -> float:
        """Grid cell spacing in meters."""
        return self._cell_size

    @property
    def nx(self) -> int:
        """Number of grid cells in x direction."""
        return self._nx

    @property
    def ny(self) -> int:
        """Number of grid cells in y direction."""
        return self._ny

    @property
    def reflectivity(self) -> np.ndarray | None:
        """Reflectivity magnitude per cell."""
        return self._reflectivity

    @property
    def scattering_matrix(self) -> np.ndarray | None:
        """Per-cell polarimetric scattering matrix."""
        return self._scattering_matrix

    @property
    def elevation(self) -> np.ndarray | None:
        """Per-cell elevation offset."""
        return self._elevation

    @property
    def clutter_model(self) -> ClutterModel | None:
        """Clutter model for reflectivity generation."""
        return self._clutter_model


class Scene:
    """Container for all scattering targets in a simulation.

    Parameters
    ----------
    origin_lat : float
        Scene origin latitude in degrees, [-90, 90].
    origin_lon : float
        Scene origin longitude in degrees, [-180, 180].
    origin_alt : float
        Scene origin altitude in meters. Must be finite.
    """

    def __init__(
        self,
        origin_lat: float,
        origin_lon: float,
        origin_alt: float,
    ) -> None:
        if not -90 <= origin_lat <= 90:
            raise ValueError(
                f"origin_lat must be in [-90, 90], got {origin_lat}"
            )
        if not -180 <= origin_lon <= 180:
            raise ValueError(
                f"origin_lon must be in [-180, 180], got {origin_lon}"
            )
        if not np.isfinite(origin_alt):
            raise ValueError(
                f"origin_alt must be finite, got {origin_alt}"
            )

        self._origin_lat = float(origin_lat)
        self._origin_lon = float(origin_lon)
        self._origin_alt = float(origin_alt)
        self._point_targets: list[PointTarget] = []
        self._distributed_targets: list[DistributedTarget] = []

    @property
    def origin_lat(self) -> float:
        """Scene origin latitude in degrees."""
        return self._origin_lat

    @property
    def origin_lon(self) -> float:
        """Scene origin longitude in degrees."""
        return self._origin_lon

    @property
    def origin_alt(self) -> float:
        """Scene origin altitude in meters."""
        return self._origin_alt

    @property
    def point_targets(self) -> list[PointTarget]:
        """List of point targets in the scene."""
        return self._point_targets

    @property
    def distributed_targets(self) -> list[DistributedTarget]:
        """List of distributed targets in the scene."""
        return self._distributed_targets

    def add_target(self, target: PointTarget | DistributedTarget) -> None:
        """Add a target to the scene.

        Parameters
        ----------
        target : PointTarget | DistributedTarget
            The target to add.

        Raises
        ------
        TypeError
            If target is not a PointTarget or DistributedTarget.
        """
        if isinstance(target, PointTarget):
            self._point_targets.append(target)
        elif isinstance(target, DistributedTarget):
            self._distributed_targets.append(target)
        else:
            raise TypeError(
                f"target must be PointTarget or DistributedTarget, "
                f"got {type(target).__name__}"
            )


__all__ = ["PointTarget", "DistributedTarget", "Scene"]
