# API Reference: Algorithms

## AlgorithmRegistry

`pySimSAR.algorithms.registry.AlgorithmRegistry[T]`

Generic typed registry for algorithm plugin classes.

### Constructor

```python
AlgorithmRegistry(base_class: type[T], name: str)
```

| Parameter | Type | Description |
|---|---|---|
| `base_class` | `type[T]` | The ABC that all registered algorithms must subclass. |
| `name` | `str` | Human-readable name for error messages. |

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `register()` | `(algorithm_class: type[T])` | `type[T]` | Register an algorithm class. Can be used as a decorator. Raises `TypeError` if not a valid subclass, `ValueError` if name already registered. |
| `get()` | `(name: str)` | `type[T]` | Look up a class by name. Raises `KeyError` if not found. |
| `list()` | `()` | `list[str]` | Sorted list of registered algorithm names. |

### Properties

| Property | Type | Description |
|---|---|---|
| `name` | `str` | Registry name. |

Supports `in` membership testing and `len()`.

### Registry instances

| Registry | Module | Base class |
|---|---|---|
| `image_formation_registry` | `pySimSAR.algorithms.image_formation` | `ImageFormationAlgorithm` |
| `autofocus_registry` | `pySimSAR.algorithms.autofocus` | `AutofocusAlgorithm` |
| `moco_registry` | `pySimSAR.algorithms.moco` | `MotionCompensationAlgorithm` |
| `geocoding_registry` | `pySimSAR.algorithms.geocoding` | `ImageTransformationAlgorithm` |
| `polarimetry_registry` | `pySimSAR.algorithms.polarimetry` | `PolarimetricDecomposition` |
| `waveform_registry` | `pySimSAR.waveforms.registry` | `Waveform` |

---

## ImageFormationAlgorithm

`pySimSAR.algorithms.base.ImageFormationAlgorithm`

Abstract base class for SAR image formation algorithms.

### Class attributes

| Attribute | Type | Description |
|---|---|---|
| `name` | `str` | Registry key (must be unique). |

### Abstract methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `process()` | `(raw_data: RawData, radar: Radar, trajectory: Trajectory)` | `SARImage` | Complete image formation pipeline. |
| `range_compress()` | `(raw_data: RawData, radar: Radar)` | `PhaseHistoryData` | Range compression step. |
| `azimuth_compress()` | `(phase_history: PhaseHistoryData, radar: Radar, trajectory: Trajectory)` | `SARImage` | Azimuth compression step. |
| `supported_modes()` | `()` | `list[SARMode]` | SAR modes this algorithm supports. |

### Optional methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `parameter_schema()` | `classmethod()` | `dict` | Parameter names, types, defaults, descriptions. |

---

## RangeDopplerAlgorithm

`pySimSAR.algorithms.image_formation.range_doppler.RangeDopplerAlgorithm`

Classic Range-Doppler algorithm. Operates in the range-Doppler domain with
RCMC via sinc interpolation and azimuth matched filtering.

**Registered name:** `"range_doppler"`

**Supported modes:** Stripmap

### Constructor

```python
RangeDopplerAlgorithm(
    apply_rcmc: bool = True,
    rcmc_interp_order: int = 8,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `apply_rcmc` | `bool` | `True` | Whether to apply Range Cell Migration Correction. |
| `rcmc_interp_order` | `int` | `8` | Interpolation kernel order for RCMC. |

---

## ChirpScalingAlgorithm

`pySimSAR.algorithms.image_formation.chirp_scaling.ChirpScalingAlgorithm`

Chirp Scaling algorithm with bulk RCMC in 2-D frequency domain at a
reference range, followed by residual interpolation-based correction.

**Registered name:** `"chirp_scaling"`

**Supported modes:** Stripmap, ScanSAR

### Constructor

```python
ChirpScalingAlgorithm(n_iterations: int = 1)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `n_iterations` | `int` | `1` | Number of range-block iterations. When > 1, the swath is partitioned and each block is focused at its local reference range. |

---

## OmegaKAlgorithm

`pySimSAR.algorithms.image_formation.omega_k.OmegaKAlgorithm`

Omega-K (Wavenumber Domain) algorithm with exact RCMC using the migration
factor `D(f_eta) = sqrt(1 - (lambda*f_eta/(2V))^2)`.

**Registered name:** `"omega_k"`

**Supported modes:** Stripmap, Spotlight

### Constructor

```python
OmegaKAlgorithm(reference_range: float = 0.0)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `reference_range` | `float` | `0.0` | Reference range for processing (0 = auto). |

---

## MotionCompensationAlgorithm

`pySimSAR.algorithms.base.MotionCompensationAlgorithm`

Abstract base class for motion compensation algorithms.

### Class attributes

| Attribute | Type | Description |
|---|---|---|
| `name` | `str` | Registry key. |

### Abstract methods/properties

| Method | Signature | Returns | Description |
|---|---|---|---|
| `compensate()` | `(raw_data: RawData, nav_data: NavigationData, reference_track: Trajectory)` | `RawData` | Apply motion compensation. |
| `order` | property | `int` | Compensation order (1 = first-order, 2 = second-order). |

Built-in implementations:

| Name | Class | Description |
|---|---|---|
| `"first_order"` | `FirstOrderMoCo` | Bulk (range-independent) phase correction from GPS positions. Fits a straight-line reference track via least squares. |
| `"second_order"` | `SecondOrderMoCo` | Range-dependent correction using per-range-bin differential path length. |

---

## AutofocusAlgorithm

`pySimSAR.algorithms.base.AutofocusAlgorithm`

Abstract base class for autofocus algorithms. Operates between range and
azimuth compression steps.

### Class attributes

| Attribute | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | `""` | Registry key. |
| `max_iterations` | `int` | `10` | Maximum autofocus iterations. |
| `convergence_threshold` | `float` | `0.01` | Stop threshold in radians. |

### Abstract methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `focus()` | `(phase_history: PhaseHistoryData, azimuth_compressor: callable)` | `SARImage` | Apply autofocus and return focused image. |

### Optional methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `estimate_phase_error()` | `(phase_history: PhaseHistoryData)` | `np.ndarray` | Estimate residual phase error, shape `(n_azimuth,)`. |

---

### PhaseGradientAutofocus (PGA)

`pySimSAR.algorithms.autofocus.pga.PhaseGradientAutofocus`

**Registered name:** `"pga"`

Selects dominant scatterers from the focused image, extracts azimuth phase
histories, estimates the phase gradient, and integrates to obtain a
correction. Iterates until convergence.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `max_iterations` | `int` | `10` | Maximum iterations. |
| `convergence_threshold` | `float` | `0.01` | Convergence threshold in radians. |

---

### MapDriftAutofocus (MDA)

`pySimSAR.algorithms.autofocus.mda.MapDriftAutofocus`

**Registered name:** `"mda"`

Splits the aperture into overlapping sub-apertures, measures Doppler
centroid drift, and fits a low-order polynomial phase error model.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `max_iterations` | `int` | `10` | Maximum iterations. |
| `convergence_threshold` | `float` | `0.01` | Convergence threshold in radians. |
| `n_subapertures` | `int` | (impl default) | Number of sub-apertures. |
| `poly_order` | `int` | (impl default) | Polynomial order (1 = linear, 2 = quadratic). |

---

### MinimumEntropyAutofocus (MEA)

`pySimSAR.algorithms.autofocus.min_entropy.MinimumEntropyAutofocus`

**Registered name:** `"min_entropy"`

Optimizes polynomial phase coefficients to minimize image entropy. Works
well on distributed scenes without strong point targets.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `max_iterations` | `int` | `10` | Maximum outer iterations. |
| `convergence_threshold` | `float` | `0.01` | Convergence threshold in radians. |
| `poly_order` | `int` | (impl default) | Order of polynomial phase model. |

---

### ProminentPointProcessing (PPP)

`pySimSAR.algorithms.autofocus.ppp.ProminentPointProcessing`

**Registered name:** `"ppp"`

Identifies prominent scatterers by energy contrast in range-compressed
data, extracts azimuth phase histories, and averages the residual phase
to estimate a common phase error.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `max_iterations` | `int` | `10` | Maximum iterations. |
| `convergence_threshold` | `float` | `0.01` | Convergence threshold in radians. |
| `n_scatterers` | `int` | `0` | Number of scatterers (0 = auto, top 25%). |
| `contrast_threshold` | `float` | (impl default) | Minimum energy contrast ratio. |

---

## ImageTransformationAlgorithm

`pySimSAR.algorithms.base.ImageTransformationAlgorithm`

Abstract base class for image geometry transformations.

### Abstract methods/properties

| Method | Signature | Returns | Description |
|---|---|---|---|
| `transform()` | `(image: SARImage, radar: Radar, trajectory: Trajectory)` | `SARImage` | Transform image geometry. |
| `output_geometry` | property | `ImageGeometry` | Output coordinate system. |

Built-in:

| Name | Class | Output geometry | Description |
|---|---|---|---|
| `"slant_to_ground"` | `SlantToGroundRange` | `GROUND_RANGE` | Flat-earth slant-to-ground range projection. |
| `"georeferencing"` | `Georeferencing` | `GEOGRAPHIC` | Pixel-to-lat/lon mapping using trajectory and radar geometry. |

---

## PolarimetricDecomposition

`pySimSAR.algorithms.base.PolarimetricDecomposition`

Abstract base class for polarimetric decomposition algorithms.

### Abstract methods/properties

| Method | Signature | Returns | Description |
|---|---|---|---|
| `decompose()` | `(image_hh, image_hv, image_vh, image_vv)` | `dict[str, np.ndarray]` | Decompose quad-pol data into scattering components. |
| `n_components` | property | `int` | Number of output components. |

### Concrete methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `validate_input()` | `(image_hh, image_hv, image_vh, image_vv)` | `None` | Check all four channels are present. Raises `ValueError` if any is None. |

Built-in:

| Name | Class | Components | Description |
|---|---|---|---|
| `"pauli"` | `PauliDecomposition` | 3 | Surface, double-bounce, volume (Pauli basis). |
| `"freeman_durden"` | `FreemanDurdenDecomposition` | 3 | Model-based 3-component. |
| `"yamaguchi"` | `YamaguchiDecomposition` | 4 | 4-component with helix scattering. |
| `"cloude_pottier"` | `CloudePottierDecomposition` | 3 | Eigenvalue-based H/A/Alpha. |
