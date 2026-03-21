"""T133: Final integration test — full pipeline from scene to geocoded polarimetric image.

End-to-end flow:
  scene (quad-pol point target)
  -> X-band LFM radar (quad-pol)
  -> simulate 128 pulses
  -> PipelineRunner (range_doppler + slant_to_ground + pauli)
  -> verify all 4 pol channels, geocoded geometry, Pauli decomposition
  -> HDF5 round-trip
"""

from __future__ import annotations

import numpy as np
import pytest

from pySimSAR.core.radar import AntennaPattern, Radar
from pySimSAR.core.scene import PointTarget, Scene
from pySimSAR.core.types import RawData, SARImage
from pySimSAR.io.config import ProcessingConfig
from pySimSAR.io.hdf5_format import read_hdf5, write_hdf5
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.pipeline.runner import PipelineRunner
from pySimSAR.simulation.engine import SimulationEngine
from pySimSAR.waveforms.lfm import LFMWaveform

N_PULSES = 128


def _setup_quad_pol_simulation():
    """Create scene, radar, and run simulation for the full pipeline test.

    Returns
    -------
    raw_data : dict[str, RawData]
    radar : Radar
    trajectory : Trajectory
    """
    # 1. Scene with a single quad-pol point target at [5000, 0, 0]
    scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)
    scattering_matrix = np.array([
        [1.0 + 0j, 0.3 + 0j],
        [0.3 + 0j, 0.8 + 0j],
    ])
    scene.add_target(PointTarget(position=[5000.0, 0.0, 0.0], rcs=scattering_matrix))

    # 2. X-band LFM radar in quad-pol mode
    wf = LFMWaveform(bandwidth=150e6, duty_cycle=0.1, prf=1000.0)
    az = np.linspace(-np.pi, np.pi, 5)
    el = np.linspace(-np.pi / 2, np.pi / 2, 5)
    pattern = np.full((len(el), len(az)), 30.0)
    antenna = AntennaPattern(
        pattern_2d=pattern,
        az_beamwidth=np.radians(10),
        el_beamwidth=np.radians(10),
        az_angles=az,
        el_angles=el,
    )
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

    # 3. Simulate 128 pulses
    engine = SimulationEngine(
        scene=scene,
        radar=radar,
        n_pulses=N_PULSES,
        platform_start=np.array([0.0, -5000.0, 0.0]),
        platform_velocity=np.array([0.0, 100.0, 0.0]),
        seed=42,
        sample_rate=sample_rate,
    )
    result = engine.run()

    # 4. Build RawData dict for all quad-pol channels
    raw_data = {}
    for ch, echo in result.echo.items():
        raw_data[ch] = RawData(
            echo=echo,
            channel=ch,
            sample_rate=sample_rate,
            carrier_freq=radar.carrier_freq,
            bandwidth=radar.bandwidth,
            prf=radar.waveform.prf,
            waveform_name=radar.waveform.name,
            sar_mode="stripmap",
            gate_delay=result.gate_delay,
        )

    # 5. Build trajectory
    trajectory = Trajectory(
        time=result.pulse_times,
        position=result.positions,
        velocity=result.velocities,
        attitude=np.zeros((N_PULSES, 3)),
    )

    return raw_data, radar, trajectory


class TestFinalPipeline:
    """T133: Full end-to-end pipeline integration test."""

    @pytest.fixture(autouse=True)
    def _run_pipeline(self):
        """Run the full pipeline once and cache the result for all tests."""
        raw_data, radar, trajectory = _setup_quad_pol_simulation()

        config = ProcessingConfig(
            image_formation="range_doppler",
            geocoding="slant_to_ground",
            polarimetric_decomposition="pauli",
        )
        runner = PipelineRunner(config)
        self.pipeline_result = runner.run(raw_data, radar, trajectory)
        self.radar = radar
        self.trajectory = trajectory
        self.raw_data = raw_data

    # ------------------------------------------------------------------
    # Verify all 4 polarimetric channels are produced
    # ------------------------------------------------------------------

    def test_all_four_pol_channels_present(self):
        """Pipeline produces images for HH, HV, VH, VV."""
        expected_channels = {"hh", "hv", "vh", "vv"}
        assert set(self.pipeline_result.images.keys()) == expected_channels

    def test_each_channel_is_sar_image(self):
        """Each output channel is a SARImage with 2-D data."""
        for ch, img in self.pipeline_result.images.items():
            assert isinstance(img, SARImage), f"Channel {ch} is not SARImage"
            assert img.data.ndim == 2, f"Channel {ch} data is not 2-D"
            assert img.data.size > 0, f"Channel {ch} has empty data"

    def test_channel_shapes_consistent(self):
        """All four channel images have the same shape."""
        shapes = {ch: img.data.shape for ch, img in self.pipeline_result.images.items()}
        ref = shapes["hh"]
        for ch, shape in shapes.items():
            assert shape == ref, f"Channel {ch} shape {shape} != HH shape {ref}"

    # ------------------------------------------------------------------
    # Verify geocoding to ground_range
    # ------------------------------------------------------------------

    def test_geocoded_to_ground_range(self):
        """All channels are geocoded to ground_range geometry."""
        for ch, img in self.pipeline_result.images.items():
            assert img.geometry == "ground_range", (
                f"Channel {ch} geometry is '{img.geometry}', expected 'ground_range'"
            )

    def test_geocoding_step_recorded(self):
        """The geocoding step is recorded in steps_applied."""
        assert "geocoding:slant_to_ground" in self.pipeline_result.steps_applied

    # ------------------------------------------------------------------
    # Verify Pauli decomposition computed
    # ------------------------------------------------------------------

    def test_pauli_decomposition_present(self):
        """Pipeline produces a Pauli polarimetric decomposition."""
        assert self.pipeline_result.decomposition is not None
        assert isinstance(self.pipeline_result.decomposition, dict)
        assert len(self.pipeline_result.decomposition) > 0

    def test_pauli_decomposition_step_recorded(self):
        """The polarimetry step is recorded in steps_applied."""
        assert "polarimetry:pauli" in self.pipeline_result.steps_applied

    def test_pauli_components_are_arrays(self):
        """Each Pauli component is a numpy array with matching image dimensions."""
        ref_shape = self.pipeline_result.images["hh"].data.shape
        for name, arr in self.pipeline_result.decomposition.items():
            assert isinstance(arr, np.ndarray), (
                f"Pauli component '{name}' is not ndarray"
            )
            assert arr.shape == ref_shape, (
                f"Pauli '{name}' shape {arr.shape} != image shape {ref_shape}"
            )

    # ------------------------------------------------------------------
    # Verify image formation step recorded
    # ------------------------------------------------------------------

    def test_image_formation_step_recorded(self):
        """The image formation step is recorded in steps_applied."""
        assert "image_formation:range_doppler" in self.pipeline_result.steps_applied

    def test_all_three_steps_applied(self):
        """All three processing steps (IF, geocoding, polarimetry) are recorded."""
        steps = self.pipeline_result.steps_applied
        assert len(steps) >= 3
        step_prefixes = [s.split(":")[0] for s in steps]
        assert "image_formation" in step_prefixes
        assert "geocoding" in step_prefixes
        assert "polarimetry" in step_prefixes

    # ------------------------------------------------------------------
    # Verify images have non-trivial content (focused energy)
    # ------------------------------------------------------------------

    def test_images_have_signal_energy(self):
        """Each channel image has a detectable peak above background."""
        for ch, img in self.pipeline_result.images.items():
            magnitude = np.abs(img.data)
            peak = np.max(magnitude)
            mean = np.mean(magnitude)
            assert peak > 3 * mean, (
                f"Channel {ch}: peak {peak:.2e} not well above mean {mean:.2e}"
            )


class TestFinalPipelineHDF5RoundTrip:
    """T133: HDF5 save/reload round-trip for the full pipeline output."""

    def test_hdf5_round_trip(self, tmp_path):
        """Save pipeline output to HDF5, reload, and verify data preserved."""
        raw_data, radar, trajectory = _setup_quad_pol_simulation()

        config = ProcessingConfig(
            image_formation="range_doppler",
            geocoding="slant_to_ground",
            polarimetric_decomposition="pauli",
        )
        runner = PipelineRunner(config)
        result = runner.run(raw_data, radar, trajectory)

        # Save images and raw data to HDF5
        filepath = tmp_path / "final_pipeline.h5"
        write_hdf5(
            filepath,
            raw_data=raw_data,
            trajectory=trajectory,
            images=result.images,
        )

        # Reload
        loaded = read_hdf5(filepath)

        # Verify raw data round-trip
        assert set(loaded["raw_data"].keys()) == {"hh", "hv", "vh", "vv"}
        for ch in ("hh", "hv", "vh", "vv"):
            np.testing.assert_array_equal(
                loaded["raw_data"][ch].echo,
                raw_data[ch].echo,
                err_msg=f"Raw data mismatch for channel {ch}",
            )
            assert loaded["raw_data"][ch].carrier_freq == raw_data[ch].carrier_freq
            assert loaded["raw_data"][ch].bandwidth == raw_data[ch].bandwidth
            assert loaded["raw_data"][ch].prf == raw_data[ch].prf
            assert loaded["raw_data"][ch].sample_rate == raw_data[ch].sample_rate

        # Verify trajectory round-trip
        assert loaded["trajectory"] is not None
        np.testing.assert_array_equal(
            loaded["trajectory"].position, trajectory.position
        )
        np.testing.assert_array_equal(
            loaded["trajectory"].velocity, trajectory.velocity
        )

        # Verify images round-trip
        assert set(loaded["images"].keys()) == {"hh", "hv", "vh", "vv"}
        for ch in ("hh", "hv", "vh", "vv"):
            loaded_img = loaded["images"][ch]
            original_img = result.images[ch]
            assert isinstance(loaded_img, SARImage)
            np.testing.assert_array_equal(
                loaded_img.data,
                original_img.data,
                err_msg=f"Image data mismatch for channel {ch}",
            )
            assert loaded_img.geometry == original_img.geometry
            assert loaded_img.algorithm == original_img.algorithm
            assert loaded_img.channel == original_img.channel
            assert loaded_img.pixel_spacing_range == pytest.approx(
                original_img.pixel_spacing_range
            )
            assert loaded_img.pixel_spacing_azimuth == pytest.approx(
                original_img.pixel_spacing_azimuth
            )
