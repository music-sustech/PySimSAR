# Contract: Image Transformation Algorithm Interface

## ABC: `ImageTransformationAlgorithm`

Base class for SAR image geometry transformation processors.

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Algorithm name (e.g., "Slant-to-Ground Range") |
| `output_geometry` | `str` | Output coordinate type: `"ground_range"` or `"geographic"` |

### Required Methods

```python
def transform(
    self,
    image: SARImage,
    radar: Radar,
    trajectory: Trajectory,
) -> SARImage:
    """Transform a SAR image from radar geometry to output geometry.

    Args:
        image: Input SAR image in slant-range/azimuth geometry.
        radar: Radar parameters (needed for range geometry calculation).
        trajectory: Platform trajectory (needed for projection geometry).

    Returns:
        Transformed SAR image in the output coordinate system, with
        updated pixel_spacing and georeferencing metadata.
    """
```

### Registration

```python
from pySimSAR.algorithms.registry import AlgorithmRegistry

AlgorithmRegistry.register("geocoding", "my_transform", MyTransformClass)
```

### Default Implementations

| Name | Class | Output Geometry | Description |
|------|-------|-----------------|-------------|
| `slant_to_ground` | `SlantToGroundRange` | `ground_range` | Projects slant-range to ground-range assuming flat earth or known DEM |
| `georeferencing` | `Georeferencing` | `geographic` | Maps pixels to lat/lon using platform trajectory and radar geometry |

### Fallback Behavior

If navigation metadata is insufficient for full georeferencing (e.g.,
no GPS data), the system falls back to `slant_to_ground` projection
and emits a warning.

### Example

```python
from pySimSAR.algorithms.geocoding import SlantToGroundRange

s2g = SlantToGroundRange()
ground_image = s2g.transform(slant_image, radar, trajectory)
print(f"Ground pixel spacing: {ground_image.pixel_spacing} m")
```
