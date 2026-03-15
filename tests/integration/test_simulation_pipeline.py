"""Integration tests for the full simulation pipeline (T031).

Verifies: point target scene -> raw echo data -> phase accuracy.
The echo phase from a point target at range R must match the analytical
range equation: phi = -4*pi*fc*R/c, within 0.01 radians.
"""

from __future__ import annotations

import numpy as np
import pytest

from pySimSAR.core.radar import AntennaPattern, C_LIGHT, Radar
from pySimSAR.core.scene import PointTarget, Scene
from pySimSAR.simulation.engine import SimulationEngine


def _make_isotropic_antenna(peak_gain_dB: float = 30.0) -> AntennaPattern:
    """Create an isotropic antenna pattern for testing."""
    az = np.linspace(-np.pi, np.pi, 5)
    el = np.linspace(-np.pi / 2, np.pi / 2, 5)
    pattern = np.full((len(el), len(az)), peak_gain_dB)
    return AntennaPattern(
        pattern_2d=pattern,
        az_beamwidth=np.radians(10),
        el_beamwidth=np.radians(10),
        peak_gain_dB=peak_gain_dB,
        az_angles=az,
        el_angles=el,
    )


def _make_radar(mode: str = "stripmap") -> Radar:
    """Create a test radar configuration."""
    from pySimSAR.waveforms.lfm import LFMWaveform

    wf = LFMWaveform(bandwidth=150e6, duty_cycle=0.1)
    antenna = _make_isotropic_antenna()
    return Radar(
        carrier_freq=9.65e9,
        prf=1000.0,
        transmit_power=100.0,
        waveform=wf,
        antenna=antenna,
        polarization="single",
        mode=mode,
        look_side="right",
        depression_angle=0.7,
    )


class TestPointTargetPhaseAccuracy:
    """Verify end-to-end phase accuracy for point targets."""

    def test_single_point_target_echo_has_correct_phase(self):
        """After range compression, echo phase matches -4*pi*fc*R/c within 0.01 rad.

        We place a single point target at a known range, simulate the echo,
        range-compress it, and verify the compressed peak has the expected phase.
        """
        scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
        # Target at a range that produces an integer delay sample count
        # to minimize quantization-induced phase error.
        # Platform at origin, target along x-axis (broadside, same altitude).
        radar = _make_radar()
        sample_rate = 2.0 * radar.bandwidth
        # Choose range so that 2*R/c * sample_rate is an integer
        target_range = 5000.0  # will be adjusted
        delay_samples_exact = 2.0 * target_range / C_LIGHT * sample_rate
        # Round to nearest integer and compute back the exact range
        delay_samples_int = round(delay_samples_exact)
        target_range = delay_samples_int * C_LIGHT / (2.0 * sample_rate)

        target_pos = np.array([target_range, 0.0, 0.0])
        scene.add_target(PointTarget(position=target_pos, rcs=10.0))

        # Platform at origin, same altitude as target (no elevation offset)
        platform_start = np.array([0.0, 0.0, 0.0])
        platform_vel = np.array([0.0, 100.0, 0.0])

        engine = SimulationEngine(
            scene=scene,
            radar=radar,
            n_pulses=1,
            platform_start=platform_start,
            platform_velocity=platform_vel,
            seed=42,
            sample_rate=sample_rate,
        )

        result = engine.run()
        echo = result.echo["single"]

        assert echo.shape[0] == 1  # 1 pulse

        # Range compress the echo to find the target peak
        compressed = radar.waveform.range_compress(
            echo[0, :], radar.prf, sample_rate
        )
        peak_idx = np.argmax(np.abs(compressed))

        # Compute expected range from platform to target
        slant_range = np.linalg.norm(target_pos - platform_start)
        expected_delay_samples = int(
            np.round(2.0 * slant_range / C_LIGHT * sample_rate)
        )

        # Peak should be near the expected delay
        assert abs(peak_idx - expected_delay_samples) <= 2, (
            f"Peak at {peak_idx}, expected near {expected_delay_samples}"
        )

        # Check phase at the compressed peak
        echo_phase = np.angle(compressed[peak_idx])
        expected_phase = -4.0 * np.pi * radar.carrier_freq * slant_range / C_LIGHT
        expected_phase_wrapped = (expected_phase + np.pi) % (2 * np.pi) - np.pi

        phase_error = abs(echo_phase - expected_phase_wrapped)
        # Wrap phase error to [0, pi]
        if phase_error > np.pi:
            phase_error = 2 * np.pi - phase_error

        assert phase_error < 0.01, (
            f"Phase error {phase_error:.4f} rad exceeds 0.01 rad threshold. "
            f"Got {echo_phase:.4f}, expected {expected_phase_wrapped:.4f}"
        )

    def test_multiple_targets_produce_distinct_echoes(self):
        """Multiple point targets at different ranges produce distinct peaks."""
        scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
        ranges = [3000.0, 5000.0, 7000.0]
        for r in ranges:
            scene.add_target(PointTarget(position=[r, 0, 0], rcs=10.0))

        radar = _make_radar()
        sample_rate = 2.0 * radar.bandwidth

        engine = SimulationEngine(
            scene=scene,
            radar=radar,
            n_pulses=1,
            platform_start=np.array([0.0, 0.0, 2000.0]),
            platform_velocity=np.array([0.0, 100.0, 0.0]),
            seed=42,
            sample_rate=sample_rate,
        )

        result = engine.run()
        pulse_echo = result.echo["single"][0, :]
        magnitudes = np.abs(pulse_echo)

        # Find expected delay samples
        for r in ranges:
            slant_range = np.sqrt(r**2 + 2000.0**2)
            delay_samples = int(np.round(2.0 * slant_range / C_LIGHT * sample_rate))
            if delay_samples < len(pulse_echo):
                # There should be signal energy near this delay
                window = magnitudes[
                    max(0, delay_samples - 2) : min(len(magnitudes), delay_samples + 3)
                ]
                assert np.max(window) > 0, f"No echo found near range {r}m"

    def test_amplitude_follows_r4_falloff(self):
        """After range compression, peak amplitude scales with 1/R^2 (power ~ 1/R^4)."""
        r1, r2 = 5000.0, 10000.0
        scene1 = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
        scene1.add_target(PointTarget(position=[r1, 0, 0], rcs=10.0))

        scene2 = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
        scene2.add_target(PointTarget(position=[r2, 0, 0], rcs=10.0))

        radar = _make_radar()
        sample_rate = 2.0 * radar.bandwidth
        common_kwargs = dict(
            radar=radar,
            n_pulses=1,
            platform_start=np.array([0.0, 0.0, 0.0]),
            platform_velocity=np.array([0.0, 100.0, 0.0]),
            seed=42,
            sample_rate=sample_rate,
        )

        result1 = SimulationEngine(scene=scene1, **common_kwargs).run()
        result2 = SimulationEngine(scene=scene2, **common_kwargs).run()

        # Range-compress to get clean amplitude peaks
        comp1 = radar.waveform.range_compress(
            result1.echo["single"][0, :], radar.prf, sample_rate
        )
        comp2 = radar.waveform.range_compress(
            result2.echo["single"][0, :], radar.prf, sample_rate
        )

        amp1 = np.max(np.abs(comp1))
        amp2 = np.max(np.abs(comp2))

        # Amplitude ratio should be ~ (R2/R1)^2 = 4.0
        ratio = amp1 / amp2
        assert ratio == pytest.approx(4.0, rel=0.2), (
            f"Amplitude ratio {ratio:.2f}, expected ~4.0"
        )

    def test_receiver_noise_present(self):
        """Echo data contains receiver thermal noise even with no targets."""
        scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
        # No targets
        radar = _make_radar()

        engine = SimulationEngine(
            scene=scene,
            radar=radar,
            n_pulses=10,
            seed=42,
        )
        result = engine.run()
        echo = result.echo["single"]

        # Echo should not be all zeros (receiver noise is added)
        assert np.any(echo != 0), "Expected receiver noise in echo data"

    def test_quad_pol_produces_four_channels(self):
        """Quad-pol mode produces HH, HV, VH, VV echo channels."""
        scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
        smat = np.array([[1.0 + 0j, 0.1 + 0j], [0.1 + 0j, 0.8 + 0j]])
        scene.add_target(PointTarget(position=[5000.0, 0, 0], rcs=smat))

        from pySimSAR.waveforms.lfm import LFMWaveform

        wf = LFMWaveform(bandwidth=150e6, duty_cycle=0.1)
        antenna = _make_isotropic_antenna()
        radar = Radar(
            carrier_freq=9.65e9,
            prf=1000.0,
            transmit_power=100.0,
            waveform=wf,
            antenna=antenna,
            polarization="quad",
            mode="stripmap",
            look_side="right",
            depression_angle=0.7,
        )

        engine = SimulationEngine(
            scene=scene,
            radar=radar,
            n_pulses=1,
            seed=42,
        )
        result = engine.run()

        assert set(result.echo.keys()) == {"hh", "hv", "vh", "vv"}
        for ch, data in result.echo.items():
            assert data.shape[0] == 1

    def test_spotlight_mode_runs(self):
        """Spotlight mode simulation completes without error."""
        scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
        scene.add_target(PointTarget(position=[5000.0, 0, 0], rcs=10.0))

        radar = _make_radar(mode="spotlight")
        engine = SimulationEngine(
            scene=scene,
            radar=radar,
            n_pulses=10,
            scene_center=np.array([5000.0, 0.0, 0.0]),
            seed=42,
        )
        result = engine.run()
        assert result.echo["single"].shape == (10, engine._compute_n_range_samples())

    def test_scanmar_mode_runs(self):
        """Scan-SAR mode simulation completes without error."""
        scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
        scene.add_target(PointTarget(position=[5000.0, 0, 0], rcs=10.0))

        radar = _make_radar(mode="scanmar")
        engine = SimulationEngine(
            scene=scene,
            radar=radar,
            n_pulses=30,
            n_subswaths=3,
            burst_length=10,
            seed=42,
        )
        result = engine.run()
        assert result.echo["single"].shape[0] == 30

    def test_platform_positions_advance(self):
        """Platform positions change correctly between pulses."""
        scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
        radar = _make_radar()

        engine = SimulationEngine(
            scene=scene,
            radar=radar,
            n_pulses=10,
            platform_start=np.array([0.0, 0.0, 2000.0]),
            platform_velocity=np.array([0.0, 100.0, 0.0]),
            seed=42,
        )
        result = engine.run()

        # Check platform moves north
        assert result.positions[0, 1] < result.positions[-1, 1]
        # Velocity should be constant
        np.testing.assert_array_equal(result.velocities[0], result.velocities[-1])
