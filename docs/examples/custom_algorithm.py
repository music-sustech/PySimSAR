"""Custom algorithm example: IdentityAlgorithm.

Defines a minimal image formation algorithm that passes range-compressed
data through without azimuth compression, registers it in the algorithm
registry, and runs it through the processing pipeline.

Usage:
    python custom_algorithm.py
"""

from __future__ import annotations

import numpy as np

from pySimSAR import (
    ProcessingConfig,
    Radar,
    Scene,
    SimulationEngine,
    create_antenna_from_preset,
)
from pySimSAR.algorithms.base import ImageFormationAlgorithm
from pySimSAR.algorithms.image_formation import image_formation_registry
from pySimSAR.core.radar import C_LIGHT
from pySimSAR.core.scene import PointTarget
from pySimSAR.core.types import PhaseHistoryData, RawData, SARImage, SARMode
from pySimSAR.pipeline.runner import PipelineRunner

# ---------------------------------------------------------------------------
# Step 1: Define the custom algorithm
# ---------------------------------------------------------------------------


class IdentityAlgorithm(ImageFormationAlgorithm):
    """Identity image formation: range compress only, skip azimuth compression.

    This is useful for inspecting range-compressed phase history data
    without the azimuth focusing step.
    """

    name = "identity"

    def supported_modes(self) -> list[SARMode]:
        return [SARMode.STRIPMAP, SARMode.SPOTLIGHT, SARMode.SCANMAR]

    def process(self, raw_data, radar, trajectory) -> SARImage:
        phd = self.range_compress(raw_data, radar)
        return self.azimuth_compress(phd, radar, trajectory)

    def range_compress(self, raw_data, radar) -> PhaseHistoryData:
        radar.waveform.generate(radar.waveform.prf, raw_data.sample_rate)
        compressed = radar.waveform.range_compress(
            raw_data.echo, radar.waveform.prf, raw_data.sample_rate
        )
        return PhaseHistoryData(
            data=compressed,
            sample_rate=raw_data.sample_rate,
            prf=radar.waveform.prf,
            carrier_freq=radar.carrier_freq,
            bandwidth=radar.bandwidth,
            channel=raw_data.channel,
            gate_delay=raw_data.gate_delay,
        )

    def azimuth_compress(self, phase_history, radar, trajectory) -> SARImage:
        # Pass data through unchanged (no azimuth compression)
        V = float(np.mean(np.linalg.norm(trajectory.velocity, axis=1)))
        near_range = phase_history.gate_delay * C_LIGHT / 2.0
        return SARImage(
            data=phase_history.data,
            pixel_spacing_range=C_LIGHT / (2.0 * phase_history.sample_rate),
            pixel_spacing_azimuth=V / phase_history.prf,
            geometry="slant_range",
            algorithm=self.name,
            channel=phase_history.channel,
            near_range=near_range,
        )

    @classmethod
    def parameter_schema(cls) -> dict:
        return {}  # No tunable parameters


# ---------------------------------------------------------------------------
# Step 2: Register the algorithm
# ---------------------------------------------------------------------------

image_formation_registry.register(IdentityAlgorithm)

# Verify registration
print(f"Registered algorithms: {image_formation_registry.list()}")
assert "identity" in image_formation_registry


# ---------------------------------------------------------------------------
# Step 3: Run through the pipeline
# ---------------------------------------------------------------------------


def main() -> None:
    from pySimSAR.waveforms.lfm import LFMWaveform

    # Scene with a single point target
    scene = Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=0.0)
    scene.add_target(PointTarget(position=np.array([5000.0, 0.0, 0.0]), rcs=1.0))

    # Radar
    waveform = LFMWaveform(bandwidth=50e6, duty_cycle=0.1, prf=500.0)
    antenna = create_antenna_from_preset(
        "sinc", az_beamwidth=0.05, el_beamwidth=0.1
    )
    radar = Radar(
        carrier_freq=9.65e9,
        transmit_power=1.0,
        waveform=waveform,
        antenna=antenna,
        polarization="single",
    )

    # Simulate
    engine = SimulationEngine(scene=scene, radar=radar, n_pulses=256, seed=42)
    sim_result = engine.run()

    # Build RawData
    raw_data = {}
    for ch, echo in sim_result.echo.items():
        raw_data[ch] = RawData(
            echo=echo,
            channel=ch,
            sample_rate=sim_result.sample_rate,
            carrier_freq=radar.carrier_freq,
            bandwidth=radar.bandwidth,
            prf=waveform.prf,
            waveform_name=waveform.name,
            gate_delay=sim_result.gate_delay,
        )

    # Build trajectory
    from pySimSAR.motion.trajectory import Trajectory

    trajectory = sim_result.true_trajectory
    if trajectory is None:
        trajectory = Trajectory(
            time=sim_result.pulse_times,
            position=sim_result.positions,
            velocity=sim_result.velocities,
            attitude=np.zeros((len(sim_result.pulse_times), 3)),
        )

    # Run pipeline with our custom "identity" algorithm
    config = ProcessingConfig(image_formation="identity")
    pipeline = PipelineRunner(config)
    result = pipeline.run(raw_data, radar, trajectory)

    image = next(iter(result.images.values()))
    print("\nIdentity algorithm result:")
    print(f"  Image shape: {image.data.shape}")
    print(f"  Algorithm: {image.algorithm}")
    print(f"  Range spacing: {image.pixel_spacing_range:.4f} m")
    print(f"  Azimuth spacing: {image.pixel_spacing_azimuth:.4f} m")
    print(f"  Peak amplitude: {np.max(np.abs(image.data)):.4f}")
    print(f"  Steps applied: {result.steps_applied}")


if __name__ == "__main__":
    main()
