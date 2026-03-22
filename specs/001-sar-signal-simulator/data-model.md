# Data Model: SAR Raw Signal Simulator

## PointTarget

A single point reflector in 3D space.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `position` | `np.ndarray` (3,) | finite values | ENU coordinates [x, y, z] in meters |
| `rcs` | `float \| np.ndarray` (2,2) | rcs > 0 (scalar) or complex 2x2 | Radar cross section (scalar for single-pol, 2x2 scattering matrix for quad-pol) |
| `velocity` | `np.ndarray` (3,) \| None | finite if provided | Target velocity [vx, vy, vz] in m/s (optional, for moving targets) |

**Relationships**: Belongs to a `Scene`.

## DistributedTarget

A spatially extended reflector defined on a grid.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `origin` | `np.ndarray` (3,) | finite values | ENU position of grid corner [x, y, z] in meters |
| `extent` | `np.ndarray` (2,) | > 0 | Grid size [dx, dy] in meters |
| `cell_size` | `float` | > 0 | Grid cell spacing in meters |
| `reflectivity` | `np.ndarray` (ny, nx) | >= 0 | Reflectivity magnitude per cell |
| `scattering_matrix` | `np.ndarray` (ny, nx, 2, 2) \| None | complex | Per-cell polarimetric scattering matrix (optional, for quad-pol) |
| `elevation` | `np.ndarray` (ny, nx) \| None | finite | Per-cell elevation offset (optional) |
| `clutter_model` | `ClutterModel \| None` | — | Statistical texture model for generating reflectivity (optional; if provided, overrides `reflectivity` field) |

**Relationships**: Belongs to a `Scene`. May reference a `ClutterModel`.

**Future extensibility**: The `elevation` field supports per-cell height
offsets for terrain. The grid structure is designed so that a future 3D
voxel-based distributed target (for vertical structures) could extend
this class by adding a z-dimension to the grid.

## ClutterModel (ABC)

Plugin interface for statistical clutter/texture generation.

| Field / Property | Type | Validation | Description |
|------------------|------|------------|-------------|
| `name` | `str` (property) | non-empty | Model identifier |

**Methods**:

```python
def generate(self, shape: tuple[int, int], seed: int | None = None) -> np.ndarray:
    """Generate a 2D reflectivity array with statistical texture.

    Args:
        shape: Grid dimensions (ny, nx).
        seed: Random seed for reproducibility.

    Returns:
        Reflectivity array (ny, nx) with values >= 0.
    """
```

**Registration**: Via `ClutterModelRegistry.register(name, cls)`

**Default Implementations**:

| Name | Class | Description |
|------|-------|-------------|
| `uniform` | `UniformClutter` | Constant reflectivity across all cells with configurable mean intensity. Simplest baseline — no statistical texture. |

**Future**: Statistical models (K-distribution, log-normal, Weibull)
can be added as modules for more realistic clutter simulation.

**Relationships**: Referenced by `DistributedTarget`.

## Scene

Collection of all targets in a simulation.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `origin_lat` | `float` | -90 to 90 | WGS84 latitude of ENU origin |
| `origin_lon` | `float` | -180 to 180 | WGS84 longitude of ENU origin |
| `origin_alt` | `float` | finite | WGS84 altitude of ENU origin (meters) |
| `point_targets` | `list[PointTarget]` | — | List of point targets |
| `distributed_targets` | `list[DistributedTarget]` | — | List of distributed targets |

**Relationships**: Contains `PointTarget` and `DistributedTarget` instances. Referenced by `SimulationConfig`.

**Future extensibility**: A `SurfaceModel` field (reflection coefficient,
roughness, material properties) can be added to Scene to enable multipath
simulation via ray tracing. The simulation engine's per-target echo
computation loop is structured to accommodate additional ray path
contributions without architectural changes.

## Radar

SAR sensor configuration.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `carrier_freq` | `float` | > 0 | Carrier frequency in Hz |
| `prf` | `float` | > 0 | Pulse/chirp repetition frequency in Hz (PRI = 1/PRF). Applies to all waveform types: pulse timing for pulsed waveforms, chirp cycle timing for FMCW. |
| `transmit_power` | `float` | > 0 | Peak transmit power in Watts |
| `noise_figure` | `float` | >= 0 | Receiver noise figure in dB (default: 3.0) |
| `system_losses` | `float` | >= 0 | Aggregate system losses in dB (cable, radome, T/R switch, etc.; default: 2.0) |
| `reference_temp` | `float` | > 0 | Reference noise temperature in Kelvin (default: 290.0) |
| `waveform` | `Waveform` | not None | Selected waveform module |
| `antenna` | `AntennaPattern` | not None | Antenna radiation pattern |
| `polarization` | `str` | one of: "single", "dual", "quad" | Polarization mode |
| `mode` | `str` | one of: "stripmap", "spotlight", "scanmar" | SAR imaging mode |
| `look_side` | `str` | one of: "left", "right" | Radar look direction relative to flight track |
| `depression_angle` | `float` | 0 to π/2 | Antenna depression angle from horizontal in radians |
| `squint_angle` | `float` | -π/2 to π/2 | Antenna squint angle in radians (0 for broadside) |

**Derived properties**:
- `bandwidth` — derived from `waveform.bandwidth`
- `pri` — 1.0 / prf (pulse/chirp repetition interval in seconds)
- `wavelength` — c / carrier_freq
- `noise_power` — k·T·B·F (thermal noise power from Boltzmann constant,
  reference temp, bandwidth, and noise figure)

**Validation**: On attachment of waveform, the system warns if
`waveform.duty_cycle / prf` (i.e., active duration) exceeds the PRI.

**Relationships**: Contains a `Waveform` and `AntennaPattern`. Referenced
by `SimulationConfig`. Provides `prf` to `Waveform` for duration
derivation.

## Waveform (ABC)

Unified plugin interface for radar waveform generation and range
compression. Each waveform knows how to generate its transmit signal
and range-compress received echoes using its own processing method.
Waveforms generate baseband signals (centered at 0 Hz); the carrier
frequency is applied by the simulation engine from `Radar.carrier_freq`.

| Field / Property | Type | Validation | Description |
|------------------|------|------------|-------------|
| `name` | `str` (property) | non-empty | Waveform identifier |
| `bandwidth` | `float` | > 0 | Waveform bandwidth in Hz |
| `duty_cycle` | `float` | 0 < x <= 1.0 | Active signal fraction of PRI |
| `phase_noise` | `PhaseNoiseModel \| None` | — | Oscillator phase noise model (optional) |
| `window` | `str` | `"none"`, `"hamming"`, `"hanning"`, `"blackman"`, `"kaiser"`, `"tukey"` | Window function applied during processing |
| `window_params` | `dict \| None` | — | Window-specific parameters (e.g., `{"beta": 6.0}` for Kaiser, `{"alpha": 0.5}` for Tukey) |

**Derived properties**:
- `duration` — `duty_cycle / prf` (computed when waveform is attached
  to a Radar; read-only property)

**Methods**:
- `generate(n_samples, sample_rate) -> np.ndarray` — generate baseband
  transmit waveform and store internally for use in range_compress()
- `range_compress(rx_signal) -> np.ndarray` — range-compress the received
  echo using the waveform's own method (matched filter, dechirp+FFT, etc.)

**Phase noise at baseband**: Phase noise φ_pn(t) represents oscillator
phase fluctuations. At baseband, it multiplies the signal as
exp(j·φ_pn(t)). This is physically equivalent to adding φ_pn(t) at the
carrier frequency, since the phase noise term is independent of whether
the signal is represented at carrier or baseband.

**Implementations**: `LFMWaveform`, `FMCWWaveform`

## LFMWaveform

Linear frequency modulated chirp (pulsed).

| Field | Type | Default | Validation | Description |
|-------|------|---------|------------|-------------|
| `bandwidth` | `float` | — | > 0 | Chirp bandwidth B in Hz |
| `duty_cycle` | `float` | `0.1` | 0 < x < 1.0 | Pulse duty cycle (must be < 1.0 for pulsed waveforms) |
| `window` | `str` | `"none"` | see Waveform | Amplitude tapering window on pulse |
| `window_params` | `dict \| None` | `None` | — | Window-specific parameters |
| `phase_noise` | `PhaseNoiseModel \| None` | `None` | — | Phase noise model |

**Derived properties**:
- `duration` = `duty_cycle / prf` (pulse duration in seconds)
- Chirp slope: K = B / duration (Hz/s)
- Time-bandwidth product: B × duration

**range_compress()**: Frequency-domain matched filtering (conjugate
time-reversed replica of the chirp, multiply in frequency domain, IFFT).

## FMCWWaveform

Frequency modulated continuous wave.

| Field | Type | Default | Validation | Description |
|-------|------|---------|------------|-------------|
| `bandwidth` | `float` | — | > 0 | Chirp sweep bandwidth B in Hz |
| `duty_cycle` | `float` | `1.0` | 0 < x <= 1.0 | Active chirp fraction of PRI (1.0 = fully continuous, < 1.0 = pulsed/duty-cycled FMCW) |
| `ramp_type` | `str` | `"up"` | `"up"`, `"down"`, `"triangle"` | Frequency ramp direction |
| `window` | `str` | `"none"` | see Waveform | Window applied to beat signal before FFT |
| `window_params` | `dict \| None` | `None` | — | Window-specific parameters |
| `phase_noise` | `PhaseNoiseModel \| None` | `None` | — | Phase noise model |

**Derived properties**:
- `duration` = `duty_cycle / prf` (active ramp duration in seconds)
- Chirp slope: K = B / duration (Hz/s)

**Ramp types**:
- `"up"`: Linear sweep from f_c to f_c + B
- `"down"`: Linear sweep from f_c + B to f_c
- `"triangle"`: Up-ramp then down-ramp, each duration/2, full B sweep

**range_compress()**: Dechirp (mix rx with stored tx reference:
s_rx · s_tx*), apply window, FFT. For triangle ramp, up and down
ramps are processed separately.

**Relationships**: Inherits from `Waveform`. May reference `PhaseNoiseModel`.

## PhaseNoiseModel (ABC)

Pluggable oscillator phase noise model, applicable to any waveform.

| Field / Property | Type | Validation | Description |
|------------------|------|------------|-------------|
| `name` | `str` (property) | non-empty | Model identifier |

**Methods**: `generate(n_samples, sample_rate, seed=None) -> np.ndarray`
(returns phase noise vector φ_pn(t) in radians)

## CompositePSDPhaseNoise

Default multi-slope PSD phase noise model.

| Field | Type | Default | Validation | Description |
|-------|------|---------|------------|-------------|
| `flicker_fm_level` | `float` | `-80.0` | — | 1/f³ component in dBc/Hz at 1 kHz offset |
| `white_fm_level` | `float` | `-100.0` | — | 1/f² component in dBc/Hz |
| `flicker_pm_level` | `float` | `-120.0` | — | 1/f component in dBc/Hz |
| `white_floor` | `float` | `-150.0` | — | White noise floor in dBc/Hz |

**Relationships**: Implements `PhaseNoiseModel`. Referenced by any
`Waveform` via the `phase_noise` field.

**Range correlation effect**: When phase noise is present, the
simulation engine computes Δφ_pn(t) = φ_pn(t) - φ_pn(t - τ) per
target, where τ is the round-trip delay. Close targets see near-total
phase noise cancellation; far targets see uncorrelated noise raising the
noise floor.

## AntennaPattern

Antenna radiation pattern model.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `pattern_2d` | `np.ndarray` (n_el, n_az) \| Callable` | — | 2D gain pattern (dB) or callable(az, el) -> gain_dB |
| `az_beamwidth` | `float` | > 0 | 3 dB azimuth beamwidth in radians |
| `el_beamwidth` | `float` | > 0 | 3 dB elevation beamwidth in radians |
| `az_angles` | `np.ndarray` (n_az,) | — | Azimuth angle samples (if pattern_2d is array) |
| `el_angles` | `np.ndarray` (n_el,) | — | Elevation angle samples (if pattern_2d is array) |
| `peak_gain_dB` | `float` | — | **Read-only.** Peak antenna gain in dB, derived from beamwidths |

**Relationships**: Belongs to `Radar`.

## Platform

Aircraft/UAV platform configuration.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `velocity` | `float` | > 0 | Nominal platform speed in m/s |
| `altitude` | `float` | > 0 | Nominal flight altitude in meters (ENU z) |
| `heading` | `float` | 0 to 2π | Nominal heading in radians (0 = North) |
| `start_position` | `np.ndarray` (3,) | finite | Starting position in ENU meters |
| `perturbation` | `MotionPerturbation \| None` | — | Motion perturbation model (optional) |
| `sensors` | `list[NavigationSensor]` | — | Attached GPS/IMU sensors |

**Relationships**: May contain `MotionPerturbation`. Contains zero or more `NavigationSensor` instances. Referenced by `SimulationConfig`.

## MotionPerturbation

Platform motion error model.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `model` | `str` | one of: "dryden", "von_karman" | Turbulence spectral model |
| `sigma_u` | `float` | >= 0 | Longitudinal turbulence intensity (m/s) |
| `sigma_v` | `float` | >= 0 | Lateral turbulence intensity (m/s) |
| `sigma_w` | `float` | >= 0 | Vertical turbulence intensity (m/s) |
| `vibration_freqs` | `np.ndarray` \| None | > 0 | Vibration frequencies in Hz |
| `vibration_amps` | `np.ndarray` \| None | >= 0 | Vibration amplitudes in meters |
| `drift_rates` | `np.ndarray` (3,) \| None | finite | Linear drift rates [dx, dy, dz] in m/s |

**Relationships**: Belongs to `Platform`.

## GPSErrorModel (ABC)

Plugin interface for GPS position error generation.

| Field / Property | Type | Validation | Description |
|------------------|------|------------|-------------|
| `name` | `str` (property) | non-empty | Model identifier |

**Methods**: `generate(true_positions, time, seed=None) -> np.ndarray`
— takes true position array (N, 3) and timestamps, returns noisy
position measurements (N, 3).

**Default Implementations**:

| Name | Class | Description |
|------|-------|-------------|
| `gaussian` | `GaussianGPSError` | Simple additive white Gaussian noise with configurable RMS. No temporal correlation. Suitable as a first-stage baseline. |

**Future**: More advanced models (RTK with ambiguity resolution,
Gauss-Markov correlated errors, multipath, etc.) can be added as
modules without changing the interface.

## GPSSensor

GPS navigation sensor configuration.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `accuracy_rms` | `float` | > 0 | Position accuracy RMS in meters |
| `update_rate` | `float` | > 0 | Output rate in Hz |
| `outage_intervals` | `list[tuple[float, float]]` | start < end | Time intervals with no GPS output |
| `error_model` | `GPSErrorModel` | not None | Error generation model (default: GaussianGPSError) |

**Relationships**: Attached to `Platform`. Contains a `GPSErrorModel`.

## IMUErrorModel (ABC)

Plugin interface for IMU error generation.

| Field / Property | Type | Validation | Description |
|------------------|------|------------|-------------|
| `name` | `str` (property) | non-empty | Model identifier |

**Methods**: `generate(true_accel, true_gyro, time, seed=None) -> tuple[np.ndarray, np.ndarray]`
— takes true acceleration (N, 3) and angular rate (N, 3) arrays with
timestamps, returns noisy measurements (accel, gyro).

**Default Implementations**:

| Name | Class | Description |
|------|-------|-------------|
| `white_noise` | `WhiteNoiseIMUError` | Additive white Gaussian noise on accelerometer and gyroscope outputs with configurable noise density. No bias drift or scale factor error. Simplest baseline. |

**Future**: IEEE-STD-952 five-term model (bias instability via
Gauss-Markov, random walk, scale factor, quantization) can be added
as a module.

## IMUSensor

Inertial measurement unit configuration.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `accel_noise_density` | `float` | >= 0 | Accelerometer noise density, VRW (m/s²/√Hz) |
| `gyro_noise_density` | `float` | >= 0 | Gyroscope noise density, ARW (rad/s/√Hz) |
| `sample_rate` | `float` | > 0 | IMU output rate in Hz |
| `error_model` | `IMUErrorModel` | not None | Error generation model (default: WhiteNoiseIMUError) |

**Relationships**: Attached to `Platform`. Contains an `IMUErrorModel`.

**Note**: The default `WhiteNoiseIMUError` uses only `accel_noise_density`
and `gyro_noise_density`. Future advanced models may add fields like
`bias_stability`, `scale_factor`, etc. to `IMUSensor` as needed.

## Trajectory

Time-stamped platform state history.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `time` | `np.ndarray` (N,) | monotonically increasing | Time stamps in seconds |
| `position` | `np.ndarray` (N, 3) | finite | ENU positions in meters |
| `velocity` | `np.ndarray` (N, 3) | finite | ENU velocities in m/s |
| `attitude` | `np.ndarray` (N, 3) | finite | Euler angles [roll, pitch, yaw] in radians |

**Relationships**: Generated by `Platform` + `MotionPerturbation`. Referenced by `RawData` and processing algorithms.

**Note**: Two trajectory instances exist per simulation — the "true"
(actual perturbed) trajectory and the "ideal" (nominal) trajectory.

## NavigationData

Sensor-measured navigation state (with errors).

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `time` | `np.ndarray` (M,) | monotonically increasing | Measurement timestamps in seconds |
| `position` | `np.ndarray` (M, 3) \| None | finite | Measured positions (GPS) or None |
| `velocity` | `np.ndarray` (M, 3) \| None | finite | Measured velocities or None |
| `acceleration` | `np.ndarray` (M, 3) \| None | finite | Measured accelerations (IMU) or None |
| `angular_rate` | `np.ndarray` (M, 3) \| None | finite | Measured angular rates (IMU) or None |
| `source` | `str` | one of: "gps", "imu", "fused" | Sensor source |

**Relationships**: Produced by `GPSSensor` or `IMUSensor` from the true `Trajectory`.

## RawData

Simulated SAR echo data.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `echo` | `np.ndarray` (n_range, n_azimuth) | complex | Echo data matrix (fast-time × slow-time) |
| `channel` | `str` | one of: "single", "hh", "hv", "vh", "vv" | Polarization channel |
| `sample_rate` | `float` | > 0 | Range sampling rate in Hz |
| `radar` | `Radar` | not None | Radar configuration reference |
| `trajectory` | `Trajectory` | not None | Platform trajectory during acquisition |

**Relationships**: References `Radar` and `Trajectory`. For quad-pol,
four `RawData` instances (one per channel) are generated. Consumed by
`MotionCompensationAlgorithm` and `ImageFormationAlgorithm`.

## PhaseHistoryData

Range-compressed phase history — the intermediate representation between
range compression and azimuth compression. This is the primary domain
for autofocus algorithms.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `data` | `np.ndarray` (n_range_bins, n_azimuth) | complex | Range-compressed phase history matrix |
| `channel` | `str` | one of: "single", "hh", "hv", "vh", "vv" | Polarization channel |
| `range_bin_spacing` | `float` | > 0 | Range bin spacing in meters |
| `azimuth_time` | `np.ndarray` (n_azimuth,) | monotonically increasing | Slow-time stamps per pulse |
| `radar` | `Radar` | not None | Radar configuration reference |
| `trajectory` | `Trajectory` | not None | Platform trajectory |

**Relationships**: Produced by `ImageFormationAlgorithm.range_compress()`.
Consumed by `AutofocusAlgorithm` and
`ImageFormationAlgorithm.azimuth_compress()`.

## SARImage

Focused SAR image product.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `data` | `np.ndarray` (ny, nx) | complex or float | Image pixel data |
| `pixel_spacing` | `tuple[float, float]` | > 0 | (range, azimuth) pixel spacing in meters |
| `geometry` | `str` | one of: "slant_range", "ground_range", "geographic" | Coordinate geometry |
| `polarization` | `str` | channel label | Polarization channel |
| `algorithm` | `str` | non-empty | Name of the algorithm that produced this image |
| `geo_transform` | `np.ndarray` (6,) \| None | — | Affine transform for georeferenced images |
| `projection_wkt` | `str \| None` | — | WKT projection string |

**Relationships**: Produced by `ImageFormationAlgorithm.azimuth_compress()`
or `AutofocusAlgorithm.focus()`. Input to `ImageTransformationAlgorithm`
and `PolarimetricDecomposition`.

## AutofocusAlgorithm (ABC)

Plugin interface for autofocus algorithms that estimate and correct
residual phase errors in the phase history domain.

| Field / Property | Type | Validation | Description |
|------------------|------|------------|-------------|
| `name` | `str` (property) | non-empty | Algorithm identifier |
| `max_iterations` | `int` | > 0 | Maximum iterations for convergence (default: 10) |
| `convergence_threshold` | `float` | > 0 | Phase error convergence threshold in radians (default: 0.01) |

**Methods**:
- `focus(phase_history: PhaseHistoryData, azimuth_compressor: Callable[[PhaseHistoryData], SARImage]) -> SARImage`
  — Iteratively estimates phase errors from the phase history, applies
  corrections, and calls `azimuth_compressor` to re-form the image
  until convergence.
- `estimate_phase_error(phase_history: PhaseHistoryData) -> np.ndarray`
  — Estimates the residual phase error vector (n_azimuth,) from the
  current phase history. Can be called standalone for diagnostics.

**Default Implementations**:

| Name | Class | Description |
|------|-------|-------------|
| `pga` | `PhaseGradientAutofocus` | Selects dominant scatterers per range bin, estimates phase gradient across azimuth, integrates to get phase error. Iterative. |
| `mda` | `MapDriftAutofocus` | Splits synthetic aperture into sub-apertures, forms sub-images, measures relative drift/misregistration to derive phase errors. |
| `min_entropy` | `MinimumEntropyAutofocus` | Optimizes image sharpness by iteratively adjusting phase coefficients (polynomial or arbitrary) to minimize image entropy. |
| `ppp` | `ProminentPointProcessing` | Identifies isolated strong scatterers in range-compressed data, extracts their phase histories, and estimates motion errors from phase deviations across azimuth. |

**Relationships**: Consumes `PhaseHistoryData`. Uses
`ImageFormationAlgorithm.azimuth_compress()` as a callback to re-form
images during iteration. Produces `SARImage`. Registered via
`AlgorithmRegistry`.

## SimulationConfig

Configuration for raw signal generation. Controls what data is produced.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `scene` | `Scene` | not None | Target scene |
| `radar` | `Radar` | not None | Radar configuration (includes waveform, antenna, PRF) |
| `platform` | `Platform` | not None | Platform configuration (includes motion perturbation, sensors) |
| `n_pulses` | `int` | > 0 | Number of azimuth pulses to simulate |
| `seed` | `int` | >= 0 | Random number generator seed |
| `description` | `str` | — | Optional run description |

**Relationships**: Aggregates `Scene`, `Radar`, `Platform`. Serializable
to/from JSON and HDF5 for reproducibility (FR-014, Principle V).

**State Transitions**:
- `created` → `validated` (after parameter validation)
- `validated` → `running` (simulation in progress)
- `running` → `completed` (all outputs generated)
- `running` → `failed` (error during simulation)

## ProcessingConfig

Configuration for the processing pipeline. Controls how raw data is
processed into images. Decoupled from SimulationConfig so that the same
raw data can be re-processed with different algorithm selections without
re-running the simulation.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `moco` | `MotionCompensationAlgorithm \| None` | — | Motion compensation algorithm (None = skip MoCo) |
| `image_formation` | `ImageFormationAlgorithm` | not None | Image formation algorithm (provides range_compress + azimuth_compress) |
| `autofocus` | `AutofocusAlgorithm \| None` | — | Autofocus algorithm (None = skip autofocus, go straight to azimuth_compress) |
| `geocoding` | `ImageTransformationAlgorithm \| None` | — | Image transformation algorithm (None = keep slant-range geometry) |
| `polarimetric_decomposition` | `PolarimetricDecomposition \| None` | — | Polarimetric decomposition (None = skip; requires quad-pol data) |

**Relationships**: References algorithm module instances. Serializable
to/from JSON for reproducibility (algorithm names + parameters).

**Pipeline execution order**:
1. MoCo (if configured)
2. Range compression (always — via image_formation.range_compress())
3. Autofocus (if configured — via autofocus.focus())
4. Azimuth compression (always — via image_formation.azimuth_compress())
5. Geocoding (if configured)
6. Polarimetric decomposition (if configured and quad-pol data)

## Entity Relationship Summary

```text
SimulationConfig (signal generation)
├── Scene
│   ├── PointTarget (0..N)
│   │   └── ClutterModel (0..1, on DistributedTarget)
│   └── DistributedTarget (0..N)
├── Radar
│   ├── Waveform (LFM or FMCW)
│   │   └── PhaseNoiseModel (0..1)
│   └── AntennaPattern
└── Platform
    ├── MotionPerturbation (0..1)
    ├── GPSSensor (0..N)
    └── IMUSensor (0..N)

ProcessingConfig (pipeline algorithms)
├── MotionCompensationAlgorithm (0..1)
├── ImageFormationAlgorithm (1)
├── AutofocusAlgorithm (0..1)
├── ImageTransformationAlgorithm (0..1)
└── PolarimetricDecomposition (0..1)

Simulation produces:
├── Trajectory (ideal + true)
├── NavigationData (per sensor)
└── RawData (per polarization channel)

Processing pipeline:
RawData → [MoCo] → RawData(compensated)
  → range_compress() → PhaseHistoryData
    → [autofocus.focus()] → azimuth_compress() → SARImage
      → [geocoding] → SARImage(georeferenced)
      → [polsar decomposition] → components
```
