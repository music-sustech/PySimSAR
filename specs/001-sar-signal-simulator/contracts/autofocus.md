# Contract: Autofocus Algorithm Interface

## ABC: `AutofocusAlgorithm`

Base class for autofocus algorithms that estimate and correct residual
phase errors after first-stage motion compensation. Operates on the
range-compressed phase history domain, iteratively refining focus.

### Required Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `name` | `str` | — | Algorithm identifier |
| `max_iterations` | `int` | `10` | Maximum iterations for convergence |
| `convergence_threshold` | `float` | `0.01` | Phase error convergence threshold (radians) |

### Required Methods

```python
def focus(
    self,
    phase_history: PhaseHistoryData,
    azimuth_compressor: Callable[[PhaseHistoryData], SARImage],
) -> SARImage:
    """Autofocus the phase history data.

    Iteratively:
      1. Estimate residual phase error from phase_history
      2. Apply phase correction to phase_history
      3. Call azimuth_compressor() to form a test image
      4. Check convergence
      5. Repeat until converged or max_iterations reached

    Args:
        phase_history: Range-compressed phase history data.
        azimuth_compressor: Callable that performs azimuth compression
            (typically ImageFormationAlgorithm.azimuth_compress).

    Returns:
        Focused SAR image after autofocus correction.
    """

def estimate_phase_error(
    self,
    phase_history: PhaseHistoryData,
) -> np.ndarray:
    """Estimate the residual phase error vector.

    Can be called standalone for diagnostics or analysis.

    Args:
        phase_history: Range-compressed phase history data.

    Returns:
        Estimated phase error vector (n_azimuth,) in radians.
    """
```

### Registration

```python
from pySimSAR.algorithms.registry import AlgorithmRegistry

AlgorithmRegistry.register("autofocus", "my_autofocus", MyAutofocusClass)
```

### Default Implementations

| Name | Class | Description |
|------|-------|-------------|
| `pga` | `PhaseGradientAutofocus` | Selects dominant scatterers per range bin, estimates phase gradient across azimuth, integrates to obtain phase error. Iterates until convergence. Best for scenes with strong isolated scatterers. |
| `mda` | `MapDriftAutofocus` | Splits the synthetic aperture into overlapping sub-apertures, forms sub-images, and measures their relative shift (map drift) to estimate phase errors. Effective for low-order errors (linear and quadratic phase). |
| `min_entropy` | `MinimumEntropyAutofocus` | Iteratively adjusts phase correction coefficients to minimize image entropy (maximize sharpness). Supports polynomial phase models of configurable order. Robust for distributed scenes without strong point targets. |
| `ppp` | `ProminentPointProcessing` | Identifies isolated prominent scatterers in range-compressed data, extracts their azimuth phase histories, and estimates motion errors from phase deviations relative to the expected model. Works directly in the phase history domain without forming intermediate images. |

#### Algorithm Selection Guidance

| Scene Characteristics | Recommended Algorithm |
|-----------------------|----------------------|
| Strong isolated scatterers present | PGA or PPP |
| Distributed scene (terrain, vegetation) | Minimum Entropy |
| Low-order phase errors (defocus, drift) | MDA |
| Unknown scene, general purpose | PGA (good all-round default) |

### Pipeline Integration

Autofocus sits between range compression and azimuth compression:

```
RawData
  │
  ├──→ MoCo (nav-based, corrects bulk motion)
  │
  ├──→ range_compress() ──→ PhaseHistoryData
  │                               │
  │                     ┌─────────┴──────────┐
  │                     │                    │
  │              (residual errors?)    (no residual errors)
  │                     │                    │
  │              autofocus.focus(        azimuth_compress()
  │                  phase_history,          │
  │                  azimuth_compress)       │
  │                     │                    │
  │                     └────────┬───────────┘
  │                              │
  └──────────────────────── SARImage
```

### Example

```python
from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm
from pySimSAR.algorithms.autofocus import PhaseGradientAutofocus

rda = RangeDopplerAlgorithm()
pga = PhaseGradientAutofocus(max_iterations=15, convergence_threshold=0.005)

# Range compress
phase_history = rda.range_compress(raw_data, nav_data)

# Autofocus
image = pga.focus(phase_history, rda.azimuth_compress)

# Or inspect phase errors without full autofocus
phase_error = pga.estimate_phase_error(phase_history)
```

### Adding a New Autofocus Algorithm

```python
from pySimSAR.algorithms.base import AutofocusAlgorithm
from pySimSAR.algorithms.registry import AlgorithmRegistry

class MinimumEntropyAutofocus(AutofocusAlgorithm):
    @property
    def name(self) -> str:
        return "minimum_entropy"

    def focus(self, phase_history, azimuth_compressor):
        for i in range(self.max_iterations):
            error = self.estimate_phase_error(phase_history)
            if np.max(np.abs(error)) < self.convergence_threshold:
                break
            phase_history = self._apply_correction(phase_history, error)
        return azimuth_compressor(phase_history)

    def estimate_phase_error(self, phase_history):
        # Minimize image entropy by optimizing phase
        ...

AlgorithmRegistry.register("autofocus", "minimum_entropy",
                           MinimumEntropyAutofocus)
```
