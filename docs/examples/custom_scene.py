"""Custom scene simulation with three point targets.

This example demonstrates the full PySimSAR workflow:
  1. Create a Scene with 3 point targets at different positions
  2. Configure a custom X-band radar with LFM waveform
  3. Set up a platform with straight-line flight path
  4. Run the simulation to generate raw SAR echoes
  5. Process with the Range-Doppler algorithm
  6. Print image shape and resolution metrics

Usage:
    python docs/examples/custom_scene.py
"""

import numpy as np

from pySimSAR import (
    PipelineRunner,
    Platform,
    PointTarget,
    ProcessingConfig,
    Radar,
    Scene,
    SimulationEngine,
    create_antenna_from_preset,
)
from pySimSAR.core.types import RawData
from pySimSAR.waveforms.lfm import LFMWaveform

# ── Physical constants ──────────────────────────────────────────────
C_LIGHT = 299_792_458.0  # m/s


# ── 1. Scene ────────────────────────────────────────────────────────
# Three point targets arranged in range, at ground level.
# Positions are in the East-North-Up (ENU) coordinate system (meters).
scene = Scene(origin_lat=22.5, origin_lon=113.9, origin_alt=0.0)

scene.add_target(PointTarget(position=np.array([900.0, 0.0, 0.0]), rcs=1.0))
scene.add_target(PointTarget(position=np.array([950.0, 0.0, 0.0]), rcs=1.0))
scene.add_target(PointTarget(position=np.array([1000.0, 0.0, 0.0]), rcs=1.0))

print(f"Scene: {len(scene.point_targets)} point targets")
for i, pt in enumerate(scene.point_targets):
    print(f"  Target {i}: position={pt.position}, RCS={pt.rcs} m^2")


# ── 2. Radar ────────────────────────────────────────────────────────
# X-band (9.65 GHz) pulsed LFM radar.
carrier_freq = 9.65e9       # Hz (X-band)
bandwidth = 150e6           # Hz (150 MHz -> ~1 m range resolution)
prf = 1000.0                # Hz
duty_cycle = 0.01           # 1% duty cycle

waveform = LFMWaveform(
    bandwidth=bandwidth,
    duty_cycle=duty_cycle,
    prf=prf,
)

antenna = create_antenna_from_preset(
    preset="flat",
    az_beamwidth=np.radians(10.0),
    el_beamwidth=np.radians(10.0),
)

radar = Radar(
    carrier_freq=carrier_freq,
    transmit_power=1.0,          # Watts
    waveform=waveform,
    antenna=antenna,
    polarization="single",
    mode="stripmap",
    look_side="right",
    depression_angle=np.radians(45.0),
    noise_figure=3.0,            # dB
    system_losses=2.0,           # dB
    receiver_gain_dB=30.0,
)

wavelength = radar.wavelength
range_resolution = C_LIGHT / (2.0 * bandwidth)
print(f"\nRadar: {carrier_freq/1e9:.2f} GHz, wavelength={wavelength*100:.2f} cm")
print(f"  Bandwidth: {bandwidth/1e6:.0f} MHz -> range resolution ~{range_resolution:.2f} m")
print(f"  PRF: {prf:.0f} Hz, duty cycle: {duty_cycle*100:.0f}%")


# ── 3. Platform ─────────────────────────────────────────────────────
# Airborne platform flying north at 100 m/s, 1000 m altitude.
platform = Platform(
    velocity=100.0,                                   # m/s
    altitude=1000.0,                                  # m
    heading=np.array([0.0, 1.0, 0.0]),                # north (+Y)
    start_position=np.array([0.0, -25.0, 1000.0]),    # ENU meters
)

n_pulses = 512
print(f"\nPlatform: v={platform.velocity} m/s, alt={platform.altitude} m")
print(f"  Heading: {platform.heading_vector}")
print(f"  Simulating {n_pulses} pulses ({n_pulses/prf:.3f} s flight)")


# ── 4. Simulate ─────────────────────────────────────────────────────
engine = SimulationEngine(
    scene=scene,
    radar=radar,
    n_pulses=n_pulses,
    platform=platform,
    seed=42,
)
sim_result = engine.run()

echo_shape = sim_result.echo["single"].shape
print("\nSimulation complete:")
print(f"  Echo shape: {echo_shape} (pulses x range samples)")
print(f"  Sample rate: {sim_result.sample_rate/1e6:.1f} MHz")
print(f"  Gate delay: {sim_result.gate_delay*1e6:.2f} us")


# ── 5. Process with Range-Doppler ───────────────────────────────────
proc_config = ProcessingConfig(
    image_formation="range_doppler",
    image_formation_params={"apply_rcmc": True},
)

# Build RawData objects for the pipeline
raw_data = {}
for ch, echo in sim_result.echo.items():
    raw_data[ch] = RawData(
        echo=echo,
        channel=ch,
        sample_rate=sim_result.sample_rate,
        carrier_freq=radar.carrier_freq,
        bandwidth=radar.bandwidth,
        prf=prf,
        waveform_name="lfm",
        sar_mode="stripmap",
        gate_delay=sim_result.gate_delay,
    )

pipeline = PipelineRunner(proc_config)
pipe_result = pipeline.run(
    raw_data=raw_data,
    radar=radar,
    trajectory=sim_result.true_trajectory or sim_result.ideal_trajectory,
    ideal_trajectory=sim_result.ideal_trajectory,
)


# ── 6. Results ──────────────────────────────────────────────────────
for ch_name, img in pipe_result.images.items():
    print(f"\nFocused image (channel={ch_name}):")
    print(f"  Shape: {img.data.shape}")
    print(f"  Range pixel spacing:   {img.pixel_spacing_range:.3f} m")
    print(f"  Azimuth pixel spacing: {img.pixel_spacing_azimuth:.3f} m")
    print(f"  Algorithm: {img.algorithm}")
    print(f"  Geometry: {img.geometry}")
    print(f"  Steps applied: {pipe_result.steps_applied}")
