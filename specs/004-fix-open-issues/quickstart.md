# Quickstart: Fix Open Issues

**Branch**: `004-fix-open-issues` | **Date**: 2026-03-22

## Prerequisites

- Python 3.10+ with NumPy, SciPy, pytest installed
- PySimSAR repository checked out on `004-fix-open-issues` branch

## Verify Current Failures

Run the failing tests to confirm the issues exist:

```bash
# Issue 1: SecondOrderMoCo AttributeError
python -m pytest tests/integration/test_scenarios.py -k "moco2" -x

# Issue 2: PGA estimate_phase_error NotImplementedError
python -m pytest tests/integration/test_moco.py -k "test_estimate_phase_error_shape" -x

# Issue 3: Fragile autofocus tests
python -m pytest tests/integration/test_moco.py -k "does_not_degrade" -x

# Issue 4: Spotlight MoCo PNR threshold
python -m pytest tests/integration/test_scenarios.py -k "spotlight_omegak_dryden_moco1" -x
```

## Verify Fixes

After implementation, all tests should pass:

```bash
# Full integration test suite
python -m pytest tests/integration/ -v

# Specific fix verification
python -m pytest tests/integration/test_scenarios.py tests/integration/test_moco.py -v
```

## Key Files to Review

1. `pySimSAR/algorithms/moco/first_order.py` — extracted helper functions
2. `pySimSAR/algorithms/moco/second_order.py` — uses shared helpers
3. `pySimSAR/pipeline/runner.py` — calls shared helpers directly
4. `pySimSAR/algorithms/autofocus/pga.py` — new `estimate_phase_error()`
5. `tests/integration/test_moco.py` — updated tolerances
6. `tests/integration/test_scenarios.py` — updated PNR threshold
