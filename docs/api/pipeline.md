# API Reference: Pipeline and Waveforms

## PipelineRunner

`pySimSAR.pipeline.runner.PipelineRunner`

Sequential SAR processing pipeline driven by `ProcessingConfig`. Chains
processing steps in order: MoCo, image formation (range compression,
optional autofocus, azimuth compression), geocoding, and polarimetric
decomposition.

### Constructor

```python
PipelineRunner(
    config: ProcessingConfig,
    stage_callback: Callable[[str], object] | None = None,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `config` | `ProcessingConfig` | (required) | Algorithm selection and parameters for each step. |
| `stage_callback` | `Callable[[str], object] \| None` | `None` | Optional callback invoked with a status message at the start of each processing stage. |

### Properties

| Property | Type | Description |
|---|---|---|
| `config` | `ProcessingConfig` | The processing configuration. |

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `run()` | `(raw_data, radar, trajectory, nav_data=None, ideal_trajectory=None)` | `PipelineResult` | Execute the full pipeline. |
| `validate_config()` | `(raw_data: dict[str, RawData])` | `None` | Check that the image formation algorithm supports the SAR mode. Raises `ValueError` on mismatch. |

### run() parameters

| Parameter | Type | Description |
|---|---|---|
| `raw_data` | `dict[str, RawData]` | Raw echo data keyed by polarization channel. |
| `radar` | `Radar` | Radar configuration. |
| `trajectory` | `Trajectory` | Platform trajectory (true/perturbed). |
| `nav_data` | `NavigationData \| list \| None` | Navigation sensor data for MoCo. |
| `ideal_trajectory` | `Trajectory \| None` | Reference trajectory for MoCo. |

### Pipeline stages

1. **Motion Compensation** (optional, if `config.moco` is set): applies
   phase corrections from GPS navigation data.
2. **Image Formation** (required): either a single `process()` call, or
   a split range-compress / autofocus / azimuth-compress sequence when
   `config.autofocus` is set.
3. **Range padding crop**: removes waveform-duration padding from the range
   dimension after compression.
4. **Geocoding** (optional, if `config.geocoding` is set): transforms from
   slant-range to ground-range or geographic coordinates.
5. **Polarimetric Decomposition** (optional, if
   `config.polarimetric_decomposition` is set): requires quad-pol data
   (channels `hh`, `hv`, `vh`, `vv`).

---

## PipelineResult

`pySimSAR.pipeline.runner.PipelineResult`

Dataclass containing processing pipeline output.

| Field | Type | Default | Description |
|---|---|---|---|
| `images` | `dict[str, SARImage]` | `{}` | Focused images keyed by channel name. |
| `phase_history` | `dict[str, PhaseHistoryData]` | `{}` | Range-compressed phase history per channel (intermediate, populated when autofocus is used). |
| `raw_data_ref` | `dict[str, RawData] \| None` | `None` | Reference to input raw data. |
| `decomposition` | `dict[str, np.ndarray] \| None` | `None` | Polarimetric decomposition results (keyed by component name). |
| `steps_applied` | `list[str]` | `[]` | Processing steps applied, in order (e.g. `["moco:first_order", "image_formation:range_doppler"]`). |

---

## Waveform (base class)

`pySimSAR.waveforms.base.Waveform`

Abstract base class for radar waveform implementations. See the
[Custom Waveforms](../customization/waveforms.md) guide for full details.

### Constructor

```python
Waveform(
    bandwidth: float,
    duty_cycle: float,
    phase_noise: PhaseNoiseModel | None = None,
    window: Callable[[int], np.ndarray] | None = None,
    prf: float | None = None,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `bandwidth` | `float` | (required) | Waveform bandwidth in Hz. Must be > 0. |
| `duty_cycle` | `float` | (required) | Fraction of PRI occupied by the waveform, in (0, 1]. |
| `phase_noise` | `PhaseNoiseModel \| None` | `None` | Phase noise model. |
| `window` | `Callable[[int], np.ndarray] \| None` | `None` | Window function `f(n) -> ndarray`. |
| `prf` | `float \| None` | `None` | Optional PRF in Hz. |

### Properties

`bandwidth`, `duty_cycle`, `phase_noise`, `window`, `prf` (all read-only).

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `duration()` | `(prf: float \| None = None)` | `float` | Waveform duration in seconds (`duty_cycle / prf`). |
| `generate()` | `(prf: float, sample_rate: float)` | `np.ndarray` | **Abstract.** Generate transmit waveform samples. |
| `range_compress()` | `(echo: np.ndarray, prf: float, sample_rate: float)` | `np.ndarray` | **Abstract.** Range-compress echo data. |

---

## LFMWaveform

`pySimSAR.waveforms.lfm.LFMWaveform`

Pulsed linear frequency modulated (chirp) waveform. Generates a baseband
LFM chirp `s(t) = exp(j*pi*K*t^2)` where `K = bandwidth/duration`. Range
compression uses frequency-domain matched filtering.

**Registered name:** `"lfm"`

### Constructor

```python
LFMWaveform(
    bandwidth: float,
    duty_cycle: float = 0.1,
    phase_noise: PhaseNoiseModel | None = None,
    window: Callable[[int], np.ndarray] | None = None,
    prf: float | None = None,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `bandwidth` | `float` | (required) | Waveform bandwidth in Hz. |
| `duty_cycle` | `float` | `0.1` | Duty cycle. Must be < 1.0 for pulsed operation. |
| `phase_noise` | `PhaseNoiseModel \| None` | `None` | Phase noise model. |
| `window` | `Callable \| None` | `None` | Window function for sidelobe control. |
| `prf` | `float \| None` | `None` | Pulse repetition frequency in Hz. |

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `generate()` | `(prf: float, sample_rate: float)` | `np.ndarray` | Generate baseband LFM chirp samples, shape `(n_samples,)`. |
| `range_compress()` | `(echo: np.ndarray, prf: float, sample_rate: float)` | `np.ndarray` | Frequency-domain matched filter compression. Handles 1-D and 2-D input. |

---

## FMCWWaveform

`pySimSAR.waveforms.fmcw.FMCWWaveform`

FMCW radar waveform with configurable frequency ramp type. Range
compression uses frequency-domain matched filtering.

**Registered name:** `"fmcw"`

### Constructor

```python
FMCWWaveform(
    bandwidth: float,
    duty_cycle: float = 1.0,
    ramp_type: RampType | str = "up",
    phase_noise: PhaseNoiseModel | None = None,
    window: Callable[[int], np.ndarray] | None = None,
    prf: float | None = None,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `bandwidth` | `float` | (required) | Waveform bandwidth in Hz. |
| `duty_cycle` | `float` | `1.0` | Duty cycle (1.0 for continuous wave). |
| `ramp_type` | `RampType \| str` | `"up"` | Frequency ramp shape: `"up"`, `"down"`, or `"triangle"`. |
| `phase_noise` | `PhaseNoiseModel \| None` | `None` | Phase noise model. |
| `window` | `Callable \| None` | `None` | Window function. |
| `prf` | `float \| None` | `None` | Pulse repetition frequency in Hz. |

### Properties

| Property | Type | Description |
|---|---|---|
| `ramp_type` | `RampType` | Frequency ramp type enum. |

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `generate()` | `(prf: float, sample_rate: float)` | `np.ndarray` | Generate FMCW waveform samples, shape `(n_samples,)`. |
| `range_compress()` | `(echo: np.ndarray, prf: float, sample_rate: float)` | `np.ndarray` | Frequency-domain matched filter compression. |
