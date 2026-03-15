"""Integration tests for motion compensation algorithms (T083-T084).

Tests verify:
- First-order MoCo corrects bulk phase errors from known position offsets
- Second-order MoCo provides additional range-dependent correction
- Both algorithms satisfy the MotionCompensationAlgorithm contract
- MoCo improves image focus for data with motion-induced errors
"""

from __future__ import annotations

import numpy as np
import pytest

from pySimSAR.algorithms.base import MotionCompensationAlgorithm
from pySimSAR.core.radar import AntennaPattern, C_LIGHT, Radar
from pySimSAR.core.scene import PointTarget, Scene
from pySimSAR.core.types import RawData, SARImage
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.sensors.nav_data import NavigationData
from pySimSAR.simulation.engine import SimulationEngine

# Scene center for all tests — the approximate target location
SCENE_CENTER = np.array([5000.0, 0.0, 0.0])


def _make_isotropic_antenna(peak_gain_dB: float = 30.0) -> AntennaPattern:
    """Create an isotropic antenna for test."""
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


def _make_radar() -> Radar:
    """Create a test radar with LFM waveform."""
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
        mode="stripmap",
        look_side="right",
        depression_angle=0.7,
    )


def _simulate_ideal(
    n_pulses: int = 256,
) -> tuple[RawData, Trajectory, Radar]:
    """Simulate a point target with an ideal trajectory.

    Returns
    -------
    tuple of (raw_data, trajectory, radar)
    """
    scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
    scene.add_target(PointTarget(position=SCENE_CENTER, rcs=10.0))

    radar = _make_radar()
    sample_rate = 2.0 * radar.bandwidth

    engine = SimulationEngine(
        scene=scene,
        radar=radar,
        n_pulses=n_pulses,
        platform_start=np.array([0.0, -5000.0, 2000.0]),
        platform_velocity=np.array([0.0, 100.0, 0.0]),
        seed=42,
        sample_rate=sample_rate,
    )

    result = engine.run()

    raw_data = RawData(
        echo=result.echo["single"],
        channel="single",
        sample_rate=sample_rate,
        carrier_freq=radar.carrier_freq,
        bandwidth=radar.bandwidth,
        prf=radar.prf,
        waveform_name=radar.waveform.name,
        sar_mode="stripmap",
    )

    trajectory = Trajectory(
        time=result.pulse_times,
        position=result.positions,
        velocity=result.velocities,
        attitude=np.zeros((n_pulses, 3)),
    )

    return raw_data, trajectory, radar


def _inject_motion_phase_error(
    raw_data: RawData,
    ideal_traj: Trajectory,
    position_offsets: np.ndarray,
    target_pos: np.ndarray,
) -> tuple[RawData, NavigationData]:
    """Inject known phase errors by simulating position offsets.

    The phase error matches the simulation convention:
        echo_phase = -4*pi/lambda * R

    Parameters
    ----------
    raw_data : RawData
        Ideal echo data.
    ideal_traj : Trajectory
        Ideal trajectory.
    position_offsets : np.ndarray
        Position offsets per pulse, shape (n_az, 3).
    target_pos : np.ndarray
        Target position for computing range change.

    Returns
    -------
    tuple of (perturbed_raw_data, nav_data)
    """
    wavelength = C_LIGHT / raw_data.carrier_freq
    perturbed_pos = ideal_traj.position + position_offsets

    # Range change per pulse
    r_ideal = np.linalg.norm(target_pos - ideal_traj.position, axis=1)
    r_perturbed = np.linalg.norm(target_pos - perturbed_pos, axis=1)
    delta_r = r_perturbed - r_ideal

    # Phase error: -4*pi/lambda * dR (matches compute_echo_phase convention)
    phase_error = -4.0 * np.pi / wavelength * delta_r

    echo = raw_data.echo.copy()
    echo *= np.exp(1j * phase_error)[:, np.newaxis]

    perturbed_raw = RawData(
        echo=echo,
        channel=raw_data.channel,
        sample_rate=raw_data.sample_rate,
        carrier_freq=raw_data.carrier_freq,
        bandwidth=raw_data.bandwidth,
        prf=raw_data.prf,
        waveform_name=raw_data.waveform_name,
        sar_mode=raw_data.sar_mode,
    )

    nav_data = NavigationData(
        time=ideal_traj.time,
        position=perturbed_pos,
        velocity=ideal_traj.velocity,
        source="fused",
    )

    return perturbed_raw, nav_data


def _image_peak_quality(image: SARImage) -> float:
    """Compute peak-to-mean ratio in dB as a focus quality metric."""
    magnitude = np.abs(image.data)
    peak_val = np.max(magnitude)
    mean_val = np.mean(magnitude)
    if mean_val > 0:
        return 20.0 * np.log10(peak_val / mean_val)
    return 0.0


class TestFirstOrderMoCo:
    """T083: Integration test for FirstOrderMoCo (phase error reduction)."""

    def test_satisfies_abc(self):
        """FirstOrderMoCo is a MotionCompensationAlgorithm."""
        from pySimSAR.algorithms.moco.first_order import FirstOrderMoCo

        moco = FirstOrderMoCo()
        assert isinstance(moco, MotionCompensationAlgorithm)
        assert moco.name == "first_order"
        assert moco.order == 1

    def test_returns_raw_data(self):
        """compensate() returns a RawData object with same shape."""
        from pySimSAR.algorithms.moco.first_order import FirstOrderMoCo

        raw_data, traj, radar = _simulate_ideal(n_pulses=64)
        offsets = 0.5 * np.random.RandomState(123).randn(64, 3)
        perturbed_raw, nav_data = _inject_motion_phase_error(
            raw_data, traj, offsets, SCENE_CENTER
        )

        moco = FirstOrderMoCo(scene_center=SCENE_CENTER)
        compensated = moco.compensate(perturbed_raw, nav_data, traj)

        assert isinstance(compensated, RawData)
        assert compensated.echo.shape == raw_data.echo.shape
        assert compensated.channel == raw_data.channel
        assert compensated.carrier_freq == raw_data.carrier_freq
        assert compensated.prf == raw_data.prf

    def test_corrects_known_phase_error(self):
        """First-order MoCo corrects a known bulk phase error."""
        from pySimSAR.algorithms.moco.first_order import FirstOrderMoCo

        n_pulses = 128
        raw_data, traj, radar = _simulate_ideal(n_pulses=n_pulses)

        # Sinusoidal cross-track oscillation
        t = np.arange(n_pulses) / radar.prf
        offsets = np.zeros((n_pulses, 3))
        offsets[:, 0] = 0.3 * np.sin(2 * np.pi * 5.0 * t)

        perturbed_raw, nav_data = _inject_motion_phase_error(
            raw_data, traj, offsets, SCENE_CENTER
        )

        # Measure phase error before MoCo
        mid_bin = raw_data.echo.shape[1] // 2
        phase_ideal = np.angle(raw_data.echo[:, mid_bin])
        phase_before = np.angle(perturbed_raw.echo[:, mid_bin])
        error_before = np.sqrt(np.mean(
            np.angle(np.exp(1j * (phase_before - phase_ideal))) ** 2
        ))

        # Apply MoCo with known scene center
        moco = FirstOrderMoCo(scene_center=SCENE_CENTER)
        compensated = moco.compensate(perturbed_raw, nav_data, traj)

        phase_after = np.angle(compensated.echo[:, mid_bin])
        error_after = np.sqrt(np.mean(
            np.angle(np.exp(1j * (phase_after - phase_ideal))) ** 2
        ))

        assert error_after < error_before * 0.5, (
            f"First-order MoCo did not sufficiently reduce phase error: "
            f"before={error_before:.4f}, after={error_after:.4f}"
        )

    def test_no_perturbation_is_identity(self):
        """When nav_data matches reference track, compensation is identity."""
        from pySimSAR.algorithms.moco.first_order import FirstOrderMoCo

        n_pulses = 64
        raw_data, traj, _ = _simulate_ideal(n_pulses=n_pulses)

        nav_data = NavigationData(
            time=traj.time,
            position=traj.position,
            velocity=traj.velocity,
            source="fused",
        )

        moco = FirstOrderMoCo(scene_center=SCENE_CENTER)
        compensated = moco.compensate(raw_data, nav_data, traj)

        np.testing.assert_allclose(
            np.abs(compensated.echo),
            np.abs(raw_data.echo),
            rtol=1e-10,
            err_msg="Magnitude should be unchanged when no motion error",
        )

    def test_restores_ideal_image_quality(self):
        """First-order MoCo restores image quality to ideal level."""
        from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm
        from pySimSAR.algorithms.moco.first_order import FirstOrderMoCo

        n_pulses = 256
        raw_data, traj, radar = _simulate_ideal(n_pulses=n_pulses)

        # Inject cross-track oscillation
        t = np.arange(n_pulses) / radar.prf
        offsets = np.zeros((n_pulses, 3))
        offsets[:, 0] = 0.5 * np.sin(2 * np.pi * 3.0 * t)

        perturbed_raw, nav_data = _inject_motion_phase_error(
            raw_data, traj, offsets, SCENE_CENTER
        )

        rda = RangeDopplerAlgorithm()

        # Ideal image
        img_ideal = rda.process(raw_data, radar, traj)
        pmr_ideal = _image_peak_quality(img_ideal)

        # Image after MoCo — should match ideal since correction is exact
        moco = FirstOrderMoCo(scene_center=SCENE_CENTER)
        compensated = moco.compensate(perturbed_raw, nav_data, traj)
        img_moco = rda.process(compensated, radar, traj)
        pmr_moco = _image_peak_quality(img_moco)

        # MoCo restores to within 0.5 dB of ideal
        assert abs(pmr_moco - pmr_ideal) < 0.5, (
            f"MoCo did not restore ideal image quality: "
            f"ideal={pmr_ideal:.1f} dB, moco={pmr_moco:.1f} dB"
        )

    def test_registered_in_moco_registry(self):
        """FirstOrderMoCo is discoverable via the moco registry."""
        from pySimSAR.algorithms.moco import moco_registry

        assert "first_order" in moco_registry
        cls = moco_registry.get("first_order")
        assert cls.name == "first_order"


class TestSecondOrderMoCo:
    """T084: Integration test for SecondOrderMoCo."""

    def test_satisfies_abc(self):
        """SecondOrderMoCo is a MotionCompensationAlgorithm."""
        from pySimSAR.algorithms.moco.second_order import SecondOrderMoCo

        moco = SecondOrderMoCo()
        assert isinstance(moco, MotionCompensationAlgorithm)
        assert moco.name == "second_order"
        assert moco.order == 2

    def test_returns_raw_data(self):
        """compensate() returns a RawData object with same shape."""
        from pySimSAR.algorithms.moco.second_order import SecondOrderMoCo

        raw_data, traj, _ = _simulate_ideal(n_pulses=64)
        offsets = 0.5 * np.random.RandomState(123).randn(64, 3)
        perturbed_raw, nav_data = _inject_motion_phase_error(
            raw_data, traj, offsets, SCENE_CENTER
        )

        moco = SecondOrderMoCo(scene_center=SCENE_CENTER)
        compensated = moco.compensate(perturbed_raw, nav_data, traj)

        assert isinstance(compensated, RawData)
        assert compensated.echo.shape == raw_data.echo.shape

    def test_corrects_known_phase_error(self):
        """Second-order MoCo corrects phase errors from position offsets."""
        from pySimSAR.algorithms.moco.second_order import SecondOrderMoCo

        n_pulses = 128
        raw_data, traj, radar = _simulate_ideal(n_pulses=n_pulses)

        # Cross-track + vertical oscillation
        t = np.arange(n_pulses) / radar.prf
        offsets = np.zeros((n_pulses, 3))
        offsets[:, 0] = 0.3 * np.sin(2 * np.pi * 5.0 * t)
        offsets[:, 2] = 0.2 * np.cos(2 * np.pi * 3.0 * t)

        perturbed_raw, nav_data = _inject_motion_phase_error(
            raw_data, traj, offsets, SCENE_CENTER
        )

        mid_bin = raw_data.echo.shape[1] // 2
        phase_ideal = np.angle(raw_data.echo[:, mid_bin])
        phase_before = np.angle(perturbed_raw.echo[:, mid_bin])
        error_before = np.sqrt(np.mean(
            np.angle(np.exp(1j * (phase_before - phase_ideal))) ** 2
        ))

        moco = SecondOrderMoCo(scene_center=SCENE_CENTER)
        compensated = moco.compensate(perturbed_raw, nav_data, traj)

        phase_after = np.angle(compensated.echo[:, mid_bin])
        error_after = np.sqrt(np.mean(
            np.angle(np.exp(1j * (phase_after - phase_ideal))) ** 2
        ))

        assert error_after < error_before * 0.5, (
            f"Second-order MoCo did not sufficiently reduce phase error: "
            f"before={error_before:.4f}, after={error_after:.4f}"
        )

    def test_at_least_as_good_as_first_order(self):
        """Second-order MoCo produces at least as good image focus."""
        from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm
        from pySimSAR.algorithms.moco.first_order import FirstOrderMoCo
        from pySimSAR.algorithms.moco.second_order import SecondOrderMoCo

        n_pulses = 256
        raw_data, traj, radar = _simulate_ideal(n_pulses=n_pulses)

        t = np.arange(n_pulses) / radar.prf
        offsets = np.zeros((n_pulses, 3))
        offsets[:, 0] = 0.5 * np.sin(2 * np.pi * 3.0 * t)
        offsets[:, 2] = 0.3 * np.cos(2 * np.pi * 2.0 * t)

        perturbed_raw, nav_data = _inject_motion_phase_error(
            raw_data, traj, offsets, SCENE_CENTER
        )

        rda = RangeDopplerAlgorithm()

        first = FirstOrderMoCo(scene_center=SCENE_CENTER)
        comp_first = first.compensate(perturbed_raw, nav_data, traj)
        pmr_first = _image_peak_quality(rda.process(comp_first, radar, traj))

        second = SecondOrderMoCo(scene_center=SCENE_CENTER)
        comp_second = second.compensate(perturbed_raw, nav_data, traj)
        pmr_second = _image_peak_quality(rda.process(comp_second, radar, traj))

        assert pmr_second >= pmr_first * 0.99, (
            f"Second-order should be at least as good as first-order: "
            f"first={pmr_first:.1f} dB, second={pmr_second:.1f} dB"
        )

    def test_registered_in_moco_registry(self):
        """SecondOrderMoCo is discoverable via the moco registry."""
        from pySimSAR.algorithms.moco import moco_registry

        assert "second_order" in moco_registry
        cls = moco_registry.get("second_order")
        assert cls.name == "second_order"
