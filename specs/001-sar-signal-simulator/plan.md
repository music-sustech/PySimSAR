# Implementation Plan: SAR Raw Signal Simulator

**Branch**: `001-sar-signal-simulator` | **Date**: 2026-03-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-sar-signal-simulator/spec.md`

## Summary

Build a Python library and desktop GUI for simulating airborne/UAV SAR
raw echo signals in a 3D target scene, with realistic motion perturbation,
GPS/RTK and IMU sensor error modeling, modular image formation and motion
compensation algorithms, image geocoding/rectification, polarimetric
decomposition, modular waveforms, and a common data format. All
processing modules follow plugin interfaces for extensibility.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: NumPy, SciPy, PyQt6, matplotlib, pyqtgraph,
h5py (for HDF5 data format), pyopengl (for 3D scene visualization)
**Storage**: HDF5 files via h5py (self-describing, supports large arrays,
metadata, and hierarchical structure)
**Testing**: pytest, pytest-qt (for GUI tests)
**Target Platform**: Windows, Linux, macOS (cross-platform desktop)
**Project Type**: Library + Desktop Application
**Performance Goals**: 1024x1024 scene pipeline < 60s on modern desktop;
vectorized NumPy/SciPy throughout
**Constraints**: Memory-aware for large 2D FFTs; deterministic with
controllable random seeds
**Scale/Scope**: 10 plugin interface types, 19 default algorithm
modules, 1 GUI application with 4+ visualization panels

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Scientific Correctness | PASS | Spec requires phase accuracy within 0.01 rad, impulse response within 5% of theory, documented math models |
| II. Library-First | PASS | FR-013 requires all GUI functionality accessible via Python API; GUI is US8 (P3), library is P1/P2 |
| III. Test-First (TDD) | PASS | Acceptance scenarios define testable criteria for every user story; pytest specified |
| IV. Performance-Aware | PASS | NumPy/SciPy vectorized ops specified in constitution; SC-006 sets 60s pipeline target |
| V. Reproducibility | PASS | FR-014 requires save/load configs; SC-004 requires bit-exact round-trip; controllable seeds in assumptions |
| VI. Modularization | PASS | FR-009, FR-019, FR-003a all require plugin interfaces; SC-003 requires zero-change integration |

All gates pass. Proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-sar-signal-simulator/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── waveform.md
│   ├── image-formation.md
│   ├── motion-compensation.md
│   ├── image-transformation.md
│   ├── polarimetric-decomposition.md
│   ├── autofocus.md
│   ├── clutter-model.md
│   └── data-format.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
pySimSAR/                    # Main Python package
├── __init__.py
├── core/                    # Core data structures and utilities
│   ├── __init__.py
│   ├── scene.py             # Scene, Target (point + distributed)
│   ├── radar.py             # Radar parameters, antenna pattern
│   ├── platform.py          # Platform trajectory, motion model
│   ├── coordinates.py       # ENU coordinate system, geo transforms
│   └── types.py             # Shared type definitions, enums
│
├── clutter/                 # Modular clutter/texture model plugins
│   ├── __init__.py
│   ├── base.py              # ClutterModel ABC interface
│   ├── uniform.py           # Default: uniform reflectivity model
│   └── registry.py          # Clutter model discovery and registration
│
├── waveforms/               # Modular waveform plugins
│   ├── __init__.py
│   ├── base.py              # Waveform ABC interface
│   ├── lfm.py               # Linear FM chirp (pulsed)
│   ├── fmcw.py              # FMCW waveform (continuous)
│   ├── phase_noise.py       # PhaseNoiseModel ABC + CompositePSD
│   └── registry.py          # Waveform + phase noise registration
│
├── simulation/              # Raw signal generation engine
│   ├── __init__.py
│   ├── engine.py            # Main simulation orchestrator
│   ├── signal.py            # Echo signal computation
│   └── antenna.py           # Antenna pattern and beam modeling
│
├── sensors/                 # Navigation sensor models
│   ├── __init__.py
│   ├── gps.py               # GPSSensor config + GPSErrorModel ABC
│   ├── gps_gaussian.py      # Default: simple Gaussian noise model
│   ├── imu.py               # IMUSensor config + IMUErrorModel ABC
│   ├── imu_white_noise.py   # Default: white noise model
│   ├── registry.py          # Sensor error model registration
│   └── nav_filter.py        # Navigation data fusion (future)
│
├── motion/                  # Motion perturbation models
│   ├── __init__.py
│   ├── perturbation.py      # Turbulence, vibration, drift models
│   └── trajectory.py        # Trajectory generation (ideal + perturbed)
│
├── algorithms/              # Modular processing algorithms
│   ├── __init__.py
│   ├── base.py              # ABC interfaces for all algorithm types
│   ├── registry.py          # Algorithm discovery and registration
│   │
│   ├── image_formation/     # Image formation plugins
│   │   ├── __init__.py
│   │   ├── range_doppler.py
│   │   ├── chirp_scaling.py
│   │   └── omega_k.py
│   │
│   ├── moco/                # Motion compensation plugins
│   │   ├── __init__.py
│   │   ├── first_order.py
│   │   └── second_order.py
│   │
│   ├── autofocus/           # Autofocus plugins
│   │   ├── __init__.py
│   │   ├── pga.py           # Phase Gradient Autofocus
│   │   ├── mda.py           # Map Drift Autofocus
│   │   ├── min_entropy.py   # Minimum Entropy Autofocus
│   │   └── ppp.py           # Prominent Point Processing
│   │
│   ├── geocoding/           # Image transformation plugins
│   │   ├── __init__.py
│   │   ├── slant_to_ground.py
│   │   └── georeferencing.py
│   │
│   └── polarimetry/         # Polarimetric decomposition plugins
│       ├── __init__.py
│       ├── pauli.py
│       ├── freeman_durden.py
│       ├── yamaguchi.py
│       └── cloude_pottier.py
│
├── core/                    # (continued)
│   └── rcs_model.py         # RCSModel ABC + StaticRCS
│
├── io/                      # Data format I/O
│   ├── __init__.py
│   ├── hdf5_format.py       # HDF5 read/write for all data types
│   ├── config.py            # Simulation config serialization
│   └── parameter_set.py     # Parameter set load/save ($ref/$data)
│
├── presets/                 # Shipped default parameter presets
│   ├── antennas/            # flat, sinc, gaussian antenna JSONs
│   ├── waveforms/           # LFM, FMCW preset JSONs
│   ├── sensors/             # GPS, IMU preset JSONs
│   └── platforms/           # Airborne, UAV preset JSONs
│
├── tools/                   # CLI utilities
│   ├── __init__.py
│   └── view_array.py        # Binary array visualization tool
│
├── pipeline/                # Processing pipeline orchestration
│   ├── __init__.py
│   └── runner.py            # Pipeline assembly and execution
│
└── gui/                     # PyQt6 desktop application
    ├── __init__.py
    ├── app.py               # Main application window
    ├── panels/
    │   ├── __init__.py
    │   ├── scene_3d.py      # 3D target scene viewer
    │   ├── trajectory.py    # Flight path visualization
    │   ├── beam_animation.py # Radar beam sweep animation
    │   └── image_viewer.py  # SAR image display
    ├── widgets/
    │   ├── __init__.py
    │   ├── param_editor.py  # Parameter configuration forms
    │   └── algorithm_selector.py # Algorithm selection UI
    └── controllers/
        ├── __init__.py
        └── simulation_ctrl.py # Simulation run controller

tests/
├── conftest.py              # Shared fixtures (scenes, radar configs)
├── unit/
│   ├── test_scene.py
│   ├── test_radar.py
│   ├── test_platform.py
│   ├── test_waveforms.py
│   ├── test_gps.py
│   ├── test_imu.py
│   ├── test_signal.py
│   ├── test_io.py
│   ├── test_parameter_set.py   # Parameter set I/O unit tests
│   ├── test_rcs_model.py       # RCS model unit tests
│   └── test_view_array.py      # Visualization tool tests
├── integration/
│   ├── test_simulation_pipeline.py
│   ├── test_image_formation.py
│   ├── test_moco.py
│   ├── test_geocoding.py
│   ├── test_polarimetry.py
│   └── test_golden.py          # Golden reference test runner
├── golden/                     # Golden reference test case directories
│   ├── single_point_stripmap/  # Case 1: simplest end-to-end
│   ├── multi_target_spotlight/ # Case 2: multi-target spotlight
│   └── motion_moco_autofocus/  # Case 3: motion + MoCo + autofocus
├── contract/
│   ├── test_waveform_interface.py
│   ├── test_algorithm_interface.py
│   └── test_data_format.py
└── gui/
    └── test_app.py
```

**Structure Decision**: Single project layout. The library (`pySimSAR/`)
and GUI (`pySimSAR/gui/`) live in the same package, with the GUI
importing from the library but never the reverse (Library-First principle).
Algorithm plugins are organized by type under `pySimSAR/algorithms/`.

## Complexity Tracking

No constitution violations. No complexity justification needed.
