# Contract: Image Formation Algorithm Interface

## ABC: `ImageFormationAlgorithm`

Base class for all SAR image formation processors. Exposes a two-step
interface (range compression → azimuth compression) to enable autofocus
algorithms to operate on the intermediate phase history data, as well
as a convenience `process()` method that runs both steps end-to-end.

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Algorithm name (e.g., "Range-Doppler") |
| `description` | `str` | Brief description of the algorithm |

### Required Methods

```python
def process(
    self,
    raw_data: RawData,
    nav_data: NavigationData | None = None,
) -> SARImage:
    """Form a focused SAR image from raw echo data (end-to-end).

    Convenience method that calls range_compress() then
    azimuth_compress() in sequence. Use the two-step interface
    when autofocus is needed between the steps.

    Args:
        raw_data: Raw SAR echo data (single polarization channel).
        nav_data: Navigation data for motion-aware processing.

    Returns:
        Focused SAR image with metadata.
    """

def range_compress(
    self,
    raw_data: RawData,
    nav_data: NavigationData | None = None,
) -> PhaseHistoryData:
    """Step 1: Range compression.

    Compresses the raw echo data in the range dimension using the
    waveform's range_compress() method, producing the intermediate
    phase history data suitable for autofocus or direct azimuth
    compression.

    Args:
        raw_data: Raw SAR echo data.
        nav_data: Navigation data (optional).

    Returns:
        Range-compressed phase history data.
    """

def azimuth_compress(
    self,
    phase_history: PhaseHistoryData,
) -> SARImage:
    """Step 2: Azimuth compression.

    Compresses the phase history in the azimuth dimension to form
    the focused SAR image. Each algorithm implements its own
    azimuth compression method (FFT-based for RDA, scaling for CSA,
    Stolt interpolation for Omega-K, etc.).

    Args:
        phase_history: Range-compressed phase history data.

    Returns:
        Focused SAR image with metadata.
    """

def supported_modes(self) -> list[str]:
    """Return list of SAR modes this algorithm supports.

    Returns:
        List of mode strings, e.g., ['stripmap', 'spotlight', 'scanmar'].
    """
```

### Two-Step Pipeline

```
                    Without autofocus:
RawData ──→ process() ──→ SARImage

                    With autofocus:
RawData ──→ range_compress() ──→ PhaseHistoryData
                                       │
                                       ├──→ autofocus.focus(
                                       │        phase_history,
                                       │        algo.azimuth_compress
                                       │    ) ──→ SARImage
                                       │
                                       └──→ azimuth_compress() ──→ SARImage
                                            (if no autofocus needed)
```

### Registration

```python
from pySimSAR.algorithms.registry import AlgorithmRegistry

AlgorithmRegistry.register("image_formation", "my_algo", MyAlgoClass)
algo_cls = AlgorithmRegistry.get("image_formation", "range_doppler")
```

### Default Implementations

| Name | Class | Supported Modes |
|------|-------|-----------------|
| `range_doppler` | `RangeDopplerAlgorithm` | stripmap |
| `chirp_scaling` | `ChirpScalingAlgorithm` | stripmap, scanmar |
| `omega_k` | `OmegaKAlgorithm` | stripmap, spotlight |

### Mode Validation

Before processing, the pipeline validates that the selected algorithm
supports the data's SAR mode via `supported_modes()`. Incompatible
combinations raise `AlgorithmModeError`.

### Example: End-to-End (No Autofocus)

```python
from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm

rda = RangeDopplerAlgorithm()
image = rda.process(raw_data)
```

### Example: Two-Step with Autofocus

```python
from pySimSAR.algorithms.image_formation import RangeDopplerAlgorithm
from pySimSAR.algorithms.autofocus import PhaseGradientAutofocus

rda = RangeDopplerAlgorithm()
pga = PhaseGradientAutofocus(max_iterations=10)

# Step 1: Range compression
phase_history = rda.range_compress(raw_data, nav_data)

# Step 2: Autofocus (iteratively corrects phase errors and
#          calls rda.azimuth_compress() internally)
image = pga.focus(phase_history, rda.azimuth_compress)
```
