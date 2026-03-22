# Data Model: Fix Open Issues

**Branch**: `004-fix-open-issues` | **Date**: 2026-03-22

## Overview

This feature introduces no new data entities. All changes are to method signatures, call sites, and test assertions within the existing class hierarchy.

## Modified Interfaces

### Navigation Helper Functions (extracted from FirstOrderMoCo)

Three static methods are extracted to module-level functions. Signatures remain identical:

- `align_nav_positions(n_az, prf, nav_data) → ndarray(n_az, 3)`
- `smooth_positions(positions) → ndarray(N, 3)`
- `fit_straight_line(positions) → ndarray(N, 3)`

### PGA estimate_phase_error (new override)

New method on `PhaseGradientAutofocus`:

- `estimate_phase_error(phase_history: PhaseHistoryData) → ndarray(n_azimuth,)`
- Internally performs azimuth FFT then delegates to `_estimate_phase_error_from_image()`
- Return type and shape matches all other autofocus implementations

## Existing Entities (unchanged)

- `MotionCompensationAlgorithm` — abstract base, no changes
- `AutofocusAlgorithm` — abstract base, no changes
- `FirstOrderMoCo` — updated to use extracted functions, behavior unchanged
- `SecondOrderMoCo` — updated to use extracted functions, behavior unchanged
- `PhaseHistoryData` — unchanged
- `RawData` — unchanged
- `NavigationData` — unchanged
