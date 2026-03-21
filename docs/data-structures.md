# Data Structures Reference

This page documents every user-facing type in PySimSAR v0.1. All types live
under the `pySimSAR` namespace and can be imported directly:

```python
from pySimSAR import (
    Scene, PointTarget, DistributedTarget,
    Radar, AntennaPattern, create_antenna_from_preset,
    Platform, RawData, SARImage, PhaseHistoryData,
    SimulationEngine, SimulationResult,
    PipelineRunner, PipelineResult,
    SimulationConfig, ProcessingConfig,
)
```

Lower-level types such as enumerations and trajectory containers are available
from their submodules:

```python
from pySimSAR.core.types import (
    SARMode, PolarizationMode, LookSide, RampType,
    PolarizationChannel, ImageGeometry, SimulationState,
    SARModeConfig,
)
from pySimSAR.motion.trajectory import Trajectory
from pySimSAR.sensors.nav_data import NavigationData
from pySimSAR.core.calculator import SARCalculator, CalculatedResult
```

---

## Enumerations

All enums inherit from both `str` and `Enum`, so they can be used wherever a
plain string is accepted. Values are **lowercase**.

### SARMode

SAR imaging mode.

| Member       | Value         | Description                              |
|-------------|---------------|------------------------------------------|
| `STRIPMAP`  | `"stripmap"`  | Continuous imaging along the flight path |
| `SPOTLIGHT` | `"spotlight"` | Beam steered to dwell on a scene center  |
| `SCANMAR`   | `"scanmar"`   | Multi-burst wide-swath scan SAR          |

```python
from pySimSAR.core.types import SARMode

mode = SARMode.STRIPMAP
assert mode == "stripmap"
assert SARMode("spotlight") is SARMode.SPOTLIGHT
```

### PolarizationMode

Radar polarization configuration.

| Member   | Value      | Channels generated                 |
|---------|------------|-------------------------------------|
| `SINGLE` | `"single"` | One co-pol channel                 |
| `DUAL`   | `"dual"`   | Two channels (e.g. HH + HV)       |
| `QUAD`   | `"quad"`   | Full polarimetric (HH, HV, VH, VV) |

### LookSide

Antenna look direction relative to the flight track.

| Member  | Value     |
|--------|-----------|
| `LEFT`  | `"left"`  |
| `RIGHT` | `"right"` |

### RampType

FMCW frequency ramp direction.

| Member     | Value        |
|-----------|--------------|
| `UP`       | `"up"`       |
| `DOWN`     | `"down"`     |
| `TRIANGLE` | `"triangle"` |

### PolarizationChannel

Label for a single polarization channel.

| Member   | Value      |
|---------|------------|
| `SINGLE` | `"single"` |
| `HH`     | `"hh"`     |
| `HV`     | `"hv"`     |
| `VH`     | `"vh"`     |
| `VV`     | `"vv"`     |

### ImageGeometry

Coordinate system of a focused SAR image.

| Member         | Value            |
|---------------|------------------|
| `SLANT_RANGE`  | `"slant_range"`  |
| `GROUND_RANGE` | `"ground_range"` |
| `GEOGRAPHIC`   | `"geographic"`   |

### SimulationState

Lifecycle state of a `SimulationConfig`.

| Member      | Value         | Transitions to          |
|------------|---------------|--------------------------|
| `CREATED`   | `"created"`   | VALIDATED                |
| `VALIDATED` | `"validated"` | RUNNING                  |
| `RUNNING`   | `"running"`   | COMPLETED or FAILED      |
| `COMPLETED` | `"completed"` | (terminal)               |
| `FAILED`    | `"failed"`    | (terminal)               |

---

## Core Configuration Types

### SARModeConfig

Imaging geometry configuration that bundles *how* the SAR system images (mode,
look direction, depression angle, beam pointing) as opposed to *what hardware*
it uses.

**Module:** `pySimSAR.core.types`

| Field              | Type                    | Default            | Valid range / notes                                        |
|-------------------|-------------------------|--------------------|-------------------------------------------------------------|
| `mode`             | `SARMode \| str`        | `SARMode.STRIPMAP` | Accepts string or enum                                      |
| `look_side`        | `LookSide \| str`       | `LookSide.RIGHT`   | Accepts string or enum                                      |
| `depression_angle` | `float`                 | `0.7854` (pi/4)    | Radians, [0, pi/2]. 45 deg default                          |
| `squint_angle`     | `float`                 | `0.0`              | Radians, [-pi/2, pi/2]. 0 = broadside                      |
| `scene_center`     | `np.ndarray \| None`    | `None`             | Shape (3,), ENU meters. Used for spotlight/scansar pointing |
| `n_subswaths`      | `int`                   | `3`                | Number of sub-swaths (scansar mode)                         |
| `burst_length`     | `int`                   | `20`               | Pulses per burst (scansar mode)                             |

String values for `mode` and `look_side` are automatically coerced to the
corresponding enum in `__post_init__`.

```python
from pySimSAR.core.types import SARModeConfig
import numpy as np

config = SARModeConfig(
    mode="spotlight",
    look_side="left",
    depression_angle=np.radians(40),
    scene_center=np.array([500.0, 0.0, 0.0]),
)
```

---

## Data Container Types

### RawData

Simulated raw SAR echo data for a single polarization channel.

**Module:** `pySimSAR.core.types`

| Field           | Type          | Default       | Description                                      |
|----------------|---------------|---------------|--------------------------------------------------|
| `echo`          | `np.ndarray`  | *(required)*  | Complex 2D array, shape (n_range, n_azimuth)     |
| `channel`       | `str`         | *(required)*  | Polarization channel name (e.g. `"single"`, `"hh"`) |
| `sample_rate`   | `float`       | *(required)*  | Range sampling rate in Hz                         |
| `carrier_freq`  | `float`       | *(required)*  | Radar carrier frequency in Hz                     |
| `bandwidth`     | `float`       | *(required)*  | Waveform bandwidth in Hz                          |
| `prf`           | `float`       | *(required)*  | Pulse repetition frequency in Hz                  |
| `waveform_name` | `str`         | `""`          | Name of the waveform (e.g. `"lfm"`, `"fmcw"`)    |
| `sar_mode`      | `str`         | `"stripmap"`  | SAR mode string                                   |
| `gate_delay`    | `float`       | `0.0`         | Range gate start delay in seconds                 |

**Validation:** `echo` must be exactly 2-D. A `ValueError` is raised otherwise.

**Methods:**

- `save(filepath)` -- Write to HDF5 via `write_hdf5()`.
- `RawData.load(filepath, channel=None)` -- Static method. Load from HDF5.
  Returns the specified channel, or the first channel if `channel` is `None`.

```python
from pySimSAR import RawData

rd = RawData.load("output.h5", channel="single")
print(rd.echo.shape)     # (n_range, n_azimuth)
print(rd.sample_rate)    # Hz
```

### PhaseHistoryData

Range-compressed phase history used as input to autofocus and azimuth
compression stages.

**Module:** `pySimSAR.core.types`

| Field          | Type          | Default      | Description                            |
|---------------|---------------|--------------|----------------------------------------|
| `data`         | `np.ndarray`  | *(required)* | Complex 2D array, shape (n_range, n_azimuth) |
| `sample_rate`  | `float`       | *(required)* | Range sampling rate in Hz               |
| `prf`          | `float`       | *(required)* | Pulse repetition frequency in Hz        |
| `carrier_freq` | `float`       | *(required)* | Carrier frequency in Hz                 |
| `bandwidth`    | `float`       | *(required)* | Waveform bandwidth in Hz                |
| `channel`      | `str`         | `"single"`   | Polarization channel name               |
| `gate_delay`   | `float`       | `0.0`        | Range gate start delay in seconds       |

**Validation:** `data` must be exactly 2-D.

### SARImage

Focused SAR image product.

**Module:** `pySimSAR.core.types`

| Field                    | Type                  | Default          | Description                                      |
|-------------------------|-----------------------|------------------|--------------------------------------------------|
| `data`                   | `np.ndarray`          | *(required)*     | 2D pixel data (complex or real), shape (n_rows, n_cols) |
| `pixel_spacing_range`    | `float`               | *(required)*     | Range pixel spacing in meters                     |
| `pixel_spacing_azimuth`  | `float`               | *(required)*     | Azimuth pixel spacing in meters                   |
| `geometry`               | `str`                 | `"slant_range"`  | `"slant_range"`, `"ground_range"`, or `"geographic"` |
| `algorithm`              | `str`                 | `""`             | Image formation algorithm name                    |
| `channel`                | `str`                 | `"single"`       | Polarization channel name                         |
| `near_range`             | `float`               | `0.0`            | Near range distance in meters                     |
| `geo_transform`          | `np.ndarray \| None`  | `None`           | Affine geo-transform, shape (6,)                  |
| `projection_wkt`         | `str \| None`         | `None`           | WKT projection string                             |

**Validation:** `data` must be exactly 2-D.

**Methods:**

- `save(filepath, name="image")` -- Write to HDF5.
- `SARImage.load(filepath, name=None)` -- Static method. Load from HDF5.

```python
from pySimSAR import SARImage

img = SARImage.load("output.h5")
print(f"Image shape: {img.data.shape}")
print(f"Range resolution: {img.pixel_spacing_range:.2f} m")
print(f"Azimuth resolution: {img.pixel_spacing_azimuth:.2f} m")
```

---

## Scene Types

### PointTarget

A single point scatterer in the scene.

**Module:** `pySimSAR.core.scene`

| Parameter    | Type                    | Default  | Description                                                                           |
|-------------|-------------------------|----------|---------------------------------------------------------------------------------------|
| `position`   | `np.ndarray`            | *(req.)* | ENU coordinates [x, y, z] in meters, shape (3,). Must be finite.                     |
| `rcs`        | `float \| np.ndarray`   | *(req.)* | Radar cross section. Scalar (m^2, must be > 0) for single-pol; complex 2x2 ndarray for quad-pol scattering matrix. |
| `velocity`   | `np.ndarray \| None`    | `None`   | Target velocity [vx, vy, vz] in m/s, shape (3,). For simulating moving targets.      |
| `rcs_model`  | `RCSModel \| None`      | `None`   | RCS fluctuation model. Defaults to `StaticRCS()` (constant).                           |

**Properties:** `position`, `rcs`, `velocity`, `rcs_model` (all read-only).

```python
import numpy as np
from pySimSAR import PointTarget

# Single-pol point target
pt = PointTarget(position=np.array([500.0, 0.0, 0.0]), rcs=1.0)

# Quad-pol scattering matrix
S = np.array([[1.0+0j, 0.1+0j],
              [0.1+0j, 0.8+0j]])
pt_pol = PointTarget(position=np.array([600.0, 0.0, 0.0]), rcs=S)

# Moving target
pt_mov = PointTarget(
    position=np.array([500.0, 0.0, 0.0]),
    rcs=1.0,
    velocity=np.array([5.0, 0.0, 0.0]),
)
```

### DistributedTarget

A gridded distributed scattering region for clutter simulation.

**Module:** `pySimSAR.core.scene`

| Parameter            | Type                    | Default  | Description                                                 |
|---------------------|-------------------------|----------|--------------------------------------------------------------|
| `origin`             | `np.ndarray`            | *(req.)* | ENU position of the grid corner, shape (3,)                 |
| `extent`             | `np.ndarray`            | *(req.)* | Grid size [dx, dy] in meters, shape (2,). Must be > 0       |
| `cell_size`          | `float`                 | *(req.)* | Grid cell spacing in meters. Must be > 0                     |
| `reflectivity`       | `np.ndarray \| None`    | `None`   | Reflectivity per cell, shape (ny, nx). Values >= 0           |
| `scattering_matrix`  | `np.ndarray \| None`    | `None`   | Per-cell polarimetric scattering, shape (ny, nx, 2, 2)       |
| `elevation`          | `np.ndarray \| None`    | `None`   | Per-cell elevation offset, shape (ny, nx)                    |
| `clutter_model`      | `ClutterModel \| None`  | `None`   | Clutter model for reflectivity generation                    |

Either `reflectivity` or `clutter_model` must be provided. Grid dimensions are
derived as `nx = int(extent[0] / cell_size)`, `ny = int(extent[1] / cell_size)`.

**Properties:** `origin`, `extent`, `cell_size`, `nx`, `ny`, `reflectivity`,
`scattering_matrix`, `elevation`, `clutter_model`.

```python
import numpy as np
from pySimSAR import DistributedTarget

dt = DistributedTarget(
    origin=np.array([400.0, -50.0, 0.0]),
    extent=np.array([100.0, 100.0]),
    cell_size=5.0,
    reflectivity=np.random.rand(20, 20) * 0.5,
)
```

### Scene

Container for all scattering targets in a simulation. Defines the geographic
origin and holds lists of point and distributed targets.

**Module:** `pySimSAR.core.scene`

| Parameter    | Type    | Valid range        | Description                            |
|-------------|---------|---------------------|----------------------------------------|
| `origin_lat` | `float` | [-90, 90] degrees  | Scene origin latitude                   |
| `origin_lon` | `float` | [-180, 180] degrees | Scene origin longitude                 |
| `origin_alt` | `float` | finite             | Scene origin altitude in meters         |

**Properties:** `origin_lat`, `origin_lon`, `origin_alt`, `point_targets` (list),
`distributed_targets` (list).

**Methods:**

- `add_target(target)` -- Add a `PointTarget` or `DistributedTarget` to the scene.
  Raises `TypeError` for other types.

```python
import numpy as np
from pySimSAR import Scene, PointTarget

scene = Scene(origin_lat=22.5, origin_lon=113.9, origin_alt=0.0)
scene.add_target(PointTarget(np.array([500.0, 0.0, 0.0]), rcs=1.0))
scene.add_target(PointTarget(np.array([600.0, 10.0, 0.0]), rcs=2.0))
print(f"Scene has {len(scene.point_targets)} targets")
```

---

## Radar Types

### AntennaPattern

2D antenna gain pattern with interpolation support. Accepts either a 2D numpy
array of gain values (dB) sampled on a regular grid, or a callable that
computes gain for arbitrary azimuth/elevation angles.

**Module:** `pySimSAR.core.radar`

| Parameter       | Type                           | Default      | Description                                         |
|----------------|--------------------------------|--------------|------------------------------------------------------|
| `pattern_2d`    | `np.ndarray \| Callable`       | *(required)* | 2D gain array (dB) shape (n_el, n_az) or callable `(az, el) -> gain_dB` |
| `az_beamwidth`  | `float`                        | *(required)* | 3 dB azimuth beamwidth in radians (must be > 0)      |
| `el_beamwidth`  | `float`                        | *(required)* | 3 dB elevation beamwidth in radians (must be > 0)    |
| `az_angles`     | `np.ndarray \| None`           | `None`       | Azimuth samples in radians. Required if `pattern_2d` is an array |
| `el_angles`     | `np.ndarray \| None`           | `None`       | Elevation samples in radians. Required if `pattern_2d` is an array |

> **Read-only property:** `peak_gain_dB` is not a constructor parameter. The antenna gain is automatically computed from beamwidths: $G = 4\pi\eta / (\theta_{az} \cdot \theta_{el})$ with $\eta = 0.6$.

**Methods:**

- `gain(az, el)` -- Evaluate antenna gain in dB at the given angles (radians).

**Factory function:** `create_antenna_from_preset(preset, az_beamwidth, el_beamwidth)`

Available presets:

| Preset       | Pattern shape                                        |
|-------------|------------------------------------------------------|
| `"flat"`     | Uniform gain within the beamwidth, -60 dB floor      |
| `"sinc"`     | Sinc-squared pattern with -60 dB floor               |
| `"gaussian"` | Gaussian taper: `G - 12 * ((az/bw)^2 + (el/bw)^2)` |

```python
from pySimSAR import create_antenna_from_preset
import numpy as np

antenna = create_antenna_from_preset(
    preset="sinc",
    az_beamwidth=np.radians(10),
    el_beamwidth=np.radians(10),
)
print(f"Boresight gain: {antenna.peak_gain_dB:.1f} dB")  # derived from beamwidths
```

### Radar

Radar system model combining waveform, antenna, and operating parameters.

**Module:** `pySimSAR.core.radar`

| Parameter         | Type                      | Default            | Valid range / notes                                  |
|------------------|---------------------------|--------------------|-------------------------------------------------------|
| `carrier_freq`    | `float`                   | *(required)*       | Hz, must be > 0                                       |
| `transmit_power`  | `float`                   | *(required)*       | Watts, must be > 0                                    |
| `waveform`        | `Waveform`                | *(required)*       | Must not be None                                       |
| `antenna`         | `AntennaPattern`          | *(required)*       | Must not be None                                       |
| `polarization`    | `PolarizationMode \| str` | *(required)*       | `"single"`, `"dual"`, or `"quad"`                     |
| `mode`            | `SARMode \| str`          | `SARMode.STRIPMAP` | Used if `sar_mode_config` is None                     |
| `look_side`       | `LookSide \| str`         | `LookSide.RIGHT`   | Used if `sar_mode_config` is None                     |
| `depression_angle` | `float`                  | `pi/4`             | Radians, [0, pi/2]. Used if `sar_mode_config` is None |
| `noise_figure`    | `float`                   | `3.0`              | dB, must be >= 0                                       |
| `system_losses`   | `float`                   | `2.0`              | dB, must be >= 0                                       |
| `reference_temp`  | `float`                   | `290.0`            | Kelvin, must be > 0                                    |
| `squint_angle`    | `float`                   | `0.0`              | Radians, [-pi/2, pi/2]                                |
| `receiver_gain_dB` | `float`                  | `0.0`              | dB, must be >= 0                                       |
| `sample_rate`     | `float \| None`           | `None`             | Hz, overrides auto-computed rate if set                |
| `sar_mode_config` | `SARModeConfig \| None`   | `None`             | Overrides mode, look_side, depression_angle, squint_angle |

**Computed properties:**

| Property            | Type    | Description                                                  |
|--------------------|---------|--------------------------------------------------------------|
| `wavelength`        | `float` | `c / carrier_freq` in meters                                 |
| `bandwidth`         | `float` | Delegated from `waveform.bandwidth` in Hz                    |
| `pri`               | `float` | `1 / waveform.prf` in seconds                                |
| `noise_power`       | `float` | Thermal noise power at receiver output in Watts               |
| `total_noise_figure` | `float` | Cascaded noise figure (system losses + receiver NF) in dB    |
| `mode`              | `SARMode` | Delegated from `sar_mode_config`                            |
| `look_side`         | `LookSide` | Delegated from `sar_mode_config`                          |
| `depression_angle`  | `float` | Delegated from `sar_mode_config`                              |
| `squint_angle`      | `float` | Delegated from `sar_mode_config`                              |

```python
import numpy as np
from pySimSAR import Radar, create_antenna_from_preset
from pySimSAR.waveforms.lfm import LFMWaveform

waveform = LFMWaveform(bandwidth=150e6, duty_cycle=0.1, prf=500)
antenna = create_antenna_from_preset("sinc", np.radians(3), np.radians(5))
radar = Radar(
    carrier_freq=9.65e9,
    transmit_power=100.0,
    waveform=waveform,
    antenna=antenna,
    polarization="single",
)
print(f"Wavelength: {radar.wavelength*100:.2f} cm")
print(f"Bandwidth: {radar.bandwidth/1e6:.0f} MHz")
```

---

## Platform & Trajectory Types

### Platform

Aircraft or UAV platform configuration.

**Module:** `pySimSAR.core.platform`

| Parameter        | Type                          | Default         | Description                                                |
|-----------------|-------------------------------|------------------|------------------------------------------------------------|
| `velocity`       | `float`                       | *(required)*    | Nominal speed in m/s. Must be > 0                           |
| `altitude`       | `float`                       | *(required)*    | Flight altitude in meters (ENU z). Must be > 0              |
| `heading`        | `float \| np.ndarray`         | `0.0`           | Scalar (radians, 0=North, pi/2=East) or 3D direction vector |
| `start_position` | `np.ndarray \| None`          | `None`          | ENU starting position, shape (3,). Defaults to `[0, 0, altitude]` |
| `perturbation`   | `MotionPerturbation \| None`  | `None`          | Motion perturbation model for turbulence simulation         |
| `sensors`        | `list \| None`                | `[]`            | Attached navigation sensors (GPS, IMU)                      |

When `heading` is a scalar, it is converted to a 3D unit vector
`[sin(heading), cos(heading), 0]`. When it is a 3-element array, it is
normalized internally.

**Properties:**

- `heading_vector` -- Unit direction vector for the flight path (read-only copy).

**Methods:**

- `generate_ideal_trajectory(n_pulses, prf)` -- Generate a straight-line,
  constant-altitude trajectory. Returns a `Trajectory`.
- `generate_perturbed_trajectory(n_pulses, prf, seed=42)` -- Generate a
  perturbed trajectory using the attached perturbation model. Falls back to
  ideal trajectory if no perturbation is configured.

```python
import numpy as np
from pySimSAR import Platform

# Heading as a 3D vector (flying north)
platform = Platform(
    velocity=100.0,
    altitude=1000.0,
    heading=np.array([0.0, 1.0, 0.0]),
    start_position=np.array([0.0, -50.0, 1000.0]),
)
traj = platform.generate_ideal_trajectory(n_pulses=500, prf=1000)
print(f"Track length: {traj.position[-1, 1] - traj.position[0, 1]:.1f} m")
```

### Trajectory

Time-stamped platform state history.

**Module:** `pySimSAR.motion.trajectory`

| Parameter   | Type          | Description                                            |
|------------|---------------|--------------------------------------------------------|
| `time`      | `np.ndarray`  | Time stamps in seconds, shape (N,). Must be monotonically increasing |
| `position`  | `np.ndarray`  | ENU positions in meters, shape (N, 3)                  |
| `velocity`  | `np.ndarray`  | ENU velocities in m/s, shape (N, 3)                    |
| `attitude`  | `np.ndarray`  | Euler angles [roll, pitch, yaw] in radians, shape (N, 3) |

All arrays are stored as public attributes.

**Methods:**

- `interpolate_position(t)` -- Linear interpolation of position at time `t`.
  Returns `np.ndarray` of shape (3,).
- `interpolate_velocity(t)` -- Linear interpolation of velocity at time `t`.
  Returns `np.ndarray` of shape (3,).

### NavigationData

Sensor-measured navigation state (with measurement errors).

**Module:** `pySimSAR.sensors.nav_data`

| Field          | Type                  | Default           | Description                                      |
|---------------|------------------------|-------------------|--------------------------------------------------|
| `time`         | `np.ndarray`           | empty array       | Measurement timestamps in seconds, shape (M,)    |
| `position`     | `np.ndarray \| None`   | `None`            | Measured positions (GPS) in ENU meters, shape (M, 3) |
| `velocity`     | `np.ndarray \| None`   | `None`            | Measured velocities in m/s, shape (M, 3)          |
| `acceleration` | `np.ndarray \| None`   | `None`            | Measured accelerations (IMU) in m/s^2, shape (M, 3) |
| `angular_rate` | `np.ndarray \| None`   | `None`            | Measured angular rates (IMU) in rad/s, shape (M, 3) |
| `source`       | `str`                  | `"gps"`           | Sensor source: `"gps"`, `"imu"`, or `"fused"`    |

**Validation:** `time` must be monotonically increasing. All provided arrays
must have shape `(M, 3)` consistent with the time array length.

---

## Simulation & Pipeline Types

### SimulationEngine

Orchestrates raw SAR echo generation. Simulates the radar pulse loop over a
scene of point and distributed targets.

**Module:** `pySimSAR.simulation.engine`

| Parameter            | Type                          | Default   | Description                                                     |
|---------------------|-------------------------------|-----------|-----------------------------------------------------------------|
| `scene`              | `Scene`                       | *(req.)*  | Target scene definition                                         |
| `radar`              | `Radar`                       | *(req.)*  | Radar system configuration                                      |
| `n_pulses`           | `int`                         | `256`     | Number of azimuth pulses to simulate                            |
| `platform_velocity`  | `np.ndarray \| None`          | `None`    | Platform velocity [vx, vy, vz] m/s. Ignored if `platform` set  |
| `platform_start`     | `np.ndarray \| None`          | `None`    | Starting position [x, y, z] ENU meters. Ignored if `platform` set |
| `seed`               | `int`                         | `42`      | Random seed for reproducibility                                  |
| `sample_rate`        | `float \| None`               | `None`    | Range sampling rate in Hz. Default: 3x bandwidth                 |
| `platform`           | `Platform \| None`            | `None`    | Full platform config (overrides velocity/start)                  |
| `swath_range`        | `tuple[float, float] \| None` | `None`    | (near_range, far_range) in meters. Auto-computed if None         |
| `sar_mode_config`    | `SARModeConfig \| None`       | `None`    | Imaging geometry override                                        |

**Methods:**

- `run()` -- Execute the simulation. Returns `SimulationResult`.

### SimulationResult

Container for simulation output data.

**Module:** `pySimSAR.simulation.engine`

| Field                | Type                            | Description                                       |
|---------------------|---------------------------------|---------------------------------------------------|
| `echo`               | `dict[str, np.ndarray]`         | Echo data per channel. Shape (n_pulses, n_range)  |
| `sample_rate`        | `float`                         | Range sampling rate in Hz                          |
| `positions`          | `np.ndarray`                    | Platform positions per pulse, shape (n_pulses, 3)  |
| `velocities`         | `np.ndarray`                    | Platform velocities per pulse, shape (n_pulses, 3) |
| `pulse_times`        | `np.ndarray`                    | Time of each pulse in seconds, shape (n_pulses,)   |
| `ideal_trajectory`   | `Trajectory \| None`            | Ideal (nominal) trajectory                         |
| `true_trajectory`    | `Trajectory \| None`            | True (perturbed) trajectory                        |
| `navigation_data`    | `list[NavigationData] \| None`  | Navigation sensor measurements                     |
| `gate_delay`         | `float`                         | Range gate start delay in seconds                   |

**Methods:**

- `save(filepath, radar=None)` -- Save results to HDF5.

### PipelineRunner

Sequential SAR processing pipeline driven by `ProcessingConfig`.

**Module:** `pySimSAR.pipeline.runner`

| Parameter        | Type                | Description                                    |
|-----------------|---------------------|------------------------------------------------|
| `config`         | `ProcessingConfig`  | Algorithm selection and parameters              |
| `stage_callback` | `Callable \| None`  | Optional callback invoked with stage name       |

**Methods:**

- `validate_config(raw_data)` -- Check that the selected algorithms are
  compatible with the raw data's SAR mode.
- `run(raw_data, radar, trajectory, nav_data=None, ideal_trajectory=None)` --
  Execute the full processing chain. Returns `PipelineResult`.

### PipelineResult

Container for processing pipeline output.

**Module:** `pySimSAR.pipeline.runner`

| Field            | Type                              | Description                                |
|-----------------|-----------------------------------|--------------------------------------------|
| `images`         | `dict[str, SARImage]`             | Formed images keyed by channel name        |
| `phase_history`  | `dict[str, PhaseHistoryData]`     | Range-compressed data per channel          |
| `raw_data_ref`   | `dict[str, RawData] \| None`     | Reference to raw data                      |
| `decomposition`  | `dict[str, np.ndarray] \| None`  | Polarimetric decomposition results         |
| `steps_applied`  | `list[str]`                       | Processing steps applied, in order         |

---

## Calculator Types

### SARCalculator

Computes derived SAR system values from a parameter dictionary.

**Module:** `pySimSAR.core.calculator`

**Expected input keys** (all SI units): `carrier_freq`, `prf`, `bandwidth`,
`duty_cycle`, `transmit_power`, `az_beamwidth`, `el_beamwidth`,
`depression_angle`, `velocity`, `altitude`, `noise_figure`, `system_losses`,
`receiver_gain_dB`, `reference_temp`, `mode`.

> **Note:** `peak_gain_dB` is not an input key. Antenna gain is automatically
> derived from `az_beamwidth` and `el_beamwidth`.

**Optional keys:** `near_range`, `far_range`, `flight_time`, `start_position`,
`stop_position`.

**Methods:**

- `compute(params)` -- Compute all derived values. Returns
  `dict[str, CalculatedResult]`.
- `compute_single(key, params)` -- Compute a single value by name.

**Available derived quantities:**

| Key                    | Unit  | Description                              |
|-----------------------|-------|------------------------------------------|
| `antenna_gain`         | dBi   | Estimated antenna gain                   |
| `wavelength`           | m     | Radar wavelength                         |
| `pulse_width`          | s     | Transmit pulse width                     |
| `range_resolution`     | m     | Range resolution (c / 2B)                |
| `azimuth_resolution`   | m     | Azimuth resolution (L/2 for stripmap)    |
| `unambiguous_range`    | m     | c / (2 * PRF)                            |
| `unambiguous_doppler`  | m/s   | Maximum unambiguous velocity             |
| `swath_width_ground`   | m     | Ground-projected swath width             |
| `nesz`                 | dB    | Noise equivalent sigma zero              |
| `snr_single_look`      | dB    | Single-look SNR for 1 m^2 target         |
| `n_range_samples`      | count | Number of range samples                   |
| `synthetic_aperture`   | m     | Synthetic aperture length                 |
| `doppler_bandwidth`    | Hz    | Doppler bandwidth                         |
| `n_pulses`             | count | Number of pulses in observation time      |
| `flight_time`          | s     | Total flight time                         |
| `track_length`         | m     | Total track length                        |

### CalculatedResult

Single derived value with metadata.

| Field     | Type           | Description                                    |
|----------|----------------|------------------------------------------------|
| `value`   | `float`        | Computed value in SI units                      |
| `unit`    | `str`          | Unit string (e.g. `"m"`, `"dB"`, `"Hz"`)       |
| `warning` | `str \| None`  | Warning message if value is outside normal range |
