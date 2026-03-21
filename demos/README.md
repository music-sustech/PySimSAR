# Demos

Comparison and analysis scripts that load example projects from `examples/`,
run simulations with parameter variations, and plot results side by side.

## Usage Pattern

```python
from pySimSAR.io.parameter_set import load_parameter_set, build_simulation

# Load an example project as the baseline
params = load_parameter_set("examples/scenarios/stripmap_rda")
# Modify one parameter, run both, compare results
```

## Example Project Configs

See `examples/` for reusable project configurations:

- `examples/golden/` — Analytical reference cases with expected results
- `examples/scenarios/` — Algorithm combination matrix (19 scenarios)
