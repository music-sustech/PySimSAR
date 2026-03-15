# Contract: Clutter Model Interface

## ABC: `ClutterModel`

Base class for statistical clutter/texture generation models.

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Model identifier (e.g., "k_distribution") |

### Required Methods

```python
def generate(
    self,
    shape: tuple[int, int],
    seed: int | None = None,
) -> np.ndarray:
    """Generate a 2D reflectivity array with statistical texture.

    Args:
        shape: Grid dimensions (ny, nx).
        seed: Random seed for reproducibility. If None, uses
            non-deterministic randomness.

    Returns:
        Reflectivity array (ny, nx) with values >= 0.
    """
```

### Registration

```python
from pySimSAR.clutter.registry import ClutterModelRegistry

# Manual registration
ClutterModelRegistry.register("my_clutter", MyClutterClass)

# Access
clutter_cls = ClutterModelRegistry.get("uniform")
clutter = clutter_cls(mean_intensity=1.0)
```

### Default Implementations

| Name | Class | Description |
|------|-------|-------------|
| `uniform` | `UniformClutter` | Constant reflectivity across all cells. Parameters: `mean_intensity` (reflectivity value). Simplest baseline — no statistical texture. |

**Future**: Statistical models (K-distribution, log-normal, Weibull)
can be added as modules for more realistic clutter simulation.

### Usage with DistributedTarget

```python
from pySimSAR.clutter import UniformClutter
from pySimSAR.core.scene import DistributedTarget

# Generate clutter reflectivity via model
clutter = UniformClutter(mean_intensity=0.5)

target = DistributedTarget(
    origin=[0, 0, 0],
    extent=[500, 500],
    cell_size=1.0,
    clutter_model=clutter,  # reflectivity generated at simulation time
)

# Or provide reflectivity directly (clutter_model=None)
target2 = DistributedTarget(
    origin=[600, 0, 0],
    extent=[200, 200],
    cell_size=1.0,
    reflectivity=my_custom_array,
)
```

### Adding a New Clutter Model

```python
from pySimSAR.clutter.base import ClutterModel
from pySimSAR.clutter.registry import ClutterModelRegistry

class LogNormalClutter(ClutterModel):
    def __init__(self, mu: float, sigma: float):
        self._mu = mu
        self._sigma = sigma

    @property
    def name(self) -> str:
        return "log_normal"

    def generate(self, shape, seed=None):
        rng = np.random.default_rng(seed)
        return rng.lognormal(self._mu, self._sigma, size=shape)

ClutterModelRegistry.register("log_normal", LogNormalClutter)
```
