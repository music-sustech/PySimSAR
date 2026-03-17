"""Simulation engine orchestrator for SAR raw signal generation.

Coordinates the pulse loop, target summation, receiver noise injection,
polarimetric channel handling, and SAR mode dispatch.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np

from typing import TYPE_CHECKING

from pySimSAR.core.radar import C_LIGHT, K_BOLTZMANN, Radar
from pySimSAR.core.scene import DistributedTarget, PointTarget, Scene
from pySimSAR.core.types import PolarizationChannel, PolarizationMode, SARMode

if TYPE_CHECKING:
    from pySimSAR.core.platform import Platform
from pySimSAR.simulation.antenna import (
    compute_beam_direction,
    compute_look_angles,
    compute_two_way_gain,
)
from pySimSAR.simulation.signal import (
    compute_distributed_target_echoes,
    compute_target_echo,
)


@dataclass
class SimulationResult:
    """Container for simulation output data.

    Attributes
    ----------
    echo : dict[str, np.ndarray]
        Echo data per polarization channel. Keys are channel names
        (e.g. "single", "hh", "hv", "vh", "vv"). Values are complex
        arrays of shape (n_pulses, n_range_samples).
    sample_rate : float
        Range sampling rate in Hz.
    positions : np.ndarray
        Platform positions per pulse, shape (n_pulses, 3).
    velocities : np.ndarray
        Platform velocities per pulse, shape (n_pulses, 3).
    pulse_times : np.ndarray
        Time of each pulse in seconds, shape (n_pulses,).
    ideal_trajectory : object | None
        Ideal (nominal) trajectory, if Platform was used.
    true_trajectory : object | None
        True (perturbed) trajectory used for echo computation.
    navigation_data : list | None
        Navigation sensor measurements (one per sensor).
    gate_delay : float
        Range gate start delay in seconds. The first range sample
        corresponds to this round-trip delay.
    """

    echo: dict[str, np.ndarray] = field(default_factory=dict)
    sample_rate: float = 0.0
    positions: np.ndarray = field(default_factory=lambda: np.empty(0))
    velocities: np.ndarray = field(default_factory=lambda: np.empty(0))
    pulse_times: np.ndarray = field(default_factory=lambda: np.empty(0))
    ideal_trajectory: object | None = None
    true_trajectory: object | None = None
    navigation_data: list | None = None
    gate_delay: float = 0.0

    def save(self, filepath: str, *, radar: object | None = None, **kwargs) -> None:
        """Save simulation results to HDF5.

        Parameters
        ----------
        filepath : str
            Output HDF5 file path.
        radar : Radar | None
            Radar config for populating RawData metadata. If None,
            stores echo data with minimal metadata.
        **kwargs
            Additional keyword arguments passed to write_hdf5.
        """
        from pySimSAR.io.hdf5_format import write_hdf5
        from pySimSAR.core.types import RawData

        raw_data = {}
        for ch, echo in self.echo.items():
            carrier_freq = 0.0
            bandwidth = 0.0
            prf = 0.0
            waveform_name = ""
            sar_mode = "stripmap"
            if radar is not None:
                carrier_freq = radar.carrier_freq
                bandwidth = radar.bandwidth
                prf = radar.prf
                waveform_name = radar.waveform.name
                sar_mode = radar.mode.value

            raw_data[ch] = RawData(
                echo=echo,
                channel=ch,
                sample_rate=self.sample_rate,
                carrier_freq=carrier_freq,
                bandwidth=bandwidth,
                prf=prf,
                waveform_name=waveform_name,
                sar_mode=sar_mode,
                gate_delay=self.gate_delay,
            )

        write_hdf5(
            filepath,
            raw_data=raw_data,
            trajectory=self.true_trajectory,
            navigation_data=self.navigation_data,
            **kwargs,
        )


class SimulationEngine:
    """SAR raw signal simulation orchestrator.

    Generates raw echo data by simulating the radar pulse loop over a
    scene of point and distributed targets. Supports stripmap, spotlight,
    and scan-SAR modes with single or quad-pol configurations.

    Parameters
    ----------
    scene : Scene
        Target scene definition.
    radar : Radar
        Radar system configuration.
    n_pulses : int
        Number of azimuth pulses to simulate.
    platform_velocity : np.ndarray | None
        Platform velocity vector [vx, vy, vz] in m/s. If None, defaults
        to [0, velocity, 0] for north-heading flight. Ignored if platform
        is provided.
    platform_start : np.ndarray | None
        Platform starting position [x, y, z] in ENU meters. Ignored if
        platform is provided.
    seed : int
        Random seed for reproducibility.
    sample_rate : float | None
        Range sampling rate in Hz. If None, defaults to 2 * bandwidth.
    scene_center : np.ndarray | None
        Scene center for spotlight mode, shape (3,). If None, uses (0,0,0).
    n_subswaths : int
        Number of sub-swaths for scan-SAR mode.
    burst_length : int
        Number of pulses per burst for scan-SAR mode.
    platform : Platform | None
        Platform configuration for trajectory and sensor generation.
        When provided, overrides platform_velocity and platform_start.
    swath_range : tuple[float, float] | None
        Range gate as (near_range_m, far_range_m). Limits the receive
        window to echoes from this slant-range interval. If None,
        auto-computed from scene targets with 20% margin.
    """

    def __init__(
        self,
        scene: Scene,
        radar: Radar,
        n_pulses: int = 256,
        platform_velocity: np.ndarray | None = None,
        platform_start: np.ndarray | None = None,
        seed: int = 42,
        sample_rate: float | None = None,
        scene_center: np.ndarray | None = None,
        n_subswaths: int = 3,
        burst_length: int = 20,
        platform: Platform | None = None,
        swath_range: tuple[float, float] | None = None,
    ) -> None:
        if n_pulses <= 0:
            raise ValueError(f"n_pulses must be positive, got {n_pulses}")

        self.scene = scene
        self.radar = radar
        self.n_pulses = n_pulses
        self.seed = seed
        self._platform = platform

        # Default sample rate: 3x bandwidth (oversampled for anti-aliasing
        # margin, RCMC interpolation accuracy, and sidelobe control)
        self.sample_rate = (
            sample_rate if sample_rate is not None else 3.0 * radar.bandwidth
        )

        # Platform motion defaults (used when no Platform object provided)
        if platform_velocity is not None:
            self._velocity = np.asarray(platform_velocity, dtype=float)
        else:
            self._velocity = np.array([0.0, 100.0, 0.0])

        if platform_start is not None:
            self._start_pos = np.asarray(platform_start, dtype=float)
        else:
            self._start_pos = np.array([0.0, -5000.0, 2000.0])

        self._scene_center = (
            np.asarray(scene_center, dtype=float)
            if scene_center is not None
            else np.array([0.0, 0.0, 0.0])
        )
        self._n_subswaths = n_subswaths
        self._burst_length = burst_length
        self._swath_range = swath_range

    @staticmethod
    def format_memory_size(size_bytes: int | float) -> str:
        """Format a byte count as a human-readable string.

        Parameters
        ----------
        size_bytes : int | float
            Size in bytes.

        Returns
        -------
        str
            Human-readable size string (e.g. "1.50 GB").
        """
        if size_bytes >= 1024**3:
            return f"{size_bytes / 1024**3:.2f} GB"
        elif size_bytes >= 1024**2:
            return f"{size_bytes / 1024**2:.2f} MB"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.2f} KB"
        else:
            return f"{size_bytes} bytes"

    def estimate_memory(self) -> int:
        """Estimate total memory usage for the simulation.

        Accounts for echo data (complex128 = 16 bytes per sample) across
        all polarization channels, plus working memory for FFT buffers
        (approximately 2x echo size).

        Returns
        -------
        int
            Estimated memory usage in bytes.

        Warns
        -----
        ResourceWarning
            If estimated memory exceeds 1 GB.
        """
        n_range = self._compute_n_range_samples()
        n_channels = len(self._get_channels())
        bytes_per_sample = 16  # complex128

        echo_bytes = self.n_pulses * n_range * n_channels * bytes_per_sample
        # Working memory: ~2x echo for FFT buffers and intermediate arrays
        total_bytes = echo_bytes * 3  # echo + 2x working

        one_gb = 1024**3
        if total_bytes > one_gb:
            warnings.warn(
                f"Estimated memory usage is {self.format_memory_size(total_bytes)} "
                f"({self.n_pulses} pulses x {n_range} range samples x "
                f"{n_channels} channels). Consider reducing simulation size.",
                ResourceWarning,
                stacklevel=2,
            )

        return total_bytes

    def _get_channels(self) -> list[str]:
        """Get polarization channels to simulate."""
        if self.radar.polarization == PolarizationMode.SINGLE:
            return [PolarizationChannel.SINGLE.value]
        elif self.radar.polarization == PolarizationMode.DUAL:
            return [PolarizationChannel.HH.value, PolarizationChannel.HV.value]
        else:  # QUAD
            return [
                PolarizationChannel.HH.value,
                PolarizationChannel.HV.value,
                PolarizationChannel.VH.value,
                PolarizationChannel.VV.value,
            ]

    def _get_rcs_for_channel(
        self, target: PointTarget, channel: str
    ) -> float:
        """Extract RCS for a specific polarization channel.

        Parameters
        ----------
        target : PointTarget
            Target with scalar or 2x2 scattering matrix RCS.
        channel : str
            Polarization channel name.

        Returns
        -------
        float
            RCS magnitude for this channel.
        """
        rcs = target.rcs
        if isinstance(rcs, (int, float)):
            return float(rcs)

        # 2x2 scattering matrix: [[HH, HV], [VH, VV]]
        idx_map = {"hh": (0, 0), "hv": (0, 1), "vh": (1, 0), "vv": (1, 1)}
        ch = channel.lower()
        if ch in idx_map:
            i, j = idx_map[ch]
            return float(np.abs(rcs[i, j]) ** 2)
        return float(np.abs(rcs[0, 0]) ** 2)

    def _get_distributed_reflectivity_for_channel(
        self, target: DistributedTarget, channel: str, seed: int | None = None
    ) -> np.ndarray:
        """Get reflectivity array for a specific channel.

        If the target has a clutter model and no reflectivity, generate it.
        For quad-pol with scattering matrix, extract the appropriate channel.
        """
        if target.scattering_matrix is not None:
            idx_map = {"hh": (0, 0), "hv": (0, 1), "vh": (1, 0), "vv": (1, 1)}
            ch = channel.lower()
            if ch in idx_map:
                i, j = idx_map[ch]
                return np.abs(target.scattering_matrix[:, :, i, j]) ** 2

        if target.reflectivity is not None:
            return target.reflectivity

        # Generate from clutter model
        if target.clutter_model is not None:
            return target.clutter_model.generate(
                (target.ny, target.nx), seed=seed
            )

        return np.zeros((target.ny, target.nx))

    def _compute_range_gate(self) -> tuple[float, int]:
        """Compute range gate delay and number of range samples.

        Returns
        -------
        gate_delay : float
            Round-trip delay to the near edge of the swath in seconds.
        n_samples : int
            Number of range samples in the receive window.
        """
        wf_duration = self.radar.waveform.duration(self.radar.prf)

        if self._swath_range is not None:
            near_range, far_range = self._swath_range
        else:
            # Auto-compute from scene targets
            near_range, far_range = self._auto_swath_range()

        gate_delay = 2.0 * near_range / C_LIGHT
        far_delay = 2.0 * far_range / C_LIGHT + wf_duration
        receive_window = far_delay - gate_delay

        # Clamp to PRI
        pri = self.radar.pri
        max_window = pri - wf_duration if wf_duration < pri else pri
        if receive_window > max_window:
            receive_window = max_window

        return gate_delay, int(receive_window * self.sample_rate)

    def _auto_swath_range(self) -> tuple[float, float]:
        """Auto-compute swath range from scene targets with 20% margin."""
        ranges = []

        # Use platform start position for range estimation
        if self._platform is not None:
            ref_pos = np.array([0.0, 0.0, self._platform.altitude])
            if self._platform.start_position is not None:
                ref_pos = self._platform.start_position
        else:
            ref_pos = self._start_pos

        for pt in self.scene.point_targets:
            ranges.append(float(np.linalg.norm(pt.position - ref_pos)))

        for dt in self.scene.distributed_targets:
            # Use corners of the distributed target
            corners = [
                dt.origin,
                dt.origin + np.array([dt.extent[0], 0, 0]),
                dt.origin + np.array([0, dt.extent[1], 0]),
                dt.origin + np.array([dt.extent[0], dt.extent[1], 0]),
            ]
            for c in corners:
                ranges.append(float(np.linalg.norm(c - ref_pos)))

        if not ranges:
            # No targets — fall back to full PRI
            pri = self.radar.pri
            wf_dur = self.radar.waveform.duration(self.radar.prf)
            max_range = C_LIGHT * (pri - wf_dur) / 2.0 if wf_dur < pri else C_LIGHT * pri / 2.0
            return 0.0, max_range

        r_min = min(ranges)
        r_max = max(ranges)
        extent = r_max - r_min
        margin = max(extent * 0.2, 100.0)  # at least 100 m margin

        return max(0.0, r_min - margin), r_max + margin

    def _compute_n_range_samples(self) -> int:
        """Compute number of range samples per pulse (backward compat)."""
        _, n = self._compute_range_gate()
        return n

    def _generate_receiver_noise(
        self, n_samples: int, rng: np.random.Generator
    ) -> np.ndarray:
        """Generate thermal receiver noise.

        Parameters
        ----------
        n_samples : int
            Number of samples.
        rng : np.random.Generator
            Random number generator.

        Returns
        -------
        np.ndarray
            Complex noise samples.
        """
        noise_power = self.radar.noise_power
        sigma = np.sqrt(noise_power / 2.0)
        return sigma * (
            rng.standard_normal(n_samples) + 1j * rng.standard_normal(n_samples)
        )

    def _generate_trajectories(self):
        """Generate platform trajectories.

        Returns
        -------
        tuple
            (ideal_trajectory, true_trajectory, navigation_data)
            If no Platform is set, trajectories are None and positions come
            from the simple velocity model.
        """
        if self._platform is None:
            return None, None, None

        ideal = self._platform.generate_ideal_trajectory(
            n_pulses=self.n_pulses, prf=self.radar.prf
        )
        true = self._platform.generate_perturbed_trajectory(
            n_pulses=self.n_pulses, prf=self.radar.prf, seed=self.seed
        )

        # Generate navigation data from each attached sensor
        nav_data_list = []
        for sensor in self._platform.sensors:
            nav = sensor.generate_measurements(true, seed=self.seed)
            nav_data_list.append(nav)

        return ideal, true, nav_data_list

    def run(self) -> SimulationResult:
        """Execute the simulation.

        Returns
        -------
        SimulationResult
            Container with echo data and metadata.
        """
        rng = np.random.default_rng(self.seed)
        channels = self._get_channels()
        gate_delay, n_range = self._compute_range_gate()
        pri = self.radar.pri

        # Generate trajectories if Platform is provided
        ideal_traj, true_traj, nav_data = self._generate_trajectories()

        # Generate transmit waveform
        tx_signal = self.radar.waveform.generate(self.radar.prf, self.sample_rate)

        # Pre-allocate echo matrices
        echoes: dict[str, np.ndarray] = {}
        for ch in channels:
            echoes[ch] = np.zeros((self.n_pulses, n_range), dtype=complex)

        # Platform trajectory arrays
        positions = np.zeros((self.n_pulses, 3))
        velocities = np.zeros((self.n_pulses, 3))
        pulse_times = np.zeros(self.n_pulses)

        for pulse_idx in range(self.n_pulses):
            t = pulse_idx * pri
            pulse_times[pulse_idx] = t

            # Platform position at this pulse
            if true_traj is not None:
                pos = true_traj.position[pulse_idx]
                vel = true_traj.velocity[pulse_idx]
            else:
                pos = self._start_pos + self._velocity * t
                vel = self._velocity.copy()

            positions[pulse_idx] = pos
            velocities[pulse_idx] = vel

            # Compute beam steering direction for this pulse
            steer_az, steer_el = compute_beam_direction(
                self.radar,
                pos,
                vel,
                pulse_idx,
                scene_center=self._scene_center,
                n_subswaths=self._n_subswaths,
                burst_length=self._burst_length,
            )

            # Generate phase noise for this pulse (if waveform has it)
            pulse_phase_noise = None
            if self.radar.waveform.phase_noise is not None:
                pulse_phase_noise = self.radar.waveform.phase_noise.generate(
                    n_range, self.sample_rate, seed=rng.integers(0, 2**31)
                )

            # Two-way gain helper
            def _gain_func(target_pos: np.ndarray) -> float:
                tgt_az, tgt_el = compute_look_angles(
                    self.radar, pos, target_pos, vel
                )
                return compute_two_way_gain(
                    self.radar, tgt_az, tgt_el, steer_az, steer_el
                )

            for ch in channels:
                pulse_echo = np.zeros(n_range, dtype=complex)

                # Point targets
                for target in self.scene.point_targets:
                    rcs = self._get_rcs_for_channel(target, ch)
                    gain = _gain_func(target.position)

                    pulse_echo += compute_target_echo(
                        radar=self.radar,
                        platform_pos=pos,
                        platform_vel=vel,
                        target_pos=target.position,
                        target_rcs=rcs,
                        sample_rate=self.sample_rate,
                        n_samples=n_range,
                        time=t,
                        two_way_gain_linear=gain,
                        target_velocity=target.velocity,
                        tx_signal=tx_signal,
                        phase_noise=pulse_phase_noise,
                        gate_delay=gate_delay,
                    )

                # Distributed targets
                for dtarget in self.scene.distributed_targets:
                    reflectivity = self._get_distributed_reflectivity_for_channel(
                        dtarget, ch, seed=rng.integers(0, 2**31)
                    )
                    pulse_echo += compute_distributed_target_echoes(
                        radar=self.radar,
                        platform_pos=pos,
                        platform_vel=vel,
                        origin=dtarget.origin,
                        cell_size=dtarget.cell_size,
                        reflectivity=reflectivity,
                        elevation=dtarget.elevation,
                        sample_rate=self.sample_rate,
                        n_samples=n_range,
                        time=t,
                        two_way_gain_func=_gain_func,
                        tx_signal=tx_signal,
                        phase_noise=pulse_phase_noise,
                        gate_delay=gate_delay,
                    )

                # Add receiver noise
                pulse_echo += self._generate_receiver_noise(n_range, rng)

                echoes[ch][pulse_idx, :] = pulse_echo

        return SimulationResult(
            echo=echoes,
            sample_rate=self.sample_rate,
            positions=positions,
            velocities=velocities,
            pulse_times=pulse_times,
            ideal_trajectory=ideal_traj,
            true_trajectory=true_traj,
            navigation_data=nav_data,
            gate_delay=gate_delay,
        )


__all__ = ["SimulationEngine", "SimulationResult"]
