# Extending Algorithms

PySimSAR uses a generic registry pattern for all algorithm families. This
guide explains how to create and register custom algorithms for image
formation, motion compensation, autofocus, geocoding, and polarimetric
decomposition.

## AlgorithmRegistry pattern

`AlgorithmRegistry[T]` is a type-safe, generic registry that stores algorithm
classes keyed by their `name` attribute.

```python
from pySimSAR.algorithms.registry import AlgorithmRegistry

# Create a registry for a given base class
registry = AlgorithmRegistry(MyBaseClass, "my_algorithms")

# Register a class (direct call)
registry.register(MyAlgorithmClass)

# Register using decorator syntax
@registry.register
class AnotherAlgorithm(MyBaseClass):
    name = "another"
    ...

# Look up by name
cls = registry.get("another")     # returns the class (not an instance)
instance = cls(param1=10)          # instantiate with parameters

# List all registered names
print(registry.list())             # ["another", ...]

# Check membership
"another" in registry               # True
```

**Key rules:**

- The registered class must be a subclass of the registry's base class.
- It must have a `name` class attribute (string, not a method or property).
- Duplicate names raise `ValueError`.
- Unknown names on `get()` raise `KeyError` with a message listing available algorithms.

## Abstract base classes

### ImageFormationAlgorithm

Located in `pySimSAR.algorithms.base`. All image formation algorithms must
subclass this and implement four abstract methods:

| Method | Signature | Returns | Description |
|---|---|---|---|
| `process()` | `(raw_data, radar, trajectory)` | `SARImage` | Full end-to-end pipeline. |
| `range_compress()` | `(raw_data, radar)` | `PhaseHistoryData` | Range compression step. |
| `azimuth_compress()` | `(phase_history, radar, trajectory)` | `SARImage` | Azimuth compression step. |
| `supported_modes()` | `()` | `list[SARMode]` | SAR modes this algorithm supports. |

Optional override:

| Method | Signature | Returns | Description |
|---|---|---|---|
| `parameter_schema()` | `classmethod()` | `dict` | Declares constructor parameter names, types, defaults, and descriptions. |

Built-in implementations:

| Name | Class | Modes |
|---|---|---|
| `"range_doppler"` | `RangeDopplerAlgorithm` | Stripmap |
| `"chirp_scaling"` | `ChirpScalingAlgorithm` | Stripmap, ScanSAR |
| `"omega_k"` | `OmegaKAlgorithm` | Stripmap, Spotlight |

### MotionCompensationAlgorithm

| Method / Property | Signature | Returns | Description |
|---|---|---|---|
| `compensate()` | `(raw_data, nav_data, reference_track)` | `RawData` | Apply phase correction to raw data. |
| `order` | property | `int` | Compensation order (1 or 2). |
| `parameter_schema()` | `classmethod()` | `dict` | Parameter declarations. |

Built-in: `"first_order"` (FirstOrderMoCo), `"second_order"` (SecondOrderMoCo).

### AutofocusAlgorithm

| Method | Signature | Returns | Description |
|---|---|---|---|
| `focus()` | `(phase_history, azimuth_compressor)` | `SARImage` | Apply autofocus and return focused image. |
| `estimate_phase_error()` | `(phase_history)` | `np.ndarray` | Estimate residual phase error (optional). |
| `parameter_schema()` | `classmethod()` | `dict` | Parameter declarations. |

Class attributes: `max_iterations` (int, default 10), `convergence_threshold` (float, default 0.01 rad).

Built-in:

| Name | Class | Strategy |
|---|---|---|
| `"pga"` | `PhaseGradientAutofocus` | Dominant scatterer phase gradient |
| `"mda"` | `MapDriftAutofocus` | Sub-aperture Doppler centroid drift |
| `"min_entropy"` | `MinimumEntropyAutofocus` | Entropy optimization |
| `"ppp"` | `ProminentPointProcessing` | Prominent scatterer phase extraction |

### ImageTransformationAlgorithm

| Method / Property | Signature | Returns | Description |
|---|---|---|---|
| `transform()` | `(image, radar, trajectory)` | `SARImage` | Transform image geometry. |
| `output_geometry` | property | `ImageGeometry` | Output coordinate system. |
| `parameter_schema()` | `classmethod()` | `dict` | Parameter declarations. |

Built-in: `"slant_to_ground"` (SlantToGroundRange), `"georeferencing"` (Georeferencing).

### PolarimetricDecomposition

| Method / Property | Signature | Returns | Description |
|---|---|---|---|
| `decompose()` | `(image_hh, image_hv, image_vh, image_vv)` | `dict[str, np.ndarray]` | Decompose quad-pol data. |
| `n_components` | property | `int` | Number of output components. |
| `validate_input()` | `(image_hh, image_hv, image_vh, image_vv)` | `None` | Check all channels present. |
| `parameter_schema()` | `classmethod()` | `dict` | Parameter declarations. |

Built-in: `"pauli"`, `"freeman_durden"`, `"yamaguchi"`, `"cloude_pottier"`.

## Tutorial: creating a new image formation algorithm

This walkthrough creates a simple pass-through algorithm that returns
range-compressed data as the "image" without azimuth compression.

### Step 1: Subclass ImageFormationAlgorithm

```python
import numpy as np
from pySimSAR.algorithms.base import ImageFormationAlgorithm
from pySimSAR.core.types import PhaseHistoryData, SARImage, SARMode
from pySimSAR.core.radar import C_LIGHT
```

### Step 2: Set the `name` class attribute

```python
class RangeOnlyAlgorithm(ImageFormationAlgorithm):
    """Image formation that performs only range compression."""

    name = "range_only"
```

### Step 3: Implement required abstract methods

```python
    def __init__(self, apply_window: bool = True):
        self._apply_window = apply_window

    def supported_modes(self) -> list[SARMode]:
        return [SARMode.STRIPMAP, SARMode.SPOTLIGHT]

    def process(self, raw_data, radar, trajectory) -> SARImage:
        phd = self.range_compress(raw_data, radar)
        return self.azimuth_compress(phd, radar, trajectory)

    def range_compress(self, raw_data, radar) -> PhaseHistoryData:
        radar.waveform.generate(radar.waveform.prf, raw_data.sample_rate)
        compressed = radar.waveform.range_compress(
            raw_data.echo, radar.waveform.prf, raw_data.sample_rate
        )
        return PhaseHistoryData(
            data=compressed,
            sample_rate=raw_data.sample_rate,
            prf=radar.waveform.prf,
            carrier_freq=radar.carrier_freq,
            bandwidth=radar.bandwidth,
            channel=raw_data.channel,
            gate_delay=raw_data.gate_delay,
        )

    def azimuth_compress(self, phase_history, radar, trajectory) -> SARImage:
        V = np.mean(np.linalg.norm(trajectory.velocity, axis=1))
        near_range = phase_history.gate_delay * C_LIGHT / 2.0
        return SARImage(
            data=phase_history.data,
            pixel_spacing_range=C_LIGHT / (2.0 * phase_history.sample_rate),
            pixel_spacing_azimuth=V / phase_history.prf,
            geometry="slant_range",
            algorithm=self.name,
            channel=phase_history.channel,
            near_range=near_range,
        )
```

### Step 4: Add `parameter_schema()` (optional but recommended)

```python
    @classmethod
    def parameter_schema(cls) -> dict:
        return {
            "apply_window": {
                "type": "bool",
                "default": True,
                "description": "Apply a window function during range compression.",
            }
        }
```

### Step 5: Register

```python
from pySimSAR.algorithms.image_formation import image_formation_registry

image_formation_registry.register(RangeOnlyAlgorithm)
```

### Step 6: Use in the pipeline

```python
from pySimSAR import ProcessingConfig, PipelineRunner

config = ProcessingConfig(image_formation="range_only")
pipeline = PipelineRunner(config)
result = pipeline.run(raw_data, radar, trajectory)
```

## Extending other algorithm families

The pattern is identical for all algorithm families. Only the base class,
registry instance, and abstract methods differ.

### Custom autofocus

```python
from pySimSAR.algorithms.base import AutofocusAlgorithm
from pySimSAR.algorithms.autofocus import autofocus_registry

class MyAutofocus(AutofocusAlgorithm):
    name = "my_autofocus"
    max_iterations = 5
    convergence_threshold = 0.005

    def focus(self, phase_history, azimuth_compressor):
        # Estimate and correct phase errors, then compress
        return azimuth_compressor(phase_history)

autofocus_registry.register(MyAutofocus)

config = ProcessingConfig(
    image_formation="range_doppler",
    autofocus="my_autofocus",
)
```

### Custom motion compensation

```python
from pySimSAR.algorithms.base import MotionCompensationAlgorithm
from pySimSAR.algorithms.moco import moco_registry

class MyMoCo(MotionCompensationAlgorithm):
    name = "my_moco"

    @property
    def order(self) -> int:
        return 1

    def compensate(self, raw_data, nav_data, reference_track=None):
        # Apply phase correction ...
        return raw_data

moco_registry.register(MyMoCo)
```

### Custom geocoding

```python
from pySimSAR.algorithms.base import ImageTransformationAlgorithm
from pySimSAR.algorithms.geocoding import geocoding_registry
from pySimSAR.core.types import ImageGeometry

class MyGeocoder(ImageTransformationAlgorithm):
    name = "my_geocoder"

    @property
    def output_geometry(self) -> ImageGeometry:
        return ImageGeometry.GROUND_RANGE

    def transform(self, image, radar, trajectory):
        # Transform image geometry ...
        return image

geocoding_registry.register(MyGeocoder)
```

### Custom polarimetric decomposition

```python
from pySimSAR.algorithms.base import PolarimetricDecomposition
from pySimSAR.algorithms.polarimetry import polarimetry_registry
import numpy as np

class MyDecomposition(PolarimetricDecomposition):
    name = "my_decomp"

    @property
    def n_components(self) -> int:
        return 2

    def decompose(self, image_hh, image_hv, image_vh, image_vv):
        self.validate_input(image_hh, image_hv, image_vh, image_vv)
        co_pol = np.abs(image_hh.data) + np.abs(image_vv.data)
        cross_pol = np.abs(image_hv.data) + np.abs(image_vh.data)
        return {"co_pol": co_pol, "cross_pol": cross_pol}

polarimetry_registry.register(MyDecomposition)
```
