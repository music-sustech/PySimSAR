# Contract: Motion Compensation Algorithm Interface

## ABC: `MotionCompensationAlgorithm`

Base class for all motion compensation processors.

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Algorithm name (e.g., "First-Order MoCo") |
| `order` | `int` | Compensation order (1 = first-order, 2 = second-order) |

### Required Methods

```python
def compensate(
    self,
    raw_data: RawData,
    nav_data: NavigationData,
    reference_track: Trajectory,
) -> RawData:
    """Apply motion compensation to raw SAR data.

    Corrects phase errors in the raw echo data caused by platform
    motion deviations from the reference (ideal) track.

    Args:
        raw_data: Raw SAR echo data with motion-induced errors.
        nav_data: Measured navigation data from GPS/IMU sensors.
        reference_track: Ideal (nominal) flight trajectory.

    Returns:
        Motion-compensated raw data, ready for image formation.
    """
```

### Registration

```python
from pySimSAR.algorithms.registry import AlgorithmRegistry

AlgorithmRegistry.register("moco", "my_moco", MyMoCoClass)
```

### Default Implementations

| Name | Class | Order | Description |
|------|-------|-------|-------------|
| `first_order` | `FirstOrderMoCo` | 1 | Range-dependent bulk phase correction to scene center |
| `second_order` | `SecondOrderMoCo` | 2 | Range-dependent correction with residual aperture-dependent terms |

### Pipeline Integration

Motion compensation is applied between raw data generation and image
formation. The pipeline calls `compensate()` and feeds the result to
the selected `ImageFormationAlgorithm.process()`.

### Example

```python
from pySimSAR.algorithms.moco import FirstOrderMoCo

moco = FirstOrderMoCo()
compensated = moco.compensate(raw_data, nav_data, ideal_trajectory)
image = rda.process(compensated)
```
