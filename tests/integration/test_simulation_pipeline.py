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

    wf = LFMWaveform(bandwidth=150e6, duty_cycle=0.1, prf=1000.0)
    antenna = _make_isotropic_antenna()
    return Radar(
        carrier_freq=9.65e9,
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
            echo[0, :], radar.waveform.prf, sample_rate
        )
        peak_idx = np.argmax(np.abs(compressed))

        # Compute expected range from platform to target, relative to gate
        slant_range = np.linalg.norm(target_pos - platform_start)
        gate_delay, _ = engine._compute_range_gate()
        expected_delay_samples = int(
            np.round((2.0 * slant_range / C_LIGHT - gate_delay) * sample_rate)
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
            result1.echo["single"][0, :], radar.waveform.prf, sample_rate
        )
        comp2 = radar.waveform.range_compress(
            result2.echo["single"][0, :], radar.waveform.prf, sample_rate
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

        wf = LFMWaveform(bandwidth=150e6, duty_cycle=0.1, prf=1000.0)
        antenna = _make_isotropic_antenna()
        radar = Radar(
            carrier_freq=9.65e9,
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


class TestQuadPolSignalCorrectness:
    """Verify quad-pol simulation produces physically correct per-channel echoes."""

    @staticmethod
    def _run_quad_pol(scattering_matrix: np.ndarray) -> dict[str, np.ndarray]:
        """Run a single-pulse quad-pol simulation and return range-compressed echoes."""
        from pySimSAR.waveforms.lfm import LFMWaveform

        scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
        scene.add_target(
            PointTarget(position=[5000.0, 0.0, 0.0], rcs=scattering_matrix)
        )

        wf = LFMWaveform(bandwidth=150e6, duty_cycle=0.1, prf=1000.0)
        antenna = _make_isotropic_antenna()
        radar = Radar(
            carrier_freq=9.65e9,
            transmit_power=1000.0,
            waveform=wf,
            antenna=antenna,
            polarization="quad",
            mode="stripmap",
            look_side="right",
            depression_angle=0.7,
        )
        sample_rate = 2.0 * radar.bandwidth

        engine = SimulationEngine(
            scene=scene,
            radar=radar,
            n_pulses=1,
            platform_start=np.array([0.0, 0.0, 0.0]),
            platform_velocity=np.array([0.0, 100.0, 0.0]),
            seed=42,
            sample_rate=sample_rate,
        )
        result = engine.run()

        compressed = {}
        for ch, echo in result.echo.items():
            compressed[ch] = radar.waveform.range_compress(
                echo[0, :], radar.waveform.prf, sample_rate
            )
        return compressed

    def test_channel_isolation_diagonal_matrix(self):
        """Diagonal scattering matrix: off-diagonal channels have no target echo.

        S = [[1, 0], [0, 0.5]] means:
        - HH (0,0) → |1|^2 = 1.0
        - HV (0,1) → |0|^2 = 0.0  (noise only)
        - VH (1,0) → |0|^2 = 0.0  (noise only)
        - VV (1,1) → |0.5|^2 = 0.25
        """
        smat = np.array([[1.0 + 0j, 0.0 + 0j], [0.0 + 0j, 0.5 + 0j]])
        compressed = self._run_quad_pol(smat)

        # HH and VV should have detectable peaks
        hh_peak = np.max(np.abs(compressed["hh"]))
        vv_peak = np.max(np.abs(compressed["vv"]))
        hv_peak = np.max(np.abs(compressed["hv"]))
        vh_peak = np.max(np.abs(compressed["vh"]))

        # Noise floor: median of a noise-only channel
        hv_median = np.median(np.abs(compressed["hv"]))
        vh_median = np.median(np.abs(compressed["vh"]))

        # HH and VV should be well above the noise floor
        assert hh_peak > 5 * hv_median, (
            f"HH peak {hh_peak:.2e} not well above HV noise floor {hv_median:.2e}"
        )
        assert vv_peak > 5 * vh_median, (
            f"VV peak {vv_peak:.2e} not well above VH noise floor {vh_median:.2e}"
        )

        # HV and VH peaks should be at noise level (no target contribution)
        # Their peak should be much smaller than HH
        assert hv_peak < hh_peak * 0.1, (
            f"HV peak {hv_peak:.2e} too large relative to HH {hh_peak:.2e}"
        )
        assert vh_peak < hh_peak * 0.1, (
            f"VH peak {vh_peak:.2e} too large relative to HH {hh_peak:.2e}"
        )

    def test_channel_amplitude_ratio_matches_scattering_matrix(self):
        """Peak amplitude ratio between channels matches |S_ij|^2 ratio.

        S = [[2, 0], [0, 1]] → RCS_HH/RCS_VV = 4/1 = 4.
        After range compression, amplitude scales as sqrt(RCS), so
        amp_HH/amp_VV ~ sqrt(4) = 2.
        """
        smat = np.array([[2.0 + 0j, 0.0 + 0j], [0.0 + 0j, 1.0 + 0j]])
        compressed = self._run_quad_pol(smat)

        hh_peak = np.max(np.abs(compressed["hh"]))
        vv_peak = np.max(np.abs(compressed["vv"]))

        ratio = hh_peak / vv_peak
        # RCS ratio is |2|^2 / |1|^2 = 4, amplitude ratio ~ sqrt(4) = 2
        assert ratio == pytest.approx(2.0, rel=0.2), (
            f"HH/VV amplitude ratio {ratio:.2f}, expected ~2.0"
        )

    def test_all_channels_have_signal_with_full_matrix(self):
        """Non-zero scattering matrix populates all four channels with signal."""
        smat = np.array([[1.0 + 0j, 0.5 + 0j], [0.3 + 0j, 0.8 + 0j]])
        compressed = self._run_quad_pol(smat)

        # All channels should have detectable peaks above noise
        for ch in ("hh", "hv", "vh", "vv"):
            peak = np.max(np.abs(compressed[ch]))
            median = np.median(np.abs(compressed[ch]))
            assert peak > 3 * median, (
                f"Channel {ch}: peak {peak:.2e} not above noise {median:.2e}"
            )

    def test_echo_shapes_match_across_channels(self):
        """All four channels have identical echo matrix shape."""
        smat = np.array([[1.0 + 0j, 0.5 + 0j], [0.3 + 0j, 0.8 + 0j]])
        compressed = self._run_quad_pol(smat)

        shapes = {ch: arr.shape for ch, arr in compressed.items()}
        ref_shape = shapes["hh"]
        for ch, shape in shapes.items():
            assert shape == ref_shape, (
                f"Channel {ch} shape {shape} != HH shape {ref_shape}"
            )


# ===========================================================================
# Phase 11: T111-T112 — PipelineRunner integration tests
# ===========================================================================


def _simulate_for_pipeline(n_pulses: int = 128) -> tuple:
    """Simulate a point target and return (raw_data_dict, radar, trajectory).

    Returns data ready for PipelineRunner.
    """
    from pySimSAR.waveforms.lfm import LFMWaveform
    from pySimSAR.core.types import RawData
    from pySimSAR.motion.trajectory import Trajectory

    scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
    scene.add_target(PointTarget(position=[5000.0, 0.0, 0.0], rcs=10.0))

    radar = _make_radar()
    sample_rate = 2.0 * radar.bandwidth

    engine = SimulationEngine(
        scene=scene,
        radar=radar,
        n_pulses=n_pulses,
        platform_start=np.array([0.0, -5000.0, 0.0]),
        platform_velocity=np.array([0.0, 100.0, 0.0]),
        seed=42,
        sample_rate=sample_rate,
    )
    result = engine.run()

    raw_data = {
        "single": RawData(
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
    }

    trajectory = Trajectory(
        time=result.pulse_times,
        position=result.positions,
        velocity=result.velocities,
        attitude=np.zeros((n_pulses, 3)),
    )

    return raw_data, radar, trajectory


class TestPipelineRunner:
    """T111: Integration test for PipelineRunner (full chain, config-driven)."""

    def test_minimal_pipeline_image_formation_only(self):
        """Pipeline with only image formation produces a focused image."""
        from pySimSAR.io.config import ProcessingConfig
        from pySimSAR.pipeline.runner import PipelineRunner
        from pySimSAR.core.types import SARImage

        raw_data, radar, trajectory = _simulate_for_pipeline(n_pulses=128)

        config = ProcessingConfig(image_formation="range_doppler")
        runner = PipelineRunner(config)
        result = runner.run(raw_data, radar, trajectory)

        assert "single" in result.images
        assert isinstance(result.images["single"], SARImage)
        assert result.images["single"].data.ndim == 2
        assert "image_formation:range_doppler" in result.steps_applied

    def test_pipeline_with_geocoding(self):
        """Pipeline with image formation + geocoding produces georeferenced image."""
        from pySimSAR.io.config import ProcessingConfig
        from pySimSAR.pipeline.runner import PipelineRunner

        raw_data, radar, trajectory = _simulate_for_pipeline(n_pulses=64)

        config = ProcessingConfig(
            image_formation="range_doppler",
            geocoding="slant_to_ground",
        )
        runner = PipelineRunner(config)
        result = runner.run(raw_data, radar, trajectory)

        img = result.images["single"]
        assert img.geometry == "ground_range"
        assert "geocoding:slant_to_ground" in result.steps_applied

    def test_pipeline_focused_peak(self):
        """Pipeline produces a focused peak for a point target."""
        from pySimSAR.io.config import ProcessingConfig
        from pySimSAR.pipeline.runner import PipelineRunner

        raw_data, radar, trajectory = _simulate_for_pipeline(n_pulses=256)

        config = ProcessingConfig(image_formation="range_doppler")
        runner = PipelineRunner(config)
        result = runner.run(raw_data, radar, trajectory)

        img = result.images["single"]
        magnitude = np.abs(img.data)
        peak = np.max(magnitude)
        mean = np.mean(magnitude)

        assert peak > 10 * mean, (
            f"Peak {peak:.2e} not well above mean {mean:.2e}"
        )

    def test_pipeline_steps_recorded(self):
        """All applied steps are recorded in the result."""
        from pySimSAR.io.config import ProcessingConfig
        from pySimSAR.pipeline.runner import PipelineRunner

        raw_data, radar, trajectory = _simulate_for_pipeline(n_pulses=64)

        config = ProcessingConfig(
            image_formation="range_doppler",
            geocoding="georeferencing",
        )
        runner = PipelineRunner(config)
        result = runner.run(raw_data, radar, trajectory)

        assert len(result.steps_applied) >= 2

    def test_pipeline_with_different_algorithms(self):
        """Pipeline works with different image formation algorithms."""
        from pySimSAR.io.config import ProcessingConfig
        from pySimSAR.pipeline.runner import PipelineRunner

        raw_data, radar, trajectory = _simulate_for_pipeline(n_pulses=128)

        for algo in ["range_doppler", "chirp_scaling", "omega_k"]:
            config = ProcessingConfig(image_formation=algo)
            runner = PipelineRunner(config)
            result = runner.run(raw_data.copy(), radar, trajectory)

            assert "single" in result.images
            assert result.images["single"].algorithm == algo


class TestPipelineReprocessing:
    """T112: Integration test for re-processing (same raw data, different config)."""

    def test_reprocess_with_different_algorithm(self):
        """Same raw data processed with different algorithms produces different images."""
        from pySimSAR.io.config import ProcessingConfig
        from pySimSAR.pipeline.runner import PipelineRunner

        raw_data, radar, trajectory = _simulate_for_pipeline(n_pulses=128)

        config1 = ProcessingConfig(image_formation="range_doppler")
        config2 = ProcessingConfig(image_formation="chirp_scaling")

        result1 = PipelineRunner(config1).run(raw_data.copy(), radar, trajectory)
        result2 = PipelineRunner(config2).run(raw_data.copy(), radar, trajectory)

        img1 = result1.images["single"]
        img2 = result2.images["single"]

        # Both should produce focused images
        assert np.max(np.abs(img1.data)) > 0
        assert np.max(np.abs(img2.data)) > 0

        # Algorithm tags should differ
        assert img1.algorithm == "range_doppler"
        assert img2.algorithm == "chirp_scaling"

    def test_reprocess_with_geocoding_vs_without(self):
        """Re-processing with geocoding changes the output geometry."""
        from pySimSAR.io.config import ProcessingConfig
        from pySimSAR.pipeline.runner import PipelineRunner

        raw_data, radar, trajectory = _simulate_for_pipeline(n_pulses=64)

        config_no_geo = ProcessingConfig(image_formation="range_doppler")
        config_geo = ProcessingConfig(
            image_formation="range_doppler",
            geocoding="slant_to_ground",
        )

        result1 = PipelineRunner(config_no_geo).run(raw_data.copy(), radar, trajectory)
        result2 = PipelineRunner(config_geo).run(raw_data.copy(), radar, trajectory)

        assert result1.images["single"].geometry == "slant_range"
        assert result2.images["single"].geometry == "ground_range"

    def test_reprocess_preserves_raw_data(self):
        """Processing does not mutate the original raw data."""
        from pySimSAR.io.config import ProcessingConfig
        from pySimSAR.pipeline.runner import PipelineRunner

        raw_data, radar, trajectory = _simulate_for_pipeline(n_pulses=64)

        # Save a copy of the echo before processing
        echo_before = raw_data["single"].echo.copy()

        config = ProcessingConfig(image_formation="range_doppler")
        PipelineRunner(config).run(raw_data, radar, trajectory)

        # Echo should not be modified
        np.testing.assert_array_equal(raw_data["single"].echo, echo_before)


class TestDataImport:
    """T114: Integration test for HDF5 data import."""

    def test_import_round_trip(self, tmp_path):
        """Simulate → save HDF5 → import → verify data matches."""
        from pySimSAR.core.types import RawData
        from pySimSAR.io.hdf5_format import write_hdf5, import_data
        from pySimSAR.motion.trajectory import Trajectory

        raw_data, radar, trajectory = _simulate_for_pipeline(n_pulses=64)

        filepath = tmp_path / "test_import.h5"
        write_hdf5(
            filepath,
            raw_data=raw_data,
            trajectory=trajectory,
        )

        imported = import_data(filepath)

        assert "single" in imported["raw_data"]
        rd = imported["raw_data"]["single"]
        assert isinstance(rd, RawData)
        np.testing.assert_array_equal(rd.echo, raw_data["single"].echo)

        assert imported["trajectory"] is not None
        np.testing.assert_array_equal(
            imported["trajectory"].position, trajectory.position
        )

        assert imported["radar_params"]["carrier_freq"] == radar.carrier_freq
        assert imported["radar_params"]["bandwidth"] == radar.bandwidth

    def test_import_no_raw_data_raises(self, tmp_path):
        """Importing a file with no raw data raises ValueError."""
        from pySimSAR.io.hdf5_format import write_hdf5, import_data

        filepath = tmp_path / "empty.h5"
        write_hdf5(filepath)  # no raw_data

        with pytest.raises(ValueError, match="No raw data"):
            import_data(filepath)


# ===========================================================================
# T130: SAR mode validation tests
# ===========================================================================


class TestModeValidation:
    """T130: Verify SAR mode compatibility checks in PipelineRunner."""

    def test_incompatible_mode_raises_value_error(self):
        """Range-Doppler only supports stripmap; spotlight data should raise."""
        from pySimSAR.io.config import ProcessingConfig
        from pySimSAR.pipeline.runner import PipelineRunner
        from pySimSAR.core.types import RawData

        # Create minimal raw data tagged as spotlight mode
        raw_data = {
            "single": RawData(
                echo=np.zeros((16, 64), dtype=np.complex64),
                channel="single",
                sample_rate=300e6,
                carrier_freq=9.65e9,
                bandwidth=150e6,
                prf=1000.0,
                waveform_name="LFM",
                sar_mode="spotlight",
                gate_delay=0.0,
            )
        }

        # Range-Doppler supports only stripmap
        config = ProcessingConfig(image_formation="range_doppler")
        runner = PipelineRunner(config)

        with pytest.raises(ValueError, match="does not support SAR mode"):
            runner.run(raw_data, radar=_make_radar(), trajectory=object())

    def test_compatible_mode_does_not_raise(self):
        """Stripmap data with range-Doppler should not raise."""
        from pySimSAR.io.config import ProcessingConfig
        from pySimSAR.pipeline.runner import PipelineRunner
        from pySimSAR.core.types import RawData

        raw_data = {
            "single": RawData(
                echo=np.zeros((16, 64), dtype=np.complex64),
                channel="single",
                sample_rate=300e6,
                carrier_freq=9.65e9,
                bandwidth=150e6,
                prf=1000.0,
                waveform_name="LFM",
                sar_mode="stripmap",
                gate_delay=0.0,
            )
        }

        config = ProcessingConfig(image_formation="range_doppler")
        runner = PipelineRunner(config)

        # validate_config should not raise
        runner.validate_config(raw_data)

    def test_omega_k_rejects_scanmar(self):
        """Omega-K supports stripmap+spotlight but not scanmar."""
        from pySimSAR.io.config import ProcessingConfig
        from pySimSAR.pipeline.runner import PipelineRunner
        from pySimSAR.core.types import RawData

        raw_data = {
            "single": RawData(
                echo=np.zeros((16, 64), dtype=np.complex64),
                channel="single",
                sample_rate=300e6,
                carrier_freq=9.65e9,
                bandwidth=150e6,
                prf=1000.0,
                waveform_name="LFM",
                sar_mode="scanmar",
                gate_delay=0.0,
            )
        }

        config = ProcessingConfig(image_formation="omega_k")
        runner = PipelineRunner(config)

        with pytest.raises(ValueError, match="does not support SAR mode"):
            runner.validate_config(raw_data)


# ===========================================================================
# T131: Polarimetric input validation tests
# ===========================================================================


class TestPolarimetricValidation:
    """T131: Verify polarimetric decomposition requires quad-pol channels."""

    def test_polsar_without_quad_pol_raises_value_error(self):
        """Requesting polarimetric decomposition on single-pol data raises."""
        from pySimSAR.io.config import ProcessingConfig
        from pySimSAR.pipeline.runner import PipelineRunner

        raw_data, radar, trajectory = _simulate_for_pipeline(n_pulses=64)

        # raw_data has only "single" channel, not quad-pol
        config = ProcessingConfig(
            image_formation="range_doppler",
            polarimetric_decomposition="pauli",
        )
        runner = PipelineRunner(config)

        with pytest.raises(ValueError, match="missing"):
            runner.run(raw_data, radar, trajectory)

    def test_polsar_with_quad_pol_does_not_raise(self):
        """Quad-pol data with polarimetric decomposition should succeed."""
        from pySimSAR.io.config import ProcessingConfig
        from pySimSAR.pipeline.runner import PipelineRunner
        from pySimSAR.core.types import RawData
        from pySimSAR.motion.trajectory import Trajectory
        from pySimSAR.waveforms.lfm import LFMWaveform

        scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
        smat = np.array([[1.0 + 0j, 0.1 + 0j], [0.1 + 0j, 0.8 + 0j]])
        scene.add_target(PointTarget(position=[5000.0, 0, 0], rcs=smat))

        wf = LFMWaveform(bandwidth=150e6, duty_cycle=0.1, prf=1000.0)
        antenna = _make_isotropic_antenna()
        radar = Radar(
            carrier_freq=9.65e9,
            transmit_power=100.0,
            waveform=wf,
            antenna=antenna,
            polarization="quad",
            mode="stripmap",
            look_side="right",
            depression_angle=0.7,
        )
        sample_rate = 2.0 * radar.bandwidth

        n_pulses = 64
        engine = SimulationEngine(
            scene=scene,
            radar=radar,
            n_pulses=n_pulses,
            platform_start=np.array([0.0, -5000.0, 0.0]),
            platform_velocity=np.array([0.0, 100.0, 0.0]),
            seed=42,
            sample_rate=sample_rate,
        )
        result = engine.run()

        raw_data = {}
        for ch in ("hh", "hv", "vh", "vv"):
            raw_data[ch] = RawData(
                echo=result.echo[ch],
                channel=ch,
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

        config = ProcessingConfig(
            image_formation="range_doppler",
            polarimetric_decomposition="pauli",
        )
        runner = PipelineRunner(config)
        pipeline_result = runner.run(raw_data, radar, trajectory)

        assert pipeline_result.decomposition is not None
        assert "polarimetry:pauli" in pipeline_result.steps_applied
