# Contract: Waveform Interface

## ABC: `Waveform`

Unified base class for all radar waveform implementations. Each waveform
generates baseband transmit signals (centered at 0 Hz) and range-compresses
received echoes using its own processing method. The carrier frequency is
applied by the simulation engine from `Radar.carrier_freq`.

The active signal duration is derived from `duty_cycle / Radar.prf`, not
specified directly. This ensures consistent timing between the waveform and
radar, and avoids invalid configurations where pulse duration exceeds PRI.

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Human-readable waveform name |
| `bandwidth` | `float` | Waveform bandwidth in Hz |
| `duty_cycle` | `float` | Active signal fraction of PRI (0 < x <= 1.0) |
| `duration` | `float` | *Derived*: duty_cycle / prf (read-only, set when attached to Radar) |

### Optional Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `phase_noise` | `PhaseNoiseModel \| None` | `None` | Oscillator phase noise model |
| `window` | `str` | `"none"` | Window function: `"none"`, `"hamming"`, `"hanning"`, `"blackman"`, `"kaiser"`, `"tukey"` |
| `window_params` | `dict \| None` | `None` | Window-specific parameters (e.g., `{"beta": 6.0}` for Kaiser, `{"alpha": 0.5}` for Tukey) |

### Required Methods

```python
def generate(self, n_samples: int, sample_rate: float) -> np.ndarray:
    """Generate the baseband transmit waveform for one pulse/chirp.

    Stores the generated signal internally for use in range_compress().
    If phase_noise is set, generates and applies φ_pn(t).

    Args:
        n_samples: Number of samples in the active portion.
        sample_rate: Sampling rate in Hz.

    Returns:
        Complex baseband transmit waveform (n_samples,).
    """

def range_compress(self, rx_signal: np.ndarray) -> np.ndarray:
    """Range-compress the received echo signal.

    Each waveform implements its own processing:
      - LFM: frequency-domain matched filtering
      - FMCW: dechirp (mix with stored tx reference) + FFT
      - Future types: correlation, demodulation, etc.

    Must be called after generate().

    Args:
        rx_signal: Received echo signal (n_samples,), complex.

    Returns:
        Range-compressed signal (n_samples,), complex.
    """
```

### Timing Model

```
|<------------ PRI = 1/PRF ------------>|
|<-- duration = DC × PRI -->|           |
|===== active signal =======|== idle ===>|
```

- `Radar.prf` owns the repetition timing (applies to all waveform types)
- `Waveform.duty_cycle` determines what fraction of PRI is active
- `Waveform.duration` = `duty_cycle / prf` (derived, read-only)
- For pulsed waveforms: `duty_cycle` MUST be < 1.0
- For FMCW: `duty_cycle` may be 1.0 (fully continuous) or < 1.0

### Registration

```python
from pySimSAR.waveforms.registry import WaveformRegistry

WaveformRegistry.register("my_waveform", MyWaveformClass)

waveform_cls = WaveformRegistry.get("lfm")
waveform = waveform_cls(bandwidth=150e6, duty_cycle=0.1)
```

---

## Default: `LFMWaveform` (Pulsed Linear FM Chirp)

| Parameter | Type | Default | Validation | Description |
|-----------|------|---------|------------|-------------|
| `bandwidth` | `float` | — | > 0 | Chirp bandwidth B in Hz |
| `duty_cycle` | `float` | `0.1` | 0 < x < 1.0 | Pulse duty cycle |
| `window` | `str` | `"none"` | see Waveform | Amplitude tapering window on pulse |
| `window_params` | `dict \| None` | `None` | — | Window-specific params |
| `phase_noise` | `PhaseNoiseModel \| None` | `None` | — | Phase noise model |

**Derived**: duration = duty_cycle / prf, chirp slope K = B / duration,
time-bandwidth product = B × duration.

**range_compress()**: Frequency-domain matched filtering (conjugate
time-reversed replica).

### Example

```python
from pySimSAR.waveforms import LFMWaveform

wfm = LFMWaveform(bandwidth=150e6, duty_cycle=0.1, window="hamming")

# After attaching to Radar with prf=1000:
# duration = 0.1 / 1000 = 100 μs
# K = 150e6 / 100e-6 = 1.5e12 Hz/s

tx = wfm.generate(n_samples=2000, sample_rate=200e6)
compressed = wfm.range_compress(rx_echo)
```

---

## Default: `FMCWWaveform` (Frequency Modulated Continuous Wave)

| Parameter | Type | Default | Validation | Description |
|-----------|------|---------|------------|-------------|
| `bandwidth` | `float` | — | > 0 | Chirp sweep bandwidth B in Hz |
| `duty_cycle` | `float` | `1.0` | 0 < x <= 1.0 | Active chirp fraction of PRI |
| `ramp_type` | `str` | `"up"` | `"up"`, `"down"`, `"triangle"` | Frequency ramp direction |
| `window` | `str` | `"none"` | see Waveform | Window on beat signal before FFT |
| `window_params` | `dict \| None` | `None` | — | Window-specific params |
| `phase_noise` | `PhaseNoiseModel \| None` | `None` | — | Phase noise model |

**Derived**: duration = duty_cycle / prf (active ramp time),
K = B / duration.

**Ramp types**:
- `"up"`: Linear sweep from f_c to f_c + B
- `"down"`: Linear sweep from f_c + B to f_c
- `"triangle"`: Up then down ramp, each duration/2, full B sweep

**Duty cycle**:
- `1.0`: Fully continuous FMCW — chirp fills entire PRI
- `< 1.0`: Pulsed/duty-cycled FMCW — chirp occupies only a fraction,
  remainder is idle

**range_compress()**: Dechirp (s_rx · s_tx*) + window + FFT. For
triangle ramp, up and down halves are processed separately.

**Phase noise handling**: `generate()` produces φ_pn(t) via the
attached model and stores it. The simulation engine applies φ_pn(t)
to the tx signal and interpolates φ_pn(t - τ) per target for the
rx signal. `range_compress()` uses the same noisy tx reference for
dechirp, naturally producing the range correlation effect.

### Example

```python
from pySimSAR.waveforms import FMCWWaveform
from pySimSAR.waveforms.phase_noise import CompositePSDPhaseNoise

pn = CompositePSDPhaseNoise(
    flicker_fm_level=-80,
    white_fm_level=-100,
    flicker_pm_level=-120,
    white_floor=-150,
)

wfm = FMCWWaveform(
    bandwidth=1e9,
    duty_cycle=0.8,
    ramp_type="triangle",
    window="hanning",
    phase_noise=pn,
)

# After attaching to Radar with prf=20000 (PRI = 50 μs):
# duration = 0.8 / 20000 = 40 μs active ramp
# idle time = 10 μs per PRI

tx = wfm.generate(n_samples=2000, sample_rate=50e6)
compressed = wfm.range_compress(rx_echo)
```

---

## `PhaseNoiseModel` (ABC)

Pluggable oscillator phase noise model, applicable to any waveform.

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Model identifier |

### Required Methods

```python
def generate(
    self,
    n_samples: int,
    sample_rate: float,
    seed: int | None = None,
) -> np.ndarray:
    """Generate a time-domain phase noise vector.

    Args:
        n_samples: Number of time samples.
        sample_rate: Sampling rate in Hz.
        seed: Random seed for reproducibility.

    Returns:
        Phase noise vector φ_pn(t) in radians (n_samples,).
    """
```

### Default: `CompositePSDPhaseNoise`

| Parameter | Type | Default | Validation | Description |
|-----------|------|---------|------------|-------------|
| `flicker_fm_level` | `float` | `-80.0` | — | 1/f³ component in dBc/Hz at 1 kHz offset |
| `white_fm_level` | `float` | `-100.0` | — | 1/f² component in dBc/Hz |
| `flicker_pm_level` | `float` | `-120.0` | — | 1/f component in dBc/Hz |
| `white_floor` | `float` | `-150.0` | — | White noise floor in dBc/Hz |

Composite PSD: L(f) = h₋₃/f³ + h₋₂/f² + h₋₁/f + h₀. Each h
coefficient derived from the dBc/Hz level. Generation: shape white
noise with PSD filter in frequency domain, IFFT to time domain.

### Registration

```python
from pySimSAR.waveforms.registry import PhaseNoiseRegistry
PhaseNoiseRegistry.register("my_noise", MyPhaseNoiseModel)
```

---

## Range Correlation Effect

When phase noise is enabled on any waveform:

1. `waveform.generate()` produces φ_pn(t) and stores it internally
2. Simulation engine adds φ_pn(t) to the transmit signal phase
3. For each target at round-trip delay τ, φ_pn(t - τ) is interpolated
4. After range compression: Δφ_pn = φ_pn(t) - φ_pn(t - τ) emerges

Close targets (small τ) → phase noise cancels → clean signal.
Far targets (large τ) → noise decorrelates → elevated noise floor.

## Target Velocity Effects

The simulation engine accounts for target motion:

1. **Time-varying delay**: τ(t) = 2(R₀ + v·t) / c
2. **Doppler shift**: f_d = 2v/λ
3. **Range-Doppler coupling**: 2Kv/c (significant for fast targets
   or long chirps)
4. **Within-pulse motion**: For FMCW, continuously varying τ(t) is
   used directly (no start-stop approximation within a chirp)
