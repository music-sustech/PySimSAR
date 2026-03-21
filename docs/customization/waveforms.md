# Custom Waveforms

PySimSAR supports plug-in waveform types through the same registry pattern
used for algorithms. This guide shows how to create and register a custom
waveform implementation.

## Waveform base class contract

All waveforms subclass `pySimSAR.waveforms.base.Waveform`. The base class
provides common properties and requires two abstract methods.

### Constructor parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `bandwidth` | `float` | (required) | Waveform bandwidth in Hz. Must be > 0. |
| `duty_cycle` | `float` | (required) | Fraction of PRI occupied by the waveform, in (0, 1]. |
| `phase_noise` | `PhaseNoiseModel \| None` | `None` | Optional phase noise model applied to the generated signal. |
| `window` | `Callable[[int], np.ndarray] \| None` | `None` | Optional window function for range compression sidelobe control. Signature: `window(n) -> ndarray`. |
| `prf` | `float \| None` | `None` | Pulse repetition frequency in Hz. When set, `duration()` can be called without arguments. |

### Properties

| Property | Type | Description |
|---|---|---|
| `bandwidth` | `float` | Waveform bandwidth in Hz. |
| `duty_cycle` | `float` | Fraction of PRI occupied by the waveform. |
| `phase_noise` | `PhaseNoiseModel \| None` | Phase noise model, or None. |
| `window` | `Callable \| None` | Window function for range compression. |
| `prf` | `float \| None` | Pulse repetition frequency, or None. |

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `duration()` | `(prf: float \| None = None)` | `float` | Compute waveform duration in seconds (`duty_cycle / prf`). Uses instance PRF if argument is None. |
| `generate()` | `(prf: float, sample_rate: float)` | `np.ndarray` | **Abstract.** Generate complex transmit waveform samples, shape `(n_samples,)`. |
| `range_compress()` | `(echo: np.ndarray, prf: float, sample_rate: float)` | `np.ndarray` | **Abstract.** Range-compress received echo data. Accepts 1-D or 2-D input. |

### Class attribute

| Attribute | Type | Description |
|---|---|---|
| `name` | `str` | Registry key. Must be unique across all waveforms. |

## Built-in waveforms

| Name | Class | Description |
|---|---|---|
| `"lfm"` | `LFMWaveform` | Pulsed linear frequency modulated chirp. Uses frequency-domain matched filtering for range compression. |
| `"fmcw"` | `FMCWWaveform` | Frequency modulated continuous wave with configurable ramp type (`"up"`, `"down"`, `"triangle"`). Default `duty_cycle=1.0`. |

## Step-by-step: create a rectangular pulse waveform

A simple unmodulated rectangular pulse demonstrates the minimum contract.

### 1. Define the class

```python
import numpy as np
from pySimSAR.waveforms.base import Waveform


class RectangularPulse(Waveform):
    """Unmodulated rectangular pulse waveform.

    The transmit signal is a constant-amplitude pulse of duration
    duty_cycle / prf. Range compression uses matched filtering
    (correlate with reference pulse).
    """

    name = "rectangular"

    def __init__(
        self,
        bandwidth: float,
        duty_cycle: float = 0.1,
        phase_noise=None,
        window=None,
        prf: float | None = None,
    ) -> None:
        super().__init__(
            bandwidth=bandwidth,
            duty_cycle=duty_cycle,
            phase_noise=phase_noise,
            window=window,
            prf=prf,
        )
        self._tx_signal: np.ndarray | None = None

    def generate(self, prf: float, sample_rate: float) -> np.ndarray:
        duration = self.duration(prf)
        n_samples = int(duration * sample_rate)

        # Constant-amplitude pulse
        signal = np.ones(n_samples, dtype=complex)

        # Apply optional phase noise
        if self.phase_noise is not None:
            pn = self.phase_noise.generate(n_samples, sample_rate)
            signal = signal * np.exp(1j * pn)

        self._tx_signal = signal
        return signal

    def range_compress(
        self, echo: np.ndarray, prf: float, sample_rate: float
    ) -> np.ndarray:
        if self._tx_signal is None:
            raise RuntimeError("Must call generate() before range_compress().")

        ref = self._tx_signal

        if echo.ndim == 1:
            n = len(echo)
            ref_fft = np.conj(np.fft.fft(ref, n=n))
            if self.window is not None:
                ref_fft *= self.window(n)
            return np.fft.ifft(np.fft.fft(echo, n=n) * ref_fft)

        elif echo.ndim == 2:
            n = echo.shape[1]
            ref_fft = np.conj(np.fft.fft(ref, n=n))
            if self.window is not None:
                ref_fft *= self.window(n)
            return np.fft.ifft(
                np.fft.fft(echo, n=n, axis=1) * ref_fft[np.newaxis, :],
                axis=1,
            )

        raise ValueError(f"echo must be 1D or 2D, got {echo.ndim}D")
```

### 2. Register in the waveform registry

```python
from pySimSAR.waveforms.registry import waveform_registry

waveform_registry.register(RectangularPulse)
```

Or use decorator syntax:

```python
@waveform_registry.register
class RectangularPulse(Waveform):
    name = "rectangular"
    ...
```

### 3. Use with Radar

```python
from pySimSAR import Radar, create_antenna_from_preset

waveform = RectangularPulse(bandwidth=10e6, duty_cycle=0.05, prf=1000.0)
antenna = create_antenna_from_preset("sinc", az_beamwidth=0.05, el_beamwidth=0.1)

radar = Radar(
    carrier_freq=9.65e9,
    transmit_power=1.0,
    waveform=waveform,
    antenna=antenna,
    polarization="single",
)
```

The waveform is now used automatically by `SimulationEngine.run()` (for
transmit signal generation) and by image formation algorithms (for range
compression).

## Implementation notes

- `generate()` must store the transmit signal internally so that
  `range_compress()` can access it as the matched filter reference.
- `range_compress()` must handle both 1-D (single pulse) and 2-D
  (n_pulses x n_range_samples) echo arrays.
- The `window` callable, if provided, receives an integer `n` and returns
  a real-valued array of length `n`. It is applied in the frequency domain
  during matched filtering for sidelobe suppression.
- Phase noise, if provided, is applied during `generate()` by multiplying
  the signal by `exp(j * phase_noise_samples)`.
