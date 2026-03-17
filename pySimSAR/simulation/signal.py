"""Echo signal computation for SAR simulation.

Computes per-target echo contributions including:
- Round-trip delay and phase from range equation
- R^4 path loss (radar range equation amplitude)
- Two-way antenna gain
- Phase noise range decorrelation
- Target velocity (Doppler)
"""

from __future__ import annotations

import numpy as np

from pySimSAR.core.radar import C_LIGHT, Radar


def compute_range(platform_pos: np.ndarray, target_pos: np.ndarray) -> float:
    """Compute one-way slant range from platform to target.

    Parameters
    ----------
    platform_pos : np.ndarray
        Platform position in ENU [x, y, z], shape (3,).
    target_pos : np.ndarray
        Target position in ENU [x, y, z], shape (3,).

    Returns
    -------
    float
        One-way slant range in meters.
    """
    return float(np.linalg.norm(target_pos - platform_pos))


def compute_round_trip_delay(slant_range: float) -> float:
    """Compute round-trip propagation delay.

    Parameters
    ----------
    slant_range : float
        One-way slant range in meters.

    Returns
    -------
    float
        Round-trip delay in seconds (2*R/c).
    """
    return 2.0 * slant_range / C_LIGHT


def compute_echo_phase(carrier_freq: float, slant_range: float) -> float:
    """Compute echo phase from the range equation.

    Parameters
    ----------
    carrier_freq : float
        Carrier frequency in Hz.
    slant_range : float
        One-way slant range in meters.

    Returns
    -------
    float
        Echo phase in radians: -4*pi*fc*R/c.
    """
    return -4.0 * np.pi * carrier_freq * slant_range / C_LIGHT


def compute_path_loss(
    slant_range: float,
    wavelength: float,
    transmit_power: float,
    system_losses_dB: float,
    receiver_gain_dB: float = 0.0,
) -> float:
    """Compute received signal amplitude factor from the radar range equation.

    The radar range equation gives received power as:
        P_r = (P_t * G_rx * lambda^2 * sigma) / ((4*pi)^3 * R^4 * L)

    This function returns the amplitude factor excluding RCS and antenna gains:
        A = sqrt(P_t * G_rx * lambda^2 / ((4*pi)^3 * R^4 * L))

    Parameters
    ----------
    slant_range : float
        One-way slant range in meters.
    wavelength : float
        Radar wavelength in meters.
    transmit_power : float
        Transmit power in Watts.
    system_losses_dB : float
        System losses in dB.
    receiver_gain_dB : float
        Receiver gain in dB (default 0.0).

    Returns
    -------
    float
        Amplitude scaling factor (linear).
    """
    if slant_range <= 0:
        return 0.0
    losses_linear = 10.0 ** (system_losses_dB / 10.0)
    g_rx_linear = 10.0 ** (receiver_gain_dB / 10.0)
    numerator = transmit_power * g_rx_linear * wavelength**2
    denominator = (4.0 * np.pi) ** 3 * slant_range**4 * losses_linear
    return float(np.sqrt(numerator / denominator))


def compute_doppler_phase(
    carrier_freq: float,
    platform_pos: np.ndarray,
    target_pos: np.ndarray,
    target_velocity: np.ndarray | None,
    time: float,
) -> float:
    """Compute additional Doppler phase from target radial velocity.

    Parameters
    ----------
    carrier_freq : float
        Carrier frequency in Hz.
    platform_pos : np.ndarray
        Platform position in ENU, shape (3,).
    target_pos : np.ndarray
        Target position in ENU, shape (3,).
    target_velocity : np.ndarray | None
        Target velocity [vx, vy, vz] in m/s, shape (3,), or None.
    time : float
        Time since start of acquisition in seconds.

    Returns
    -------
    float
        Additional Doppler phase in radians from target motion.
    """
    if target_velocity is None:
        return 0.0

    # Radial velocity component: v dot unit_range_vector
    diff = target_pos - platform_pos
    r = np.linalg.norm(diff)
    if r == 0:
        return 0.0
    unit_range = diff / r
    v_radial = float(np.dot(target_velocity, unit_range))

    # Doppler phase: -4*pi*v_r*t/lambda
    wavelength = C_LIGHT / carrier_freq
    return -4.0 * np.pi * v_radial * time / wavelength


def compute_phase_noise_decorrelation(
    phase_noise: np.ndarray,
    delay_samples: int,
) -> np.ndarray:
    """Compute residual phase noise after range decorrelation.

    For a target at round-trip delay tau (in samples), the residual
    phase noise is: delta_phi(t) = phi(t) - phi(t - tau).

    Close targets (small tau): noise samples are correlated -> cancels.
    Far targets (large tau): noise decorrelates -> elevated noise floor.

    Parameters
    ----------
    phase_noise : np.ndarray
        Phase noise vector in radians, shape (n_samples,).
    delay_samples : int
        Round-trip delay in samples.

    Returns
    -------
    np.ndarray
        Residual phase noise, shape (n_samples,).
    """
    n = len(phase_noise)
    if delay_samples <= 0 or delay_samples >= n:
        return phase_noise.copy()
    delayed = np.zeros_like(phase_noise)
    delayed[delay_samples:] = phase_noise[: n - delay_samples]
    return phase_noise - delayed


def compute_target_echo(
    radar: Radar,
    platform_pos: np.ndarray,
    platform_vel: np.ndarray,
    target_pos: np.ndarray,
    target_rcs: float,
    sample_rate: float,
    n_samples: int,
    time: float,
    two_way_gain_linear: float = 1.0,
    target_velocity: np.ndarray | None = None,
    tx_signal: np.ndarray | None = None,
    phase_noise: np.ndarray | None = None,
    gate_delay: float = 0.0,
) -> np.ndarray:
    """Compute the echo signal from a single point target for one pulse.

    Parameters
    ----------
    radar : Radar
        Radar configuration.
    platform_pos : np.ndarray
        Platform position in ENU [x, y, z], shape (3,).
    platform_vel : np.ndarray
        Platform velocity in ENU [vx, vy, vz], shape (3,).
    target_pos : np.ndarray
        Target position in ENU [x, y, z], shape (3,).
    target_rcs : float
        Target radar cross section in m^2.
    sample_rate : float
        Range sampling rate in Hz.
    n_samples : int
        Number of range samples per pulse.
    time : float
        Time of this pulse since start of acquisition.
    two_way_gain_linear : float
        Two-way antenna gain in linear scale.
    target_velocity : np.ndarray | None
        Target velocity [vx, vy, vz] m/s, or None.
    tx_signal : np.ndarray | None
        Transmit waveform samples. If provided, used as reference for
        echo waveform modulation.
    phase_noise : np.ndarray | None
        Phase noise vector for this pulse. If provided, range
        decorrelation is applied.
    gate_delay : float
        Range gate start delay in seconds. The first sample in the
        output corresponds to this round-trip delay.

    Returns
    -------
    np.ndarray
        Complex echo signal, shape (n_samples,).
    """
    echo = np.zeros(n_samples, dtype=complex)

    slant_range = compute_range(platform_pos, target_pos)
    if slant_range <= 0:
        return echo

    # Round-trip delay relative to range gate start
    delay = compute_round_trip_delay(slant_range) - gate_delay
    delay_samples = int(np.round(delay * sample_rate))

    if delay_samples < 0 or delay_samples >= n_samples:
        return echo

    # Amplitude from radar range equation (excluding RCS and antenna gain)
    amplitude = compute_path_loss(
        slant_range, radar.wavelength, radar.transmit_power, radar.system_losses,
        getattr(radar, 'receiver_gain', 0.0),
    )
    # Include RCS and two-way gain
    amplitude *= np.sqrt(target_rcs) * np.sqrt(two_way_gain_linear)

    # Phase from range equation
    range_phase = compute_echo_phase(radar.carrier_freq, slant_range)

    # Additional Doppler phase from target motion
    doppler_phase = compute_doppler_phase(
        radar.carrier_freq, platform_pos, target_pos, target_velocity, time
    )

    total_phase = range_phase + doppler_phase

    # Place echo at correct delay
    if tx_signal is not None:
        # Modulate with delayed transmit waveform
        n_tx = len(tx_signal)
        end_idx = min(delay_samples + n_tx, n_samples)
        n_copy = end_idx - delay_samples
        if n_copy > 0 and delay_samples >= 0:
            echo[delay_samples:end_idx] = (
                amplitude * tx_signal[:n_copy] * np.exp(1j * total_phase)
            )
    else:
        # Delta function echo at the delay bin
        if 0 <= delay_samples < n_samples:
            echo[delay_samples] = amplitude * np.exp(1j * total_phase)

    # Apply phase noise range decorrelation
    if phase_noise is not None and len(phase_noise) == n_samples:
        residual_pn = compute_phase_noise_decorrelation(phase_noise, delay_samples)
        echo = echo * np.exp(1j * residual_pn)

    return echo


def compute_distributed_target_echoes(
    radar: Radar,
    platform_pos: np.ndarray,
    platform_vel: np.ndarray,
    origin: np.ndarray,
    cell_size: float,
    reflectivity: np.ndarray,
    elevation: np.ndarray | None,
    sample_rate: float,
    n_samples: int,
    time: float,
    two_way_gain_func=None,
    tx_signal: np.ndarray | None = None,
    phase_noise: np.ndarray | None = None,
    gate_delay: float = 0.0,
) -> np.ndarray:
    """Compute echo from a distributed target grid.

    Each cell in the grid is treated as a point scatterer with RCS
    equal to reflectivity * cell_size^2.

    Parameters
    ----------
    radar : Radar
        Radar configuration.
    platform_pos : np.ndarray
        Platform position in ENU, shape (3,).
    platform_vel : np.ndarray
        Platform velocity in ENU, shape (3,).
    origin : np.ndarray
        Grid corner position in ENU, shape (3,).
    cell_size : float
        Grid cell spacing in meters.
    reflectivity : np.ndarray
        Reflectivity per cell, shape (ny, nx).
    elevation : np.ndarray | None
        Elevation offset per cell, shape (ny, nx), or None.
    sample_rate : float
        Range sampling rate in Hz.
    n_samples : int
        Number of range samples.
    time : float
        Pulse time since start.
    two_way_gain_func : callable | None
        Function(target_pos) -> two_way_gain_linear. If None, gain=1.
    tx_signal : np.ndarray | None
        Transmit waveform.
    phase_noise : np.ndarray | None
        Phase noise vector.

    Returns
    -------
    np.ndarray
        Summed echo from all grid cells, shape (n_samples,).
    """
    echo = np.zeros(n_samples, dtype=complex)
    ny, nx = reflectivity.shape
    cell_area = cell_size**2

    for iy in range(ny):
        for ix in range(nx):
            if reflectivity[iy, ix] <= 0:
                continue

            # Cell center position
            cell_pos = origin.copy()
            cell_pos[0] += (ix + 0.5) * cell_size  # East
            cell_pos[1] += (iy + 0.5) * cell_size  # North
            if elevation is not None:
                cell_pos[2] += elevation[iy, ix]

            rcs = float(reflectivity[iy, ix]) * cell_area

            gain = 1.0
            if two_way_gain_func is not None:
                gain = two_way_gain_func(cell_pos)

            echo += compute_target_echo(
                radar=radar,
                platform_pos=platform_pos,
                platform_vel=platform_vel,
                target_pos=cell_pos,
                target_rcs=rcs,
                sample_rate=sample_rate,
                n_samples=n_samples,
                time=time,
                two_way_gain_linear=gain,
                tx_signal=tx_signal,
                phase_noise=phase_noise,
                gate_delay=gate_delay,
            )

    return echo


__all__ = [
    "compute_range",
    "compute_round_trip_delay",
    "compute_echo_phase",
    "compute_path_loss",
    "compute_doppler_phase",
    "compute_phase_noise_decorrelation",
    "compute_target_echo",
    "compute_distributed_target_echoes",
]
