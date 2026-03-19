# Implementation Plan: GUI Overhaul

**Branch**: `002-gui-overhaul` | **Date**: 2026-03-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-gui-overhaul/spec.md`

## Summary

Comprehensive GUI restructuring of PySimSAR: replace the flat sidebar with an inline-editing parameter tree (Cadence Virtuoso style), add a live-updating calculated values panel, expose all backend algorithm parameters, add 5 new visualization panels with tiled display, implement project creation and data import wizards, extend HDF5 for full parameter parity with real measurement data support, and introduce a two-tier preset system with user data directory.

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: PyQt6 >= 6.5, pyqtgraph >= 0.13, matplotlib >= 3.7, PyOpenGL >= 3.1, h5py >= 3.8, numpy >= 1.24, scipy >= 1.10
**New Dependencies**: trimesh >= 3.20 (OBJ/STL mesh loading), platformdirs >= 3.0 (cross-platform user data dir)
**Storage**: HDF5 (extended schema v2), JSON project directories, .pysimsar zip archives, user preferences JSON
**Testing**: pytest, pytest-qt
**Target Platform**: Windows 11 (primary), cross-platform compatible
**Project Type**: Desktop application (PyQt6) with library backend
**Performance Goals**: < 200ms parameter change → calculated values update, responsive tree navigation for 80+ parameters
**Constraints**: Constitution II (Library-First) — all computation in library, GUI depends on library. Constitution VI (Modularization) — algorithms as independent modules.
**Scale/Scope**: ~3,650 lines of GUI code to restructure, ~15 new files, ~20 modified files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Scientific Correctness | PASS | SARCalculator formulas documented with references. Calculated values verified against analytical solutions. |
| II. Library-First | PASS | SARCalculator lives in `pySimSAR/core/calculator.py`. HDF5 schema extension in `pySimSAR/io/`. GUI only displays/collects values. |
| III. Test-First (TDD) | PASS | Unit tests for SARCalculator, HDF5 round-trip, archive format. Widget tests via pytest-qt. Golden tests for calculated values. |
| IV. Performance-Aware | PASS | QTreeWidget adequate for 80-100 parameter items. Calculated values update is simple arithmetic (< 1ms). No heavy computation in GUI thread. |
| V. Reproducibility | PASS | Project file formats (JSON, .pysimsar, HDF5) all produce identical parameter state. Complete parameter set stored in every format. |
| VI. Modularization | PASS | New visualization panels as independent classes. Parameter tree widget decoupled from specific parameters. Preset system independent of tree. |

**Post-Phase 1 re-check**: Algorithm parameters are hardcoded in the GUI for this wave (per deferred plugin decision). This is a known deviation from full modularization but is explicitly staged for a future wave with entry-point plugin discovery and enforced `parameter_schema()`.

## Project Structure

### Documentation (this feature)

```text
specs/002-gui-overhaul/
├── plan.md              # This file
├── research.md          # Phase 0 output — technology decisions
├── data-model.md        # Phase 1 output — entity definitions
├── quickstart.md        # Phase 1 output — implementation guide
├── contracts/
│   ├── parameter-tree.md    # Tree widget interface contract
│   ├── calculated-values.md # Calculator and panel contract
│   ├── hdf5-schema.md       # Extended HDF5 schema v2
│   └── project-file.md      # Project directory and archive format
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
pySimSAR/
├── core/
│   └── calculator.py              # NEW: SARCalculator (library layer)
├── assets/
│   ├── models/aircraft.obj        # NEW: Low-poly aircraft 3D model
│   └── icons/                     # NEW: Tree category icons (SVG/PNG)
├── gui/
│   ├── app.py                     # MODIFIED: New layout (tree | viz+calc | statusbar)
│   ├── widgets/
│   │   ├── param_tree.py          # NEW: QTreeWidget with inline editors
│   │   ├── calc_panel.py          # NEW: Calculated values display
│   │   ├── peak_tool.py           # NEW: Find-peak tool + markers
│   │   └── preset_browser.py      # NEW: Two-tier preset browser
│   ├── panels/
│   │   ├── scene_3d.py            # MODIFIED: OBJ model loader
│   │   ├── image_viewer.py        # MODIFIED: Peak tool integration
│   │   ├── phase_history.py       # NEW: Range-compressed waterfall
│   │   ├── range_profile.py       # NEW: Range profile plot
│   │   ├── azimuth_profile.py     # NEW: Azimuth profile plot
│   │   ├── doppler_spectrum.py    # NEW: Doppler spectrum plot
│   │   ├── polarimetry.py         # NEW: Decomposition display
│   │   └── tiled_view.py          # NEW: QSplitter tiled panel manager
│   ├── wizards/
│   │   ├── project_wizard.py      # NEW: Project creation wizard
│   │   └── import_wizard.py       # NEW: HDF5 import wizard
│   └── controllers/
│       └── simulation_ctrl.py     # MODIFIED: Intermediate result capture
├── io/
│   ├── hdf5_format.py             # MODIFIED: Schema v2 with /parameters
│   ├── parameter_set.py           # MODIFIED: Self-contained project save
│   ├── archive.py                 # NEW: .pysimsar zip archive
│   └── user_data.py               # NEW: User data dir + preferences
└── pipeline/
    └── runner.py                  # MODIFIED: Expose intermediate results

tests/
├── unit/
│   ├── test_calculator.py         # NEW: SARCalculator formula tests
│   ├── test_archive.py            # NEW: .pysimsar round-trip
│   ├── test_hdf5_v2.py            # NEW: Extended schema tests
│   └── test_user_data.py          # NEW: Preferences persistence
├── widget/
│   ├── test_param_tree.py         # NEW: Tree widget (pytest-qt)
│   ├── test_calc_panel.py         # NEW: Calculated values panel
│   ├── test_wizards.py            # NEW: Wizard navigation
│   └── test_preset_browser.py     # NEW: Preset CRUD operations
└── golden/
    └── calculated_values/         # NEW: Reference configs + expected values
```

**Structure Decision**: Extends existing single-project layout. New files organized by GUI subsystem (widgets, panels, wizards). Library additions in `core/` and `io/`. No new top-level packages.

## Complexity Tracking

No constitution violations requiring justification. All new dependencies (trimesh, platformdirs) are justified:
- trimesh: Required by FR-015b (OBJ/STL aircraft model). No built-in alternative.
- platformdirs: Required by FR-024a/FR-029 (cross-platform user data directory). Manual path logic would be fragile across Windows/macOS/Linux.
