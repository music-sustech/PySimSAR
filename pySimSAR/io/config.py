"""Simulation and processing configuration with JSON serialization."""

from __future__ import annotations

import json

from pySimSAR.core.platform import Platform
from pySimSAR.core.scene import Scene
from pySimSAR.core.radar import Radar
from pySimSAR.core.types import SimulationState

# Valid state transitions: maps current state -> set of reachable states
_TRANSITIONS: dict[SimulationState, set[SimulationState]] = {
    SimulationState.CREATED: {SimulationState.VALIDATED},
    SimulationState.VALIDATED: {SimulationState.RUNNING},
    SimulationState.RUNNING: {SimulationState.COMPLETED, SimulationState.FAILED},
    SimulationState.COMPLETED: set(),
    SimulationState.FAILED: set(),
}


class SimulationConfig:
    """Configuration for raw SAR signal generation.

    Controls what data is produced during a simulation run and tracks
    the simulation lifecycle through a simple state machine.

    Parameters
    ----------
    scene : Scene
        Target scene containing point and distributed targets. Must not be None.
    radar : Radar
        Radar system configuration including waveform, antenna, and PRF.
        Must not be None.
    n_pulses : int
        Number of azimuth pulses to simulate. Must be > 0.
    seed : int
        Random number generator seed for reproducibility. Must be >= 0.
    platform : Platform | None
        Platform configuration (optional).
    description : str
        Optional human-readable description of this simulation run.
    """

    def __init__(
        self,
        scene: Scene,
        radar: Radar,
        n_pulses: int,
        seed: int,
        platform: Platform | None = None,
        description: str = "",
    ) -> None:
        if scene is None:
            raise ValueError("scene must not be None")
        if not isinstance(scene, Scene):
            raise TypeError(
                f"scene must be a Scene instance, got {type(scene).__name__}"
            )

        if radar is None:
            raise ValueError("radar must not be None")
        if not isinstance(radar, Radar):
            raise TypeError(
                f"radar must be a Radar instance, got {type(radar).__name__}"
            )

        n_pulses = int(n_pulses)
        if n_pulses <= 0:
            raise ValueError(f"n_pulses must be > 0, got {n_pulses}")

        seed = int(seed)
        if seed < 0:
            raise ValueError(f"seed must be >= 0, got {seed}")

        self._scene = scene
        self._radar = radar
        self._platform = platform
        self._n_pulses = n_pulses
        self._seed = seed
        self._description = str(description)
        self._state = SimulationState.CREATED

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def scene(self) -> Scene:
        """Target scene."""
        return self._scene

    @property
    def radar(self) -> Radar:
        """Radar system configuration."""
        return self._radar

    @property
    def platform(self) -> Platform | None:
        """Platform configuration."""
        return self._platform

    @property
    def n_pulses(self) -> int:
        """Number of azimuth pulses to simulate."""
        return self._n_pulses

    @property
    def seed(self) -> int:
        """Random number generator seed."""
        return self._seed

    @property
    def description(self) -> str:
        """Optional run description."""
        return self._description

    @property
    def state(self) -> SimulationState:
        """Current simulation state."""
        return self._state

    # ------------------------------------------------------------------
    # State machine transitions
    # ------------------------------------------------------------------

    def _transition(self, target: SimulationState) -> None:
        """Attempt a state transition, raising ValueError on invalid moves."""
        allowed = _TRANSITIONS[self._state]
        if target not in allowed:
            raise ValueError(
                f"Cannot transition from '{self._state.value}' to "
                f"'{target.value}'. Allowed transitions from "
                f"'{self._state.value}': "
                + (
                    ", ".join(f"'{s.value}'" for s in allowed)
                    if allowed
                    else "none"
                )
            )
        self._state = target

    def validate(self) -> None:
        """Validate parameters and transition to VALIDATED.

        Performs all parameter constraint checks and moves the configuration
        from CREATED to VALIDATED.

        Raises
        ------
        ValueError
            If any parameter constraint is violated, or if the current state
            does not allow a transition to VALIDATED.
        """
        # Re-check invariants (guards against post-construction mutation
        # if attributes are ever made writable in a subclass)
        if self._scene is None:
            raise ValueError("scene must not be None")
        if self._radar is None:
            raise ValueError("radar must not be None")
        if self._n_pulses <= 0:
            raise ValueError(f"n_pulses must be > 0, got {self._n_pulses}")
        if self._seed < 0:
            raise ValueError(f"seed must be >= 0, got {self._seed}")

        self._transition(SimulationState.VALIDATED)

    def start(self) -> None:
        """Transition to RUNNING.

        The configuration must be in VALIDATED state before calling this
        method. Call :meth:`validate` first.

        Raises
        ------
        ValueError
            If the current state is not VALIDATED.
        """
        self._transition(SimulationState.RUNNING)

    def complete(self) -> None:
        """Transition to COMPLETED.

        Marks the simulation as successfully finished. The configuration
        must currently be in the RUNNING state.

        Raises
        ------
        ValueError
            If the current state is not RUNNING.
        """
        self._transition(SimulationState.COMPLETED)

    def fail(self) -> None:
        """Transition to FAILED.

        Marks the simulation as having encountered an error. The configuration
        must currently be in the RUNNING state.

        Raises
        ------
        ValueError
            If the current state is not RUNNING.
        """
        self._transition(SimulationState.FAILED)

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # JSON serialization
    # ------------------------------------------------------------------

    def to_json(self) -> str:
        """Serialize configuration parameters to JSON string.

        Serializes the reproducibility-relevant parameters (n_pulses, seed,
        description, state, radar summary, scene summary). Complex objects
        (Scene, Radar, Platform) are summarized by their key parameters
        rather than fully serialized.
        """
        data: dict = {
            "n_pulses": self._n_pulses,
            "seed": self._seed,
            "description": self._description,
            "state": self._state.value,
            "radar": {
                "carrier_freq": self._radar.carrier_freq,
                "prf": self._radar.prf,
                "bandwidth": self._radar.bandwidth,
                "waveform": self._radar.waveform.name,
                "sar_mode": self._radar.mode.value,
                "polarization": self._radar.polarization.value,
            },
            "scene": {
                "origin_lat": self._scene.origin_lat,
                "origin_lon": self._scene.origin_lon,
                "origin_alt": self._scene.origin_alt,
                "n_point_targets": len(self._scene.point_targets),
                "n_distributed_targets": len(self._scene.distributed_targets),
            },
        }
        if self._platform is not None:
            data["platform"] = {
                "velocity": self._platform.velocity,
                "altitude": self._platform.altitude,
                "heading": self._platform.heading,
            }
        return json.dumps(data, default=_json_default, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> dict:
        """Deserialize JSON string to a parameter dictionary.

        Returns a plain dict of the stored parameters. Full reconstruction
        of Scene/Radar/Platform objects requires domain-specific factories
        and is not handled here.
        """
        return json.loads(json_str)

    def __repr__(self) -> str:
        return (
            f"SimulationConfig("
            f"n_pulses={self._n_pulses}, "
            f"seed={self._seed}, "
            f"state='{self._state.value}', "
            f"description={self._description!r})"
        )


class ProcessingConfig:
    """Configuration for the SAR processing pipeline.

    Controls algorithm selection for each processing step. Decoupled from
    SimulationConfig so the same raw data can be re-processed with
    different algorithm selections.

    Parameters
    ----------
    image_formation : str
        Name of the image formation algorithm (required).
    moco : str | None
        Name of the motion compensation algorithm (None = skip).
    autofocus : str | None
        Name of the autofocus algorithm (None = skip).
    geocoding : str | None
        Name of the geocoding algorithm (None = skip).
    polarimetric_decomposition : str | None
        Name of the polarimetric decomposition (None = skip).
    description : str
        Optional description of this processing configuration.
    """

    def __init__(
        self,
        image_formation: str,
        image_formation_params: dict | None = None,
        moco: str | None = None,
        moco_params: dict | None = None,
        autofocus: str | None = None,
        autofocus_params: dict | None = None,
        geocoding: str | None = None,
        geocoding_params: dict | None = None,
        polarimetric_decomposition: str | None = None,
        polarimetric_decomposition_params: dict | None = None,
        description: str = "",
    ) -> None:
        if not image_formation:
            raise ValueError("image_formation algorithm name is required")
        self._image_formation = image_formation
        self._image_formation_params = image_formation_params or {}
        self._moco = moco
        self._moco_params = moco_params or {}
        self._autofocus = autofocus
        self._autofocus_params = autofocus_params or {}
        self._geocoding = geocoding
        self._geocoding_params = geocoding_params or {}
        self._polarimetric_decomposition = polarimetric_decomposition
        self._polarimetric_decomposition_params = polarimetric_decomposition_params or {}
        self._description = str(description)

    @property
    def image_formation(self) -> str:
        return self._image_formation

    @property
    def image_formation_params(self) -> dict:
        return self._image_formation_params

    @property
    def moco(self) -> str | None:
        return self._moco

    @property
    def moco_params(self) -> dict:
        return self._moco_params

    @property
    def autofocus(self) -> str | None:
        return self._autofocus

    @property
    def autofocus_params(self) -> dict:
        return self._autofocus_params

    @property
    def geocoding(self) -> str | None:
        return self._geocoding

    @property
    def geocoding_params(self) -> dict:
        return self._geocoding_params

    @property
    def polarimetric_decomposition(self) -> str | None:
        return self._polarimetric_decomposition

    @property
    def polarimetric_decomposition_params(self) -> dict:
        return self._polarimetric_decomposition_params

    @property
    def description(self) -> str:
        return self._description

    def to_json(self) -> str:
        """Serialize to JSON string."""
        data = {
            "image_formation": self._image_formation,
            "image_formation_params": self._image_formation_params,
            "moco": self._moco,
            "moco_params": self._moco_params,
            "autofocus": self._autofocus,
            "autofocus_params": self._autofocus_params,
            "geocoding": self._geocoding,
            "geocoding_params": self._geocoding_params,
            "polarimetric_decomposition": self._polarimetric_decomposition,
            "polarimetric_decomposition_params": self._polarimetric_decomposition_params,
            "description": self._description,
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> ProcessingConfig:
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(
            image_formation=data["image_formation"],
            image_formation_params=data.get("image_formation_params"),
            moco=data.get("moco"),
            moco_params=data.get("moco_params"),
            autofocus=data.get("autofocus"),
            autofocus_params=data.get("autofocus_params"),
            geocoding=data.get("geocoding"),
            geocoding_params=data.get("geocoding_params"),
            polarimetric_decomposition=data.get("polarimetric_decomposition"),
            polarimetric_decomposition_params=data.get("polarimetric_decomposition_params"),
            description=data.get("description", ""),
        )

    def __repr__(self) -> str:
        return (
            f"ProcessingConfig("
            f"image_formation={self._image_formation!r}, "
            f"moco={self._moco!r}, "
            f"autofocus={self._autofocus!r})"
        )


def _json_default(obj):
    """JSON serializer for numpy types and other non-standard types."""
    import numpy as np

    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


__all__ = ["SimulationConfig", "ProcessingConfig"]
