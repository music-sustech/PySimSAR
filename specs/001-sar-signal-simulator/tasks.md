# Tasks: SAR Raw Signal Simulator

**Input**: Design documents from `/specs/001-sar-signal-simulator/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md, quickstart.md

**Tests**: Included per constitution (Principle III: Test-First TDD).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Package**: `pySimSAR/` at repository root
- **Tests**: `tests/` at repository root

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create project structure, configure dependencies, and establish shared infrastructure.

- [x] T001 Create project directory structure per plan.md layout (`pySimSAR/`, `tests/`, and all subdirectories)
- [x] T002 Initialize Python package with `pyproject.toml` (Python 3.10+, dependencies: numpy, scipy, PyQt6, matplotlib, pyqtgraph, h5py, pyopengl, pytest, pytest-qt)
- [x] T003 [P] Configure linting and formatting (ruff) in `pyproject.toml`
- [x] T004 [P] Create shared type definitions and enums in `pySimSAR/core/types.py` (PolarizationMode, SARMode, LookSide, RampType enums)
- [x] T005 [P] Implement ENU coordinate system and WGS84 geodetic transforms in `pySimSAR/core/coordinates.py`
- [x] T006 [P] Create test fixtures (shared scenes, radar configs, platform configs) in `tests/conftest.py`

**Checkpoint**: Project builds, imports, and pytest runs with no errors.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented.

**CRITICAL**: No user story work can begin until this phase is complete.

- [x] T007 Implement AlgorithmRegistry (generic registry for all plugin types) in `pySimSAR/algorithms/registry.py`
- [x] T008 [P] Implement WaveformRegistry and PhaseNoiseRegistry in `pySimSAR/waveforms/registry.py`
- [x] T009 [P] Implement ClutterModelRegistry in `pySimSAR/clutter/registry.py`
- [x] T010 [P] Implement SensorErrorModelRegistry in `pySimSAR/sensors/registry.py`
- [x] T011 Implement Waveform ABC (generate, range_compress, duty_cycle, bandwidth, window, phase_noise) in `pySimSAR/waveforms/base.py`
- [x] T012 [P] Implement PhaseNoiseModel ABC in `pySimSAR/waveforms/phase_noise.py`
- [x] T013 [P] Implement ClutterModel ABC in `pySimSAR/clutter/base.py`
- [x] T014 [P] Implement GPSErrorModel ABC in `pySimSAR/sensors/gps.py`
- [x] T015 [P] Implement IMUErrorModel ABC in `pySimSAR/sensors/imu.py`
- [x] T016 Implement ImageFormationAlgorithm ABC (process, range_compress, azimuth_compress, supported_modes) in `pySimSAR/algorithms/base.py`
- [x] T017 [P] Implement MotionCompensationAlgorithm ABC in `pySimSAR/algorithms/base.py`
- [x] T018 [P] Implement AutofocusAlgorithm ABC (focus, estimate_phase_error) in `pySimSAR/algorithms/base.py`
- [x] T019 [P] Implement ImageTransformationAlgorithm ABC in `pySimSAR/algorithms/base.py`
- [x] T020 [P] Implement PolarimetricDecomposition ABC in `pySimSAR/algorithms/base.py`
- [x] T021 Implement contract tests for Waveform interface in `tests/contract/test_waveform_interface.py`
- [x] T022 [P] Implement contract tests for all algorithm ABCs (including plugin extensibility test: register a mock algorithm, verify it appears in registry and is callable without modifying existing code — SC-003) in `tests/contract/test_algorithm_interface.py`

**Checkpoint**: All ABCs defined, registries working, contract tests passing. User story implementation can begin.

---

## Phase 3: User Story 1 — Simulate SAR Raw Signal from 3D Scene (Priority: P1) MVP

**Goal**: Generate raw SAR echo data for point and distributed targets in a 3D scene with configurable radar parameters and polarimetric support.

**Independent Test**: Generate echo data for a known point target grid and verify phase history matches analytical range equation within 0.01 radians.

### Tests for User Story 1

- [x] T023 [P] [US1] Unit test for PointTarget and DistributedTarget in `tests/unit/test_scene.py`
- [x] T024 [P] [US1] Unit test for Radar (carrier_freq, prf, noise params, derived properties) in `tests/unit/test_radar.py`
- [x] T025 [P] [US1] Unit test for AntennaPattern (2D gain lookup, beamwidth) in `tests/unit/test_radar.py`
- [x] T026 [P] [US1] Unit test for LFMWaveform (generate, range_compress, duty_cycle derivation) in `tests/unit/test_waveforms.py`
- [x] T027 [P] [US1] Unit test for FMCWWaveform (ramp types, dechirp, triangle processing) in `tests/unit/test_waveforms.py`
- [x] T028 [P] [US1] Unit test for CompositePSDPhaseNoise (PSD shaping, generation) in `tests/unit/test_waveforms.py`
- [x] T029 [P] [US1] Unit test for UniformClutter in `tests/unit/test_scene.py`
- [x] T030 [P] [US1] Unit test for echo signal computation (single point target phase accuracy) in `tests/unit/test_signal.py`
- [x] T031 [US1] Integration test for full simulation pipeline (point target scene → raw data → verify phase) in `tests/integration/test_simulation_pipeline.py`

### Implementation for User Story 1

- [x] T032 [P] [US1] Implement PointTarget (position, rcs, velocity) in `pySimSAR/core/scene.py`
- [x] T033 [P] [US1] Implement DistributedTarget (grid, reflectivity, scattering_matrix, elevation, clutter_model) in `pySimSAR/core/scene.py`
- [x] T034 [P] [US1] Implement Scene (origin, target collections, add_target) in `pySimSAR/core/scene.py`
- [x] T035 [P] [US1] Implement UniformClutter in `pySimSAR/clutter/uniform.py`
- [x] T036 [P] [US1] Implement AntennaPattern (2D pattern lookup, gain calculation) in `pySimSAR/core/radar.py`
- [x] T037 [US1] Implement Radar (carrier_freq, prf, power, noise_figure, system_losses, ref_temp, look_side, depression_angle, squint_angle, derived properties) in `pySimSAR/core/radar.py`
- [x] T038 [US1] Implement LFMWaveform (chirp generation, matched filter range compression) in `pySimSAR/waveforms/lfm.py`
- [x] T039 [US1] Implement FMCWWaveform (up/down/triangle ramps, duty cycle, dechirp + FFT range compression) in `pySimSAR/waveforms/fmcw.py`
- [x] T040 [US1] Implement CompositePSDPhaseNoise (multi-slope PSD generation, frequency shaping, IFFT) in `pySimSAR/waveforms/phase_noise.py`
- [x] T041 [US1] Implement antenna beam modeling for stripmap mode (fixed broadside/squint direction, two-way gain computation) in `pySimSAR/simulation/antenna.py`
- [x] T042 [US1] Implement spotlight beam steering (per-pulse antenna pointing to track fixed scene center, wider Doppler bandwidth handling) in `pySimSAR/simulation/antenna.py`
- [x] T043 [US1] Implement scan-SAR beam steering (cyclic elevation sweep across sub-swaths, burst-mode pulse scheduling, scalloping modeling) in `pySimSAR/simulation/antenna.py`
- [x] T044 [US1] Implement echo signal computation (per-target echo with radar range equation, phase noise, target velocity, R⁴ path loss, mode-aware beam direction per pulse) in `pySimSAR/simulation/signal.py`
- [x] T045 [US1] Implement SimulationEngine orchestrator (pulse loop, target summation, receiver noise, polarimetric channels, SAR mode dispatch) in `pySimSAR/simulation/engine.py`
- [x] T046 [US1] Implement SimulationConfig (validation, state transitions) in `pySimSAR/io/config.py`

**Checkpoint**: Can simulate point target and distributed target scenes in stripmap, spotlight, and scan-SAR modes. Raw echo data with correct phase, amplitude (range equation), and noise. LFM and FMCW waveforms working. Phase noise and range correlation modeled.

---

## Phase 4: User Story 2 — Model Airborne/UAV Motion and Sensor Errors (Priority: P1)

**Goal**: Generate realistic perturbed flight trajectories and navigation sensor measurements with configurable error characteristics.

**Independent Test**: Generate a perturbed trajectory and verify sensor measurement error RMS matches configured accuracy within 10%.

### Tests for User Story 2

- [x] T047 [P] [US2] Unit test for Platform (nominal path generation) in `tests/unit/test_platform.py`
- [x] T048 [P] [US2] Unit test for DrydenTurbulence (spectral characteristics) in `tests/unit/test_platform.py`
- [x] T049 [P] [US2] Unit test for Trajectory (ideal vs perturbed generation) in `tests/unit/test_platform.py`
- [x] T050 [P] [US2] Unit test for GaussianGPSError (RMS accuracy, outage handling) in `tests/unit/test_gps.py`
- [x] T051 [P] [US2] Unit test for WhiteNoiseIMUError (noise density matching) in `tests/unit/test_imu.py`

### Implementation for User Story 2

- [x] T052 [P] [US2] Implement Platform (velocity, altitude, heading, start_position, sensor attachment) in `pySimSAR/core/platform.py`
- [x] T053 [P] [US2] Implement Trajectory (time, position, velocity, attitude arrays) in `pySimSAR/motion/trajectory.py`
- [x] T054 [US2] Implement ideal trajectory generation (straight-line from Platform params) in `pySimSAR/motion/trajectory.py`
- [x] T055 [US2] Implement MotionPerturbation and DrydenTurbulence (MIL-HDBK-1797 transfer functions, white noise filtering) in `pySimSAR/motion/perturbation.py`
- [x] T056 [US2] Implement perturbed trajectory generation (ideal + perturbation → true trajectory) in `pySimSAR/motion/trajectory.py`
- [x] T057 [P] [US2] Implement GPSSensor config and GaussianGPSError (additive Gaussian noise, outage intervals) in `pySimSAR/sensors/gps.py` and `pySimSAR/sensors/gps_gaussian.py`
- [x] T058 [P] [US2] Implement IMUSensor config and WhiteNoiseIMUError (additive white noise on accel/gyro) in `pySimSAR/sensors/imu.py` and `pySimSAR/sensors/imu_white_noise.py`
- [x] T059 [US2] Implement NavigationData generation (sensors sample true trajectory → noisy measurements) in `pySimSAR/sensors/gps.py` and `pySimSAR/sensors/imu.py`
- [x] T060 [US2] Integrate motion and sensors with SimulationEngine (perturbed trajectory used for echo computation, nav data stored in result) in `pySimSAR/simulation/engine.py`

**Checkpoint**: Platform generates ideal + perturbed trajectories. GPS and IMU sensors produce noisy measurements. SimulationEngine uses perturbed trajectory for signal generation.

---

## Phase 5: User Story 3 — Standard Data Format for Interoperability (Priority: P1)

**Goal**: HDF5-based data format for all simulation artifacts with self-describing metadata and bit-exact round-trip fidelity.

**Independent Test**: Save and reload all data types, verify bit-exact round-trip.

### Tests for User Story 3

- [x] T061 [P] [US3] Unit test for HDF5 write/read of RawData in `tests/unit/test_io.py`
- [x] T062 [P] [US3] Unit test for HDF5 write/read of NavigationData and Trajectory in `tests/unit/test_io.py`
- [x] T063 [P] [US3] Unit test for HDF5 write/read of SARImage in `tests/unit/test_io.py`
- [x] T064 [P] [US3] Unit test for SimulationConfig and ProcessingConfig JSON serialization in `tests/unit/test_io.py`
- [x] T065 [US3] Contract test for data format (round-trip fidelity, metadata completeness) in `tests/contract/test_data_format.py`

### Implementation for User Story 3

- [x] T066 [US3] Implement RawData entity (echo matrix, channel, sample_rate, radar/trajectory refs) in `pySimSAR/core/types.py`
- [x] T067 [US3] Implement NavigationData entity in `pySimSAR/core/types.py`
- [x] T068 [US3] Implement PhaseHistoryData entity in `pySimSAR/core/types.py`
- [x] T069 [US3] Implement SARImage entity in `pySimSAR/core/types.py`
- [x] T070 [US3] Implement HDF5 writer (raw_data, navigation, trajectory, images, config groups per data-format contract) in `pySimSAR/io/hdf5_format.py`
- [x] T071 [US3] Implement HDF5 reader (load any data type from HDF5, reconstruct entities) in `pySimSAR/io/hdf5_format.py`
- [x] T072 [US3] Implement ProcessingConfig entity and JSON serialization in `pySimSAR/io/config.py`
- [x] T073 [US3] Implement SimulationConfig JSON serialization in `pySimSAR/io/config.py`
- [x] T074 [US3] Add save/load convenience methods to RawData, SARImage, and SimulationResult in `pySimSAR/core/types.py`

**Checkpoint**: All data types serialize to HDF5 and round-trip bit-exactly. Configs serialize to JSON. Data format contract tests pass.

---

## Phase 6: User Story 4 — Form SAR Image with Modular Algorithms (Priority: P2)

**Goal**: Focused SAR image formation from raw data using swappable algorithms with two-step interface (range compress → azimuth compress).

**Independent Test**: Form image from point-target data, measure impulse response (resolution, PSLR, ISLR) against theoretical values.

### Tests for User Story 4

- [x] T075 [P] [US4] Integration test for Range-Doppler algorithm (point target impulse response) in `tests/integration/test_image_formation.py`
- [x] T076 [P] [US4] Integration test for Chirp Scaling algorithm in `tests/integration/test_image_formation.py`
- [x] T077 [P] [US4] Integration test for Omega-K algorithm in `tests/integration/test_image_formation.py`
- [x] T078 [US4] Integration test for two-step interface (range_compress → PhaseHistoryData → azimuth_compress) in `tests/integration/test_image_formation.py`

### Implementation for User Story 4

- [x] T079 [US4] Implement Range-Doppler algorithm (range_compress, azimuth_compress, process, supported_modes) in `pySimSAR/algorithms/image_formation/range_doppler.py`
- [x] T080 [US4] Implement Chirp Scaling algorithm in `pySimSAR/algorithms/image_formation/chirp_scaling.py`
- [x] T081 [US4] Implement Omega-K algorithm (Stolt interpolation) in `pySimSAR/algorithms/image_formation/omega_k.py`
- [x] T082 [US4] Register all image formation algorithms in `pySimSAR/algorithms/image_formation/__init__.py`

**Checkpoint**: Three image formation algorithms produce focused images. Two-step interface works. Impulse response matches theory within 5%.

---

## Phase 7: User Story 5 — Apply Motion Compensation with Modular Algorithms (Priority: P2)

**Goal**: Correct platform motion errors in raw data using swappable MoCo algorithms.

**Independent Test**: Apply MoCo to data with known motion errors, measure residual phase error reduction.

### Tests for User Story 5

- [ ] T083 [P] [US5] Integration test for FirstOrderMoCo (phase error reduction) in `tests/integration/test_moco.py`
- [ ] T084 [P] [US5] Integration test for SecondOrderMoCo in `tests/integration/test_moco.py`

### Implementation for User Story 5

- [ ] T085 [US5] Implement FirstOrderMoCo (bulk range-dependent phase correction to scene center) in `pySimSAR/algorithms/moco/first_order.py`
- [ ] T086 [US5] Implement SecondOrderMoCo (range-dependent + aperture-dependent correction) in `pySimSAR/algorithms/moco/second_order.py`
- [ ] T087 [US5] Register MoCo algorithms in `pySimSAR/algorithms/moco/__init__.py`

**Checkpoint**: MoCo reduces motion-induced phase errors. Both first-order and second-order working.

---

## Phase 8: User Story 5a — Autofocus for Residual Phase Error Correction (Priority: P2)

**Goal**: Data-driven autofocus algorithms that correct residual phase errors after MoCo, operating on PhaseHistoryData.

**Independent Test**: Inject known residual phase errors, apply autofocus, measure improvement in focus metrics.

### Tests for User Story 5a

- [ ] T088 [P] [US5a] Integration test for PGA autofocus (convergence, phase error estimation) in `tests/integration/test_moco.py`
- [ ] T089 [P] [US5a] Integration test for MDA autofocus in `tests/integration/test_moco.py`
- [ ] T090 [P] [US5a] Integration test for MinimumEntropy autofocus in `tests/integration/test_moco.py`
- [ ] T091 [P] [US5a] Integration test for PPP autofocus in `tests/integration/test_moco.py`

### Implementation for User Story 5a

- [ ] T092 [US5a] Implement PhaseGradientAutofocus (dominant scatterer selection, phase gradient estimation, iterative correction) in `pySimSAR/algorithms/autofocus/pga.py`
- [ ] T093 [P] [US5a] Implement MapDriftAutofocus (sub-aperture splitting, drift measurement, low-order phase estimation) in `pySimSAR/algorithms/autofocus/mda.py`
- [ ] T094 [P] [US5a] Implement MinimumEntropyAutofocus (entropy optimization, polynomial phase model) in `pySimSAR/algorithms/autofocus/min_entropy.py`
- [ ] T095 [P] [US5a] Implement ProminentPointProcessing (scatterer identification, phase history extraction, error estimation) in `pySimSAR/algorithms/autofocus/ppp.py`
- [ ] T096 [US5a] Register all autofocus algorithms in `pySimSAR/algorithms/autofocus/__init__.py`

**Checkpoint**: All 4 autofocus algorithms produce measurably sharper images. PGA converges on known phase errors within threshold.

---

## Phase 9: User Story 6 — Image Geocoding and Rectification (Priority: P2)

**Goal**: Transform SAR images from radar geometry to ground-range or geographic coordinates.

**Independent Test**: Transform point-target image from slant-range to ground-range, verify target positions match known coordinates.

### Tests for User Story 6

- [ ] T097 [P] [US6] Integration test for SlantToGroundRange (spatial scaling correctness) in `tests/integration/test_geocoding.py`
- [ ] T098 [P] [US6] Integration test for Georeferencing (lat/lon accuracy) in `tests/integration/test_geocoding.py`

### Implementation for User Story 6

- [ ] T099 [US6] Implement SlantToGroundRange (slant-range → ground-range projection, flat earth) in `pySimSAR/algorithms/geocoding/slant_to_ground.py`
- [ ] T100 [US6] Implement Georeferencing (pixel → lat/lon mapping using trajectory and radar geometry) in `pySimSAR/algorithms/geocoding/georeferencing.py`
- [ ] T101 [US6] Register geocoding algorithms in `pySimSAR/algorithms/geocoding/__init__.py`

**Checkpoint**: Images transform correctly from slant-range to ground-range and geographic coordinates.

---

## Phase 10: User Story 7 — Polarimetric Decomposition (Priority: P2)

**Goal**: Extract scattering mechanism information from quad-pol SAR data using modular decomposition algorithms.

**Independent Test**: Simulate canonical scattering scenarios, verify decomposition correctly identifies dominant mechanisms.

### Tests for User Story 7

- [ ] T102 [P] [US7] Integration test for Pauli decomposition (component verification) in `tests/integration/test_polarimetry.py`
- [ ] T103 [P] [US7] Integration test for Freeman-Durden (power conservation) in `tests/integration/test_polarimetry.py`
- [ ] T104 [P] [US7] Integration test for Yamaguchi (4-component) in `tests/integration/test_polarimetry.py`
- [ ] T105 [P] [US7] Integration test for Cloude-Pottier (H/A/Alpha) in `tests/integration/test_polarimetry.py`

### Implementation for User Story 7

- [ ] T106 [P] [US7] Implement PauliDecomposition (surface, double-bounce, volume from S-matrix) in `pySimSAR/algorithms/polarimetry/pauli.py`
- [ ] T107 [P] [US7] Implement FreemanDurdenDecomposition (model-based 3-component) in `pySimSAR/algorithms/polarimetry/freeman_durden.py`
- [ ] T108 [P] [US7] Implement YamaguchiDecomposition (4-component with helix) in `pySimSAR/algorithms/polarimetry/yamaguchi.py`
- [ ] T109 [P] [US7] Implement CloudePottierDecomposition (eigenvalue decomposition, H/A/Alpha) in `pySimSAR/algorithms/polarimetry/cloude_pottier.py`
- [ ] T110 [US7] Register all polarimetry algorithms in `pySimSAR/algorithms/polarimetry/__init__.py`

**Checkpoint**: All 4 decomposition methods produce correct results for canonical scattering scenarios. Power conservation verified.

---

## Phase 11: User Story 8 — Processing Pipeline and Project Model (Priority: P2)

**Goal**: Pipeline orchestrator that chains MoCo → range compression → autofocus → azimuth compression → geocoding → polsar, driven by ProcessingConfig. Project model supports simulation and import workflows.

**Independent Test**: Run full pipeline via ProcessingConfig, re-process same data with different config.

### Tests for User Story 8

- [ ] T111 [US8] Integration test for PipelineRunner (full chain, config-driven) in `tests/integration/test_simulation_pipeline.py`
- [ ] T112 [US8] Integration test for re-processing (same raw data, different ProcessingConfig) in `tests/integration/test_simulation_pipeline.py`

### Implementation for User Story 8

- [ ] T113 [US8] Implement PipelineRunner (sequential execution per ProcessingConfig, optional step skipping) in `pySimSAR/pipeline/runner.py`
- [ ] T114 [US8] Implement data import (load external HDF5 as RawData + NavigationData for processing-only workflow) in `pySimSAR/io/hdf5_format.py`

**Checkpoint**: Full pipeline runs end-to-end via config. Re-processing works without re-simulation. Data import works.

---

## Phase 12: User Story 9 — Interactive GUI for Simulation and Visualization (Priority: P3)

**Goal**: Desktop GUI for configuring simulation, running pipeline, and visualizing 3D scene, trajectory, beam animation, and SAR images.

**Independent Test**: Launch GUI, configure point-target scene, run pipeline, verify all panels display correct data.

### Tests for User Story 9

- [ ] T115 [US9] GUI smoke test (launch, configure, run basic simulation) in `tests/gui/test_app.py`

### Implementation for User Story 9

- [ ] T116 [US9] Implement main application window (menu, toolbar, panel layout) in `pySimSAR/gui/app.py`
- [ ] T117 [P] [US9] Implement parameter editor widgets (radar, waveform, platform, scene config forms with validation) in `pySimSAR/gui/widgets/param_editor.py`
- [ ] T118 [P] [US9] Implement algorithm selector widget (dropdowns for MoCo, image formation, autofocus, geocoding, polsar from registries) in `pySimSAR/gui/widgets/algorithm_selector.py`
- [ ] T119 [P] [US9] Implement 3D scene viewer panel (point targets as scatter, distributed targets as mesh, pyqtgraph GLViewWidget) in `pySimSAR/gui/panels/scene_3d.py`
- [ ] T120 [P] [US9] Implement trajectory viewer panel (ideal + perturbed paths in 3D, rotate/zoom) in `pySimSAR/gui/panels/trajectory.py`
- [ ] T121 [P] [US9] Implement beam animation panel (radar footprint sweep along trajectory, playback controls) in `pySimSAR/gui/panels/beam_animation.py`
- [ ] T122 [P] [US9] Implement SAR image viewer panel (matplotlib display, colormap, dynamic range, zoom) in `pySimSAR/gui/panels/image_viewer.py`
- [ ] T123 [US9] Implement simulation controller (run simulation in background thread, progress reporting, cancellation) in `pySimSAR/gui/controllers/simulation_ctrl.py`
- [ ] T124 [US9] Implement project model (create new simulation project, import existing HDF5, save/load project state) in `pySimSAR/gui/controllers/simulation_ctrl.py`
- [ ] T125 [US9] Wire all panels and controllers to main window (signal/slot connections, data flow) in `pySimSAR/gui/app.py`

**Checkpoint**: GUI launches, parameters configurable, simulation runs with progress, all 4 visualization panels display correct data. Projects can be created from simulation or data import.

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories.

- [ ] T126 [P] Run full validation of quickstart.md examples end-to-end
- [ ] T127 [P] Performance profiling of simulation engine for 1024×1024 scene (SC-006: < 60s target)
- [ ] T128 [P] Memory estimation and warning for large simulations (edge case from spec)
- [ ] T129 Code cleanup, docstrings for all public APIs
- [ ] T130 SAR mode validation (stripmap/spotlight/scanmar compatibility checks across waveform + algorithm)
- [ ] T131 [P] Polarimetric input validation (quad-pol channel checks before decomposition)
- [ ] T132 Validate API parity: verify every GUI action (configure, run, visualize, import) has a corresponding Python API call (FR-013)
- [ ] T133 Final integration test: full pipeline from scene definition through GUI to geocoded polarimetric image

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Phase 2 — signal generation foundation
- **Phase 4 (US2)**: Depends on Phase 2 — can run in PARALLEL with Phase 3
- **Phase 5 (US3)**: Depends on Phase 3 and Phase 4 (needs RawData + NavData entities)
- **Phase 6 (US4)**: Depends on Phase 3 (needs RawData)
- **Phase 7 (US5)**: Depends on Phase 3 and Phase 4 (needs RawData + NavData)
- **Phase 8 (US5a)**: Depends on Phase 6 (needs two-step image formation)
- **Phase 9 (US6)**: Depends on Phase 6 (needs SARImage)
- **Phase 10 (US7)**: Depends on Phase 6 (needs quad-pol SARImages)
- **Phase 11 (US8)**: Depends on Phases 6-10 (orchestrates all algorithms)
- **Phase 12 (US9)**: Depends on Phase 11 (GUI wraps the pipeline)
- **Phase 13 (Polish)**: Depends on all prior phases

### Parallel Opportunities

- **Phase 3 (US1) and Phase 4 (US2)** can run in parallel after Phase 2
- Within Phase 3: T032-T035 (targets/scene/clutter) parallel with T036-T040 (radar/waveforms)
- Within Phase 4: T057 (GPS) parallel with T058 (IMU)
- Within Phase 6: T079-T081 (3 image formation algorithms) can be parallelized
- Within Phase 8: T093-T095 (MDA, MinEntropy, PPP) parallel after T092 (PGA)
- Within Phase 10: T106-T109 (4 polsar decompositions) fully parallel
- Within Phase 12: T119-T122 (4 GUI panels) fully parallel

### User Story Dependencies

```
Phase 2 (Foundational)
    ├──→ Phase 3 (US1: Signal) ──┬──→ Phase 5 (US3: I/O)
    │                            ├──→ Phase 6 (US4: Image Formation) ──┬──→ Phase 8 (US5a: Autofocus)
    │                            │                                     ├──→ Phase 9 (US6: Geocoding)
    │                            │                                     └──→ Phase 10 (US7: PolSAR)
    └──→ Phase 4 (US2: Motion) ──┼──→ Phase 5 (US3: I/O)
                                 └──→ Phase 7 (US5: MoCo) ──→ Phase 8 (US5a: Autofocus)

All above ──→ Phase 11 (US8: Pipeline) ──→ Phase 12 (US9: GUI) ──→ Phase 13 (Polish)
```

---

## Implementation Strategy

### MVP First (Phase 1-3: Setup + Foundation + US1)

1. Complete Phase 1: Project setup
2. Complete Phase 2: ABCs and registries
3. Complete Phase 3: Raw signal simulation with LFM + FMCW
4. **STOP and VALIDATE**: Point target phase accuracy, distributed targets, polarimetric channels, phase noise, range equation, receiver noise

### Incremental Delivery

1. Phase 1-3 → Signal generation MVP
2. Phase 4 → Motion/sensor modeling (parallel with Phase 3)
3. Phase 5 → Data I/O (save/load everything)
4. Phase 6-8 → Image formation + MoCo + Autofocus
5. Phase 9-10 → Geocoding + PolSAR
6. Phase 11 → Pipeline orchestration
7. Phase 12 → GUI
8. Phase 13 → Polish

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Each user story is independently completable and testable
- Tests written FIRST per TDD (Principle III)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
