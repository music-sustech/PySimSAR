# API Reference: Simulation

## SimulationEngine

`pySimSAR.simulation.engine.SimulationEngine`

SAR raw signal simulation orchestrator. Generates raw echo data by
simulating the radar pulse loop over a scene of point and distributed
targets.

### Constructor

```python
SimulationEngine(
    scene: Scene,
    radar: Radar,
    n_pulses: int = 256,
    platform_velocity: np.ndarray | None = None,
    platform_start: np.ndarray | None = None,
    seed: int = 42,
    sample_rate: float | None = None,
    scene_center: np.ndarray | None = None,
    n_subswaths: int = 3,
    burst_length: int = 20,
    platform: Platform | None = None,
    swath_range: tuple[float, float] | None = None,
    sar_mode_config: SARModeConfig | None = None,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `scene` | `Scene` | (required) | Target scene definition. |
| `radar` | `Radar` | (required) | Radar system configuration. |
| `n_pulses` | `int` | `256` | Number of azimuth pulses to simulate. Must be > 0. |
| `platform_velocity` | `np.ndarray \| None` | `None` | Platform velocity vector [vx, vy, vz] in m/s. Defaults to `[0, 100, 0]`. Ignored if `platform` is provided. |
| `platform_start` | `np.ndarray \| None` | `None` | Platform starting position [x, y, z] in ENU meters. Defaults to `[0, -5000, 2000]`. Ignored if `platform` is provided. |
| `seed` | `int` | `42` | Random seed for reproducibility. |
| `sample_rate` | `float \| None` | `None` | Range sampling rate in Hz. Defaults to 3x bandwidth. |
| `scene_center` | `np.ndarray \| None` | `None` | Scene center for spotlight mode, shape `(3,)`. |
| `n_subswaths` | `int` | `3` | Number of sub-swaths for scan-SAR mode. |
| `burst_length` | `int` | `20` | Pulses per burst for scan-SAR mode. |
| `platform` | `Platform \| None` | `None` | Platform configuration (overrides `platform_velocity` and `platform_start`). |
| `swath_range` | `tuple[float, float] \| None` | `None` | Range gate as `(near_range_m, far_range_m)`. If None, auto-computed from scene targets with 20% margin. |
| `sar_mode_config` | `SARModeConfig \| None` | `None` | Explicit SAR mode geometry configuration. |

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `run()` | `()` | `SimulationResult` | Execute the simulation and return echo data with metadata. |
| `estimate_memory()` | `()` | `int` | Estimate total memory usage in bytes. Warns if > 1 GB. |
| `format_memory_size()` | `(size_bytes: int)` | `str` | Static method. Format bytes as human-readable string (e.g. `"1.50 GB"`). |

### Simulation behavior

- For each pulse, the engine computes the platform position (from `Platform`
  trajectory or simple velocity model), generates the transmit waveform,
  computes echoes from all point and distributed targets, applies antenna
  gain weighting, adds slow-time phase noise (if configured), and adds
  receiver thermal noise.
- The range gate is determined automatically from scene target positions
  (with 20% margin) unless `swath_range` is explicitly provided.
- The default sample rate is 3x bandwidth for oversampling margin.

---

## SimulationResult

`pySimSAR.simulation.engine.SimulationResult`

Dataclass containing simulation output data.

| Field | Type | Default | Description |
|---|---|---|---|
| `echo` | `dict[str, np.ndarray]` | `{}` | Echo data per channel. Keys: `"single"`, `"hh"`, `"hv"`, `"vh"`, `"vv"`. Values: complex arrays `(n_pulses, n_range_samples)`. |
| `sample_rate` | `float` | `0.0` | Range sampling rate in Hz. |
| `positions` | `np.ndarray` | empty | Platform positions per pulse, shape `(n_pulses, 3)`. |
| `velocities` | `np.ndarray` | empty | Platform velocities per pulse, shape `(n_pulses, 3)`. |
| `pulse_times` | `np.ndarray` | empty | Time of each pulse in seconds. |
| `ideal_trajectory` | `Trajectory \| None` | `None` | Ideal trajectory (if Platform was used). |
| `true_trajectory` | `Trajectory \| None` | `None` | Perturbed trajectory used for echo computation. |
| `navigation_data` | `list \| None` | `None` | Navigation sensor measurements. |
| `gate_delay` | `float` | `0.0` | Range gate start delay in seconds. |

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `save()` | `(filepath: str, *, radar: Radar \| None = None)` | `None` | Save simulation results to HDF5. If `radar` is provided, populates RawData metadata. |

---

## SimulationConfig

`pySimSAR.io.config.SimulationConfig`

Configuration for raw SAR signal generation with state machine lifecycle
tracking.

### Constructor

```python
SimulationConfig(
    scene: Scene,
    radar: Radar,
    n_pulses: int,
    seed: int,
    platform: Platform | None = None,
    description: str = "",
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `scene` | `Scene` | (required) | Target scene. Must not be None. |
| `radar` | `Radar` | (required) | Radar system configuration. Must not be None. |
| `n_pulses` | `int` | (required) | Number of azimuth pulses. Must be > 0. |
| `seed` | `int` | (required) | Random seed. Must be >= 0. |
| `platform` | `Platform \| None` | `None` | Platform configuration. |
| `description` | `str` | `""` | Human-readable description. |

### Properties

| Property | Type | Description |
|---|---|---|
| `scene` | `Scene` | Target scene (read-only). |
| `radar` | `Radar` | Radar configuration (read-only). |
| `platform` | `Platform \| None` | Platform (read-only). |
| `n_pulses` | `int` | Number of pulses (read-only). |
| `seed` | `int` | Random seed (read-only). |
| `description` | `str` | Run description (read-only). |
| `state` | `SimulationState` | Current lifecycle state (read-only). |

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `validate()` | `()` | `None` | Validate parameters, transition `CREATED -> VALIDATED`. |
| `start()` | `()` | `None` | Transition `VALIDATED -> RUNNING`. |
| `complete()` | `()` | `None` | Transition `RUNNING -> COMPLETED`. |
| `fail()` | `()` | `None` | Transition `RUNNING -> FAILED`. |
| `to_json()` | `()` | `str` | Serialize to JSON string. |
| `from_json()` | `(json_str: str)` | `dict` | Class method. Deserialize JSON to parameter dict. |
