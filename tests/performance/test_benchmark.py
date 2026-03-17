"""Performance benchmark for SAR simulation engine (T127, SC-006).

Verifies that a 1024-pulse simulation with 16 point targets completes
end-to-end (signal generation + range-Doppler image formation) in
under 60 seconds wall-clock time.

Run manually with:
    python -m pytest tests/performance/test_benchmark.py -v -m slow
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from pySimSAR.core.radar import Radar, create_antenna_from_preset
from pySimSAR.core.scene import PointTarget, Scene
from pySimSAR.core.types import RawData
from pySimSAR.io.config import ProcessingConfig
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.pipeline.runner import PipelineRunner
from pySimSAR.simulation.engine import SimulationEngine
from pySimSAR.waveforms.lfm import LFMWaveform

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

N_PULSES = 1024
N_TARGETS = 16
TIME_LIMIT_SECONDS = 60.0


def _create_scene(n_targets: int = N_TARGETS) -> Scene:
    """Create a scene with point targets spread in a 4x4 grid.

    Targets are placed in the x-y plane at z=0, spanning a 1 km x 1 km
    area centered at (5000, 0, 0) so they sit at ~5 km range from the
    platform.
    """
    scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=0.0)

    grid_side = int(np.ceil(np.sqrt(n_targets)))
    spacing = 1000.0 / max(grid_side - 1, 1)  # 1 km extent

    count = 0
    for i in range(grid_side):
        for j in range(grid_side):
            if count >= n_targets:
                break
            x = 4500.0 + i * spacing  # range direction: 4500-5500 m
            y = -500.0 + j * spacing  # azimuth direction: -500 to +500 m
            scene.add_target(PointTarget(position=np.array([x, y, 0.0]), rcs=10.0))
            count += 1

    return scene


def _create_radar() -> Radar:
    """Create a standard X-band LFM radar configuration."""
    waveform = LFMWaveform(bandwidth=150e6, duty_cycle=0.1)
    antenna = create_antenna_from_preset(
        preset="sinc",
        az_beamwidth=np.radians(3.0),
        el_beamwidth=np.radians(5.0),
        peak_gain_dB=30.0,
    )
    return Radar(
        carrier_freq=9.65e9,  # X-band
        prf=1000.0,
        transmit_power=100.0,
        waveform=waveform,
        antenna=antenna,
        polarization="single",
        mode="stripmap",
        look_side="right",
        depression_angle=0.7,
    )


# ---------------------------------------------------------------------------
# Benchmark test
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestSimulationBenchmark:
    """Performance benchmark: 1024 pulses, 16 targets, full pipeline."""

    def test_full_pipeline_under_60s(self):
        """End-to-end simulation + image formation completes in < 60 s.

        Steps timed:
        1. SimulationEngine.run() -- raw echo generation (1024 pulses,
           16 point targets, single-pol stripmap).
        2. PipelineRunner.run() -- range-Doppler image formation.

        Success criterion (SC-006): total wall-clock time < 60 seconds.
        """
        # -- Setup (not timed) --
        scene = _create_scene(N_TARGETS)
        radar = _create_radar()
        bandwidth = radar.bandwidth
        sample_rate = 2.0 * bandwidth

        engine = SimulationEngine(
            scene=scene,
            radar=radar,
            n_pulses=N_PULSES,
            platform_start=np.array([0.0, -5000.0, 2000.0]),
            platform_velocity=np.array([0.0, 100.0, 0.0]),
            seed=42,
            sample_rate=sample_rate,
        )

        # -- Timed section --
        t_start = time.perf_counter()

        # Step 1: Raw signal simulation
        sim_result = engine.run()

        t_sim = time.perf_counter()

        # Prepare data for the processing pipeline
        raw_data = {
            "single": RawData(
                echo=sim_result.echo["single"],
                channel="single",
                sample_rate=sample_rate,
                carrier_freq=radar.carrier_freq,
                bandwidth=bandwidth,
                prf=radar.prf,
                waveform_name=radar.waveform.name,
                sar_mode="stripmap",
                gate_delay=sim_result.gate_delay,
            )
        }

        trajectory = Trajectory(
            time=sim_result.pulse_times,
            position=sim_result.positions,
            velocity=sim_result.velocities,
            attitude=np.zeros((N_PULSES, 3)),
        )

        # Step 2: Image formation (range-Doppler)
        config = ProcessingConfig(image_formation="range_doppler")
        runner = PipelineRunner(config)
        pipeline_result = runner.run(raw_data, radar, trajectory)

        t_end = time.perf_counter()

        # -- Timing report --
        dt_sim = t_sim - t_start
        dt_proc = t_end - t_sim
        dt_total = t_end - t_start

        print(f"\n{'='*60}")
        print(f"  Performance Benchmark Results")
        print(f"  Pulses: {N_PULSES}, Targets: {N_TARGETS}")
        print(f"{'='*60}")
        print(f"  Simulation time : {dt_sim:8.2f} s")
        print(f"  Processing time : {dt_proc:8.2f} s")
        print(f"  Total time      : {dt_total:8.2f} s")
        print(f"  Time limit      : {TIME_LIMIT_SECONDS:8.2f} s")
        print(f"  Status          : {'PASS' if dt_total < TIME_LIMIT_SECONDS else 'FAIL'}")
        print(f"{'='*60}")

        # -- Assertions --
        # Sanity: pipeline produced an image
        assert "single" in pipeline_result.images, (
            "Pipeline did not produce a 'single' channel image"
        )
        img = pipeline_result.images["single"]
        assert img.data.ndim == 2, f"Image is not 2-D, shape={img.data.shape}"
        assert img.data.size > 0, "Image is empty"

        # Performance gate
        assert dt_total < TIME_LIMIT_SECONDS, (
            f"Total time {dt_total:.2f}s exceeds {TIME_LIMIT_SECONDS:.0f}s limit "
            f"(sim={dt_sim:.2f}s, proc={dt_proc:.2f}s)"
        )
