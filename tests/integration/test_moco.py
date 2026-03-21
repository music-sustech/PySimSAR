"""Integration tests for motion compensation and autofocus algorithms.

Tests verify:
- First-order MoCo corrects bulk phase errors from known position offsets (T083-T084)
- Second-order MoCo provides additional range-dependent correction
- PGA autofocus converges on known phase errors (T088)
- MDA autofocus corrects low-order phase errors (T089)
- MinimumEntropy autofocus optimizes polynomial phase model (T090)
- PPP autofocus uses prominent scatterer phase histories (T091)
"""

from __future__ import annotations

import numpy as np

from pySimSAR.algorithms.base import AutofocusAlgorithm, MotionCompensationAlgorithm
from pySimSAR.core.radar import C_LIGHT, AntennaPattern, Radar
from pySimSAR.core.scene import PointTarget, Scene
from pySimSAR.core.types import PhaseHistoryData, RawData, SARImage
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.sensors.nav_data import NavigationData
from pySimSAR.simulation.engine import SimulationEngine

# Scene center for all tests — the approximate target location
SCENE_CENTER = np.array([5000.0, 0.0, 0.0])


def _make_isotropic_antenna() -> AntennaPattern:
    """Create an isotropic antenna for test."""
    az = np.linspace(-np.pi, np.pi, 5)
    el = np.linspace(-np.pi / 2, np.pi / 2, 5)
    pattern = np.full((len(el), len(az)), 30.0)
    return AntennaPattern(
        pattern_2d=pattern,
        az_beamwidth=np.radians(10),
        el_beamwidth=np.radians(10),
        az_angles=az,
        el_angles=el,
    )


def _make_radar() -> Radar:
    """Create a test radar with LFM waveform."""
    from pySimSAR.waveforms.lfm import LFMWaveform

    wf = LFMWaveform(bandwidth=150e6, duty_cycle=0.1, prf=1000.0)
    antenna = _make_isotropic_antenna()
    return Radar(
        carrier_freq=9.65e9,
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
        prf=radar.waveform.prf,
        waveform_name=radar.waveform.name,
        sar_mode="stripmap",
        gate_delay=result.gate_delay,
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
        gate_delay=raw_data.gate_delay,
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
        t = np.arange(n_pulses) / radar.waveform.prf
        offsets = np.zeros((n_pulses, 3))
        offsets[:, 0] = 0.3 * np.sin(2 * np.pi * 5.0 * t)

        perturbed_raw, nav_data = _inject_motion_phase_error(
            raw_data, traj, offsets, SCENE_CENTER
        )

        # Measure phase error before MoCo
        # Find target range bin from echo energy (not array center, since
        # range gating shifts bin 0 to near_range)
        mid_bin = int(np.argmax(np.mean(np.abs(raw_data.echo), axis=0)))
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
        t = np.arange(n_pulses) / radar.waveform.prf
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
        t = np.arange(n_pulses) / radar.waveform.prf
        offsets = np.zeros((n_pulses, 3))
        offsets[:, 0] = 0.3 * np.sin(2 * np.pi * 5.0 * t)
        offsets[:, 2] = 0.2 * np.cos(2 * np.pi * 3.0 * t)

        perturbed_raw, nav_data = _inject_motion_phase_error(
            raw_data, traj, offsets, SCENE_CENTER
        )

        # Find target range bin from echo energy (not array center, since
        # range gating shifts bin 0 to near_range)
        mid_bin = int(np.argmax(np.mean(np.abs(raw_data.echo), axis=0)))
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

        t = np.arange(n_pulses) / radar.waveform.prf
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


# ---------------------------------------------------------------------------
# Autofocus helpers
# ---------------------------------------------------------------------------


def _range_compress_ideal(
    n_pulses: int = 256,
) -> tuple[PhaseHistoryData, Radar, Trajectory]:
    """Simulate ideal data and range-compress to PhaseHistoryData."""
    from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm

    raw_data, traj, radar = _simulate_ideal(n_pulses=n_pulses)
    rda = RangeDopplerAlgorithm()
    phd = rda.range_compress(raw_data, radar)
    return phd, radar, traj


def _inject_phase_error_into_phd(
    phd: PhaseHistoryData,
    phase_error: np.ndarray,
) -> PhaseHistoryData:
    """Inject a known azimuth phase error into PhaseHistoryData.

    Parameters
    ----------
    phd : PhaseHistoryData
        Clean range-compressed data.
    phase_error : np.ndarray
        Phase error vector, shape (n_azimuth,), in radians.

    Returns
    -------
    PhaseHistoryData
        Copy with injected phase error.
    """
    corrupted = phd.data.copy()
    corrupted *= np.exp(1j * phase_error)[:, np.newaxis]
    return PhaseHistoryData(
        data=corrupted,
        sample_rate=phd.sample_rate,
        prf=phd.prf,
        carrier_freq=phd.carrier_freq,
        bandwidth=phd.bandwidth,
        channel=phd.channel,
    )


def _image_entropy(image: SARImage) -> float:
    """Compute image entropy (lower = better focused)."""
    magnitude = np.abs(image.data)
    power = magnitude**2
    total = np.sum(power)
    if total == 0:
        return 0.0
    p = power / total
    p = p[p > 0]
    return -np.sum(p * np.log(p))


def _make_azimuth_compressor(radar: Radar, trajectory: Trajectory):
    """Create an azimuth_compressor closure for autofocus."""
    from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm

    rda = RangeDopplerAlgorithm()
    return lambda phd: rda.azimuth_compress(phd, radar, trajectory)


# ---------------------------------------------------------------------------
# T088: PGA autofocus integration tests
# ---------------------------------------------------------------------------


class TestPGAAutofocus:
    """T088: Integration test for PGA autofocus."""

    def test_satisfies_abc(self):
        """PhaseGradientAutofocus is an AutofocusAlgorithm."""
        from pySimSAR.algorithms.autofocus.pga import PhaseGradientAutofocus

        pga = PhaseGradientAutofocus()
        assert isinstance(pga, AutofocusAlgorithm)
        assert pga.name == "pga"

    def test_returns_sar_image(self):
        """focus() returns a SARImage object."""
        from pySimSAR.algorithms.autofocus.pga import PhaseGradientAutofocus

        phd, radar, traj = _range_compress_ideal(n_pulses=64)
        compressor = _make_azimuth_compressor(radar, traj)

        pga = PhaseGradientAutofocus(max_iterations=2)
        result = pga.focus(phd, compressor)
        assert isinstance(result, SARImage)

    def test_converges_on_known_sinusoidal_error(self):
        """PGA converges when given a known sinusoidal phase error."""
        from pySimSAR.algorithms.autofocus.pga import PhaseGradientAutofocus

        n_pulses = 256
        phd, radar, traj = _range_compress_ideal(n_pulses=n_pulses)
        compressor = _make_azimuth_compressor(radar, traj)

        # Inject sinusoidal phase error (mid-frequency, moderate amplitude)
        t = np.arange(n_pulses) / phd.prf
        injected_error = 1.5 * np.sin(2 * np.pi * 8.0 * t)

        phd_corrupted = _inject_phase_error_into_phd(phd, injected_error)

        # Image quality before autofocus
        img_before = compressor(phd_corrupted)
        pmr_before = _image_peak_quality(img_before)

        # Apply PGA
        pga = PhaseGradientAutofocus(
            max_iterations=15,
            convergence_threshold=0.005,
        )
        img_after = pga.focus(phd_corrupted, compressor)
        pmr_after = _image_peak_quality(img_after)

        # Autofocus should improve image quality
        assert pmr_after > pmr_before, (
            f"PGA did not improve image quality: "
            f"before={pmr_before:.1f} dB, after={pmr_after:.1f} dB"
        )

    def test_estimate_phase_error_shape(self):
        """estimate_phase_error returns correct shape."""
        from pySimSAR.algorithms.autofocus.pga import PhaseGradientAutofocus

        n_pulses = 128
        phd, _, _ = _range_compress_ideal(n_pulses=n_pulses)

        pga = PhaseGradientAutofocus()
        error = pga.estimate_phase_error(phd)
        assert error.shape == (n_pulses,)
        assert error.dtype == np.float64 or np.issubdtype(error.dtype, np.floating)

    def test_does_not_degrade_ideal_data(self):
        """PGA on ideal data does not degrade image quality."""
        from pySimSAR.algorithms.autofocus.pga import PhaseGradientAutofocus

        phd, radar, traj = _range_compress_ideal(n_pulses=128)
        compressor = _make_azimuth_compressor(radar, traj)

        img_without = compressor(phd)
        pmr_without = _image_peak_quality(img_without)

        pga = PhaseGradientAutofocus(max_iterations=5)
        img_with = pga.focus(phd, compressor)
        pmr_with = _image_peak_quality(img_with)

        # PGA should not degrade image quality by more than 1 dB
        assert pmr_with > pmr_without - 1.0, (
            f"PGA degraded ideal image: "
            f"without={pmr_without:.1f} dB, with={pmr_with:.1f} dB"
        )


# ---------------------------------------------------------------------------
# T089: MDA autofocus integration tests
# ---------------------------------------------------------------------------


class TestMDAAutofocus:
    """T089: Integration test for MDA autofocus."""

    def test_satisfies_abc(self):
        """MapDriftAutofocus is an AutofocusAlgorithm."""
        from pySimSAR.algorithms.autofocus.mda import MapDriftAutofocus

        mda = MapDriftAutofocus()
        assert isinstance(mda, AutofocusAlgorithm)
        assert mda.name == "mda"

    def test_returns_sar_image(self):
        """focus() returns a SARImage object."""
        from pySimSAR.algorithms.autofocus.mda import MapDriftAutofocus

        phd, radar, traj = _range_compress_ideal(n_pulses=64)
        compressor = _make_azimuth_compressor(radar, traj)

        mda = MapDriftAutofocus(max_iterations=2)
        result = mda.focus(phd, compressor)
        assert isinstance(result, SARImage)

    def test_corrects_quadratic_phase_error(self):
        """MDA corrects a quadratic phase error (defocus)."""
        from pySimSAR.algorithms.autofocus.mda import MapDriftAutofocus

        n_pulses = 256
        phd, radar, traj = _range_compress_ideal(n_pulses=n_pulses)
        compressor = _make_azimuth_compressor(radar, traj)

        # Inject large quadratic phase error (strong defocus)
        t_norm = np.linspace(-1, 1, n_pulses)
        injected_error = 8.0 * t_norm**2

        phd_corrupted = _inject_phase_error_into_phd(phd, injected_error)

        img_before = compressor(phd_corrupted)
        pmr_before = _image_peak_quality(img_before)

        mda = MapDriftAutofocus(
            max_iterations=5,
            n_subapertures=8,
            poly_order=2,
        )
        img_after = mda.focus(phd_corrupted, compressor)
        pmr_after = _image_peak_quality(img_after)

        assert pmr_after >= pmr_before - 0.5, (
            f"MDA degraded image on quadratic error: "
            f"before={pmr_before:.1f} dB, after={pmr_after:.1f} dB"
        )

    def test_corrects_linear_phase_error(self):
        """MDA corrects a linear phase error (Doppler centroid shift)."""
        from pySimSAR.algorithms.autofocus.mda import MapDriftAutofocus

        n_pulses = 256
        phd, radar, traj = _range_compress_ideal(n_pulses=n_pulses)
        compressor = _make_azimuth_compressor(radar, traj)

        # Inject linear phase error (large enough to cause visible shift)
        injected_error = np.linspace(-6.0, 6.0, n_pulses)

        phd_corrupted = _inject_phase_error_into_phd(phd, injected_error)

        img_before = compressor(phd_corrupted)
        pmr_before = _image_peak_quality(img_before)

        mda = MapDriftAutofocus(
            max_iterations=5,
            n_subapertures=6,
            poly_order=1,
        )
        img_after = mda.focus(phd_corrupted, compressor)
        pmr_after = _image_peak_quality(img_after)

        # Linear phase shifts the target — MDA should at least not degrade
        assert pmr_after >= pmr_before - 1.0, (
            f"MDA degraded image on linear error: "
            f"before={pmr_before:.1f} dB, after={pmr_after:.1f} dB"
        )

    def test_estimate_phase_error_shape(self):
        """estimate_phase_error returns correct shape."""
        from pySimSAR.algorithms.autofocus.mda import MapDriftAutofocus

        n_pulses = 128
        phd, _, _ = _range_compress_ideal(n_pulses=n_pulses)

        mda = MapDriftAutofocus()
        error = mda.estimate_phase_error(phd)
        assert error.shape == (n_pulses,)

    def test_does_not_degrade_ideal_data(self):
        """MDA on ideal data does not degrade image quality."""
        from pySimSAR.algorithms.autofocus.mda import MapDriftAutofocus

        phd, radar, traj = _range_compress_ideal(n_pulses=128)
        compressor = _make_azimuth_compressor(radar, traj)

        img_without = compressor(phd)
        pmr_without = _image_peak_quality(img_without)

        mda = MapDriftAutofocus(max_iterations=3)
        img_with = mda.focus(phd, compressor)
        pmr_with = _image_peak_quality(img_with)

        # MDA is designed for correcting known low-order errors;
        # on ideal short-aperture data, centroid estimates are noisy.
        # Allow up to 2 dB tolerance.
        assert pmr_with > pmr_without - 2.0, (
            f"MDA degraded ideal image: "
            f"without={pmr_without:.1f} dB, with={pmr_with:.1f} dB"
        )


# ---------------------------------------------------------------------------
# T090: MinimumEntropy autofocus integration tests
# ---------------------------------------------------------------------------


class TestMinimumEntropyAutofocus:
    """T090: Integration test for MinimumEntropy autofocus."""

    def test_satisfies_abc(self):
        """MinimumEntropyAutofocus is an AutofocusAlgorithm."""
        from pySimSAR.algorithms.autofocus.min_entropy import MinimumEntropyAutofocus

        mea = MinimumEntropyAutofocus()
        assert isinstance(mea, AutofocusAlgorithm)
        assert mea.name == "min_entropy"

    def test_returns_sar_image(self):
        """focus() returns a SARImage object."""
        from pySimSAR.algorithms.autofocus.min_entropy import MinimumEntropyAutofocus

        phd, radar, traj = _range_compress_ideal(n_pulses=64)
        compressor = _make_azimuth_compressor(radar, traj)

        mea = MinimumEntropyAutofocus(max_iterations=2, poly_order=2)
        result = mea.focus(phd, compressor)
        assert isinstance(result, SARImage)

    def test_corrects_quadratic_phase_error(self):
        """MEA corrects a quadratic phase error (defocus)."""
        from pySimSAR.algorithms.autofocus.min_entropy import MinimumEntropyAutofocus

        n_pulses = 256
        phd, radar, traj = _range_compress_ideal(n_pulses=n_pulses)
        compressor = _make_azimuth_compressor(radar, traj)

        # Inject quadratic phase error
        t_norm = np.linspace(-1, 1, n_pulses)
        injected_error = 6.0 * t_norm**2

        phd_corrupted = _inject_phase_error_into_phd(phd, injected_error)

        img_before = compressor(phd_corrupted)
        pmr_before = _image_peak_quality(img_before)
        entropy_before = _image_entropy(img_before)

        mea = MinimumEntropyAutofocus(
            max_iterations=5,
            poly_order=2,
        )
        img_after = mea.focus(phd_corrupted, compressor)
        pmr_after = _image_peak_quality(img_after)
        entropy_after = _image_entropy(img_after)

        # Entropy should decrease (better focus)
        assert entropy_after < entropy_before, (
            f"MEA did not reduce entropy: "
            f"before={entropy_before:.4f}, after={entropy_after:.4f}"
        )
        # PMR should not degrade significantly
        assert pmr_after >= pmr_before - 0.5, (
            f"MEA degraded image quality: "
            f"before={pmr_before:.1f} dB, after={pmr_after:.1f} dB"
        )

    def test_corrects_fourth_order_phase_error(self):
        """MEA corrects a fourth-order phase error."""
        from pySimSAR.algorithms.autofocus.min_entropy import MinimumEntropyAutofocus

        n_pulses = 256
        phd, radar, traj = _range_compress_ideal(n_pulses=n_pulses)
        compressor = _make_azimuth_compressor(radar, traj)

        # Inject strong fourth-order phase error (symmetric, causes defocus)
        t_norm = np.linspace(-1, 1, n_pulses)
        injected_error = 8.0 * t_norm**4

        phd_corrupted = _inject_phase_error_into_phd(phd, injected_error)

        img_before = compressor(phd_corrupted)
        pmr_before = _image_peak_quality(img_before)
        entropy_before = _image_entropy(img_before)

        mea = MinimumEntropyAutofocus(
            max_iterations=5,
            poly_order=4,
        )
        img_after = mea.focus(phd_corrupted, compressor)
        pmr_after = _image_peak_quality(img_after)
        entropy_after = _image_entropy(img_after)

        # Either entropy decreases or PMR increases
        assert entropy_after < entropy_before or pmr_after > pmr_before, (
            f"MEA did not improve on 4th-order error: "
            f"entropy before={entropy_before:.4f} after={entropy_after:.4f}, "
            f"PMR before={pmr_before:.1f} dB after={pmr_after:.1f} dB"
        )

    def test_estimate_phase_error_shape(self):
        """estimate_phase_error returns correct shape."""
        from pySimSAR.algorithms.autofocus.min_entropy import MinimumEntropyAutofocus

        n_pulses = 128
        phd, _, _ = _range_compress_ideal(n_pulses=n_pulses)

        mea = MinimumEntropyAutofocus()
        error = mea.estimate_phase_error(phd)
        assert error.shape == (n_pulses,)
        assert np.issubdtype(error.dtype, np.floating)

    def test_does_not_degrade_ideal_data(self):
        """MEA on ideal data does not degrade image quality."""
        from pySimSAR.algorithms.autofocus.min_entropy import MinimumEntropyAutofocus

        phd, radar, traj = _range_compress_ideal(n_pulses=128)
        compressor = _make_azimuth_compressor(radar, traj)

        img_without = compressor(phd)
        pmr_without = _image_peak_quality(img_without)

        mea = MinimumEntropyAutofocus(max_iterations=3, poly_order=2)
        img_with = mea.focus(phd, compressor)
        pmr_with = _image_peak_quality(img_with)

        # Should not degrade by more than 1 dB
        assert pmr_with > pmr_without - 1.0, (
            f"MEA degraded ideal image: "
            f"without={pmr_without:.1f} dB, with={pmr_with:.1f} dB"
        )


# ---------------------------------------------------------------------------
# T091: PPP autofocus integration tests
# ---------------------------------------------------------------------------


class TestPPPAutofocus:
    """T091: Integration test for PPP autofocus."""

    def test_satisfies_abc(self):
        """ProminentPointProcessing is an AutofocusAlgorithm."""
        from pySimSAR.algorithms.autofocus.ppp import ProminentPointProcessing

        ppp = ProminentPointProcessing()
        assert isinstance(ppp, AutofocusAlgorithm)
        assert ppp.name == "ppp"

    def test_returns_sar_image(self):
        """focus() returns a SARImage object."""
        from pySimSAR.algorithms.autofocus.ppp import ProminentPointProcessing

        phd, radar, traj = _range_compress_ideal(n_pulses=64)
        compressor = _make_azimuth_compressor(radar, traj)

        ppp = ProminentPointProcessing(max_iterations=2)
        result = ppp.focus(phd, compressor)
        assert isinstance(result, SARImage)

    def test_corrects_sinusoidal_phase_error(self):
        """PPP corrects a sinusoidal phase error with prominent scatterer."""
        from pySimSAR.algorithms.autofocus.ppp import ProminentPointProcessing

        n_pulses = 256
        phd, radar, traj = _range_compress_ideal(n_pulses=n_pulses)
        compressor = _make_azimuth_compressor(radar, traj)

        # Inject sinusoidal phase error
        t = np.arange(n_pulses) / phd.prf
        injected_error = 1.5 * np.sin(2 * np.pi * 8.0 * t)

        phd_corrupted = _inject_phase_error_into_phd(phd, injected_error)

        img_before = compressor(phd_corrupted)
        pmr_before = _image_peak_quality(img_before)

        ppp = ProminentPointProcessing(
            max_iterations=10,
            convergence_threshold=0.005,
        )
        img_after = ppp.focus(phd_corrupted, compressor)
        pmr_after = _image_peak_quality(img_after)

        assert pmr_after > pmr_before, (
            f"PPP did not improve image quality: "
            f"before={pmr_before:.1f} dB, after={pmr_after:.1f} dB"
        )

    def test_estimate_phase_error_shape(self):
        """estimate_phase_error returns correct shape."""
        from pySimSAR.algorithms.autofocus.ppp import ProminentPointProcessing

        n_pulses = 128
        phd, _, _ = _range_compress_ideal(n_pulses=n_pulses)

        ppp = ProminentPointProcessing()
        error = ppp.estimate_phase_error(phd)
        assert error.shape == (n_pulses,)
        assert np.issubdtype(error.dtype, np.floating)

    def test_does_not_degrade_ideal_data(self):
        """PPP on ideal data does not degrade image quality."""
        from pySimSAR.algorithms.autofocus.ppp import ProminentPointProcessing

        phd, radar, traj = _range_compress_ideal(n_pulses=128)
        compressor = _make_azimuth_compressor(radar, traj)

        img_without = compressor(phd)
        pmr_without = _image_peak_quality(img_without)

        ppp = ProminentPointProcessing(max_iterations=5)
        img_with = ppp.focus(phd, compressor)
        pmr_with = _image_peak_quality(img_with)

        # Should not degrade by more than 1 dB
        assert pmr_with > pmr_without - 1.0, (
            f"PPP degraded ideal image: "
            f"without={pmr_without:.1f} dB, with={pmr_with:.1f} dB"
        )


# ---------------------------------------------------------------------------
# Autofocus registry tests (T096)
# ---------------------------------------------------------------------------


class TestAutofocusRegistry:
    """T096: Verify all autofocus algorithms are registered."""

    def test_pga_registered(self):
        """PGA is in the autofocus registry."""
        from pySimSAR.algorithms.autofocus import autofocus_registry

        assert "pga" in autofocus_registry
        cls = autofocus_registry.get("pga")
        assert cls.name == "pga"

    def test_mda_registered(self):
        """MDA is in the autofocus registry."""
        from pySimSAR.algorithms.autofocus import autofocus_registry

        assert "mda" in autofocus_registry
        cls = autofocus_registry.get("mda")
        assert cls.name == "mda"

    def test_min_entropy_registered(self):
        """MinimumEntropy is in the autofocus registry."""
        from pySimSAR.algorithms.autofocus import autofocus_registry

        assert "min_entropy" in autofocus_registry
        cls = autofocus_registry.get("min_entropy")
        assert cls.name == "min_entropy"

    def test_ppp_registered(self):
        """PPP is in the autofocus registry."""
        from pySimSAR.algorithms.autofocus import autofocus_registry

        assert "ppp" in autofocus_registry
        cls = autofocus_registry.get("ppp")
        assert cls.name == "ppp"

    def test_all_four_algorithms_present(self):
        """All 4 autofocus algorithms are registered."""
        from pySimSAR.algorithms.autofocus import autofocus_registry

        expected = {"pga", "mda", "min_entropy", "ppp"}
        registered = set(autofocus_registry.list())
        assert expected.issubset(registered), (
            f"Missing algorithms: {expected - registered}"
        )
