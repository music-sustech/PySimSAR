# Configuration Guide

PySimSAR uses JSON parameter sets for all simulation and processing
configuration. This guide covers the file format, preset system, HDF5 output
structure, and reproducibility guarantees.

---

## JSON Parameter Set Format

A PySimSAR project is a directory containing multiple JSON files that together
define a complete SAR simulation. The entry point is always `project.json`,
which references the other files.

### Project directory structure

```
my_project/
    project.json      # Top-level manifest (required)
    radar.json        # Radar hardware parameters
    waveform.json     # Waveform definition
    antenna.json      # Antenna pattern configuration
    sarmode.json      # SAR imaging geometry
    scene.json        # Target scene definition
    platform.json     # Platform motion parameters
    processing.json   # Processing algorithm selection
```

### project.json

The top-level file must include a `format_version` field. All other sections
use `$ref` to point to their respective files:

```json
{
  "format_version": "1.0",
  "name": "Default Stripmap",
  "description": "X-band airborne stripmap simulation.",
  "scene": { "$ref": "scene.json" },
  "radar": { "$ref": "radar.json" },
  "sarmode": { "$ref": "sarmode.json" },
  "platform": { "$ref": "platform.json" },
  "simulation": {
    "seed": 42,
    "swath_range_m": [1330.0, 1500.0],
    "sample_rate_hz": null
  },
  "processing": { "$ref": "processing.json" }
}
```

### radar.json

```json
{
  "carrier_freq_hz": 9650000000.0,
  "transmit_power_w": 1.0,
  "receiver_gain_dB": 30.0,
  "noise_figure_dB": 3.0,
  "system_losses_dB": 2.0,
  "reference_temp_K": 290.0,
  "polarization": "single",
  "waveform": { "$ref": "waveform.json" },
  "antenna": { "$ref": "antenna.json" }
}
```

### waveform.json

```json
{
  "type": "lfm",
  "prf_hz": 1000.0,
  "bandwidth_hz": 300000000.0,
  "duty_cycle": 0.01,
  "window": null,
  "phase_noise": null
}
```

### antenna.json

```json
{
  "type": "preset",
  "preset": "flat",
  "az_beamwidth_deg": 10.0,
  "el_beamwidth_deg": 10.0
}
```

### sarmode.json

```json
{
  "mode": "stripmap",
  "look_side": "right",
  "depression_angle_deg": 45.0,
  "squint_angle_deg": 0.0,
  "scene_center_m": null,
  "n_subswaths": 3,
  "burst_length": 20
}
```

### scene.json

```json
{
  "origin_lat_deg": 0.0,
  "origin_lon_deg": 0.0,
  "origin_alt_m": 0.0,
  "point_targets": [
    {
      "position_m": [500.0, 0.0, 0.0],
      "rcs_m2": 1.0,
      "velocity_mps": null
    }
  ]
}
```

### platform.json

```json
{
  "velocity_mps": 100.0,
  "altitude_m": 1000.0,
  "heading": [0.0, 1.0, 0.0],
  "start_position_m": [0.0, -25.0, 1000.0],
  "flight_path_mode": "heading_time",
  "flight_time": 0.5,
  "perturbation": null,
  "sensors": null
}
```

### Unit conventions in JSON

JSON keys carry unit suffixes that are **automatically stripped** on load.
Degree values (except geographic coordinates) are converted to radians.

| Suffix    | Unit              | Conversion on load                |
|----------|-------------------|---------------------------------------|
| `_hz`     | Hertz             | Suffix stripped, value unchanged      |
| `_m`      | meters            | Suffix stripped, value unchanged      |
| `_mps`    | meters per second | Suffix stripped, value unchanged      |
| `_dB`     | decibels          | Suffix stripped, value unchanged      |
| `_dBc`    | decibels          | Suffix stripped, value unchanged      |
| `_K`      | Kelvin            | Suffix stripped, value unchanged      |
| `_w`      | Watts             | Suffix stripped, value unchanged      |
| `_m2`     | square meters     | Suffix stripped, value unchanged      |
| `_deg`    | degrees           | Suffix stripped, converted to radians |

**Exception:** `origin_lat_deg` and `origin_lon_deg` are geographic coordinates
and are stripped but NOT converted to radians.

---

## Preset System

### Shipped presets

PySimSAR includes ready-to-use project presets in the
`pySimSAR/presets/projects/` directory. Currently available:

- `default_stripmap` -- X-band airborne stripmap with 93 point targets on a
  4m grid (spelling "SUSTech").

### The `$preset/` prefix

Inside any JSON file, a `$ref` value starting with `$preset/` resolves
relative to the `pySimSAR/presets/` directory rather than the current file's
directory. This lets user projects reference shipped configurations:

```json
{
  "waveform": { "$ref": "$preset/waveforms/x_band_lfm.json" }
}
```

### Reference resolution (`$ref` and `$data`)

The `resolve_refs()` function in `pySimSAR.io.parameter_set` recursively walks
a parsed JSON structure and replaces special objects:

**`$ref`** -- File reference. Must be the only key in the object. The
referenced JSON file is loaded, parsed, and recursively resolved:

```json
{ "$ref": "radar.json" }
```

Resolves relative to the directory containing the current file. Use `$preset/`
for paths relative to the presets directory.

**`$data`** -- Binary data reference. Must be the only key in the object.
Loads external data files:

```json
{ "$data": "positions.npy" }
```

Supported formats: `.npy` (NumPy array), `.npz` (NumPy archive), `.csv`
(comma-separated values loaded via `numpy.loadtxt`).

**Circular reference detection:** `resolve_refs()` tracks visited file paths
and raises a `ValueError` if a circular chain is detected.

### Loading a parameter set programmatically

```python
from pySimSAR.io.parameter_set import load_parameter_set, build_simulation

# Load and resolve all references + convert units
params = load_parameter_set("path/to/my_project/")

# Build simulation objects from the resolved dict
objects = build_simulation(params)
scene = objects["scene"]
radar = objects["radar"]
platform = objects["platform"]
processing_config = objects["processing_config"]
```

---

## HDF5 Output Format

PySimSAR stores simulation results and focused images in HDF5 files using the
following group structure:

```
/
    metadata/                   (group)
        @software_version       "pySimSAR 0.1.0"
        @creation_date          ISO 8601 UTC timestamp
        @coordinate_system      "ENU"
        @origin_lat             float64
        @origin_lon             float64
        @origin_alt             float64

    config/                     (group)
        @simulation_config      JSON string (optional)
        @processing_config      JSON string (optional)

    raw_data/                   (group, optional)
        {channel_name}/         one group per polarization channel
            echo                complex dataset (n_range, n_azimuth)
            @carrier_freq       float64 (Hz)
            @bandwidth          float64 (Hz)
            @prf                float64 (Hz)
            @sample_rate        float64 (Hz)
            @waveform           string
            @sar_mode           string
            @polarization       string

    navigation/                 (group, optional)
        trajectory/
            time                float64 (N,)
            position            float64 (N, 3)
            velocity            float64 (N, 3)
            attitude            float64 (N, 3)
        gps/                    (if GPS sensor present)
            time                float64 (M,)
            position            float64 (M, 3)
            velocity            float64 (M, 3)
        imu/                    (if IMU sensor present)
            time                float64 (M,)
            acceleration        float64 (M, 3)
            angular_rate        float64 (M, 3)

    images/                     (group, optional)
        {image_name}/
            data                complex or float dataset (n_rows, n_cols)
            @algorithm          string
            @pixel_spacing_range    float64 (m)
            @pixel_spacing_azimuth  float64 (m)
            @geometry           string
            @polarization       string
            @geo_transform      float64 (6,) (optional)
            @projection_wkt     string (optional)
```

### Compression

Arrays larger than 1 MB are automatically gzip-compressed (level 4) when
written. Smaller arrays are stored uncompressed for faster access.

### Reading HDF5 files with h5py

```python
import h5py
import numpy as np

with h5py.File("output.h5", "r") as f:
    # Read metadata
    print(f["metadata"].attrs["software_version"])
    print(f["metadata"].attrs["creation_date"])

    # Read raw echo data for the 'single' channel
    echo = f["raw_data"]["single"]["echo"][:]
    prf = f["raw_data"]["single"].attrs["prf"]
    print(f"Echo shape: {echo.shape}, PRF: {prf} Hz")

    # Read trajectory
    if "navigation" in f and "trajectory" in f["navigation"]:
        pos = f["navigation"]["trajectory"]["position"][:]
        print(f"Track length: {np.linalg.norm(pos[-1] - pos[0]):.1f} m")

    # Read focused image
    if "images" in f:
        for name in f["images"]:
            img_data = f["images"][name]["data"][:]
            alg = f["images"][name].attrs["algorithm"]
            print(f"Image '{name}': {img_data.shape}, algorithm={alg}")
```

### Using PySimSAR convenience functions

```python
from pySimSAR import read_hdf5, RawData, SARImage

# Read everything at once
data = read_hdf5("output.h5")
print(data["metadata"])           # dict of metadata attributes
print(data["raw_data"].keys())    # channel names
print(data["images"].keys())      # image names

# Or load specific types directly
rd = RawData.load("output.h5", channel="single")
img = SARImage.load("output.h5")
```

---

## ProcessingConfig

`ProcessingConfig` controls algorithm selection for the SAR processing
pipeline. Each stage is optional except `image_formation`.

**Module:** `pySimSAR.io.config`

| Property                              | Type           | Required | Description                     |
|--------------------------------------|----------------|----------|---------------------------------|
| `image_formation`                     | `str`          | Yes      | Algorithm name                   |
| `image_formation_params`              | `dict`         | No       | Algorithm-specific parameters    |
| `moco`                                | `str \| None`  | No       | Motion compensation algorithm    |
| `moco_params`                         | `dict`         | No       | MoCo parameters                  |
| `autofocus`                           | `str \| None`  | No       | Autofocus algorithm              |
| `autofocus_params`                    | `dict`         | No       | Autofocus parameters             |
| `geocoding`                           | `str \| None`  | No       | Geocoding algorithm              |
| `geocoding_params`                    | `dict`         | No       | Geocoding parameters             |
| `polarimetric_decomposition`          | `str \| None`  | No       | Polarimetric decomposition       |
| `polarimetric_decomposition_params`   | `dict`         | No       | Decomposition parameters         |

### Available algorithms

**Image formation:**

- `range_doppler` -- Range-Doppler algorithm. Params: `{"apply_rcmc": true}`
- `omega_k` -- Omega-K (Stolt interpolation) algorithm
- `chirp_scaling` -- Chirp Scaling algorithm

**Motion compensation:**

- `first_order` -- First-order MoCo (bulk range shift)
- `second_order` -- Second-order MoCo (residual phase correction)

**Autofocus:**

- `pga` -- Phase Gradient Autofocus
- `mda` -- Map Drift Autofocus
- `min_entropy` -- Minimum Entropy Autofocus
- `ppp` -- Prominent Point Processing

**Geocoding:**

- `slant_to_ground` -- Slant-range to ground-range projection

**Polarimetric decomposition:**

- `pauli` -- Pauli decomposition
- `freeman_durden` -- Freeman-Durden 3-component decomposition

### JSON processing.json example

```json
{
  "image_formation": {
    "algorithm": "range_doppler",
    "params": {
      "apply_rcmc": true
    }
  },
  "moco": null,
  "autofocus": null,
  "geocoding": null,
  "polarimetric_decomposition": null
}
```

A fully configured processing pipeline with motion compensation and autofocus:

```json
{
  "image_formation": {
    "algorithm": "omega_k",
    "params": {}
  },
  "moco": {
    "algorithm": "first_order",
    "params": {}
  },
  "autofocus": {
    "algorithm": "pga",
    "params": {
      "max_iterations": 20
    }
  },
  "geocoding": {
    "algorithm": "slant_to_ground",
    "params": {}
  },
  "polarimetric_decomposition": null
}
```

### Constructing ProcessingConfig in code

```python
from pySimSAR import ProcessingConfig

config = ProcessingConfig(
    image_formation="range_doppler",
    image_formation_params={"apply_rcmc": True},
    moco="first_order",
    autofocus="pga",
    autofocus_params={"max_iterations": 20},
)

# Serialize to JSON
json_str = config.to_json()

# Reconstruct from JSON
config2 = ProcessingConfig.from_json(json_str)
```

---

## SimulationConfig

`SimulationConfig` bundles scene, radar, and platform references together
with pulse count and random seed. It tracks lifecycle state through a simple
state machine.

**Module:** `pySimSAR.io.config`

| Parameter    | Type              | Description                                     |
|-------------|-------------------|-------------------------------------------------|
| `scene`      | `Scene`           | Target scene. Must not be None                   |
| `radar`      | `Radar`           | Radar system. Must not be None                   |
| `n_pulses`   | `int`             | Number of azimuth pulses. Must be > 0            |
| `seed`       | `int`             | RNG seed for reproducibility. Must be >= 0       |
| `platform`   | `Platform \| None` | Platform configuration (optional)               |
| `description` | `str`            | Human-readable description (optional)            |

**State machine:**

```
CREATED -> validate() -> VALIDATED -> start() -> RUNNING -> complete() -> COMPLETED
                                                         -> fail()     -> FAILED
```

**Serialization:**

- `to_json()` -- Serialize reproducibility-relevant parameters to JSON.
- `SimulationConfig.from_json(json_str)` -- Deserialize to a parameter dict
  (not a full `SimulationConfig` object; complex objects require domain
  factories).

---

## Reproducibility

PySimSAR is designed to produce deterministic, reproducible results:

1. **Deterministic simulation:** Given identical parameter sets and the same
   `seed` value, the simulation engine produces bit-identical echo data across
   runs. The `seed` controls all random number generation including noise
   injection, perturbation models, and clutter generation.

2. **Full serializability:** Both `SimulationConfig` and `ProcessingConfig`
   support JSON serialization via `to_json()` and reconstruction via
   `from_json()`. Save these alongside your output HDF5 file to fully document
   any result.

3. **Parameter set archival:** The JSON parameter set format captures the
   complete specification for a simulation. Copy the project directory to
   reproduce the simulation on any machine with PySimSAR installed.

4. **HDF5 metadata:** Every output file records the software version, creation
   timestamp, and coordinate system origin in the `/metadata` group. The
   `/config` group stores the serialized simulation and processing
   configurations.

### Recommended workflow

```python
from pySimSAR import (
    SimulationEngine, SimulationConfig, ProcessingConfig,
    PipelineRunner, Scene, Radar, Platform,
)

# 1. Configure
sim_config = SimulationConfig(scene=scene, radar=radar,
                               n_pulses=512, seed=42,
                               platform=platform)
sim_config.validate()

# 2. Simulate
engine = SimulationEngine(scene=scene, radar=radar,
                          n_pulses=512, seed=42,
                          platform=platform)
sim_config.start()
result = engine.run()
sim_config.complete()

# 3. Save with full provenance
result.save("output.h5", radar=radar,
            simulation_config_json=sim_config.to_json())

# 4. Process and save images
proc_config = ProcessingConfig(image_formation="range_doppler",
                                image_formation_params={"apply_rcmc": True})
pipeline = PipelineRunner(proc_config)
# ... run pipeline and save
```
