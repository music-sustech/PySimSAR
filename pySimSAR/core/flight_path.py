"""Flight path computation helpers.

Provides two modes of flight path specification:

- **Mode A (Start + Stop):** Given start_position, stop_position, and velocity,
  derive heading, distance, flight_time, and optionally n_pulses.
- **Mode B (Start + Heading + Time):** Given start_position, heading, velocity,
  and flight_time, derive stop_position, distance, and optionally n_pulses.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["FlightPathResult", "compute_flight_path"]


@dataclass
class FlightPathResult:
    """Result of flight path computation."""

    start_position: np.ndarray  # (3,)
    stop_position: np.ndarray  # (3,)
    heading: np.ndarray  # (3,) unit vector
    velocity: float  # m/s
    flight_time: float  # seconds
    distance: float  # meters
    n_pulses: int | None  # if PRF was provided


def _to_array3(value: np.ndarray | list[float], name: str) -> np.ndarray:
    """Convert *value* to a 1-D float64 array of length 3."""
    arr = np.asarray(value, dtype=np.float64).ravel()
    if arr.shape != (3,):
        raise ValueError(f"{name} must have exactly 3 elements, got {arr.size}")
    return arr


def compute_flight_path(
    *,
    start_position: np.ndarray | list[float],
    velocity: float,
    stop_position: np.ndarray | list[float] | None = None,
    heading: np.ndarray | list[float] | None = None,
    flight_time: float | None = None,
    prf: float | None = None,
) -> FlightPathResult:
    """Compute flight path from either start+stop or start+heading+time.

    Exactly one of these must be provided:

    - *stop_position* (Mode A)
    - *heading* **and** *flight_time* (Mode B)

    Parameters
    ----------
    start_position : array-like, shape (3,)
        Starting position in 3-D space (metres).
    velocity : float
        Platform speed (m/s).  Must be positive.
    stop_position : array-like, shape (3,), optional
        Ending position (Mode A).
    heading : array-like, shape (3,), optional
        Flight direction unit vector (Mode B).  Will be normalised internally.
    flight_time : float, optional
        Total flight duration in seconds (Mode B).  Must be positive.
    prf : float, optional
        Pulse repetition frequency (Hz).  If given, ``n_pulses`` is computed.

    Returns
    -------
    FlightPathResult

    Raises
    ------
    ValueError
        For invalid or ambiguous inputs.
    """
    # --- velocity validation ------------------------------------------------
    velocity = float(velocity)
    if velocity <= 0:
        raise ValueError(f"velocity must be positive, got {velocity}")

    # --- prf validation (optional) ------------------------------------------
    if prf is not None:
        prf = float(prf)
        if prf <= 0:
            raise ValueError(f"prf must be positive, got {prf}")

    # --- convert start_position ---------------------------------------------
    start_pos = _to_array3(start_position, "start_position")

    # --- determine mode -----------------------------------------------------
    has_stop = stop_position is not None
    has_heading = heading is not None
    has_time = flight_time is not None

    mode_a = has_stop and (not has_heading) and (not has_time)
    mode_b = (not has_stop) and has_heading and has_time

    if not (mode_a or mode_b):
        raise ValueError(
            "Provide exactly one of: stop_position (Mode A) "
            "or heading AND flight_time (Mode B). "
            f"Got stop_position={'set' if has_stop else 'None'}, "
            f"heading={'set' if has_heading else 'None'}, "
            f"flight_time={'set' if has_time else 'None'}."
        )

    # --- Mode A: start + stop -----------------------------------------------
    if mode_a:
        stop_pos = _to_array3(stop_position, "stop_position")  # type: ignore[arg-type]
        diff = stop_pos - start_pos
        distance = float(np.linalg.norm(diff))
        if distance == 0:
            raise ValueError(
                "start_position and stop_position are identical (zero distance)"
            )
        heading_vec = diff / distance
        ft = distance / velocity

    # --- Mode B: start + heading + flight_time ------------------------------
    else:
        flight_time = float(flight_time)  # type: ignore[arg-type]
        if flight_time <= 0:
            raise ValueError(f"flight_time must be positive, got {flight_time}")

        heading_vec = _to_array3(heading, "heading")  # type: ignore[arg-type]
        heading_norm = float(np.linalg.norm(heading_vec))
        if heading_norm == 0:
            raise ValueError("heading must be a non-zero vector")
        heading_vec = heading_vec / heading_norm

        distance = velocity * flight_time
        stop_pos = start_pos + heading_vec * distance
        ft = flight_time

    # --- n_pulses -----------------------------------------------------------
    n_pulses: int | None = None
    if prf is not None:
        n_pulses = int(prf * ft)

    return FlightPathResult(
        start_position=start_pos,
        stop_position=stop_pos,
        heading=heading_vec,
        velocity=velocity,
        flight_time=ft,
        distance=distance,
        n_pulses=n_pulses,
    )
