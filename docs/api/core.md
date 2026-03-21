# API Reference: Core

## Radar

`pySimSAR.core.radar.Radar`

Radar system model combining waveform, antenna, and operating parameters.

### Constructor

```python
Radar(
    carrier_freq: float,
    transmit_power: float,
    waveform: Waveform,
    antenna: AntennaPattern,
    polarization: PolarizationMode | str,
    mode: SARMode | str = SARMode.STRIPMAP,
    look_side: LookSide | str = LookSide.RIGHT,
    depression_angle: float = pi/4,
    noise_figure: float = 3.0,
    system_losses: float = 2.0,
    reference_temp: float = 290.0,
    squint_angle: float = 0.0,
    receiver_gain_dB: float = 0.0,
    sample_rate: float | None = None,
    sar_mode_config: SARModeConfig | None = None,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `carrier_freq` | `float` | (required) | Carrier frequency in Hz. Must be > 0. |
| `transmit_power` | `float` | (required) | Transmit power in Watts. Must be > 0. |
| `waveform` | `Waveform` | (required) | Radar waveform instance. |
| `antenna` | `AntennaPattern` | (required) | Antenna pattern instance. |
| `polarization` | `PolarizationMode \| str` | (required) | Polarization mode: `"single"`, `"dual"`, or `"quad"`. |
| `mode` | `SARMode \| str` | `"stripmap"` | SAR imaging mode. Ignored if `sar_mode_config` is provided. |
| `look_side` | `LookSide \| str` | `"right"` | Radar look direction. Ignored if `sar_mode_config` is provided. |
| `depression_angle` | `float` | `pi/4` | Depression angle in radians [0, pi/2]. |
| `noise_figure` | `float` | `3.0` | Receiver noise figure in dB (>= 0). |
| `system_losses` | `float` | `2.0` | System losses in dB (>= 0). |
| `reference_temp` | `float` | `290.0` | Reference temperature in Kelvin (> 0). |
| `squint_angle` | `float` | `0.0` | Squint angle in radians [-pi/2, pi/2]. |
| `receiver_gain_dB` | `float` | `0.0` | Receiver gain in dB (>= 0). |
| `sample_rate` | `float \| None` | `None` | Range sampling rate in Hz. |
| `sar_mode_config` | `SARModeConfig \| None` | `None` | Explicit SAR mode configuration (overrides mode/look_side/depression_angle). |

### Properties

| Property | Type | Description |
|---|---|---|
| `sar_mode_config` | `SARModeConfig` | SAR imaging geometry configuration. |
| `mode` | `SARMode` | SAR imaging mode (delegated to sar_mode_config). |
| `look_side` | `LookSide` | Look direction (delegated to sar_mode_config). |
| `depression_angle` | `float` | Depression angle in radians. |
| `squint_angle` | `float` | Squint angle in radians. |
| `bandwidth` | `float` | Waveform bandwidth in Hz. |
| `pri` | `float` | Pulse repetition interval in seconds (1/PRF). |
| `wavelength` | `float` | Radar wavelength in meters (c / carrier_freq). |
| `total_noise_figure` | `float` | Cascaded noise figure in dB (system_losses + noise_figure). |
| `noise_power` | `float` | Thermal noise power at receiver output in Watts. |

---

## AntennaPattern

`pySimSAR.core.radar.AntennaPattern`

2-D antenna gain pattern with interpolation support.

### Constructor

```python
AntennaPattern(
    pattern_2d: np.ndarray | Callable[..., float],
    az_beamwidth: float,
    el_beamwidth: float,
    az_angles: np.ndarray | None = None,
    el_angles: np.ndarray | None = None,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pattern_2d` | `np.ndarray \| Callable` | (required) | 2-D gain pattern in dB (shape `(n_el, n_az)`) or callable `(az, el) -> gain_dB`. |
| `az_beamwidth` | `float` | (required) | 3 dB azimuth beamwidth in radians. Must be > 0. |
| `el_beamwidth` | `float` | (required) | 3 dB elevation beamwidth in radians. Must be > 0. |
| `az_angles` | `np.ndarray \| None` | `None` | Azimuth angle samples in radians. Required when `pattern_2d` is an array. |
| `el_angles` | `np.ndarray \| None` | `None` | Elevation angle samples in radians. Required when `pattern_2d` is an array. |

### Properties

| Property | Type | Description |
|---|---|---|
| `peak_gain_dB` | `float` | **Read-only.** Peak antenna gain in dB, automatically computed from beamwidths: $G = 4\pi\eta / (\theta_{az} \cdot \theta_{el})$ with $\eta = 0.6$. |

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `gain()` | `(az: float, el: float)` | `float` | Evaluate antenna gain at given angles (returns dB). |

---

## create_antenna_from_preset

`pySimSAR.core.radar.create_antenna_from_preset`

Factory function that creates an `AntennaPattern` from a named preset.

```python
create_antenna_from_preset(
    preset: str,
    az_beamwidth: float,
    el_beamwidth: float,
) -> AntennaPattern
```

| Parameter | Type | Description |
|---|---|---|
| `preset` | `str` | Preset name: `"flat"`, `"sinc"`, or `"gaussian"`. |
| `az_beamwidth` | `float` | 3 dB azimuth beamwidth in radians. |
| `el_beamwidth` | `float` | 3 dB elevation beamwidth in radians. |

> **Note:** `peak_gain_dB` is not a parameter. The antenna gain is automatically computed from beamwidths: $G = 4\pi\eta / (\theta_{az} \cdot \theta_{el})$ with $\eta = 0.6$.

---

## Scene

`pySimSAR.core.scene.Scene`

Container for all scattering targets in a simulation.

### Constructor

```python
Scene(
    origin_lat: float,
    origin_lon: float,
    origin_alt: float,
)
```

| Parameter | Type | Description |
|---|---|---|
| `origin_lat` | `float` | Scene origin latitude in degrees [-90, 90]. |
| `origin_lon` | `float` | Scene origin longitude in degrees [-180, 180]. |
| `origin_alt` | `float` | Scene origin altitude in meters. Must be finite. |

### Properties

| Property | Type | Description |
|---|---|---|
| `origin_lat` | `float` | Scene origin latitude in degrees. |
| `origin_lon` | `float` | Scene origin longitude in degrees. |
| `origin_alt` | `float` | Scene origin altitude in meters. |
| `point_targets` | `list[PointTarget]` | List of point targets. |
| `distributed_targets` | `list[DistributedTarget]` | List of distributed targets. |

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `add_target()` | `(target: PointTarget \| DistributedTarget)` | `None` | Add a target to the scene. Raises `TypeError` if target is an unsupported type. |

---

## PointTarget

`pySimSAR.core.scene.PointTarget`

A single point scatterer in the scene.

### Constructor

```python
PointTarget(
    position: np.ndarray,
    rcs: float | np.ndarray,
    velocity: np.ndarray | None = None,
    rcs_model: RCSModel | None = None,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `position` | `np.ndarray` | (required) | ENU coordinates [x, y, z] in meters, shape `(3,)`. |
| `rcs` | `float \| np.ndarray` | (required) | Radar cross section. Scalar (> 0) for single-pol, complex `(2, 2)` scattering matrix for quad-pol. |
| `velocity` | `np.ndarray \| None` | `None` | Target velocity [vx, vy, vz] in m/s, shape `(3,)`. |
| `rcs_model` | `RCSModel \| None` | `None` | RCS fluctuation model. Defaults to `StaticRCS()`. |

### Properties

| Property | Type | Description |
|---|---|---|
| `position` | `np.ndarray` | ENU coordinates, shape `(3,)`. |
| `rcs` | `float \| np.ndarray` | Radar cross section. |
| `velocity` | `np.ndarray \| None` | Target velocity, or None. |
| `rcs_model` | `RCSModel` | RCS fluctuation model. |

---

## DistributedTarget

`pySimSAR.core.scene.DistributedTarget`

A gridded distributed scattering region.

### Constructor

```python
DistributedTarget(
    origin: np.ndarray,
    extent: np.ndarray,
    cell_size: float,
    reflectivity: np.ndarray | None = None,
    scattering_matrix: np.ndarray | None = None,
    elevation: np.ndarray | None = None,
    clutter_model: ClutterModel | None = None,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `origin` | `np.ndarray` | (required) | ENU position of the grid corner, shape `(3,)`. |
| `extent` | `np.ndarray` | (required) | Grid size [dx, dy] in meters, shape `(2,)`. Must be > 0. |
| `cell_size` | `float` | (required) | Grid cell spacing in meters. Must be > 0. |
| `reflectivity` | `np.ndarray \| None` | `None` | Reflectivity per cell, shape `(ny, nx)`. Required if no `clutter_model`. |
| `scattering_matrix` | `np.ndarray \| None` | `None` | Per-cell polarimetric scattering matrix, shape `(ny, nx, 2, 2)`. |
| `elevation` | `np.ndarray \| None` | `None` | Per-cell elevation offset, shape `(ny, nx)`. |
| `clutter_model` | `ClutterModel \| None` | `None` | Clutter model for reflectivity generation. |

### Properties

| Property | Type | Description |
|---|---|---|
| `origin` | `np.ndarray` | ENU position of grid corner. |
| `extent` | `np.ndarray` | Grid size [dx, dy] in meters. |
| `cell_size` | `float` | Cell spacing in meters. |
| `nx` | `int` | Number of cells in x direction. |
| `ny` | `int` | Number of cells in y direction. |
| `reflectivity` | `np.ndarray \| None` | Reflectivity per cell. |
| `scattering_matrix` | `np.ndarray \| None` | Per-cell scattering matrix. |
| `elevation` | `np.ndarray \| None` | Per-cell elevation offset. |
| `clutter_model` | `ClutterModel \| None` | Clutter model. |

---

## Platform

`pySimSAR.core.platform.Platform`

Aircraft/UAV platform configuration.

### Constructor

```python
Platform(
    velocity: float,
    altitude: float,
    heading: float | np.ndarray = 0.0,
    start_position: np.ndarray | None = None,
    perturbation: MotionPerturbation | None = None,
    sensors: list | None = None,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `velocity` | `float` | (required) | Nominal platform speed in m/s. Must be > 0. |
| `altitude` | `float` | (required) | Nominal flight altitude in meters. Must be > 0. |
| `heading` | `float \| np.ndarray` | `0.0` | Scalar (radians, 0 = North) or 3-D direction vector `[hx, hy, hz]`. |
| `start_position` | `np.ndarray \| None` | `None` | Starting position in ENU meters, shape `(3,)`. Defaults to `[0, 0, altitude]`. |
| `perturbation` | `MotionPerturbation \| None` | `None` | Motion perturbation model (turbulence). |
| `sensors` | `list \| None` | `None` | Attached navigation sensors (GPSSensor, IMUSensor). Defaults to `[]`. |

### Properties

| Property | Type | Description |
|---|---|---|
| `heading_vector` | `np.ndarray` | Unit direction vector for the flight path, shape `(3,)`. |

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `generate_ideal_trajectory()` | `(n_pulses: int, prf: float)` | `Trajectory` | Straight-line constant-altitude trajectory. |
| `generate_perturbed_trajectory()` | `(n_pulses: int, prf: float, seed: int = 42)` | `Trajectory` | Trajectory with turbulence perturbations (falls back to ideal if no perturbation model). |

---

## SARCalculator

`pySimSAR.core.calculator.SARCalculator`

Computes derived SAR system parameters from a flat parameter dictionary.

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `compute()` | `(params: dict)` | `dict[str, CalculatedResult]` | Compute all derived values. |
| `compute_single()` | `(key: str, params: dict)` | `CalculatedResult` | Compute a single derived value by name. |

### Expected `params` keys

All values in SI units: `carrier_freq`, `prf`, `bandwidth`, `duty_cycle`,
`transmit_power`, `az_beamwidth`, `el_beamwidth`,
`depression_angle`, `velocity`, `altitude`, `noise_figure`, `system_losses`,
`receiver_gain_dB`, `reference_temp`, `mode`, `near_range` (opt),
`far_range` (opt), `flight_time` (opt), `start_position` (opt),
`stop_position` (opt).

> **Note:** `peak_gain_dB` is not an input key. Antenna gain is automatically
> derived from `az_beamwidth` and `el_beamwidth`.

### Computed quantities

| Key | Unit | Description |
|---|---|---|
| `wavelength` | m | Radar wavelength (c / carrier_freq). |
| `antenna_gain` | dBi | Antenna gain from beamwidths (aperture efficiency 0.6). |
| `pulse_width` | s | Pulse duration (duty_cycle / prf). |
| `range_resolution` | m | Slant-range resolution (c / 2B). |
| `azimuth_resolution` | m | Azimuth resolution (antenna_length / 2). |
| `unambiguous_range` | m | Maximum unambiguous range (c / 2*prf). |
| `unambiguous_doppler` | m/s | Maximum unambiguous velocity (lambda*prf / 4). |
| `swath_width_ground` | m | Ground-range swath width. |
| `nesz` | dB | Noise equivalent sigma zero. |
| `snr_single_look` | dB | Single-look SNR for 1 m^2 target. |
| `n_range_samples` | count | Number of range samples in the swath. |
| `synthetic_aperture` | m | Synthetic aperture length. |
| `doppler_bandwidth` | Hz | Doppler bandwidth. |
| `n_pulses` | count | Number of pulses in the observation. |
| `flight_time` | s | Total flight time. |
| `track_length` | m | Flight track length. |

### CalculatedResult

Dataclass with fields: `value` (`float`), `unit` (`str`), `warning` (`str | None`).

---

## SARModeConfig

`pySimSAR.core.types.SARModeConfig`

Dataclass for SAR imaging geometry configuration.

| Field | Type | Default | Description |
|---|---|---|---|
| `mode` | `SARMode \| str` | `SARMode.STRIPMAP` | SAR mode: `"stripmap"`, `"spotlight"`, `"scanmar"`. |
| `look_side` | `LookSide \| str` | `LookSide.RIGHT` | Look direction: `"left"` or `"right"`. |
| `depression_angle` | `float` | `0.7854` (45 deg) | Depression angle in radians [0, pi/2]. |
| `squint_angle` | `float` | `0.0` | Squint angle in radians [-pi/2, pi/2]. |
| `scene_center` | `np.ndarray \| None` | `None` | Scene center for spotlight/scansar, shape `(3,)`. |
| `n_subswaths` | `int` | `3` | Number of sub-swaths (scansar mode). |
| `burst_length` | `int` | `20` | Pulses per burst (scansar mode). |

---

## RawData

`pySimSAR.core.types.RawData`

Dataclass for simulated raw SAR echo data (single channel).

| Field | Type | Default | Description |
|---|---|---|---|
| `echo` | `np.ndarray` | (required) | Complex echo matrix, shape `(n_azimuth, n_range)`. |
| `channel` | `str` | (required) | Polarization channel name. |
| `sample_rate` | `float` | (required) | Range sampling rate in Hz. |
| `carrier_freq` | `float` | (required) | Carrier frequency in Hz. |
| `bandwidth` | `float` | (required) | Waveform bandwidth in Hz. |
| `prf` | `float` | (required) | Pulse repetition frequency in Hz. |
| `waveform_name` | `str` | `""` | Waveform type name. |
| `sar_mode` | `str` | `"stripmap"` | SAR mode string. |
| `gate_delay` | `float` | `0.0` | Range gate start delay in seconds. |

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `save()` | `(filepath: str)` | `None` | Save to HDF5 file. |
| `load()` | `(filepath: str, channel: str \| None = None)` | `RawData` | Static method. Load from HDF5 file. |

---

## PhaseHistoryData

`pySimSAR.core.types.PhaseHistoryData`

Dataclass for range-compressed phase history data.

| Field | Type | Default | Description |
|---|---|---|---|
| `data` | `np.ndarray` | (required) | Complex phase history, shape `(n_azimuth, n_range)`. |
| `sample_rate` | `float` | (required) | Range sampling rate in Hz. |
| `prf` | `float` | (required) | Pulse repetition frequency in Hz. |
| `carrier_freq` | `float` | (required) | Carrier frequency in Hz. |
| `bandwidth` | `float` | (required) | Waveform bandwidth in Hz. |
| `channel` | `str` | `"single"` | Polarization channel name. |
| `gate_delay` | `float` | `0.0` | Range gate start delay in seconds. |

---

## SARImage

`pySimSAR.core.types.SARImage`

Dataclass for a focused SAR image product.

| Field | Type | Default | Description |
|---|---|---|---|
| `data` | `np.ndarray` | (required) | Image pixel data, shape `(n_rows, n_cols)`. Complex or real. |
| `pixel_spacing_range` | `float` | (required) | Range pixel spacing in meters. |
| `pixel_spacing_azimuth` | `float` | (required) | Azimuth pixel spacing in meters. |
| `geometry` | `str` | `"slant_range"` | Coordinate geometry: `"slant_range"`, `"ground_range"`, or `"geographic"`. |
| `algorithm` | `str` | `""` | Image formation algorithm name. |
| `channel` | `str` | `"single"` | Polarization channel name. |
| `near_range` | `float` | `0.0` | Near range in meters. |
| `geo_transform` | `np.ndarray \| None` | `None` | Affine geo-transform, shape `(6,)`. |
| `projection_wkt` | `str \| None` | `None` | WKT projection string. |

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `save()` | `(filepath: str, name: str = "image")` | `None` | Save to HDF5. |
| `load()` | `(filepath: str, name: str \| None = None)` | `SARImage` | Static method. Load from HDF5. |

---

## SimulationState

`pySimSAR.core.types.SimulationState`

Enum for simulation lifecycle states.

| Value | Description |
|---|---|
| `CREATED` | Initial state after construction. |
| `VALIDATED` | Parameters have been validated. |
| `RUNNING` | Simulation is executing. |
| `COMPLETED` | Simulation finished successfully. |
| `FAILED` | Simulation encountered an error. |

Transitions: `CREATED -> VALIDATED -> RUNNING -> COMPLETED | FAILED`

---

## Enums

### SARMode

Values: `STRIPMAP` (`"stripmap"`), `SPOTLIGHT` (`"spotlight"`), `SCANMAR` (`"scanmar"`).

### PolarizationMode

Values: `SINGLE` (`"single"`), `DUAL` (`"dual"`), `QUAD` (`"quad"`).

### LookSide

Values: `LEFT` (`"left"`), `RIGHT` (`"right"`).

### ImageGeometry

Values: `SLANT_RANGE` (`"slant_range"`), `GROUND_RANGE` (`"ground_range"`), `GEOGRAPHIC` (`"geographic"`).
