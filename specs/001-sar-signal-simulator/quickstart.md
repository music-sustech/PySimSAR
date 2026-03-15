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
from pySimSAR.core.radar import Radar
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
radar = Radar(
    carrier_freq=9.65e9,
    prf=1000.0,
    transmit_power=100.0,
    waveform=waveform,
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
result.save("point_target_sim.h5")
```

## 2. With Motion Perturbation and Sensors

```python
from pySimSAR.motion.perturbation import DrydenTurbulence
from pySimSAR.sensors.gps import GPSSensor
from pySimSAR.sensors.imu import IMUSensor

# Add motion perturbation
platform.set_perturbation(DrydenTurbulence(
    sigma_u=1.0, sigma_v=1.0, sigma_w=0.5,
    altitude=2000.0, velocity=100.0,
))

# Attach sensors (simple Gaussian GPS, white noise IMU)
gps = GPSSensor(accuracy_rms=0.02, update_rate=10.0)
imu = IMUSensor(
    accel_noise_density=0.0002,  # m/s^2/sqrt(Hz)
    gyro_noise_density=5e-6,     # rad/s/sqrt(Hz)
    sample_rate=200.0,
)
platform.attach_sensor(gps)
platform.attach_sensor(imu)

# Simulate
engine = SimulationEngine(scene=scene, radar=radar, platform=platform, seed=42)
result = engine.run()
```

## 3. Processing Pipeline (MoCo + Image Formation)

```python
from pySimSAR.algorithms.moco import FirstOrderMoCo
from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm

# Option A: End-to-end (no autofocus)
moco = FirstOrderMoCo()
compensated = moco.compensate(
    result.raw_data, result.nav_data, result.ideal_trajectory
)

rda = RangeDopplerAlgorithm()
image = rda.process(compensated)
```

## 4. Two-Step Image Formation with Autofocus

```python
from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm
from pySimSAR.algorithms.autofocus import PhaseGradientAutofocus

rda = RangeDopplerAlgorithm()
pga = PhaseGradientAutofocus(max_iterations=10)

# Step 1: Range compression → PhaseHistoryData
phase_history = rda.range_compress(compensated, result.nav_data)

# Step 2: Autofocus corrects residual phase errors,
#          calls rda.azimuth_compress() internally
image = pga.focus(phase_history, rda.azimuth_compress)
```

## 5. Using ProcessingConfig

```python
from pySimSAR.pipeline.runner import PipelineRunner
from pySimSAR.io.config import ProcessingConfig

# Configure the full pipeline
proc_config = ProcessingConfig(
    moco=FirstOrderMoCo(),
    image_formation=RangeDopplerAlgorithm(),
    autofocus=PhaseGradientAutofocus(max_iterations=10),
    geocoding=None,                    # skip geocoding
    polarimetric_decomposition=None,   # skip polsar
)

# Run the pipeline
runner = PipelineRunner(result, proc_config)
image = runner.run()

# Re-process with a different algorithm — no re-simulation needed
proc_config_2 = ProcessingConfig(
    moco=FirstOrderMoCo(),
    image_formation=OmegaKAlgorithm(),
    autofocus=None,  # skip autofocus this time
)
image_2 = PipelineRunner(result, proc_config_2).run()
```

## 6. FMCW Waveform with Phase Noise

```python
from pySimSAR.waveforms import FMCWWaveform
from pySimSAR.waveforms.phase_noise import CompositePSDPhaseNoise

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
    window="hanning",
    phase_noise=pn,
)

radar = Radar(
    carrier_freq=77e9,       # W-band FMCW
    prf=20000.0,             # PRI = 50 μs
    transmit_power=0.1,
    waveform=waveform,
    polarization="single",
    mode="stripmap",
    look_side="right",
    depression_angle=0.8,
)
# waveform.duration = 0.8 / 20000 = 40 μs (derived automatically)
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
