"""Numba-accelerated echo computation kernels.

Provides a batch function that computes echoes from all point targets
for one pulse in a single call.  Uses Numba JIT when available; falls
back to a vectorised NumPy implementation otherwise.
"""

from __future__ import annotations

import numpy as np

C_LIGHT = 299_792_458.0

# ------------------------------------------------------------------
# Numba kernel (compiled on first call, cached on disk)
# ------------------------------------------------------------------
try:
    import numba

    @numba.njit(cache=True)
    def _echo_kernel_numba(
        platform_pos,
        target_positions,
        target_rcs,
        target_gains,
        carrier_freq,
        wavelength,
        transmit_power,
        sys_loss_lin,
        rx_gain_lin,
        sample_rate,
        n_samples,
        time,
        tx_signal,
        gate_delay,
        target_velocities,
        has_velocity,
    ):
        echo = np.zeros(n_samples, dtype=numba.complex128)
        n_targets = target_positions.shape[0]
        n_tx = tx_signal.shape[0]

        four_pi_cubed = (4.0 * np.pi) ** 3
        neg4pi_fc_c = -4.0 * np.pi * carrier_freq / C_LIGHT
        two_over_c = 2.0 / C_LIGHT
        amp_const = transmit_power * rx_gain_lin * wavelength * wavelength / (
            four_pi_cubed * sys_loss_lin
        )

        for i in range(n_targets):
            dx = target_positions[i, 0] - platform_pos[0]
            dy = target_positions[i, 1] - platform_pos[1]
            dz = target_positions[i, 2] - platform_pos[2]
            R = np.sqrt(dx * dx + dy * dy + dz * dz)
            if R <= 0.0:
                continue

            delay = two_over_c * R - gate_delay
            delay_samples = int(round(delay * sample_rate))
            if delay_samples < 0 or delay_samples >= n_samples:
                continue

            R4 = R * R * R * R
            amplitude = np.sqrt(amp_const / R4)
            amplitude *= np.sqrt(target_rcs[i]) * np.sqrt(target_gains[i])

            total_phase = neg4pi_fc_c * R

            if has_velocity[i]:
                inv_R = 1.0 / R
                v_rad = (
                    target_velocities[i, 0] * dx * inv_R
                    + target_velocities[i, 1] * dy * inv_R
                    + target_velocities[i, 2] * dz * inv_R
                )
                total_phase += -4.0 * np.pi * v_rad * time / wavelength

            phasor = amplitude * np.exp(1j * total_phase)

            end_idx = min(delay_samples + n_tx, n_samples)
            for j in range(end_idx - delay_samples):
                echo[delay_samples + j] += phasor * tx_signal[j]

        return echo

    _HAS_NUMBA = True
except Exception:  # ImportError or numba compilation issue
    _HAS_NUMBA = False


# ------------------------------------------------------------------
# NumPy fallback (vectorised ranges/phases, loop only for placement)
# ------------------------------------------------------------------
def _echo_kernel_numpy(
    platform_pos,
    target_positions,
    target_rcs,
    target_gains,
    carrier_freq,
    wavelength,
    transmit_power,
    sys_loss_lin,
    rx_gain_lin,
    sample_rate,
    n_samples,
    time,
    tx_signal,
    gate_delay,
    target_velocities,
    has_velocity,
):
    echo = np.zeros(n_samples, dtype=complex)
    n_targets = target_positions.shape[0]
    if n_targets == 0:
        return echo

    # Vectorised range computation
    diff = target_positions - platform_pos  # (n_targets, 3)
    R = np.linalg.norm(diff, axis=1)  # (n_targets,)

    # Vectorised delay
    delay = 2.0 * R / C_LIGHT - gate_delay
    delay_samples = np.round(delay * sample_rate).astype(np.intp)

    # Valid targets mask
    valid = (R > 0) & (delay_samples >= 0) & (delay_samples < n_samples)
    if not np.any(valid):
        return echo

    # Vectorised amplitude
    amp_const = (
        transmit_power * rx_gain_lin * wavelength**2
        / ((4.0 * np.pi) ** 3 * sys_loss_lin)
    )
    amplitudes = np.sqrt(amp_const / R**4) * np.sqrt(target_rcs) * np.sqrt(
        target_gains
    )

    # Vectorised phase
    phases = -4.0 * np.pi * carrier_freq * R / C_LIGHT

    # Doppler phase for moving targets
    moving = valid & has_velocity
    if np.any(moving):
        unit = diff[moving] / R[moving, np.newaxis]
        v_rad = np.sum(target_velocities[moving] * unit, axis=1)
        phases[moving] += -4.0 * np.pi * v_rad * time / wavelength

    # Placement loop (unavoidable — targets go at different delays)
    n_tx = len(tx_signal)
    for i in np.where(valid)[0]:
        ds = delay_samples[i]
        end = min(ds + n_tx, n_samples)
        n_copy = end - ds
        if n_copy > 0:
            phasor = amplitudes[i] * np.exp(1j * phases[i])
            echo[ds:end] += phasor * tx_signal[:n_copy]

    return echo


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------
def compute_point_echoes_batch(
    platform_pos: np.ndarray,
    target_positions: np.ndarray,
    target_rcs: np.ndarray,
    target_gains: np.ndarray,
    carrier_freq: float,
    wavelength: float,
    transmit_power: float,
    system_losses_dB: float,
    receiver_gain_dB: float,
    sample_rate: float,
    n_samples: int,
    time: float,
    tx_signal: np.ndarray,
    gate_delay: float,
    target_velocities: np.ndarray | None = None,
    has_velocity: np.ndarray | None = None,
) -> np.ndarray:
    """Compute echoes from all point targets for one pulse.

    Parameters
    ----------
    platform_pos : (3,) array
    target_positions : (n_targets, 3) array
    target_rcs : (n_targets,) array, m^2
    target_gains : (n_targets,) two-way antenna gain, linear
    carrier_freq, wavelength, transmit_power : scalars
    system_losses_dB, receiver_gain_dB : dB
    sample_rate : Hz
    n_samples : int
    time : pulse time since start (s)
    tx_signal : (n_tx,) complex transmit waveform
    gate_delay : range-gate start delay (s)
    target_velocities : (n_targets, 3) or None
    has_velocity : (n_targets,) bool or None

    Returns
    -------
    (n_samples,) complex echo
    """
    n_targets = target_positions.shape[0]
    if n_targets == 0:
        return np.zeros(n_samples, dtype=complex)

    # Prepare velocity arrays
    if target_velocities is None:
        target_velocities = np.zeros((n_targets, 3))
        has_velocity = np.zeros(n_targets, dtype=np.bool_)
    elif has_velocity is None:
        has_velocity = np.ones(n_targets, dtype=np.bool_)

    # Convert dB → linear once
    sys_loss_lin = 10.0 ** (system_losses_dB / 10.0)
    rx_gain_lin = 10.0 ** (receiver_gain_dB / 10.0)

    # Ensure contiguous float64 arrays for Numba
    platform_pos = np.ascontiguousarray(platform_pos, dtype=np.float64)
    target_positions = np.ascontiguousarray(target_positions, dtype=np.float64)
    target_rcs = np.ascontiguousarray(target_rcs, dtype=np.float64)
    target_gains = np.ascontiguousarray(target_gains, dtype=np.float64)
    target_velocities = np.ascontiguousarray(target_velocities, dtype=np.float64)
    has_velocity = np.ascontiguousarray(has_velocity, dtype=np.bool_)
    tx_signal = np.ascontiguousarray(tx_signal, dtype=np.complex128)

    kernel = _echo_kernel_numba if _HAS_NUMBA else _echo_kernel_numpy
    return kernel(
        platform_pos,
        target_positions,
        target_rcs,
        target_gains,
        float(carrier_freq),
        float(wavelength),
        float(transmit_power),
        float(sys_loss_lin),
        float(rx_gain_lin),
        float(sample_rate),
        int(n_samples),
        float(time),
        tx_signal,
        float(gate_delay),
        target_velocities,
        has_velocity,
    )


__all__ = ["compute_point_echoes_batch"]
