"""Antenna beam direction computation for all three SAR modes.

Supports:
- Stripmap: fixed broadside or squint direction across all pulses
- Spotlight: per-pulse beam steering to track a fixed scene center
- ScanSAR: cyclic elevation sweep across sub-swaths with burst-mode scheduling
  and scalloping modeling

Coordinate system: ENU (x=East, y=North, z=Up).
Look direction: "right" means the antenna points to the right of the velocity
vector when viewed from above.
"""

from __future__ import annotations

import math

import numpy as np

from pySimSAR.core.radar import Radar
from pySimSAR.core.types import LookSide, SARMode


def compute_look_angles(
    radar: Radar,
    platform_pos: np.ndarray,
    target_pos: np.ndarray,
    platform_vel: np.ndarray,
) -> tuple[float, float]:
    """Compute azimuth and elevation angles from the platform to a target.

    Parameters
    ----------
    radar : Radar
        Radar system model (used for look_side).
    platform_pos : np.ndarray
        Platform ENU position [x, y, z] in metres, shape (3,).
    target_pos : np.ndarray
        Target ENU position [x, y, z] in metres, shape (3,).
    platform_vel : np.ndarray
        Platform ENU velocity [vx, vy, vz] in m/s, shape (3,).

    Returns
    -------
    azimuth : float
        Angle in the horizontal plane relative to the velocity direction,
        in radians.  Positive toward the look side (right for RIGHT look,
        left for LEFT look).
    elevation : float
        Depression angle below the horizontal plane, in radians.
        Positive values indicate the target is below the platform.
    """
    platform_pos = np.asarray(platform_pos, dtype=float)
    target_pos = np.asarray(target_pos, dtype=float)
    platform_vel = np.asarray(platform_vel, dtype=float)

    # Line-of-sight vector from platform to target
    los = target_pos - platform_pos  # shape (3,)

    # Build a local coordinate frame aligned with the velocity vector.
    # x_hat: along-track (velocity direction, horizontal component)
    # z_hat: up (ENU z)
    # y_hat: cross-track, pointing to the right of x_hat

    vel_speed = np.linalg.norm(platform_vel)
    if vel_speed < 1e-12:
        # Degenerate: fall back to North as forward
        x_hat = np.array([0.0, 1.0, 0.0])
    else:
        # Use horizontal component of velocity for along-track direction
        vel_h = platform_vel.copy()
        vel_h[2] = 0.0
        h_speed = np.linalg.norm(vel_h)
        if h_speed < 1e-12:
            x_hat = np.array([0.0, 1.0, 0.0])
        else:
            x_hat = vel_h / h_speed

    z_hat = np.array([0.0, 0.0, 1.0])  # ENU up

    # Cross-track: x_hat × z_hat gives the right side in ENU.
    # (e.g. North × Up = East = right of the velocity direction)
    y_hat_right = np.cross(x_hat, z_hat)  # points right of x_hat

    if radar.look_side == LookSide.LEFT:
        y_hat = -y_hat_right  # left side
    else:
        y_hat = y_hat_right  # right side (default)

    # Project LOS onto the local frame
    los_along = float(np.dot(los, x_hat))    # along-track component
    los_cross = float(np.dot(los, y_hat))    # cross-track component (signed)
    los_up = float(np.dot(los, z_hat))       # vertical component

    # Azimuth: angle from the cross-track direction toward along-track,
    # measured in the look-side half-plane.  In broadside geometry this
    # is zero when the target is exactly perpendicular to the flight track.
    azimuth = math.atan2(los_along, los_cross)

    # Elevation (depression): angle below the horizontal plane.
    # los_cross is the horizontal range in the cross-track plane.
    slant_horiz = math.sqrt(los_along**2 + los_cross**2)
    elevation = math.atan2(-los_up, slant_horiz)  # positive = target below

    return azimuth, elevation


def _stripmap_beam(
    radar: Radar,
    platform_pos: np.ndarray,
    platform_vel: np.ndarray,
) -> tuple[float, float]:
    """Return the fixed beam steering angles for stripmap mode.

    The beam is steered to the nominal depression angle and squint angle
    encoded in the Radar object.  These remain constant for every pulse.

    Returns
    -------
    az_steer : float
        Azimuth steering angle in radians (equals radar.squint_angle).
    el_steer : float
        Elevation steering angle in radians (equals radar.depression_angle,
        negated to represent downward-looking geometry).
    """
    az_steer = float(radar.squint_angle)
    # depression_angle is measured from horizontal, positive downward
    el_steer = -float(radar.depression_angle)
    return az_steer, el_steer


def _spotlight_beam(
    radar: Radar,
    platform_pos: np.ndarray,
    platform_vel: np.ndarray,
    scene_center: np.ndarray,
) -> tuple[float, float]:
    """Compute per-pulse beam steering angles for spotlight mode.

    The beam is pointed at *scene_center* from the current platform position.

    Parameters
    ----------
    radar : Radar
        Radar system model.
    platform_pos : np.ndarray
        Current platform ENU position, shape (3,).
    platform_vel : np.ndarray
        Current platform ENU velocity, shape (3,).
    scene_center : np.ndarray
        Fixed scene center ENU position, shape (3,).

    Returns
    -------
    az_steer : float
        Azimuth steering angle in radians.
    el_steer : float
        Elevation steering angle in radians.
    """
    az_steer, el_raw = compute_look_angles(
        radar, platform_pos, scene_center, platform_vel
    )
    # el_raw from compute_look_angles is depression (positive = below).
    # The beam steering convention here uses negative for downward.
    el_steer = -el_raw
    return az_steer, el_steer


def _scanmar_beam(
    radar: Radar,
    platform_pos: np.ndarray,
    platform_vel: np.ndarray,
    pulse_idx: int,
    n_subswaths: int,
    burst_length: int,
) -> tuple[float, float]:
    """Compute burst-mode beam steering angles for ScanSAR mode.

    Sub-swaths are illuminated cyclically.  Within each burst the azimuth
    steering is fixed (broadside + squint), while the elevation is stepped
    per sub-swath based on the nominal depression angle and a symmetric
    elevation range derived from the antenna elevation beamwidth.

    Parameters
    ----------
    radar : Radar
        Radar system model.
    platform_pos : np.ndarray
        Current platform ENU position, shape (3,).
    platform_vel : np.ndarray
        Current platform ENU velocity, shape (3,).
    pulse_idx : int
        Zero-based pulse index.
    n_subswaths : int
        Number of sub-swaths (>= 1).
    burst_length : int
        Number of pulses per sub-swath burst (>= 1).

    Returns
    -------
    az_steer : float
        Azimuth steering angle in radians.
    el_steer : float
        Elevation steering angle in radians.
    """
    # Determine which sub-swath this pulse belongs to
    pulses_per_cycle = n_subswaths * burst_length
    subswath_idx = (pulse_idx % pulses_per_cycle) // burst_length

    # Distribute sub-swath elevation offsets symmetrically around the nominal
    # depression angle.  For n sub-swaths the offsets span from
    # -(n-1)/2 * step to +(n-1)/2 * step, where step = el_beamwidth.
    # This places adjacent beams one beamwidth apart.
    el_step = float(radar.antenna.el_beamwidth)
    center_offset = (n_subswaths - 1) / 2.0
    el_offset = (subswath_idx - center_offset) * el_step

    az_steer = float(radar.squint_angle)
    el_steer = -float(radar.depression_angle) + el_offset
    return az_steer, el_steer


def compute_beam_direction(
    radar: Radar,
    platform_pos: np.ndarray,
    platform_vel: np.ndarray,
    pulse_idx: int,
    scene_center: np.ndarray | None = None,
    n_subswaths: int | None = None,
    burst_length: int | None = None,
) -> tuple[float, float]:
    """Compute beam pointing direction for a given pulse.

    Dispatches to the appropriate mode-specific implementation.

    Parameters
    ----------
    radar : Radar
        Radar system model.  ``radar.mode`` determines which implementation
        is used.
    platform_pos : np.ndarray
        Platform ENU position [x, y, z] in metres, shape (3,).
    platform_vel : np.ndarray
        Platform ENU velocity [vx, vy, vz] in m/s, shape (3,).
    pulse_idx : int
        Zero-based pulse index.
    scene_center : np.ndarray | None
        ENU position of the spotlight scene center, shape (3,).
        Required for SARMode.SPOTLIGHT; ignored otherwise.
    n_subswaths : int | None
        Number of ScanSAR sub-swaths.  Required for SARMode.SCANMAR;
        defaults to 3 if not provided.
    burst_length : int | None
        Number of pulses per ScanSAR burst.  Required for SARMode.SCANMAR;
        defaults to 1 if not provided.

    Returns
    -------
    az_steer : float
        Azimuth beam steering angle in radians.
    el_steer : float
        Elevation beam steering angle in radians.  Negative values indicate
        the beam points below the horizontal plane (normal operation).

    Raises
    ------
    ValueError
        If SARMode.SPOTLIGHT is requested but *scene_center* is not provided.
    """
    platform_pos = np.asarray(platform_pos, dtype=float)
    platform_vel = np.asarray(platform_vel, dtype=float)

    if radar.mode == SARMode.STRIPMAP:
        return _stripmap_beam(radar, platform_pos, platform_vel)

    if radar.mode == SARMode.SPOTLIGHT:
        if scene_center is None:
            raise ValueError(
                "scene_center must be provided for SARMode.SPOTLIGHT"
            )
        scene_center = np.asarray(scene_center, dtype=float)
        return _spotlight_beam(radar, platform_pos, platform_vel, scene_center)

    if radar.mode == SARMode.SCANMAR:
        _n = int(n_subswaths) if n_subswaths is not None else 3
        _b = int(burst_length) if burst_length is not None else 1
        if _n < 1:
            raise ValueError(f"n_subswaths must be >= 1, got {_n}")
        if _b < 1:
            raise ValueError(f"burst_length must be >= 1, got {_b}")
        return _scanmar_beam(
            radar, platform_pos, platform_vel, pulse_idx, _n, _b
        )

    raise ValueError(f"Unknown SAR mode: {radar.mode}")


def compute_two_way_gain(
    radar: Radar,
    target_az: float,
    target_el: float,
    steer_az: float,
    steer_el: float,
) -> float:
    """Compute two-way antenna gain for a target given beam steering angles.

    The gain is evaluated at the angular offset of the target from the beam
    centre: ``(target_az - steer_az, target_el - steer_el)``.  The two-way
    gain is the one-way gain applied twice (transmit and receive paths are
    assumed to use the same antenna pattern).

    Parameters
    ----------
    radar : Radar
        Radar system model containing the antenna pattern.
    target_az : float
        Target azimuth angle relative to the platform frame, in radians.
    target_el : float
        Target elevation angle relative to the platform frame, in radians.
    steer_az : float
        Beam steering azimuth angle, in radians.
    steer_el : float
        Beam steering elevation angle, in radians.

    Returns
    -------
    float
        Two-way gain in **linear** scale (not dB).  Always >= 0.
        Equals ``10 ** (2 * gain_dB / 10)`` where *gain_dB* is the one-way
        gain in dB evaluated at the angular offset.
    """
    az_offset = target_az - steer_az
    el_offset = target_el - steer_el

    gain_dB = radar.antenna.gain(az_offset, el_offset)
    # Two-way gain: apply the pattern twice (transmit + receive)
    two_way_gain_dB = 2.0 * gain_dB
    return float(10.0 ** (two_way_gain_dB / 10.0))


def scalloping_loss(
    pulse_in_burst: int,
    burst_length: int,
    az_beamwidth: float,
) -> float:
    """Compute ScanSAR scalloping loss for a pulse within a burst.

    Scalloping arises because the azimuth beam sweeps across a target only
    during a short burst rather than the full synthetic aperture.  Within
    the burst the target moves through the two-way azimuth beam pattern,
    producing amplitude modulation (scalloping).

    A sinc-squared model is used.  The burst is mapped onto the central lobe
    of the azimuth beam pattern, and the pulse at position *pulse_in_burst*
    within the burst sees a gain factor derived from the two-way sinc² pattern.

    Parameters
    ----------
    pulse_in_burst : int
        Zero-based index of the pulse within the current burst [0, burst_length).
    burst_length : int
        Total number of pulses in the burst (>= 1).
    az_beamwidth : float
        One-way 3 dB azimuth beamwidth in radians (> 0).

    Returns
    -------
    float
        Scalloping loss factor in linear scale, in the range (0, 1].
        A value of 1.0 means no loss (pulse is at beam centre); smaller
        values indicate higher loss at the burst edges.

    Notes
    -----
    The maximum scalloping loss occurs at the first and last pulses of a
    burst, where the target is near the 3 dB edge of the beam.  The model
    uses a normalised sinc² approximation of the two-way azimuth beam:

        G(u) = sinc²(u)   where  u = az_offset / az_beamwidth

    with the burst spanning u ∈ [-0.5, 0.5] (i.e. within the 3 dB width).
    """
    if burst_length < 1:
        raise ValueError(f"burst_length must be >= 1, got {burst_length}")
    if az_beamwidth <= 0:
        raise ValueError(f"az_beamwidth must be > 0, got {az_beamwidth}")

    if burst_length == 1:
        # Single pulse: no scalloping possible, assume beam centre
        return 1.0

    # Normalised position within burst: -0.5 (first pulse) to +0.5 (last pulse)
    norm_pos = (pulse_in_burst / (burst_length - 1)) - 0.5  # in [-0.5, 0.5]

    # Map to angular position within the 3 dB beamwidth.
    # At norm_pos = ±0.5 the target is at the ±az_beamwidth/2 beam edge.
    u = norm_pos  # already in [-0.5, 0.5]; sinc argument

    # Two-way sinc² pattern: sinc(u)² where sinc = sin(pi*u)/(pi*u)
    if abs(u) < 1e-14:
        one_way_pattern = 1.0
    else:
        one_way_pattern = math.sin(math.pi * u) / (math.pi * u)

    two_way_pattern = one_way_pattern**2  # transmit × receive

    # Normalise so the peak (u=0) gives loss = 1.0
    return float(two_way_pattern)


__all__ = [
    "compute_beam_direction",
    "compute_two_way_gain",
    "compute_look_angles",
    "scalloping_loss",
]
