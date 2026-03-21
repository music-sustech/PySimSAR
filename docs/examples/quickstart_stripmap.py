"""End-to-end stripmap simulation using the default preset.

This script demonstrates a complete SAR simulation workflow:
scene setup, radar configuration, signal simulation, image formation,
and result inspection — all using the shipped default_stripmap preset
parameters.
"""

from pySimSAR import (
    PipelineRunner,
    Platform,
    PointTarget,
    Radar,
    Scene,
    SimulationEngine,
)
from pySimSAR.core.radar import create_antenna_from_preset
from pySimSAR.core.types import RawData, SARModeConfig
from pySimSAR.io.config import ProcessingConfig
from pySimSAR.waveforms.lfm import LFMWaveform

# --- Scene: single point target at scene center ---
scene = Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=0.0)
scene.add_target(PointTarget(position=[0, 0, 0], rcs=1.0))

# --- Radar: X-band stripmap (default_stripmap preset values) ---
waveform = LFMWaveform(bandwidth=50e6, duty_cycle=0.1, prf=500)
antenna = create_antenna_from_preset("sinc", az_beamwidth=0.05, el_beamwidth=0.1)
radar = Radar(
    carrier_freq=9.65e9,
    transmit_power=1000,
    waveform=waveform,
    antenna=antenna,
    polarization="single",
    sar_mode_config=SARModeConfig(mode="stripmap", depression_angle=0.7854),
)

# --- Platform: straight-and-level flight ---
platform = Platform(velocity=100, altitude=5000, heading=0)

# --- Simulate raw echo data ---
engine = SimulationEngine(scene=scene, radar=radar, n_pulses=256, platform=platform)
result = engine.run()
print(f"Simulation complete: {result.echo['single'].shape} echo samples")

# --- Process into focused image ---
config = ProcessingConfig(image_formation="range_doppler")
runner = PipelineRunner(config)
raw_data = {}
for ch, echo in result.echo.items():
    raw_data[ch] = RawData(
        echo=echo, channel=ch, sample_rate=result.sample_rate,
        carrier_freq=radar.carrier_freq, bandwidth=radar.bandwidth,
        prf=waveform.prf, waveform_name="lfm", sar_mode="stripmap",
        gate_delay=result.gate_delay,
    )
trajectory = result.true_trajectory or result.ideal_trajectory
pipeline_result = runner.run(raw_data, radar, trajectory,
                             ideal_trajectory=result.ideal_trajectory)

# --- Inspect the focused image ---
image = pipeline_result.images["single"]
print(f"Focused image shape: {image.data.shape}")
print(f"Range pixel spacing:   {image.pixel_spacing_range:.2f} m")
print(f"Azimuth pixel spacing: {image.pixel_spacing_azimuth:.2f} m")
print(f"Algorithm: {image.algorithm}")
print(f"Geometry:  {image.geometry}")

# --- Optional: save to HDF5 ---
# result.save("stripmap_raw.h5", radar=radar)
# image.save("stripmap_image.h5")
