# Contract: Polarimetric Decomposition Interface

## ABC: `PolarimetricDecomposition`

Base class for all polarimetric decomposition methods.

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Decomposition name (e.g., "Pauli") |
| `n_components` | `int` | Number of output components |

### Required Methods

```python
def decompose(
    self,
    image_hh: SARImage,
    image_hv: SARImage,
    image_vh: SARImage,
    image_vv: SARImage,
) -> dict[str, np.ndarray]:
    """Apply polarimetric decomposition to quad-pol SAR data.

    Args:
        image_hh: Co-pol HH channel image.
        image_hv: Cross-pol HV channel image.
        image_vh: Cross-pol VH channel image.
        image_vv: Co-pol VV channel image.

    Returns:
        Dictionary mapping component names to 2D arrays.
        E.g., {"surface": ..., "double_bounce": ..., "volume": ...}
    """

def validate_input(
    self,
    image_hh: SARImage | None,
    image_hv: SARImage | None,
    image_vh: SARImage | None,
    image_vv: SARImage | None,
) -> None:
    """Validate that required polarization channels are present.

    Raises:
        PolarimetricInputError: If required channels are missing or
            images have incompatible dimensions.
    """
```

### Registration

```python
from pySimSAR.algorithms.registry import AlgorithmRegistry

AlgorithmRegistry.register("polarimetry", "my_decomp", MyDecompClass)
```

### Default Implementations

| Name | Class | Components | Description |
|------|-------|------------|-------------|
| `pauli` | `PauliDecomposition` | 3 | Surface (HH+VV), double-bounce (HH-VV), volume (HV) |
| `freeman_durden` | `FreemanDurdenDecomposition` | 3 | Model-based: surface, double-bounce, volume power |
| `yamaguchi` | `YamaguchiDecomposition` | 4 | Adds helix scattering to Freeman-Durden |
| `cloude_pottier` | `CloudePottierDecomposition` | 3 | Entropy (H), anisotropy (A), alpha angle |

### Example

```python
from pySimSAR.algorithms.polarimetry import PauliDecomposition

pauli = PauliDecomposition()
pauli.validate_input(img_hh, img_hv, img_vh, img_vv)
components = pauli.decompose(img_hh, img_hv, img_vh, img_vv)

surface = components["surface"]
dbl_bounce = components["double_bounce"]
volume = components["volume"]
```
