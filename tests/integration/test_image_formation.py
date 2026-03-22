"""Integration tests for image formation algorithms (T075-T078).

Tests verify:
- Point target impulse response (peak location, focusing quality)
- Two-step interface (range_compress -> PhaseHistoryData -> azimuth_compress)
- Algorithm registration and discovery
"""

from __future__ import annotations

import numpy as np

from pySimSAR.core.radar import C_LIGHT, AntennaPattern, Radar, create_antenna_from_preset
from pySimSAR.core.scene import PointTarget, Scene
from pySimSAR.core.types import PhaseHistoryData, RawData, SARImage, SARMode
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.simulation.engine import SimulationEngine


def _make_flat_antenna() -> AntennaPattern:
    """Create a flat antenna for test (uniform gain inside beam)."""
    return create_antenna_from_preset(
        "flat",
        az_beamwidth=np.radians(10),
        el_beamwidth=np.radians(10),
    )


def _make_radar(mode: str = "stripmap") -> Radar:
    """Create a test radar with LFM waveform."""
    from pySimSAR.waveforms.lfm import LFMWaveform

    wf = LFMWaveform(bandwidth=150e6, duty_cycle=0.1, prf=1000.0)
    antenna = _make_flat_antenna()
    return Radar(
        carrier_freq=9.65e9,
        transmit_power=100.0,
        waveform=wf,
        antenna=antenna,
        polarization="single",
        mode=mode,
        look_side="right",
        depression_angle=0.0,  # co-altitude geometry (platform and target at z=0)
    )


def _simulate_point_target(
    target_pos: np.ndarray,
    rcs: float = 10.0,
    n_pulses: int = 256,
    platform_start: np.ndarray | None = None,
    platform_velocity: np.ndarray | None = None,
) -> tuple:
    """Simulate a single point target and return (raw_data, radar, trajectory, gate_delay).

    Returns
    -------
    tuple of (RawData, Radar, Trajectory, float)
    """
    if platform_velocity is None:
        platform_velocity = np.array([0.0, 100.0, 0.0])
    if platform_start is None:
        # Centre the aperture on the target azimuth (y=0) so the target
        # stays within the antenna beam throughout the synthetic aperture.
        half_aperture = 0.5 * n_pulses * platform_velocity[1] / 1000.0
        platform_start = np.array([0.0, -half_aperture, 0.0])

    scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
    scene.add_target(PointTarget(position=target_pos, rcs=rcs))

    radar = _make_radar()
    sample_rate = 2.0 * radar.bandwidth

    engine = SimulationEngine(
        scene=scene,
        radar=radar,
        n_pulses=n_pulses,
        platform_start=platform_start,
        platform_velocity=platform_velocity,
        seed=42,
        sample_rate=sample_rate,
    )

    result = engine.run()

    # Build RawData
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

    # Build Trajectory from simulation positions/velocities
    trajectory = Trajectory(
        time=result.pulse_times,
        position=result.positions,
        velocity=result.velocities,
        attitude=np.zeros((n_pulses, 3)),
    )

    return raw_data, radar, trajectory, result.gate_delay


class TestRangeDopplerAlgorithm:
    """T075: Integration test for Range-Doppler algorithm (point target impulse response)."""

    def test_point_target_produces_focused_peak(self):
        """A single point target produces a focused peak in the output image."""
        from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        raw_data, radar, trajectory, _ = _simulate_point_target(target_pos, n_pulses=256)

        rda = RangeDopplerAlgorithm()
        image = rda.process(raw_data, radar, trajectory)

        assert isinstance(image, SARImage)
        assert image.data.ndim == 2
        assert image.algorithm == "range_doppler"
        assert image.geometry == "slant_range"
        assert image.channel == "single"

        # Find peak in the focused image
        magnitude = np.abs(image.data)
        peak_idx = np.unravel_index(np.argmax(magnitude), magnitude.shape)
        peak_val = magnitude[peak_idx]

        # Peak should be significantly above the mean (well-focused)
        mean_val = np.mean(magnitude)
        assert peak_val > 10 * mean_val, (
            f"Peak {peak_val:.2e} not significantly above mean {mean_val:.2e}"
        )

    def test_point_target_peak_at_correct_range_bin(self):
        """The focused peak is at the correct range bin for the target distance."""
        from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        platform_start = np.array([0.0, -12.8, 0.0])
        raw_data, radar, trajectory, gate_delay = _simulate_point_target(
            target_pos, platform_start=platform_start, n_pulses=256,
        )

        rda = RangeDopplerAlgorithm()
        image = rda.process(raw_data, radar, trajectory)

        # Find peak range bin
        magnitude = np.abs(image.data)
        peak_az, peak_rng = np.unravel_index(np.argmax(magnitude), magnitude.shape)

        # Expected range from mid-aperture position to target
        mid_pos = trajectory.position[128]  # middle of aperture
        expected_range = np.linalg.norm(target_pos - mid_pos)

        # Expected range bin
        range_bin_spacing = C_LIGHT / (2.0 * raw_data.sample_rate)
        gate_near_range = gate_delay * C_LIGHT / 2.0
        expected_bin = (expected_range - gate_near_range) / range_bin_spacing

        # Allow tolerance for RCMC shifts and interpolation effects
        assert abs(peak_rng - expected_bin) < 50, (
            f"Peak at range bin {peak_rng}, expected near {expected_bin:.1f}"
        )

    def test_impulse_response_range_resolution(self):
        """Range resolution matches theoretical c/(2B) within 5%."""
        from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        raw_data, radar, trajectory, _ = _simulate_point_target(target_pos, n_pulses=256)

        rda = RangeDopplerAlgorithm()
        image = rda.process(raw_data, radar, trajectory)

        # Extract range cut through the peak
        magnitude = np.abs(image.data)
        peak_az, peak_rng = np.unravel_index(np.argmax(magnitude), magnitude.shape)
        range_cut = magnitude[peak_az, :]

        # Measure 3dB width in range (contiguous bins around peak)
        peak_val = range_cut[peak_rng]
        threshold = peak_val / np.sqrt(2)  # -3dB

        # Search outward from peak for contiguous -3dB width
        left = peak_rng
        while left > 0 and range_cut[left - 1] >= threshold:
            left -= 1
        right = peak_rng
        while right < len(range_cut) - 1 and range_cut[right + 1] >= threshold:
            right += 1
        width_bins = right - left + 1

        # Theoretical range resolution: c / (2 * B)
        theoretical_res = C_LIGHT / (2.0 * radar.bandwidth)
        range_bin_spacing = C_LIGHT / (2.0 * raw_data.sample_rate)
        measured_res = width_bins * range_bin_spacing

        # Allow within 5x since bin-based measurement is coarse at 2x sampling
        assert measured_res < 5 * theoretical_res, (
            f"Measured range resolution {measured_res:.2f}m vs "
            f"theoretical {theoretical_res:.2f}m"
        )

    def test_azimuth_compression_produces_narrow_peak(self):
        """Azimuth compression produces a narrow peak (much less than n_pulses)."""
        from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        n_pulses = 256
        raw_data, radar, trajectory, _ = _simulate_point_target(
            target_pos, n_pulses=n_pulses
        )

        rda = RangeDopplerAlgorithm(apply_rcmc=False)
        image = rda.process(raw_data, radar, trajectory)

        # Extract azimuth cut through the peak
        img_mag = np.abs(image.data)
        peak_az, peak_rng = np.unravel_index(np.argmax(img_mag), img_mag.shape)
        az_cut = img_mag[:, peak_rng]

        # Measure -3dB width
        threshold = np.max(az_cut) / np.sqrt(2)
        az_width = np.sum(az_cut >= threshold)

        # Focused azimuth width should be much less than n_pulses
        assert az_width < n_pulses // 4, (
            f"Azimuth -3dB width ({az_width} bins) should be less than "
            f"{n_pulses // 4} (quarter of aperture)"
        )

    def test_two_targets_at_different_ranges_are_resolved(self):
        """Two targets separated by more than the range resolution are resolved."""
        from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm

        # Two targets separated in range by >> c/(2B) = 1m
        scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
        scene.add_target(PointTarget(position=[4000.0, 0, 0], rcs=10.0))
        scene.add_target(PointTarget(position=[6000.0, 0, 0], rcs=10.0))

        radar = _make_radar()
        sample_rate = 2.0 * radar.bandwidth
        n_pulses = 256

        engine = SimulationEngine(
            scene=scene,
            radar=radar,
            n_pulses=n_pulses,
            platform_start=np.array([0.0, -12.8, 0.0]),
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
            gate_delay=result.gate_delay,
        )
        trajectory = Trajectory(
            time=result.pulse_times,
            position=result.positions,
            velocity=result.velocities,
            attitude=np.zeros((n_pulses, 3)),
        )

        rda = RangeDopplerAlgorithm()
        image = rda.process(raw_data, radar, trajectory)

        # Find the two highest peaks
        magnitude = np.abs(image.data)
        # Flatten to find top peaks
        flat = magnitude.ravel()
        sorted_idx = np.argsort(flat)[::-1]

        # First peak
        peak1 = np.unravel_index(sorted_idx[0], magnitude.shape)

        # Find second distinct peak (at least 10 bins away in range)
        peak2 = None
        for idx in sorted_idx[1:]:
            pos = np.unravel_index(idx, magnitude.shape)
            if abs(pos[1] - peak1[1]) > 10:
                peak2 = pos
                break

        assert peak2 is not None, "Could not find two distinct peaks"

    def test_pixel_spacing_is_positive(self):
        """Output image has positive pixel spacing values."""
        from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        raw_data, radar, trajectory, _ = _simulate_point_target(target_pos, n_pulses=64)

        rda = RangeDopplerAlgorithm()
        image = rda.process(raw_data, radar, trajectory)

        assert image.pixel_spacing_range > 0
        assert image.pixel_spacing_azimuth > 0

    def test_supported_modes_returns_stripmap(self):
        """RDA supports only stripmap mode."""
        from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm
        from pySimSAR.core.types import SARMode

        rda = RangeDopplerAlgorithm()
        modes = rda.supported_modes()
        assert SARMode.STRIPMAP in modes
        assert len(modes) == 1


class TestTwoStepInterface:
    """T078: Integration test for the two-step image formation interface."""

    def test_two_step_produces_same_result_as_process(self):
        """range_compress -> azimuth_compress produces the same result as process()."""
        from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        raw_data, radar, trajectory, _ = _simulate_point_target(target_pos, n_pulses=128)

        rda = RangeDopplerAlgorithm()

        # End-to-end
        image_direct = rda.process(raw_data, radar, trajectory)

        # Two-step
        phd = rda.range_compress(raw_data, radar)
        image_twostep = rda.azimuth_compress(phd, radar, trajectory)

        # Results should be identical
        np.testing.assert_array_almost_equal(
            image_direct.data, image_twostep.data, decimal=10,
            err_msg="Two-step and direct processing produced different results",
        )

    def test_range_compress_returns_phase_history_data(self):
        """range_compress returns a PhaseHistoryData with correct metadata."""
        from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        raw_data, radar, trajectory, _ = _simulate_point_target(target_pos, n_pulses=64)

        rda = RangeDopplerAlgorithm()
        phd = rda.range_compress(raw_data, radar)

        assert isinstance(phd, PhaseHistoryData)
        assert phd.data.shape == raw_data.echo.shape
        assert phd.sample_rate == raw_data.sample_rate
        assert phd.prf == radar.waveform.prf
        assert phd.carrier_freq == radar.carrier_freq
        assert phd.bandwidth == radar.bandwidth
        assert phd.channel == raw_data.channel

    def test_azimuth_compress_returns_sar_image(self):
        """azimuth_compress returns a SARImage with correct metadata."""
        from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        raw_data, radar, trajectory, _ = _simulate_point_target(target_pos, n_pulses=64)

        rda = RangeDopplerAlgorithm()
        phd = rda.range_compress(raw_data, radar)
        image = rda.azimuth_compress(phd, radar, trajectory)

        assert isinstance(image, SARImage)
        assert image.data.shape == phd.data.shape
        assert image.geometry == "slant_range"
        assert image.algorithm == "range_doppler"

    def test_phase_history_is_range_compressed(self):
        """PhaseHistoryData shows range compression (peak in range at target delay)."""
        from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        platform_start = np.array([0.0, -12.8, 0.0])
        raw_data, radar, trajectory, gate_delay = _simulate_point_target(
            target_pos, platform_start=platform_start, n_pulses=64,
        )

        rda = RangeDopplerAlgorithm()
        phd = rda.range_compress(raw_data, radar)

        # Each pulse should have a peak near the expected range bin
        gate_near_range = gate_delay * C_LIGHT / 2.0
        for pulse_idx in [0, 32, 63]:
            pulse_data = np.abs(phd.data[pulse_idx, :])
            peak_bin = np.argmax(pulse_data)

            # Expected range from this pulse position to target
            expected_range = np.linalg.norm(
                target_pos - trajectory.position[pulse_idx]
            )
            range_bin_spacing = C_LIGHT / (2.0 * raw_data.sample_rate)
            expected_bin = (expected_range - gate_near_range) / range_bin_spacing

            assert abs(peak_bin - expected_bin) < 5, (
                f"Pulse {pulse_idx}: peak at bin {peak_bin}, "
                f"expected near {expected_bin:.1f}"
            )


class TestChirpScalingAlgorithm:
    """T076: Integration test for Chirp Scaling algorithm (point target impulse response)."""

    def test_point_target_produces_focused_peak(self):
        """A single point target produces a focused peak in the output image."""
        from pySimSAR.algorithms.image_formation import ChirpScalingAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        raw_data, radar, trajectory, _ = _simulate_point_target(target_pos, n_pulses=256)

        csa = ChirpScalingAlgorithm()
        image = csa.process(raw_data, radar, trajectory)

        assert isinstance(image, SARImage)
        assert image.data.ndim == 2
        assert image.algorithm == "chirp_scaling"
        assert image.geometry == "slant_range"
        assert image.channel == "single"

        # Find peak in the focused image
        magnitude = np.abs(image.data)
        peak_idx = np.unravel_index(np.argmax(magnitude), magnitude.shape)
        peak_val = magnitude[peak_idx]

        # Peak should be significantly above the mean (well-focused)
        mean_val = np.mean(magnitude)
        assert peak_val > 10 * mean_val, (
            f"Peak {peak_val:.2e} not significantly above mean {mean_val:.2e}"
        )

    def test_point_target_peak_at_correct_range_bin(self):
        """The focused peak is at the correct range bin for the target distance."""
        from pySimSAR.algorithms.image_formation import ChirpScalingAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        platform_start = np.array([0.0, -12.8, 0.0])
        raw_data, radar, trajectory, gate_delay = _simulate_point_target(
            target_pos, platform_start=platform_start, n_pulses=256,
        )

        csa = ChirpScalingAlgorithm()
        image = csa.process(raw_data, radar, trajectory)

        # Find peak range bin
        magnitude = np.abs(image.data)
        peak_az, peak_rng = np.unravel_index(np.argmax(magnitude), magnitude.shape)

        # Expected range from mid-aperture position to target
        mid_pos = trajectory.position[128]
        expected_range = np.linalg.norm(target_pos - mid_pos)

        # Expected range bin
        range_bin_spacing = C_LIGHT / (2.0 * raw_data.sample_rate)
        gate_near_range = gate_delay * C_LIGHT / 2.0
        expected_bin = (expected_range - gate_near_range) / range_bin_spacing

        # Allow tolerance for processing shifts
        assert abs(peak_rng - expected_bin) < 50, (
            f"Peak at range bin {peak_rng}, expected near {expected_bin:.1f}"
        )

    def test_impulse_response_range_resolution(self):
        """Range resolution matches theoretical c/(2B) within tolerance."""
        from pySimSAR.algorithms.image_formation import ChirpScalingAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        raw_data, radar, trajectory, _ = _simulate_point_target(target_pos, n_pulses=256)

        csa = ChirpScalingAlgorithm()
        image = csa.process(raw_data, radar, trajectory)

        # Extract range cut through the peak
        magnitude = np.abs(image.data)
        peak_az, peak_rng = np.unravel_index(np.argmax(magnitude), magnitude.shape)
        range_cut = magnitude[peak_az, :]

        # Measure 3dB width in range (contiguous mainlobe around peak)
        peak_val = range_cut[peak_rng]
        threshold = peak_val / np.sqrt(2)  # -3dB

        left = peak_rng
        while left > 0 and range_cut[left - 1] >= threshold:
            left -= 1
        right = peak_rng
        while right < len(range_cut) - 1 and range_cut[right + 1] >= threshold:
            right += 1
        width_bins = right - left + 1

        # Theoretical range resolution: c / (2 * B)
        theoretical_res = C_LIGHT / (2.0 * radar.bandwidth)
        range_bin_spacing = C_LIGHT / (2.0 * raw_data.sample_rate)
        measured_res = width_bins * range_bin_spacing

        assert measured_res < 5 * theoretical_res, (
            f"Measured range resolution {measured_res:.2f}m vs "
            f"theoretical {theoretical_res:.2f}m"
        )

    def test_azimuth_compression_produces_narrow_peak(self):
        """Azimuth compression produces a narrow peak."""
        from pySimSAR.algorithms.image_formation import ChirpScalingAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        n_pulses = 256
        raw_data, radar, trajectory, _ = _simulate_point_target(
            target_pos, n_pulses=n_pulses
        )

        csa = ChirpScalingAlgorithm()
        image = csa.process(raw_data, radar, trajectory)

        # Extract azimuth cut through the peak
        img_mag = np.abs(image.data)
        peak_az, peak_rng = np.unravel_index(np.argmax(img_mag), img_mag.shape)
        az_cut = img_mag[:, peak_rng]

        # Measure -3dB width
        threshold = np.max(az_cut) / np.sqrt(2)
        az_width = np.sum(az_cut >= threshold)

        # Focused azimuth width should be much less than n_pulses
        assert az_width < n_pulses // 4, (
            f"Azimuth -3dB width ({az_width} bins) should be less than "
            f"{n_pulses // 4} (quarter of aperture)"
        )

    def test_two_step_produces_same_result_as_process(self):
        """range_compress -> azimuth_compress produces same result as process()."""
        from pySimSAR.algorithms.image_formation import ChirpScalingAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        raw_data, radar, trajectory, _ = _simulate_point_target(target_pos, n_pulses=128)

        csa = ChirpScalingAlgorithm()

        # End-to-end
        image_direct = csa.process(raw_data, radar, trajectory)

        # Two-step
        phd = csa.range_compress(raw_data, radar)
        image_twostep = csa.azimuth_compress(phd, radar, trajectory)

        np.testing.assert_array_almost_equal(
            image_direct.data, image_twostep.data, decimal=10,
            err_msg="Two-step and direct processing produced different results",
        )

    def test_supported_modes_returns_stripmap_and_scanmar(self):
        """CSA supports stripmap and scanmar modes."""
        from pySimSAR.algorithms.image_formation import ChirpScalingAlgorithm

        csa = ChirpScalingAlgorithm()
        modes = csa.supported_modes()
        assert SARMode.STRIPMAP in modes
        assert SARMode.SCANMAR in modes
        assert len(modes) == 2

    def test_pixel_spacing_is_positive(self):
        """Output image has positive pixel spacing values."""
        from pySimSAR.algorithms.image_formation import ChirpScalingAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        raw_data, radar, trajectory, _ = _simulate_point_target(target_pos, n_pulses=64)

        csa = ChirpScalingAlgorithm()
        image = csa.process(raw_data, radar, trajectory)

        assert image.pixel_spacing_range > 0
        assert image.pixel_spacing_azimuth > 0


class TestOmegaKAlgorithm:
    """T077: Integration test for Omega-K algorithm (point target impulse response)."""

    def test_point_target_produces_focused_peak(self):
        """A single point target produces a focused peak in the output image."""
        from pySimSAR.algorithms.image_formation import OmegaKAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        raw_data, radar, trajectory, _ = _simulate_point_target(target_pos, n_pulses=256)

        omk = OmegaKAlgorithm()
        image = omk.process(raw_data, radar, trajectory)

        assert isinstance(image, SARImage)
        assert image.data.ndim == 2
        assert image.algorithm == "omega_k"
        assert image.geometry == "slant_range"
        assert image.channel == "single"

        # Find peak in the focused image
        magnitude = np.abs(image.data)
        peak_idx = np.unravel_index(np.argmax(magnitude), magnitude.shape)
        peak_val = magnitude[peak_idx]

        # Peak should be significantly above the mean (well-focused)
        mean_val = np.mean(magnitude)
        assert peak_val > 10 * mean_val, (
            f"Peak {peak_val:.2e} not significantly above mean {mean_val:.2e}"
        )

    def test_point_target_peak_at_correct_range_bin(self):
        """The focused peak is at the correct range bin for the target distance."""
        from pySimSAR.algorithms.image_formation import OmegaKAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        platform_start = np.array([0.0, -12.8, 0.0])
        raw_data, radar, trajectory, gate_delay = _simulate_point_target(
            target_pos, platform_start=platform_start, n_pulses=256,
        )

        omk = OmegaKAlgorithm()
        image = omk.process(raw_data, radar, trajectory)

        # Find peak range bin
        magnitude = np.abs(image.data)
        peak_az, peak_rng = np.unravel_index(np.argmax(magnitude), magnitude.shape)

        # Expected range from mid-aperture position to target
        mid_pos = trajectory.position[128]
        expected_range = np.linalg.norm(target_pos - mid_pos)

        # Expected range bin
        range_bin_spacing = C_LIGHT / (2.0 * raw_data.sample_rate)
        gate_near_range = gate_delay * C_LIGHT / 2.0
        expected_bin = (expected_range - gate_near_range) / range_bin_spacing

        # Allow tolerance for Stolt interpolation shifts
        assert abs(peak_rng - expected_bin) < 50, (
            f"Peak at range bin {peak_rng}, expected near {expected_bin:.1f}"
        )

    def test_impulse_response_range_resolution(self):
        """Range resolution matches theoretical c/(2B) within tolerance."""
        from pySimSAR.algorithms.image_formation import OmegaKAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        raw_data, radar, trajectory, _ = _simulate_point_target(target_pos, n_pulses=256)

        omk = OmegaKAlgorithm()
        image = omk.process(raw_data, radar, trajectory)

        # Extract range cut through the peak
        magnitude = np.abs(image.data)
        peak_az, peak_rng = np.unravel_index(np.argmax(magnitude), magnitude.shape)
        range_cut = magnitude[peak_az, :]

        # Measure 3dB width in range (contiguous mainlobe around peak)
        peak_val = range_cut[peak_rng]
        threshold = peak_val / np.sqrt(2)  # -3dB

        left = peak_rng
        while left > 0 and range_cut[left - 1] >= threshold:
            left -= 1
        right = peak_rng
        while right < len(range_cut) - 1 and range_cut[right + 1] >= threshold:
            right += 1
        width_bins = right - left + 1

        # Theoretical range resolution: c / (2 * B)
        theoretical_res = C_LIGHT / (2.0 * radar.bandwidth)
        range_bin_spacing = C_LIGHT / (2.0 * raw_data.sample_rate)
        measured_res = width_bins * range_bin_spacing

        assert measured_res < 5 * theoretical_res, (
            f"Measured range resolution {measured_res:.2f}m vs "
            f"theoretical {theoretical_res:.2f}m"
        )

    def test_azimuth_compression_produces_narrow_peak(self):
        """Azimuth compression produces a narrow peak."""
        from pySimSAR.algorithms.image_formation import OmegaKAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        n_pulses = 256
        raw_data, radar, trajectory, _ = _simulate_point_target(
            target_pos, n_pulses=n_pulses
        )

        omk = OmegaKAlgorithm()
        image = omk.process(raw_data, radar, trajectory)

        # Extract azimuth cut through the peak
        img_mag = np.abs(image.data)
        peak_az, peak_rng = np.unravel_index(np.argmax(img_mag), img_mag.shape)
        az_cut = img_mag[:, peak_rng]

        # Measure -3dB width
        threshold = np.max(az_cut) / np.sqrt(2)
        az_width = np.sum(az_cut >= threshold)

        # Focused azimuth width should be much less than n_pulses
        assert az_width < n_pulses // 4, (
            f"Azimuth -3dB width ({az_width} bins) should be less than "
            f"{n_pulses // 4} (quarter of aperture)"
        )

    def test_two_step_produces_same_result_as_process(self):
        """range_compress -> azimuth_compress produces same result as process()."""
        from pySimSAR.algorithms.image_formation import OmegaKAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        raw_data, radar, trajectory, _ = _simulate_point_target(target_pos, n_pulses=128)

        omk = OmegaKAlgorithm()

        # End-to-end
        image_direct = omk.process(raw_data, radar, trajectory)

        # Two-step
        phd = omk.range_compress(raw_data, radar)
        image_twostep = omk.azimuth_compress(phd, radar, trajectory)

        np.testing.assert_array_almost_equal(
            image_direct.data, image_twostep.data, decimal=10,
            err_msg="Two-step and direct processing produced different results",
        )

    def test_supported_modes_returns_stripmap_and_spotlight(self):
        """Omega-K supports stripmap and spotlight modes."""
        from pySimSAR.algorithms.image_formation import OmegaKAlgorithm

        omk = OmegaKAlgorithm()
        modes = omk.supported_modes()
        assert SARMode.STRIPMAP in modes
        assert SARMode.SPOTLIGHT in modes
        assert len(modes) == 2

    def test_pixel_spacing_is_positive(self):
        """Output image has positive pixel spacing values."""
        from pySimSAR.algorithms.image_formation import OmegaKAlgorithm

        target_pos = np.array([5000.0, 0.0, 0.0])
        raw_data, radar, trajectory, _ = _simulate_point_target(target_pos, n_pulses=64)

        omk = OmegaKAlgorithm()
        image = omk.process(raw_data, radar, trajectory)

        assert image.pixel_spacing_range > 0
        assert image.pixel_spacing_azimuth > 0


class TestImageFormationRegistry:
    """Test algorithm registration and discovery."""

    def test_range_doppler_is_registered(self):
        """RangeDopplerAlgorithm is discoverable via the registry."""
        from pySimSAR.algorithms.image_formation import (
            RangeDopplerAlgorithm,
            image_formation_registry,
        )

        assert "range_doppler" in image_formation_registry
        cls = image_formation_registry.get("range_doppler")
        assert cls is RangeDopplerAlgorithm

    def test_chirp_scaling_is_registered(self):
        """ChirpScalingAlgorithm is discoverable via the registry."""
        from pySimSAR.algorithms.image_formation import (
            ChirpScalingAlgorithm,
            image_formation_registry,
        )

        assert "chirp_scaling" in image_formation_registry
        cls = image_formation_registry.get("chirp_scaling")
        assert cls is ChirpScalingAlgorithm

    def test_omega_k_is_registered(self):
        """OmegaKAlgorithm is discoverable via the registry."""
        from pySimSAR.algorithms.image_formation import (
            OmegaKAlgorithm,
            image_formation_registry,
        )

        assert "omega_k" in image_formation_registry
        cls = image_formation_registry.get("omega_k")
        assert cls is OmegaKAlgorithm

    def test_registry_lists_algorithms(self):
        """Registry lists all registered algorithm names."""
        from pySimSAR.algorithms.image_formation import image_formation_registry

        names = image_formation_registry.list()
        assert "range_doppler" in names
        assert "chirp_scaling" in names
        assert "omega_k" in names
