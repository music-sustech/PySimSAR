# Quickstart: PySimSAR

## Installation

```bash
# Clone and install in development mode
git clone <repo-url> PySimSAR
cd PySimSAR
pip install -e ".[dev]"
```

## 1. Basic Point Target Simulation (Python API)

```python
from pySimSAR.core.scene import Scene, PointTarget
from pySimSAR.core.radar import Radar, create_antenna_from_preset
from pySimSAR.core.platform import Platform
from pySimSAR.waveforms import LFMWaveform
from pySimSAR.simulation.engine import SimulationEngine

# Define a scene with 3 point targets
scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=1600.0)
scene.add_target(PointTarget(position=[0, 0, 0], rcs=1.0))
scene.add_target(PointTarget(position=[100, 0, 0], rcs=0.5))
scene.add_target(PointTarget(position=[0, 200, 0], rcs=0.8))

# Configure X-band radar with LFM chirp
# duty_cycle=0.1 means pulse occupies 10% of PRI
waveform = LFMWaveform(bandwidth=150e6, duty_cycle=0.1)

# Create a flat antenna pattern (beamwidths in radians, gain derived from beamwidths)
antenna = create_antenna_from_preset(
    "flat",
    az_beamwidth=0.05,
    el_beamwidth=0.1,
)

radar = Radar(
    carrier_freq=9.65e9,
    prf=1000.0,
    transmit_power=100.0,
    waveform=waveform,
    antenna=antenna,
    polarization="single",
    mode="stripmap",
    look_side="right",
    depression_angle=0.7,  # ~40 degrees from horizontal
)

# Define platform (straight-line flight, 2000m altitude, 100 m/s)
platform = Platform(
    velocity=100.0,
    altitude=2000.0,
    heading=0.0,
    start_position=[-500, -5000, 2000],
)

# Run simulation
engine = SimulationEngine(scene=scene, radar=radar, platform=platform, seed=42)
result = engine.run()

# Save to HDF5
result.save("point_target_sim.h5", radar=radar)
```

## 2. With Motion Perturbation and Sensors

```python
from pySimSAR.motion.perturbation import DrydenTurbulence
from pySimSAR.sensors.gps import GPSSensor
from pySimSAR.sensors.imu import IMUSensor
from pySimSAR.sensors.gps_gaussian import GaussianGPSError
from pySimSAR.sensors.imu_white_noise import WhiteNoiseIMUError

# Create motion perturbation model
perturbation = DrydenTurbulence(
    sigma_u=1.0, sigma_v=1.0, sigma_w=0.5,
)

# Create sensors with error models
gps = GPSSensor(
    accuracy_rms=0.02,
    update_rate=10.0,
    error_model=GaussianGPSError(accuracy_rms=0.02),
)
imu = IMUSensor(
    accel_noise_density=0.0002,  # m/s^2/sqrt(Hz)
    gyro_noise_density=5e-6,     # rad/s/sqrt(Hz)
    sample_rate=200.0,
    error_model=WhiteNoiseIMUError(
        accel_noise_density=0.0002,
        gyro_noise_density=5e-6,
    ),
)

# Pass perturbation and sensors via Platform constructor
platform = Platform(
    velocity=100.0,
    altitude=2000.0,
    heading=0.0,
    start_position=[-500, -5000, 2000],
    perturbation=perturbation,
    sensors=[gps, imu],
)

# Simulate (reusing scene and radar from Section 1)
engine = SimulationEngine(scene=scene, radar=radar, platform=platform, seed=42)
result = engine.run()

# result.ideal_trajectory    -- Trajectory object (ideal straight line)
# result.true_trajectory     -- Trajectory object (perturbed by turbulence)
# result.navigation_data     -- list of NavigationData from each sensor
# result.echo                -- dict of echo arrays keyed by channel name
```

## 3. Processing Pipeline (MoCo + Image Formation)

```python
from pySimSAR.algorithms.moco import FirstOrderMoCo
from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm
from pySimSAR.core.types import RawData

# Build RawData from simulation result for the "single" channel
raw = RawData(
    echo=result.echo["single"],
    channel="single",
    sample_rate=result.sample_rate,
    carrier_freq=radar.carrier_freq,
    bandwidth=radar.bandwidth,
    prf=radar.prf,
    waveform_name=radar.waveform.name,
    sar_mode=radar.mode.value,
    gate_delay=result.gate_delay,
)

# Option A: Manual step-by-step (no autofocus)
moco = FirstOrderMoCo()
compensated = moco.compensate(
    raw, result.navigation_data[0], result.ideal_trajectory
)

rda = RangeDopplerAlgorithm()
image = rda.process(compensated, radar, result.true_trajectory)
```

## 4. Two-Step Image Formation with Autofocus

```python
from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm
from pySimSAR.algorithms.autofocus import PhaseGradientAutofocus

rda = RangeDopplerAlgorithm()
pga = PhaseGradientAutofocus(max_iterations=10)

# Step 1: Range compression -> PhaseHistoryData
phase_history = rda.range_compress(compensated, radar)

# Step 2: Autofocus corrects residual phase errors,
#          calls rda.azimuth_compress() internally
def az_compress(phd):
    return rda.azimuth_compress(phd, radar, result.true_trajectory)

image = pga.focus(phase_history, az_compress)
```

## 5. Using ProcessingConfig and PipelineRunner

```python
from pySimSAR.pipeline.runner import PipelineRunner
from pySimSAR.io.config import ProcessingConfig
from pySimSAR.core.types import RawData

# Configure the full pipeline using algorithm name strings
proc_config = ProcessingConfig(
    moco="first_order",
    image_formation="range_doppler",
    autofocus="pga",
    autofocus_params={"max_iterations": 10},
    geocoding=None,                    # skip geocoding
    polarimetric_decomposition=None,   # skip polsar
)

# Build raw_data dict from simulation result
raw_data = {
    "single": RawData(
        echo=result.echo["single"],
        channel="single",
        sample_rate=result.sample_rate,
        carrier_freq=radar.carrier_freq,
        bandwidth=radar.bandwidth,
        prf=radar.prf,
        waveform_name=radar.waveform.name,
        sar_mode=radar.mode.value,
        gate_delay=result.gate_delay,
    ),
}

# Run the pipeline
runner = PipelineRunner(proc_config)
pipeline_result = runner.run(
    raw_data=raw_data,
    radar=radar,
    trajectory=result.true_trajectory,
    nav_data=result.navigation_data[0] if result.navigation_data else None,
    ideal_trajectory=result.ideal_trajectory,
)

# Re-process with a different algorithm -- no re-simulation needed
proc_config_2 = ProcessingConfig(
    moco="first_order",
    image_formation="omega_k",
    autofocus=None,  # skip autofocus this time
)
pipeline_result_2 = PipelineRunner(proc_config_2).run(
    raw_data=raw_data,
    radar=radar,
    trajectory=result.true_trajectory,
    nav_data=result.navigation_data[0] if result.navigation_data else None,
    ideal_trajectory=result.ideal_trajectory,
)
```

## 6. FMCW Waveform with Phase Noise

```python
import numpy as np
from pySimSAR.waveforms import FMCWWaveform, CompositePSDPhaseNoise
from pySimSAR.core.radar import Radar, create_antenna_from_preset

pn = CompositePSDPhaseNoise(
    flicker_fm_level=-80,   # dBc/Hz at 1 kHz offset
    white_fm_level=-100,
    flicker_pm_level=-120,
    white_floor=-150,
)

waveform = FMCWWaveform(
    bandwidth=1e9,
    duty_cycle=0.8,
    ramp_type="triangle",
    window=np.hanning,      # callable: np.hanning(n) -> array
    phase_noise=pn,
)

antenna = create_antenna_from_preset(
    "sinc",
    az_beamwidth=0.02,
    el_beamwidth=0.04,
)

radar = Radar(
    carrier_freq=77e9,       # W-band FMCW
    prf=20000.0,             # PRI = 50 us
    transmit_power=0.1,
    waveform=waveform,
    antenna=antenna,
    polarization="single",
    mode="stripmap",
    look_side="right",
    depression_angle=0.8,
)
# waveform.duration = 0.8 / 20000 = 40 us (derived automatically)
```

## 7. Launch the GUI

```bash
python -m pySimSAR.gui
```

Or from Python:

```python
from pySimSAR.gui.app import launch
launch()
```

## 8. Run Tests

```bash
# All tests
pytest tests/

# Specific test category
pytest tests/unit/
pytest tests/integration/
pytest tests/contract/

# Single test file
pytest tests/unit/test_waveforms.py -v
```
