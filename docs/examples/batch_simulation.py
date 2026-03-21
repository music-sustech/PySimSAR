"""Batch simulation across multiple carrier frequencies.

Loops over three carrier frequencies (1 GHz, 5 GHz, 10 GHz), runs a SAR
simulation for each, forms a focused image, and prints the resulting image
resolution and peak response.

Usage:
    python batch_simulation.py
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
from pySimSAR.core.scene import PointTarget
from pySimSAR.core.types import RawData
from pySimSAR.pipeline.runner import PipelineRunner
from pySimSAR.waveforms.lfm import LFMWaveform


def main() -> None:
    # Carrier frequencies to test
    carrier_frequencies = [1e9, 5e9, 10e9]

    # Fixed scene: single point target at 5 km range
    scene = Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=0.0)
    scene.add_target(PointTarget(position=np.array([5000.0, 0.0, 0.0]), rcs=1.0))

    print("Carrier Freq (GHz) | Range Res (m) | Azimuth Res (m) | Peak Amplitude")
    print("-" * 75)

    for fc in carrier_frequencies:
        # Configure radar for this carrier frequency
        waveform = LFMWaveform(bandwidth=50e6, duty_cycle=0.1, prf=500.0)
        antenna = create_antenna_from_preset(
            "sinc",
            az_beamwidth=0.05,
            el_beamwidth=0.1,
        )
        radar = Radar(
            carrier_freq=fc,
            transmit_power=1.0,
            waveform=waveform,
            antenna=antenna,
            polarization="single",
        )

        # Simulate raw echo data
        engine = SimulationEngine(
            scene=scene,
            radar=radar,
            n_pulses=256,
            seed=42,
        )
        sim_result = engine.run()

        # Build RawData for pipeline
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

        # Form focused image using Range-Doppler algorithm
        config = ProcessingConfig(image_formation="range_doppler")
        pipeline = PipelineRunner(config)

        # Use true_trajectory if available, else fall back to sim_result
        trajectory = sim_result.true_trajectory
        if trajectory is None:
            # Build a simple trajectory from positions/velocities
            from pySimSAR.motion.trajectory import Trajectory

            trajectory = Trajectory(
                time=sim_result.pulse_times,
                position=sim_result.positions,
                velocity=sim_result.velocities,
                attitude=np.zeros((len(sim_result.pulse_times), 3)),
            )

        pipe_result = pipeline.run(raw_data, radar, trajectory)

        # Extract results
        image = next(iter(pipe_result.images.values()))
        peak = float(np.max(np.abs(image.data)))

        print(
            f"{fc / 1e9:>18.1f} | "
            f"{image.pixel_spacing_range:>13.3f} | "
            f"{image.pixel_spacing_azimuth:>15.3f} | "
            f"{peak:>14.2f}"
        )


if __name__ == "__main__":
    main()
