# Scripting Simulations

This guide covers how to use the PySimSAR Python API to run SAR simulations
without the GUI. All examples assume `import pySimSAR` has been executed.

## Minimal headless simulation

A complete simulation in ten lines:

```python
import numpy as np
from pySimSAR import (
    Scene, PointTarget, Radar, AntennaPattern, create_antenna_from_preset,
    SimulationEngine, PipelineRunner, ProcessingConfig,
)
from pySimSAR.waveforms.lfm import LFMWaveform

# 1. Scene with a single point target
scene = Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=0.0)
scene.add_target(PointTarget(position=np.array([5000.0, 0.0, 0.0]), rcs=1.0))

# 2. Radar configuration
waveform = LFMWaveform(bandwidth=50e6, duty_cycle=0.1, prf=500.0)
antenna = create_antenna_from_preset("sinc", az_beamwidth=0.05, el_beamwidth=0.1)
radar = Radar(
    carrier_freq=9.65e9,
    transmit_power=1.0,
    waveform=waveform,
    antenna=antenna,
    polarization="single",
)

# 3. Simulate raw echo data
engine = SimulationEngine(scene=scene, radar=radar, n_pulses=256)
result = engine.run()

# 4. Form a focused image
config = ProcessingConfig(image_formation="range_doppler")
pipeline = PipelineRunner(config)
from pySimSAR.core.types import RawData
raw_data = {
    ch: RawData(
        echo=echo,
        channel=ch,
        sample_rate=result.sample_rate,
        carrier_freq=radar.carrier_freq,
        bandwidth=radar.bandwidth,
        prf=waveform.prf,
        waveform_name=waveform.name,
        gate_delay=result.gate_delay,
    )
    for ch, echo in result.echo.items()
}
pipeline_result = pipeline.run(raw_data, radar, result.true_trajectory or result)

# 5. Access the focused image
image = next(iter(pipeline_result.images.values()))
print(f"Image shape: {image.data.shape}")
print(f"Range spacing: {image.pixel_spacing_range:.3f} m")
print(f"Azimuth spacing: {image.pixel_spacing_azimuth:.3f} m")
```

## Batch simulation pattern

Loop over parameter values, collect results, and compare:

```python
import numpy as np
from pySimSAR import (
    Scene, PointTarget, Radar, SimulationEngine, PipelineRunner, ProcessingConfig,
    create_antenna_from_preset,
)
from pySimSAR.waveforms.lfm import LFMWaveform
from pySimSAR.core.types import RawData

frequencies = [1e9, 5e9, 10e9]
results = {}

scene = Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=0.0)
scene.add_target(PointTarget(position=np.array([5000.0, 0.0, 0.0]), rcs=1.0))

for fc in frequencies:
    waveform = LFMWaveform(bandwidth=50e6, duty_cycle=0.1, prf=500.0)
    antenna = create_antenna_from_preset("sinc", az_beamwidth=0.05, el_beamwidth=0.1)
    radar = Radar(
        carrier_freq=fc,
        transmit_power=1.0,
        waveform=waveform,
        antenna=antenna,
        polarization="single",
    )

    engine = SimulationEngine(scene=scene, radar=radar, n_pulses=256, seed=42)
    sim_result = engine.run()

    raw_data = {
        ch: RawData(
            echo=echo, channel=ch,
            sample_rate=sim_result.sample_rate,
            carrier_freq=radar.carrier_freq,
            bandwidth=radar.bandwidth,
            prf=waveform.prf,
            waveform_name=waveform.name,
            gate_delay=sim_result.gate_delay,
        )
        for ch, echo in sim_result.echo.items()
    }

    config = ProcessingConfig(image_formation="range_doppler")
    pipeline = PipelineRunner(config)
    pipe_result = pipeline.run(raw_data, radar, sim_result.true_trajectory or sim_result)

    image = next(iter(pipe_result.images.values()))
    results[fc] = {
        "range_resolution": image.pixel_spacing_range,
        "azimuth_resolution": image.pixel_spacing_azimuth,
        "peak_amplitude": float(np.max(np.abs(image.data))),
    }

for fc, res in results.items():
    print(f"fc={fc/1e9:.1f} GHz  range_res={res['range_resolution']:.3f} m  "
          f"az_res={res['azimuth_resolution']:.3f} m  peak={res['peak_amplitude']:.2f}")
```

## Custom scene construction

### Multiple point targets

```python
import numpy as np
from pySimSAR import Scene, PointTarget

scene = Scene(origin_lat=34.0, origin_lon=-118.0, origin_alt=0.0)

# Grid of targets at different cross-range and along-range positions
for x in [4000, 5000, 6000]:
    for y in [-200, 0, 200]:
        scene.add_target(PointTarget(
            position=np.array([float(x), float(y), 0.0]),
            rcs=1.0,
        ))

# Strong corner reflector
scene.add_target(PointTarget(
    position=np.array([5000.0, 0.0, 0.0]),
    rcs=10.0,
))

# Moving target with velocity
scene.add_target(PointTarget(
    position=np.array([5500.0, 100.0, 0.0]),
    rcs=2.0,
    velocity=np.array([0.0, 5.0, 0.0]),  # 5 m/s along-track
))
```

### Distributed targets

```python
import numpy as np
from pySimSAR import Scene
from pySimSAR.core.scene import DistributedTarget

scene = Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=0.0)

# 100 m x 100 m clutter patch at 5 km range, 1 m cell size
nx, ny = 100, 100
reflectivity = np.random.uniform(0.01, 0.1, size=(ny, nx))

scene.add_target(DistributedTarget(
    origin=np.array([4950.0, -50.0, 0.0]),
    extent=np.array([100.0, 100.0]),
    cell_size=1.0,
    reflectivity=reflectivity,
))
```

### Quad-pol scattering matrix

```python
import numpy as np
from pySimSAR import PointTarget

# Define a 2x2 scattering matrix [[S_HH, S_HV], [S_VH, S_VV]]
scattering = np.array([
    [1.0 + 0.1j, 0.05 + 0.02j],
    [0.05 + 0.02j, 0.8 - 0.1j],
])

target = PointTarget(
    position=np.array([5000.0, 0.0, 0.0]),
    rcs=scattering,
)
```

## Accessing results

### SimulationResult

After `engine.run()`, the `SimulationResult` object contains:

| Attribute | Type | Description |
|---|---|---|
| `echo` | `dict[str, np.ndarray]` | Raw echo data per channel. Keys: `"single"`, `"hh"`, `"hv"`, `"vh"`, `"vv"`. Values: complex arrays of shape `(n_pulses, n_range_samples)`. |
| `sample_rate` | `float` | Range sampling rate in Hz. |
| `positions` | `np.ndarray` | Platform positions per pulse, shape `(n_pulses, 3)`. |
| `velocities` | `np.ndarray` | Platform velocities per pulse, shape `(n_pulses, 3)`. |
| `pulse_times` | `np.ndarray` | Time of each pulse in seconds. |
| `ideal_trajectory` | `Trajectory \| None` | Ideal trajectory (if Platform was used). |
| `true_trajectory` | `Trajectory \| None` | Perturbed trajectory used for echo computation. |
| `gate_delay` | `float` | Range gate start delay in seconds. |

```python
result = engine.run()

# Access echo data for single-pol
echo_matrix = result.echo["single"]  # shape (n_pulses, n_range)

# Phase history (range line of first pulse)
first_pulse = echo_matrix[0, :]
```

### PipelineResult

After `pipeline.run()`, the `PipelineResult` object contains:

| Attribute | Type | Description |
|---|---|---|
| `images` | `dict[str, SARImage]` | Focused images keyed by channel name. |
| `phase_history` | `dict[str, PhaseHistoryData]` | Range-compressed data (intermediate). |
| `decomposition` | `dict[str, np.ndarray] \| None` | Polarimetric decomposition results. |
| `steps_applied` | `list[str]` | Processing steps applied, in order. |

```python
image = pipeline_result.images["single"]
amplitude = np.abs(image.data)         # amplitude image
phase = np.angle(image.data)           # phase image
intensity_dB = 20 * np.log10(amplitude + 1e-10)
```

## Saving and loading data

### HDF5 I/O

```python
from pySimSAR import write_hdf5, read_hdf5

# Save simulation result
result.save("output.h5", radar=radar)

# Save a focused image directly
image.save("focused.h5", name="my_image")

# Read back
data = read_hdf5("output.h5")
raw_data = data["raw_data"]       # dict[str, RawData]
trajectory = data["trajectory"]   # Trajectory or None
images = data["images"]           # dict[str, SARImage]

# Load a single image
from pySimSAR.core.types import SARImage
img = SARImage.load("focused.h5", name="my_image")
```

### Standalone save/load on data types

```python
# RawData
from pySimSAR.core.types import RawData
raw = raw_data["single"]
raw.save("raw_single.h5")
loaded_raw = RawData.load("raw_single.h5")

# SARImage
image.save("image.h5")
loaded_image = SARImage.load("image.h5")
```

### Parameter set projects

```python
from pySimSAR.io.parameter_set import load_parameter_set, build_simulation, save_parameter_set

# Load a project directory
params = load_parameter_set("path/to/project_dir")
sim_objects = build_simulation(params)
# Returns: {"scene", "radar", "platform", "engine_kwargs", "processing_config"}

# Save the current setup to a new project
save_parameter_set(
    "path/to/new_project",
    scene=scene,
    radar=radar,
    platform=platform,
    seed=42,
    flight_time=0.5,
    name="My Simulation",
)
```

### Archive projects

```python
from pySimSAR.io.archive import pack_project, unpack_project

# Pack a project directory into a portable .pysimsar archive
pack_project("path/to/project_dir", "my_project.pysimsar")

# Unpack an archive
unpack_project("my_project.pysimsar", "path/to/extracted")
```
