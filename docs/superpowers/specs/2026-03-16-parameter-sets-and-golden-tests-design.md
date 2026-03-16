# Design: Parameter Sets, Presets, and Golden Reference Test Cases

**Date**: 2026-03-16
**Branch**: `001-sar-signal-simulator`
**Status**: Approved

## Overview

This design adds three capabilities to PySimSAR:

1. **Parameter Set I/O** — Save and load complete simulation/processing configurations as project directories containing JSON files and binary array data.
2. **Reusable Presets** — Ship default parameter sets for common components (antennas, waveforms, sensors, platforms) that users can reference or extend.
3. **Golden Reference Test Cases** — Three canonical simulation scenarios under `tests/golden/` that serve as end-to-end regression tests with analytical ground truth.

Additionally, two model changes support the parameter set design:

4. **Receiver Gain** — Add explicit `receiver_gain_dB` to the Radar model with corrected cascade noise calculation.
5. **Point Target RCS Model** — Add a pluggable `rcs_model` interface to PointTarget, with `static` as the shipped default.

---

## 1. Parameter Set Format

### 1.1 Project Directory Structure

A parameter set is a directory containing a main `project.json` and supporting files:

```
my_project/
├── project.json                        # Main entry point
├── scene.json                          # Scene definition
├── radar.json                          # Radar system parameters
├── waveform.json                       # Waveform definition
├── antenna.json                        # Antenna pattern
├── platform.json                       # Platform + sensors
├── processing.json                     # Processing pipeline config
├── algorithms/                         # Algorithm-specific parameter files
│   ├── image_formation.json
│   ├── moco.json
│   └── autofocus.json
├── scene_point_targets_positions.npy   # (N, 3) float64 — bulk point targets
├── scene_point_targets_rcs.npy         # (N,) float64 or (N, 2, 2) complex128
├── scene_point_targets_velocities.npy  # (N, 3) float64 — optional
├── scene_point_targets_rcs_models.json # [{type, ...}, ...] per target
├── dist_target_0_reflectivity.npy      # (ny, nx) float64
├── dist_target_0_scattering_matrix.npy # (ny, nx, 2, 2) complex128
├── dist_target_0_elevation.npy         # (ny, nx) float64
└── antenna_pattern_measured.npz        # pattern_2d, az_angles, el_angles
```

Not all files are required. A minimal project needs only `project.json` with inline parameters or `$ref` links to component files.

### 1.2 Reference Mechanisms

Two reference types are used within JSON files:

| Mechanism | Syntax | Purpose |
|-----------|--------|---------|
| `$ref` | `{"$ref": "path/to/file.json"}` | Load and merge another JSON file |
| `$data` | `{"$data": "filename.npy"}` | Load binary array data (.npy, .npz, .csv) |

**`$ref` resolution rules:**
- Paths are relative to the file containing the `$ref`.
- Resolution is recursive — a referenced file may itself contain `$ref` entries.
- A `$ref` replaces the entire object it appears in. Sibling keys alongside `$ref` are an error — the loader raises `ValueError` if any keys other than `$ref` are present in the same object.
- Circular references are detected via a visited-path set and raise `ValueError`.

**`$data` resolution rules:**
- Paths are relative to the file containing the `$data`.
- Supported formats:
  - `.npy` — Single array. The `$data` object is replaced with the loaded `np.ndarray`.
  - `.npz` — Named arrays. The `$data` object is replaced with a `dict[str, np.ndarray]` mapping archive keys to arrays.
  - `.csv` — 2D float data. Loaded via `np.loadtxt` with comma delimiter, no header, UTF-8 encoding. The `$data` object is replaced with the loaded 2D `np.ndarray`.

### 1.3 Conventions

| Convention | Rule |
|------------|------|
| Unit suffixes | Keys include units: `_hz`, `_m`, `_mps`, `_deg`, `_dB`, `_dBc`, `_K`, `_w`, `_m2` |
| Angles | Degrees in JSON, converted to radians on load (except geographic coordinates — see below) |
| Geographic coords | `origin_lat_deg` and `origin_lon_deg` are **not** converted to radians — they remain in degrees and are passed directly to `Scene()` which stores them as degrees |
| Unit suffix stripping | On load, unit suffixes (`_hz`, `_m`, `_dB`, `_dBc`, `_K`, `_w`, `_m2`, `_mps`) are stripped from keys when mapping to constructor parameters. E.g., `carrier_freq_hz` maps to `carrier_freq`. The `_deg` suffix is both stripped and triggers degree-to-radian conversion (except geographic coords). |
| `null` | Means "use default" or "feature disabled" |
| `type` field | Discriminator for polymorphic components (waveform type, sensor type, etc.) |
| Complex numbers | Stored as `[real, imag]` pairs in JSON |
| Format version | `project.json` includes a `"format_version": "1.0"` field for forward compatibility |

---

## 2. File Schemas

### 2.1 project.json

```json
{
  "format_version": "1.0",
  "name": "Project Name",
  "description": "Free-text description of this simulation setup",
  "scene": { "$ref": "scene.json" },
  "radar": { "$ref": "radar.json" },
  "platform": { "$ref": "platform.json" },
  "simulation": {
    "n_pulses": 256,
    "seed": 42,
    "sample_rate_hz": null,
    "scene_center_m": null,
    "n_subswaths": 3,
    "burst_length": 20
  },
  "processing": { "$ref": "processing.json" }
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `format_version` | string | yes | — | Parameter set format version (currently `"1.0"`) |
| `name` | string | no | `""` | Human-readable project name |
| `description` | string | no | `""` | Free-text description |
| `scene` | object or `$ref` | yes | — | Scene definition |
| `radar` | object or `$ref` | yes | — | Radar system parameters |
| `platform` | object or `$ref` | yes | — | Platform configuration |
| `simulation` | object | yes | — | Simulation control parameters |
| `simulation.n_pulses` | int | yes | — | Number of azimuth pulses (> 0) |
| `simulation.seed` | int | yes | — | Random seed for reproducibility (>= 0) |
| `simulation.sample_rate_hz` | float or null | no | null (= 2x bandwidth) | Range sampling rate |
| `simulation.scene_center_m` | [x,y,z] or null | no | null (= [0,0,0]) | Spotlight scene center in ENU meters |
| `simulation.n_subswaths` | int | no | 3 | Number of sub-swaths for ScanSAR |
| `simulation.burst_length` | int | no | 20 | Pulses per burst for ScanSAR |
| `processing` | object, `$ref`, or null | no | null | Processing pipeline configuration |

### 2.2 scene.json

```json
{
  "origin_lat_deg": 34.05,
  "origin_lon_deg": -118.25,
  "origin_alt_m": 0.0,
  "point_targets": [
    {
      "position_m": [100, 0, 0],
      "rcs_m2": 10.0,
      "rcs_model": { "type": "static" },
      "velocity_mps": null
    }
  ],
  "point_targets_file": {
    "positions": { "$data": "scene_point_targets_positions.npy" },
    "rcs": { "$data": "scene_point_targets_rcs.npy" },
    "velocities": { "$data": "scene_point_targets_velocities.npy" },
    "rcs_models": { "$ref": "scene_point_targets_rcs_models.json" }
  },
  "distributed_targets": [
    {
      "origin_m": [500, -200, 0],
      "extent_m": [100, 100],
      "cell_size_m": 1.0,
      "reflectivity": { "$data": "dist_target_0_reflectivity.npy" },
      "scattering_matrix": { "$data": "dist_target_0_scattering_matrix.npy" },
      "elevation": { "$data": "dist_target_0_elevation.npy" },
      "clutter_model": { "type": "uniform", "mean_intensity": 1.0 }
    }
  ]
}
```

**Point targets** can be specified via:

- **Inline** (`point_targets` array): For small numbers of targets. Each target has `position_m` [x,y,z], `rcs_m2` (scalar or quad-pol matrix), `rcs_model`, and optional `velocity_mps`.
- **External files** (`point_targets_file`): For bulk targets. Separate .npy files with descriptive names. All arrays must have the same number of rows (N targets).

Both mechanisms may be present — targets are merged (inline first, then file-based).

**Quad-pol RCS in JSON** (inline point target):

```json
{
  "rcs_m2": {
    "hh": [1.0, 0.0], "hv": [0.1, 0.05],
    "vh": [0.1, -0.05], "vv": [0.3, 0.0]
  }
}
```

Each channel value is `[real, imag]`. Constructed into a 2x2 complex matrix: `[[hh, hv], [vh, vv]]`.

**Point target fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `position_m` | [x, y, z] | yes | — | ENU position in meters |
| `rcs_m2` | float or quad-pol object | yes | — | RCS in m^2 (scalar) or scattering matrix |
| `rcs_model` | object | no | `{"type": "static"}` | Statistical RCS model |
| `velocity_mps` | [vx, vy, vz] or null | no | null | Target velocity in m/s |

**Distributed target fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `origin_m` | [x, y, z] | yes | — | Grid corner position in ENU meters |
| `extent_m` | [dx, dy] | yes | — | Grid size in meters |
| `cell_size_m` | float | yes | — | Grid cell spacing in meters |
| `reflectivity` | 2D array or `$data` | conditional | — | Per-cell reflectivity (required if no clutter_model) |
| `scattering_matrix` | 4D array or `$data` | no | null | Per-cell quad-pol scattering matrix |
| `elevation` | 2D array or `$data` | no | null | Per-cell elevation offset |
| `clutter_model` | object | no | null | Statistical clutter model |

### 2.3 radar.json

```json
{
  "carrier_freq_hz": 9.65e9,
  "prf_hz": 1000.0,
  "transmit_power_w": 1000.0,
  "receiver_gain_dB": 30.0,
  "noise_figure_dB": 3.0,
  "system_losses_dB": 2.0,
  "reference_temp_K": 290.0,
  "polarization": "single",
  "mode": "stripmap",
  "look_side": "right",
  "depression_angle_deg": 45.0,
  "squint_angle_deg": 0.0,
  "waveform": { "$ref": "waveform.json" },
  "antenna": { "$ref": "antenna.json" }
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `carrier_freq_hz` | float | yes | — | Carrier frequency in Hz (> 0) |
| `prf_hz` | float | yes | — | Pulse repetition frequency in Hz (> 0) |
| `transmit_power_w` | float | yes | — | Transmit power in Watts (> 0) |
| `receiver_gain_dB` | float | no | 0.0 | Receiver gain in dB (>= 0) |
| `noise_figure_dB` | float | no | 3.0 | Receiver noise figure in dB (>= 0) |
| `system_losses_dB` | float | no | 2.0 | Pre-receiver system losses in dB (>= 0) |
| `reference_temp_K` | float | no | 290.0 | Reference temperature in Kelvin (> 0) |
| `polarization` | string | yes | — | "single", "dual", or "quad" |
| `mode` | string | yes | — | "stripmap", "spotlight", or "scanmar" (alias "scansar" also accepted) |
| `look_side` | string | yes | — | "left" or "right" |
| `depression_angle_deg` | float | yes | — | Depression angle in degrees [0, 90] |
| `squint_angle_deg` | float | no | 0.0 | Squint angle in degrees [-90, 90] |
| `waveform` | object or `$ref` | yes | — | Waveform definition |
| `antenna` | object or `$ref` | yes | — | Antenna pattern definition |

**Receiver gain and noise model:**

The signal chain is: antenna -> passive losses (L_sys) -> receiver (G_rx, NF_rx).

- Signal amplitude factor includes `receiver_gain_dB` as amplification.
- Total system noise figure: `F_total = L_sys_linear * F_rx_linear` (cascade of passive loss followed by active receiver, per Friis formula).
- Noise power: `P_noise = k * T_ref * B * F_total * G_rx_linear`, where `B` is the waveform bandwidth (which equals the matched filter noise bandwidth for a matched-filter receiver).
- SNR at receiver output is independent of G_rx (amplifies signal and noise equally), but absolute signal levels depend on it.

### 2.4 waveform.json

**LFM example:**
```json
{
  "type": "lfm",
  "bandwidth_hz": 150e6,
  "duty_cycle": 0.1,
  "window": "hamming",
  "window_params": null,
  "phase_noise": null
}
```

**FMCW example:**
```json
{
  "type": "fmcw",
  "bandwidth_hz": 1e9,
  "duty_cycle": 1.0,
  "ramp_type": "up",
  "window": "hanning",
  "window_params": null,
  "phase_noise": {
    "type": "composite_psd",
    "flicker_fm_level_dBc": -80.0,
    "white_fm_level_dBc": -100.0,
    "flicker_pm_level_dBc": -120.0,
    "white_floor_dBc": -150.0
  }
}
```

**Fields (common):**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | yes | — | `"lfm"` or `"fmcw"` |
| `bandwidth_hz` | float | yes | — | Waveform bandwidth in Hz (> 0) |
| `duty_cycle` | float | no | 0.1 (LFM), 1.0 (FMCW) | Fraction of PRI (0, 1] |
| `window` | string or null | no | null | Window function name |
| `window_params` | object or null | no | null | Window-specific parameters (e.g., `{"beta": 6}` for Kaiser) |
| `phase_noise` | object or null | no | null | Phase noise model configuration |

**Window name-to-callable resolution:** The `build_simulation()` function maps JSON window names to callables using a window factory. Supported names and their mappings:

| JSON name | Callable | Params |
|-----------|----------|--------|
| `"hamming"` | `lambda n: np.hamming(n)` | — |
| `"hanning"` | `lambda n: np.hanning(n)` | — |
| `"blackman"` | `lambda n: np.blackman(n)` | — |
| `"kaiser"` | `lambda n: np.kaiser(n, beta)` | `{"beta": float}` (required) |
| `"tukey"` | `lambda n: scipy.signal.windows.tukey(n, alpha)` | `{"alpha": float}` (default 0.5) |
| `null` / `"none"` | `None` (no windowing) | — |

When `window_params` is provided, the parameters are passed to the window function. Unrecognized window names raise `ValueError`.

**Fields (FMCW-specific):**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `ramp_type` | string | no | `"up"` | Frequency ramp: `"up"`, `"down"`, or `"triangle"` |

**Phase noise fields (composite_psd):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | — | `"composite_psd"` |
| `flicker_fm_level_dBc` | float | -80.0 | Flicker FM noise level at 1 Hz offset |
| `white_fm_level_dBc` | float | -100.0 | White FM noise level at 1 Hz offset |
| `flicker_pm_level_dBc` | float | -120.0 | Flicker PM noise level at 1 Hz offset |
| `white_floor_dBc` | float | -150.0 | White phase noise floor |

### 2.5 antenna.json

**Preset mode:**
```json
{
  "type": "preset",
  "preset": "sinc",
  "az_beamwidth_deg": 3.0,
  "el_beamwidth_deg": 10.0,
  "peak_gain_dB": 30.0
}
```

**Measured mode:**
```json
{
  "type": "measured",
  "pattern": { "$data": "antenna_pattern_measured.npz" },
  "peak_gain_dB": 30.0
}
```

**Fields (preset mode):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | `"preset"` |
| `preset` | string | yes | `"flat"`, `"sinc"`, or `"gaussian"` |
| `az_beamwidth_deg` | float | yes | 3 dB azimuth beamwidth in degrees (> 0) |
| `el_beamwidth_deg` | float | yes | 3 dB elevation beamwidth in degrees (> 0) |
| `peak_gain_dB` | float | yes | Peak antenna gain in dB |

**Fields (measured mode):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | `"measured"` |
| `pattern` | `$data` ref to .npz | yes | Contains `pattern_2d` (n_el, n_az), `az_angles` (n_az,), `el_angles` (n_el,) in radians |
| `peak_gain_dB` | float | yes | Peak antenna gain in dB |

**Antenna presets:**

| Preset | Pattern function | Description |
|--------|-----------------|-------------|
| `flat` | `G(az, el) = peak_gain_dB` if `|az| < bw_az/2` and `|el| < bw_el/2`, else `peak_gain_dB - 60` | Ideal rectangular beam with -60 dB floor |
| `sinc` | `G(az, el) = peak_gain_dB + max(-60, 20*log10(sinc(0.886*az/bw_az) * sinc(0.886*el/bw_el)))` | Approximate uniform aperture |
| `gaussian` | `G(az, el) = peak_gain_dB - 12 * ((az/bw_az)^2 + (el/bw_el)^2)` | Gaussian beam approximation |

The `sinc` preset uses `sinc(x) = sin(pi*x)/(pi*x)`. The 0.886 factor relates the 3 dB beamwidth to the first null. A -60 dB gain floor (relative to peak) is applied to prevent numerical issues at nulls.

The `gaussian` preset constant K=12 ensures 3 dB attenuation at the half-beamwidth point: at `az = bw_az/2, el = 0`, the loss is `12 * (0.5)^2 = 3 dB`. This corresponds to a Gaussian with `sigma = bw / (2*sqrt(2*ln(2)))`.

### 2.6 platform.json

```json
{
  "velocity_mps": 100.0,
  "altitude_m": 2000.0,
  "heading_deg": 0.0,
  "start_position_m": [0, 0, 2000],
  "perturbation": {
    "type": "dryden",
    "sigma_u": 1.0,
    "sigma_v": 1.0,
    "sigma_w": 0.5
  },
  "sensors": [
    {
      "type": "gps",
      "accuracy_rms_m": 0.5,
      "update_rate_hz": 10.0,
      "outage_intervals": [],
      "error_model": { "type": "gaussian" }
    },
    {
      "type": "imu",
      "accel_noise_density": 0.003,
      "gyro_noise_density": 0.0005,
      "sample_rate_hz": 100.0,
      "error_model": { "type": "white_noise" }
    }
  ]
}
```

**Platform fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `velocity_mps` | float | yes | — | Nominal speed in m/s (> 0) |
| `altitude_m` | float | yes | — | Flight altitude in meters (> 0) |
| `heading_deg` | float | no | 0.0 | Heading in degrees (0 = North, 90 = East) |
| `start_position_m` | [x,y,z] or null | no | null (= [0, 0, altitude]) | Starting position in ENU meters |
| `perturbation` | object or null | no | null | Motion perturbation model |
| `sensors` | list or null | no | null (= []) | Navigation sensors |

**Perturbation fields (dryden):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | — | `"dryden"` |
| `sigma_u` | float | 1.0 | Longitudinal turbulence intensity (m/s) |
| `sigma_v` | float | 1.0 | Lateral turbulence intensity (m/s) |
| `sigma_w` | float | 0.5 | Vertical turbulence intensity (m/s) |

**GPS sensor fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | — | `"gps"` |
| `accuracy_rms_m` | float | — | Position accuracy RMS in meters (> 0) |
| `update_rate_hz` | float | — | Output rate in Hz (> 0) |
| `outage_intervals` | list of [start, end] | [] | Time intervals with no output |
| `error_model` | object | — | Error model config (e.g., `{"type": "gaussian"}`) |

**IMU sensor fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | — | `"imu"` |
| `accel_noise_density` | float | — | Accelerometer VRW in m/s^2/sqrt(Hz) (>= 0) |
| `gyro_noise_density` | float | — | Gyroscope ARW in rad/s/sqrt(Hz) (>= 0) |
| `sample_rate_hz` | float | — | Output rate in Hz (> 0) |
| `error_model` | object | — | Error model config (e.g., `{"type": "white_noise"}`) |

### 2.7 processing.json

```json
{
  "image_formation": { "$ref": "algorithms/image_formation.json" },
  "moco": { "$ref": "algorithms/moco.json" },
  "autofocus": null,
  "geocoding": null,
  "polarimetric_decomposition": null
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `image_formation` | object or `$ref` | yes | — | Image formation algorithm config |
| `moco` | object, `$ref`, or null | no | null | Motion compensation config |
| `autofocus` | object, `$ref`, or null | no | null | Autofocus config |
| `geocoding` | object, `$ref`, or null | no | null | Geocoding config |
| `polarimetric_decomposition` | object, `$ref`, or null | no | null | Polarimetric decomposition config |

### 2.8 Algorithm Configuration Files

**Standard algorithm:**
```json
{
  "algorithm": "range_doppler",
  "params": {}
}
```

**Algorithm with parameters:**
```json
{
  "algorithm": "pga",
  "params": {
    "max_iterations": 10,
    "convergence_threshold": 0.01
  }
}
```

**User-written algorithm (external module):**
```json
{
  "algorithm": "my_custom_autofocus",
  "module": "my_plugins.autofocus_v2",
  "params": {
    "max_iterations": 20,
    "window_size": 64,
    "threshold": 0.005
  }
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `algorithm` | string | yes | — | Algorithm name (must be in registry or loadable via `module`) |
| `module` | string | no | null | Python module path for user-written algorithms |
| `params` | object | no | `{}` | Algorithm-specific parameters |

**Algorithm self-description interface:**

Algorithm classes declare their expected parameters via a classmethod:

```python
class MyAutofocus(AutofocusAlgorithm):
    @classmethod
    def parameter_schema(cls) -> dict:
        """Declare parameters, types, defaults, and descriptions.

        Returns dict mapping parameter name to:
          - type: Python type name ("int", "float", "str", "bool")
          - default: default value (None if required)
          - description: human-readable description
        """
        return {
            "max_iterations": {
                "type": "int", "default": 10,
                "description": "Maximum iterations for convergence"
            },
            "window_size": {
                "type": "int", "default": 32,
                "description": "Azimuth window size in samples"
            },
        }
```

The `build_simulation()` function uses this schema to validate JSON params and apply defaults before passing to the constructor. Built-in algorithms provide `parameter_schema()` as well, even if they currently have no tunable parameters (returning `{}`).

---

## 3. Core I/O Module

**File:** `pySimSAR/io/parameter_set.py`

### 3.1 Public API

```python
def resolve_refs(data: dict | list, base_dir: Path) -> dict | list:
    """Recursively resolve all $ref and $data entries in a nested structure.

    - $ref: loads a JSON file and replaces the $ref object with its contents.
    - $data: loads a binary file (.npy, .npz, .csv) and replaces the $data
      object with the loaded array(s).

    Paths are relative to the file that contains the reference.
    Circular references raise ValueError.
    """

def load_parameter_set(project_path: str | Path) -> dict:
    """Load a parameter set from a project directory.

    Reads project.json (or the file at project_path if it's a file),
    resolves all $ref and $data entries, converts units (degrees to radians),
    and returns the fully resolved parameter dictionary.
    """

def build_simulation(params: dict) -> dict:
    """Construct simulation objects from a resolved parameter dictionary.

    Returns a dict with keys:
      - 'scene': Scene (with all targets populated)
      - 'radar': Radar (with waveform, antenna, receiver_gain)
      - 'platform': Platform (with perturbation, sensors)
      - 'engine_kwargs': dict (n_pulses, seed, sample_rate, scene_center, etc.)
      - 'processing_config': ProcessingConfig | None

    Algorithm objects are resolved through their registries.
    User-written algorithms (with 'module' field) are dynamically imported.
    """

def save_parameter_set(
    output_dir: str | Path,
    *,
    scene: Scene,
    radar: Radar,
    platform: Platform,
    n_pulses: int,
    seed: int,
    sample_rate: float | None = None,
    scene_center: np.ndarray | None = None,
    n_subswaths: int = 3,
    burst_length: int = 20,
    processing_config: ProcessingConfig | None = None,
    name: str = "",
    description: str = "",
) -> Path:
    """Serialize a complete simulation setup to a project directory.

    Creates the directory (if needed) and writes:
      - project.json with $ref links to component files
      - Individual JSON files for each component
      - .npy files for large array data (antenna patterns, distributed target
        reflectivity, scattering matrices, elevation maps, bulk point targets)

    Point targets with <= 20 targets are saved inline in scene.json.
    Point targets with > 20 targets are saved to external .npy files.

    Returns the Path to the created project directory.
    """
```

### 3.2 Unit Conversion

On load, the following conversions are applied automatically:

| JSON key suffix | Conversion |
|-----------------|------------|
| `_deg` | degrees -> radians (key renamed to drop `_deg`, add `_rad` internally) |

On save, the reverse conversion is applied (radians -> degrees in JSON).

### 3.3 Validation

`load_parameter_set()` performs structural validation:
- Required fields present
- Types correct (string, number, array)
- Enum values valid (polarization, mode, look_side, waveform type, etc.)
- Array shapes consistent (point target files have matching row counts)

`build_simulation()` delegates to each class's constructor for domain validation (value ranges, physical constraints).

---

## 4. Reusable Presets

### 4.1 Directory Structure

```
pySimSAR/presets/
├── antennas/
│   ├── flat_default.json       # Flat beam, 3 deg az, 10 deg el, 30 dB
│   ├── sinc_xband.json         # Sinc pattern, X-band typical
│   └── gaussian_default.json   # Gaussian beam, generic
├── waveforms/
│   ├── lfm_xband_150mhz.json  # X-band pulsed LFM, 150 MHz BW
│   ├── lfm_cband_50mhz.json   # C-band pulsed LFM, 50 MHz BW
│   └── fmcw_wband_1ghz.json   # W-band FMCW, 1 GHz BW
├── sensors/
│   ├── tactical_gps.json       # Typical tactical GPS (1m RMS)
│   ├── rtk_gps.json            # RTK GPS (0.02m RMS)
│   ├── mems_imu.json           # Consumer MEMS IMU
│   └── navigation_imu.json     # Navigation-grade IMU
└── platforms/
    ├── airborne_100mps.json    # Fixed-wing aircraft, 100 m/s, 2 km alt
    └── uav_30mps.json          # Small UAV, 30 m/s, 500 m alt
```

### 4.2 Referencing Presets

Users can reference shipped presets via `$ref` with a `$preset` prefix:

```json
{
  "antenna": { "$ref": "$preset/antennas/sinc_xband.json" }
}
```

The `$preset` prefix resolves to the `pySimSAR/presets/` directory within the installed package. This allows presets to work regardless of where the user's project directory is.

Users can also copy a preset into their project directory and modify it — the local `$ref` takes precedence.

---

## 5. Model Changes

### 5.1 Receiver Gain (Radar)

**File:** `pySimSAR/core/radar.py`

Add `receiver_gain_dB` parameter to `Radar.__init__()`:

```python
def __init__(
    self,
    ...,
    receiver_gain_dB: float = 0.0,  # NEW
    ...
) -> None:
```

- **Validation:** `receiver_gain_dB >= 0`
- **Stored as:** `self.receiver_gain = receiver_gain_dB` (in dB)

**Updated derived properties:**

```python
@property
def total_noise_figure(self) -> float:
    """Total system noise figure in dB (cascade: passive loss + receiver)."""
    l_sys = 10.0 ** (self.system_losses / 10.0)
    f_rx = 10.0 ** (self.noise_figure / 10.0)
    f_total = l_sys * f_rx
    return 10.0 * np.log10(f_total)

@property
def noise_power(self) -> float:
    """Thermal noise power at receiver output in Watts."""
    f_total_linear = 10.0 ** (self.total_noise_figure / 10.0)
    g_rx_linear = 10.0 ** (self.receiver_gain / 10.0)
    return K_BOLTZMANN * self.reference_temp * self.bandwidth * f_total_linear * g_rx_linear
```

**Signal path update** (`pySimSAR/simulation/signal.py`):

`compute_path_loss()` gains a `receiver_gain_dB` parameter:

```python
def compute_path_loss(
    slant_range: float,
    wavelength: float,
    transmit_power: float,
    system_losses_dB: float,
    receiver_gain_dB: float = 0.0,  # NEW
) -> float:
    """Amplitude factor: sqrt(P_t * G_rx * lambda^2 / ((4*pi)^3 * R^4 * L_sys))"""
```

**Call chain update:** `compute_target_echo()` in `signal.py` already receives the `Radar` object and calls `compute_path_loss()`. It must be updated to pass `radar.receiver_gain` as the new parameter. `compute_distributed_target_echoes()` calls `compute_target_echo()` internally, so it inherits the fix. `SimulationEngine._compute_echoes()` in `engine.py` passes `radar.system_losses` to the signal functions — this call site must also pass `radar.receiver_gain`.

### 5.2 Point Target RCS Model

**New file:** `pySimSAR/core/rcs_model.py`

```python
class RCSModel(ABC):
    """Abstract base class for point target RCS fluctuation models."""

    name: str = ""

    @abstractmethod
    def apply(self, rcs: float | np.ndarray, seed: int | None = None) -> float | np.ndarray:
        """Apply statistical fluctuation to the base RCS value.

        Parameters
        ----------
        rcs : float | np.ndarray
            Base RCS value (scalar or 2x2 scattering matrix).
        seed : int | None
            Random seed for reproducibility.

        Returns
        -------
        float | np.ndarray
            Fluctuated RCS value, same type as input.
        """

    @classmethod
    def parameter_schema(cls) -> dict:
        """Declare parameters for JSON serialization."""
        return {}


class StaticRCS(RCSModel):
    """Non-fluctuating RCS model. Returns the base RCS unchanged."""

    name = "static"

    def apply(self, rcs, seed=None):
        return rcs
```

**PointTarget update** (`pySimSAR/core/scene.py`):

```python
class PointTarget:
    def __init__(
        self,
        position: np.ndarray,
        rcs: float | np.ndarray,
        velocity: np.ndarray | None = None,
        rcs_model: RCSModel | None = None,  # NEW — defaults to StaticRCS()
    ) -> None:
```

**Future work (noted, not implemented now):** Swerling case 1-4 models as additional `RCSModel` implementations. These would be registered in a `rcs_model_registry` following the same pattern as other registries.

---

## 6. Binary Data Visualization Tool

**File:** `pySimSAR/tools/view_array.py`

A CLI tool for inspecting binary array files used in parameter sets.

**Usage:**
```bash
python -m pySimSAR.tools.view_array <file_path> [options]
```

**Supported formats:**
- `.npy` — Single array. Displays shape, dtype, min/max/mean, and a plot.
- `.npz` — Multiple arrays. Lists contents; specify `--key` to view one.
- `.csv` — 2D float data.

**Display behavior by array shape:**
- **1D** — Line plot
- **2D real** — Imshow with colorbar (e.g., reflectivity, elevation, antenna pattern)
- **2D complex** — Side-by-side magnitude and phase plots
- **3D+** — Slice selection prompt or `--slice` option
- **(N, 3) positions** — 3D scatter plot (auto-detected when file name contains "positions")

**Options:**
- `--key <name>` — Select array from .npz file
- `--slice <spec>` — Slice specification for 3D+ arrays (e.g., `0,:,:` for first plane)
- `--cmap <name>` — Matplotlib colormap (default: `viridis`)
- `--title <text>` — Custom plot title
- `--save <path>` — Save figure to file instead of displaying
- `--no-show` — Suppress interactive display (useful with `--save`)

**Future work:** GUI integration as a viewer panel within the PyQt6 application.

---

## 7. Golden Reference Test Cases

Three parameter set directories under `tests/golden/`, each containing a complete project directory plus a `README.md` with analytical calculations.

### 7.1 Case 1: `single_point_stripmap`

**Purpose:** Simplest end-to-end validation. One point target, ideal flight, no windowing, stripmap RDA.

**Geometry:**

```
                    Platform (0, y, 2000) ──▶ North (y+)
                    │
                    │  45° depression
                    │ ╲
           2000 m   │   ╲  R₀ = 2828.4 m
                    │    ╲
                    │     ╲
         ───────────┴──────● Target (2000, 0, 0)
                   2000 m East (x+)
```

Platform flies North at altitude 2000 m. Beam looks right (East) at 45° depression.
Target at **(2000, 0, 0)** ENU — 2000 m East on the ground, placing it at beam center.
Slant range at broadside: R₀ = sqrt(2000² + 2000²) = **2828.4 m**.

**Configuration:**

| Component | Parameter | Value |
|-----------|-----------|-------|
| Scene | target position | (2000, 0, 0) ENU meters |
| | target RCS | 1.0 m² |
| | rcs_model | static |
| Radar | carrier_freq | 9.65 GHz → λ = 0.03107 m |
| | PRF | 1000 Hz |
| | transmit_power | 1000 W |
| | receiver_gain | 0 dB |
| | noise_figure | 3.0 dB |
| | system_losses | 2.0 dB |
| | polarization | single |
| | mode | stripmap |
| | look_side | right |
| | depression_angle | 45° |
| | squint_angle | 0° |
| Waveform | type | LFM, 150 MHz BW, 10% duty, no window |
| Antenna | preset | flat, 3° az, 10° el, 30 dB |
| Platform | velocity | 100 m/s North |
| | altitude | 2000 m |
| | start_position | (0, -12.8, 2000) — centers aperture on target azimuth |
| | perturbation | none |
| | sensors | none |
| Simulation | n_pulses | 256, seed 42, sample_rate auto (2× BW = 300 MHz) |
| Processing | image_formation | range_doppler, no MoCo, no autofocus |

**Analytical calculations:**

| Quantity | Formula | Value |
|----------|---------|-------|
| Wavelength | c / f_c | 0.03107 m |
| Slant range (broadside) | sqrt(2000² + 2000²) | 2828.4 m |
| Pulse spacing | v / PRF | 0.1 m |
| Aperture length | n_pulses × pulse_spacing | 25.6 m |
| **Range resolution** | c / (2B) | **1.0 m** |
| Beam footprint (azimuth) | R₀ × θ_az = 2828.4 × 0.05236 | 148.2 m |
| Target illuminated? | 25.6 m < 148.2 m → all 256 pulses | yes |
| **Azimuth resolution** | λR₀ / (2 × L_sa) = 0.03107 × 2828.4 / (2 × 25.6) | **1.72 m** |
| Azimuth bandwidth | v / δ_az | 58.3 Hz (well below PRF) |
| Single-pulse SNR | P_t G² λ² σ / ((4π)³ R⁴ L × kTBF) | ~6 dB |
| Integrated SNR | SNR_1 + 10log₁₀(256) | ~30 dB |
| Echo phase (broadside) | -4πf_c R₀/c | deterministic (verify < 0.01 rad error) |

**Pass criteria:**

1. Echo phase at broadside pulse matches analytical `-4πf_c R₀/c` within **0.01 rad**
2. Range IRW (3 dB width) within **5%** of 1.0 m
3. Azimuth IRW (3 dB width) within **5%** of 1.72 m
4. Target peak at correct range-azimuth bin position

### 7.2 Case 2: `multi_target_spotlight`

**Purpose:** Multiple targets, spotlight mode, windowed resolution, sinc antenna pattern, relative amplitude validation.

**Geometry:**

```
        Platform (0, y, 3000) ──▶ North
              ╲  45° depression
               ╲
                ╲  R ≈ 4243 m
                 ╲
    ──────────────●──────── Ground (z=0)
              3000 m East

    Targets (3000 m cross-track baseline):
      T1: (2950, -30, 0)  RCS=1 m²   (near range, offset azimuth)
      T2: (3000,   0, 0)  RCS=5 m²   (scene center)
      T3: (3060,  40, 0)  RCS=10 m²  (far range, offset azimuth)
```

**Configuration:**

| Component | Parameter | Value |
|-----------|-----------|-------|
| Scene | target T1 | pos=(2950, -30, 0), rcs=1.0 m² |
| | target T2 | pos=(3000, 0, 0), rcs=5.0 m² |
| | target T3 | pos=(3060, 40, 0), rcs=10.0 m² |
| | all rcs_model | static |
| Radar | carrier_freq | 9.65 GHz → λ = 0.03107 m |
| | PRF | 2000 Hz |
| | transmit_power | 1000 W |
| | receiver_gain | 0 dB |
| | noise_figure | 3.0 dB, system_losses 2.0 dB |
| | polarization | single |
| | mode | **spotlight** |
| | look_side | right, depression_angle 45° |
| Waveform | type | LFM, **300 MHz** BW, 10% duty, **Hamming window** |
| Antenna | preset | **sinc**, 5° az, 15° el, 30 dB |
| Platform | velocity | 100 m/s North, **3000 m** altitude |
| | start_position | (0, -6.4, 3000) |
| | perturbation | none |
| Simulation | n_pulses | 512, seed 42, scene_center=(3000, 0, 0) |
| Processing | image_formation | **omega_k**, no MoCo, no autofocus |

**Analytical calculations:**

| Quantity | Formula | Value |
|----------|---------|-------|
| Slant range to T2 (center) | sqrt(3000² + 3000²) | 4243 m |
| **Range resolution (Hamming)** | 1.5 × c/(2B) = 1.5 × 0.5 m | **0.75 m** |
| Integration time | 512 / 2000 | 0.256 s |
| Traverse length | 100 × 0.256 | 25.6 m |
| Angular subtent | L / R = 25.6 / 4243 | 0.00603 rad |
| **Azimuth resolution (spotlight)** | λ / (4 × Δθ) | **1.29 m** |
| T1-T2 range separation | ~50 m >> 0.75 m | well resolved |
| T1-T2 azimuth separation | ~30 m >> 1.29 m | well resolved |
| Expected amplitude ratio T3/T2 | sqrt(10/5) × (R_T2/R_T3)² × G_ratio | ~1.34 (~2.5 dB) |
| Expected amplitude ratio T2/T1 | sqrt(5/1) × (R_T1/R_T2)² × G_ratio | ~2.18 (~6.8 dB) |

Note: Sinc antenna pattern means targets at different azimuth angles from beam center
will have different gains — this must be accounted for in the amplitude comparison.

**Pass criteria:**

1. All 3 targets **resolved** as separate peaks
2. Relative peak amplitudes match expected values within **1 dB** (corrected for range and antenna gain differences)
3. Range IRW within **10%** of 0.75 m (Hamming-windowed)
4. Azimuth IRW within **10%** of 1.29 m

### 7.3 Case 3: `motion_moco_autofocus`

**Purpose:** Validate the full correction chain: simulation with motion errors → MoCo → autofocus → focused image. Tests that the pipeline recovers image quality.

**Geometry:** Same as Case 1 (single target at (2000, 0, 0), 45° depression, stripmap), but with motion perturbation and 512 pulses.

**Configuration:**

| Component | Parameter | Value |
|-----------|-----------|-------|
| Scene | target position | (2000, 0, 0) ENU |
| | target RCS | **10.0 m²** (higher for better SNR margin) |
| | rcs_model | static |
| Radar | same as Case 1 (9.65 GHz, 1000 Hz PRF, 1 kW, single, stripmap, right, 45°) |
| Waveform | LFM, 150 MHz, 10% duty, no window |
| Antenna | preset **gaussian**, 3° az, 10° el, 30 dB |
| Platform | 100 m/s North, 2000 m altitude |
| | start_position | (0, -25.6, 2000) |
| | **perturbation** | **Dryden(σ_u=1.5, σ_v=1.5, σ_w=0.75)** |
| | **sensors** | GPS(1.0 m RMS, 10 Hz, gaussian), IMU(0.003 VRW, 0.0005 ARW, 100 Hz, white_noise) |
| Simulation | **512 pulses**, seed 42 |
| Processing | RDA, **first_order MoCo**, **PGA autofocus** |

**Test methodology:** The test runs the pipeline **three times** with the same scene:

1. **Baseline (ideal)**: Simulate with no perturbation → RDA → measure PMR
2. **Degraded**: Simulate with Dryden perturbation → RDA (no MoCo) → measure PMR
3. **Corrected**: Same perturbed data → first-order MoCo → PGA → RDA → measure PMR

**Analytical expectations:**

| Stage | Quantity | Expected |
|-------|----------|----------|
| No MoCo | Phase error from dR | 4π × dR / λ — can be many radians over aperture |
| | PMR degradation | > 5 dB below ideal case (motion spreads sidelobes) |
| After MoCo | Residual phase error | Bulk correction removes scene-center component |
| | PMR improvement | > 5 dB over no-MoCo case |
| After MoCo + PGA | Residual phase error | Data-driven correction of remaining errors |
| | PMR vs ideal | Within 3 dB of no-perturbation case |

**Pass criteria:**

1. **Degraded PMR** is at least **5 dB worse** than baseline
2. **After MoCo**: PMR improves by at least **5 dB** over degraded
3. **After MoCo + PGA**: PMR within **3 dB** of baseline (ideal)

**Open items for post-implementation review:** Target positions, target separation distances, Dryden turbulence intensity, n_pulses vs resolution trade-offs — to be reviewed and tuned after Phase 8.5 implementation.

### 7.4 Test Runner

**File:** `tests/integration/test_golden.py`

```python
import pytest
from pySimSAR.io.parameter_set import load_parameter_set, build_simulation

GOLDEN_CASES = [
    "tests/golden/single_point_stripmap",
    "tests/golden/multi_target_spotlight",
    "tests/golden/motion_moco_autofocus",
]

@pytest.mark.parametrize("case_dir", GOLDEN_CASES)
class TestGoldenReference:
    def test_load_parameter_set(self, case_dir):
        """Parameter set loads without errors."""
        params = load_parameter_set(case_dir)
        assert params is not None

    def test_build_simulation(self, case_dir):
        """Constructed objects are valid."""
        params = load_parameter_set(case_dir)
        sim = build_simulation(params)
        assert sim['scene'] is not None
        assert sim['radar'] is not None

    def test_simulation_runs(self, case_dir):
        """Simulation produces echo data."""
        ...

    def test_image_formation(self, case_dir):
        """Image formation produces focused image."""
        ...

    def test_analytical_validation(self, case_dir):
        """Results match analytical expectations from README.md."""
        ...
```

Each golden case directory is self-contained: load parameters, build objects, run simulation, form image, validate against analytical ground truth.

---

## 8. File Inventory

### New Files

| File | Purpose |
|------|---------|
| `pySimSAR/io/parameter_set.py` | Core I/O: resolve_refs, load, build, save |
| `pySimSAR/core/rcs_model.py` | RCSModel ABC + StaticRCS |
| `pySimSAR/tools/__init__.py` | Tools package init |
| `pySimSAR/tools/view_array.py` | CLI array visualization tool |
| `pySimSAR/presets/antennas/*.json` | Shipped antenna presets |
| `pySimSAR/presets/waveforms/*.json` | Shipped waveform presets |
| `pySimSAR/presets/sensors/*.json` | Shipped sensor presets |
| `pySimSAR/presets/platforms/*.json` | Shipped platform presets |
| `tests/golden/single_point_stripmap/` | Golden test case 1 |
| `tests/golden/multi_target_spotlight/` | Golden test case 2 |
| `tests/golden/motion_moco_autofocus/` | Golden test case 3 |
| `tests/integration/test_golden.py` | Golden case test runner |
| `tests/unit/test_parameter_set.py` | Parameter set I/O unit tests |
| `tests/unit/test_rcs_model.py` | RCS model unit tests |
| `tests/unit/test_view_array.py` | Visualization tool tests |

### Modified Files

| File | Change |
|------|--------|
| `pySimSAR/core/radar.py` | Add `receiver_gain_dB` parameter, `total_noise_figure` property, update `noise_power` |
| `pySimSAR/core/scene.py` | Add `rcs_model` parameter to `PointTarget` |
| `pySimSAR/simulation/signal.py` | Add `receiver_gain_dB` to `compute_path_loss()` and propagate through `compute_target_echo()` |
| `pySimSAR/simulation/engine.py` | Pass `radar.receiver_gain` through signal computation call chain |
| `pySimSAR/io/config.py` | Extend `ProcessingConfig` to store per-algorithm parameter dicts (see below) |
| `tests/conftest.py` | Add fixtures for parameter set testing |

**ProcessingConfig extension** (`pySimSAR/io/config.py`):

The existing `ProcessingConfig` stores algorithm names as plain strings. It must be extended to carry algorithm-specific parameters:

```python
class ProcessingConfig:
    def __init__(
        self,
        image_formation: str,
        image_formation_params: dict | None = None,  # NEW
        moco: str | None = None,
        moco_params: dict | None = None,             # NEW
        autofocus: str | None = None,
        autofocus_params: dict | None = None,         # NEW
        geocoding: str | None = None,
        geocoding_params: dict | None = None,         # NEW
        polarimetric_decomposition: str | None = None,
        polarimetric_decomposition_params: dict | None = None,  # NEW
        description: str = "",
    ) -> None:
```

Each `*_params` dict defaults to `{}` if not provided. The `to_json()` / `from_json()` methods are updated to serialize/deserialize these dicts alongside the algorithm names.

---

## 9. Future Work (Not in Scope)

- **Swerling RCS models** (cases 1-4) — Interface defined via `RCSModel` ABC, implementation deferred.
- **GUI array viewer** — The CLI `view_array` tool will be integrated into the PyQt6 GUI as a viewer panel in the GUI phase.
- **Von Karman turbulence** — Additional `MotionPerturbation` implementation, uses same interface.
- **Additional clutter models** — K-distribution, log-normal, Weibull — use existing `ClutterModel` ABC.
- **Preset browser/editor GUI** — Browse and edit preset files from the GUI.
