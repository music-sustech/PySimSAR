# Tasks: Version 0.1 Release Documentation

**Input**: Design documents from `/specs/003-release-docs/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: No test tasks included — this is a documentation deliverable. Validation is covered in the Polish phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize MkDocs project structure, configuration, and shared assets

- [x] T001 Create MkDocs configuration file at mkdocs.yml with Material theme, pymdownx.arithmatex, Mermaid support, and full navigation structure per contracts/doc-outline.md
- [x] T002 Create MathJax configuration file at docs/javascripts/mathjax.js with inline/display math settings per research.md R1
- [x] T003 [P] Create documentation directory structure: docs/, docs/math/, docs/customization/, docs/api/, docs/assets/, docs/examples/
- [x] T004 [P] Add mkdocs-material to project dependencies in pyproject.toml (optional docs extra)
- [x] T005 [P] Add site/ to .gitignore

**Checkpoint**: `mkdocs serve` runs and shows empty site with navigation skeleton

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Home page and core diagrams that all user stories reference

**CRITICAL**: These provide the shared context that documentation chapters link to

- [x] T006 Write project home page at docs/index.md — project description, v0.1 badge, feature highlights, quick links to all sections, installation one-liner
- [x] T007 [P] Create system architecture diagram (Mermaid) showing Scene+Radar+Platform → SimulationEngine → RawData → PipelineRunner → SARImage data flow, to be embedded in docs/architecture.md
- [x] T008 [P] Create processing pipeline diagram (Mermaid) showing MoCo → Range Compression → Autofocus → Azimuth Compression → Geocoding → Polarimetry stages, to be embedded in docs/architecture.md
- [x] T009 [P] Create SAR imaging geometry diagram (PNG) showing antenna, beam footprint, ground swath, slant range, and coordinate system, save to docs/assets/sar-geometry.png

**Checkpoint**: Home page renders with navigation; diagrams ready for embedding

---

## Phase 3: User Story 1 — First-Time User Orientation (Priority: P1) MVP

**Goal**: A new user can install PySimSAR, run their first simulation, and understand the program structure

**Independent Test**: Give docs to a SAR-knowledgeable person with no PySimSAR experience; they complete a full simulation within 30 minutes

### Implementation for User Story 1

- [x] T010 [US1] Write Getting Started guide at docs/getting-started.md — prerequisites (Python 3.10+, OS support), pip install instructions, core vs. GUI dependency distinction, troubleshooting common installation errors
- [x] T011 [US1] Add GUI walkthrough section to docs/getting-started.md — launch GUI, load default_stripmap preset, run simulation, view focused image, save results (with screenshots or descriptive steps)
- [x] T012 [US1] Add headless quickstart section to docs/getting-started.md and save as standalone script at docs/examples/headless_quickstart.py — minimal 10-line Python script that runs a simulation and saves the image without GUI
- [x] T013 [US1] Write Program Organization chapter at docs/architecture.md — package directory tree with one-line descriptions of each module, embed the architecture and pipeline diagrams from T007/T008/T009, explain registry/plugin pattern overview
- [x] T014 [US1] Create runnable example script at docs/examples/quickstart_stripmap.py — end-to-end simulation using default_stripmap preset, validate it runs successfully
- [x] T015 [US1] Add troubleshooting section to docs/getting-started.md — common errors (missing PyQt6 for headless, import errors, preset not found), platform-specific notes (Windows paths)

**Checkpoint**: Getting Started + Architecture chapters complete; quickstart example runs; user can go from install to focused image

---

## Phase 4: User Story 2 — Data Structures and Configuration (Priority: P1)

**Goal**: A SAR engineer can configure custom simulations by understanding all user-facing data types and configuration formats

**Independent Test**: Engineer creates a custom simulation configuration from scratch without reading source code

### Implementation for User Story 2

- [x] T016 [P] [US2] Write Data Structures Reference at docs/data-structures.md — document all enums (SARMode, PolarizationMode, LookSide, RampType, ImageGeometry, SimulationState) with valid values and descriptions
- [x] T017 [US2] Add core type documentation to docs/data-structures.md — SARModeConfig (all fields, valid ranges, mode-specific fields), RawData (fields, array shapes, I/O methods), PhaseHistoryData, SARImage (fields, geometry types, save/load)
- [x] T018 [US2] Add scene and radar type documentation to docs/data-structures.md — PointTarget (position, RCS scalar vs 2x2 matrix, velocity), DistributedTarget (origin, extent, cell_size, reflectivity grid), Scene (container, add methods), Radar (constructor params, derived properties), AntennaPattern (array vs callable, preset types)
- [x] T019 [US2] Add platform and trajectory type documentation to docs/data-structures.md — Platform (velocity, altitude, heading, sensors, perturbation), Trajectory (arrays), NavigationData (sensor measurements, uncertainty covariance)
- [x] T020 [P] [US2] Write Configuration Guide at docs/configuration.md — JSON parameter set format, project file structure (project.json, radar.json, scene.json, waveform.json, antenna.json, sarmode.json, platform.json, processing.json), reproducibility section (seed parameter for deterministic output, configuration serialization for result reproduction)
- [x] T021 [US2] Add preset system documentation to docs/configuration.md — $preset/ paths, shipped presets inventory (default_stripmap), $ref and $data resolution mechanism with examples
- [x] T022 [US2] Add HDF5 format documentation to docs/configuration.md — output file structure (groups: /metadata, /config, /raw_data, /trajectory, /nav_data, /images), dataset shapes and dtypes, compression, how to read with h5py
- [x] T023 [US2] Create runnable example at docs/examples/custom_scene.py — build a multi-target scene with custom radar parameters, run simulation, save to HDF5, validate it runs
- [x] T024 [US2] Add ProcessingConfig documentation to docs/configuration.md — algorithm selection for each pipeline stage (moco, image_formation, autofocus, geocoding, polarimetry), parameter passing, complete JSON example

**Checkpoint**: Data Structures + Configuration chapters complete; custom_scene example runs; engineer can configure any simulation parameter

---

## Phase 5: User Story 3 — Algorithm Mathematical Reference (Priority: P2)

**Goal**: Researchers can understand the mathematical principles behind all 15 algorithms with LaTeX equations and literature references

**Independent Test**: Reader with graduate SAR knowledge can trace each algorithm from documentation to code module and verify equations match references

### Implementation for User Story 3

- [x] T025 [P] [US3] Write Signal Model and Waveforms chapter at docs/math/signal-model.md — SAR geometry and coordinate system, point target range equation $R(\eta)$, transmitted LFM signal model $s_{tx}(t) = \exp(j\pi K_r t^2)$, chirp rate derivation, received echo with delay and Doppler, FMCW dechirp processing model, antenna pattern integration, radar range equation path loss, phase noise model; all in LaTeX with 2-3 derivation steps each; cite Cumming & Wong (2005), Richards (2014), Stove (1992)
- [x] T026 [P] [US3] Write Image Formation chapter at docs/math/image-formation.md — Range-Doppler Algorithm: matched filter range compression, azimuth FFT, RCMC sinc interpolation, azimuth compression with transfer functions; Chirp Scaling Algorithm: chirp scaling function derivation, range-dependent phase multiply, bulk compression, residual correction; Omega-K Algorithm: 2D FFT, Stolt interpolation, reference function; all in LaTeX; cite Cumming & Wong Ch. 6/7/9, Raney et al. (1994), Cafforio et al. (1991)
- [x] T027 [P] [US3] Write Motion Compensation chapter at docs/math/motion-compensation.md — first-order bulk phase correction to scene center, second-order range-dependent correction, phase error model from trajectory deviations, residual phase terms; cite Moreira & Huang (1994), Fornaro (1999)
- [x] T028 [P] [US3] Write Autofocus chapter at docs/math/autofocus.md — PGA: dominant scatterer selection, circular shift, phase gradient estimation, windowed integration, iterative convergence with sharpness guard; MDA: sub-aperture splitting, Doppler centroid estimation, drift fitting; MEA: entropy cost function $H = -\sum p \ln p$, polynomial phase model, gradient descent; PPP: prominent point detection, phase history extraction, least-squares fit; cite Wahl et al. (1994), Bamler & Eineder (1996), Kragh (2006), Eichel et al. (1989)
- [x] T029 [P] [US3] Write Geocoding chapter at docs/math/geocoding.md — flat-earth slant-to-ground range projection geometry, ground range calculation from depression angle, georeferencing pixel-to-lat/lon mapping using trajectory and radar geometry, ENU to geodetic coordinate transforms; cite Cumming & Wong Ch. 12, Schreier (1993)
- [x] T030 [P] [US3] Write Polarimetry chapter at docs/math/polarimetry.md — scattering matrix $[S]$, covariance and coherency matrices $[C]$ and $[T]$; Pauli decomposition: $|S_{HH}+S_{VV}|$, $|S_{HH}-S_{VV}|$, $|2S_{HV}|$ with physical interpretation; Freeman-Durden 3-component model fitting; Yamaguchi 4-component with helix term; Cloude-Pottier eigenvalue decomposition, H/A/Alpha parameters and classification plane; cite Lee & Pottier (2009), Freeman & Durden (1998), Yamaguchi et al. (2005), Cloude & Pottier (1997)
- [x] T031 [US3] Write Notation Table at docs/math/notation.md — complete symbol-to-code-variable mapping organized by domain (geometry, waveform, image formation, motion compensation, autofocus, polarimetry); columns: Symbol (LaTeX), Description, Code Variable, Module path; cover all symbols used in T025-T030

**Checkpoint**: All 7 math pages complete; every algorithm has LaTeX equations, derivation sketches, and literature references; notation table cross-references all symbols

---

## Phase 6: User Story 4 — Customization and Programming Guide (Priority: P2)

**Goal**: Developers can extend PySimSAR with custom algorithms, waveforms, sensors, and script batch simulations

**Independent Test**: Developer implements a new image formation algorithm following the guide without reading existing algorithm source code, within 1 hour

### Implementation for User Story 4

- [x] T032 [P] [US4] Write Scripting Guide at docs/customization/scripting.md — minimal headless simulation example, batch simulation pattern (loop over parameters), custom scene construction from code, accessing raw data and focused images programmatically, saving/loading with HDF5
- [x] T033 [P] [US4] Write Algorithm Extension Guide at docs/customization/algorithms.md — explain AlgorithmRegistry pattern, abstract base classes (ImageFormationAlgorithm, MotionCompensationAlgorithm, AutofocusAlgorithm, ImageTransformationAlgorithm, PolarimetricDecomposition); step-by-step tutorial: subclass ImageFormationAlgorithm, implement process/range_compress/azimuth_compress/supported_modes, add parameter_schema(), register in registry, use in ProcessingConfig; repeat pattern outline for MoCo, autofocus, geocoding, polarimetry
- [x] T034 [P] [US4] Write Waveform Extension Guide at docs/customization/waveforms.md — Waveform base class contract (generate, range_compress, bandwidth, duty_cycle, prf, duration), step-by-step: create custom waveform class, register in waveform_registry, integrate with SimulationEngine; include complete example of a simple pulse waveform
- [x] T035 [P] [US4] Write Sensor Extension Guide at docs/customization/sensors.md — GPSErrorModel and IMUErrorModel interfaces, step-by-step: create custom error model, register in sensor registry, attach to Platform, run simulation with custom navigation errors; include complete example
- [x] T036 [US4] Create runnable example at docs/examples/batch_simulation.py — parameterized batch run over multiple carrier frequencies, save results, validate it runs
- [x] T037 [US4] Create runnable example at docs/examples/custom_algorithm.py — skeleton image formation algorithm that subclasses base, registers, and runs through pipeline, validate it runs

**Checkpoint**: All 4 customization pages complete; batch and custom algorithm examples run; developer can extend any subsystem

---

## Phase 7: User Story 5 — API Reference (Priority: P3)

**Goal**: Hand-written API reference for ~27 key public classes with parameter descriptions, types, and return values

**Independent Test**: 10 random public classes from the codebase each have a corresponding API entry with parameter descriptions

### Implementation for User Story 5

- [x] T038 [P] [US5] Write Core API reference at docs/api/core.md — Radar (constructor, properties, methods), AntennaPattern (constructor, gain method, create_antenna_from_preset), Scene (add_target, iteration), PointTarget (fields), DistributedTarget (fields), Platform (constructor, generate_ideal_trajectory, heading_vector), SARCalculator (constructor, all computed properties)
- [x] T039 [P] [US5] Write Simulation API reference at docs/api/simulation.md — SimulationEngine (constructor, run, SimulationResult fields), SimulationConfig (constructor, validate, run_simulation, state machine), signal module functions (compute_range, compute_echo_phase, compute_path_loss)
- [x] T040 [P] [US5] Write Algorithms API reference at docs/api/algorithms.md — AlgorithmRegistry (register, get, list), ImageFormationAlgorithm (process, range_compress, azimuth_compress, supported_modes), RangeDopplerAlgorithm (params), MotionCompensationAlgorithm (compensate), AutofocusAlgorithm (focus, estimate_phase_error), ImageTransformationAlgorithm (transform), PolarimetricDecomposition (decompose, n_components); include parameter_schema() for each concrete algorithm
- [x] T041 [P] [US5] Write I/O API reference at docs/api/io.md — ProcessingConfig (fields, JSON serialization), write_hdf5/read_hdf5 (parameters, file structure), import_data (external HDF5 import), ParameterSet functions (resolve_refs, $ref/$data), pack_project/unpack_project (archive utilities)
- [x] T042 [P] [US5] Write Pipeline API reference at docs/api/pipeline.md — PipelineRunner (constructor, run method, PipelineResult fields), LFMWaveform (constructor, generate, range_compress), FMCWWaveform (constructor, ramp_type, dechirp), Waveform base class contract
- [x] T043 [US5] Write type reference entries in docs/api/core.md — SARModeConfig, RawData, PhaseHistoryData, SARImage, SimulationState enum; include constructor params, fields, I/O methods, usage examples

**Checkpoint**: All 5 API reference pages complete; 27 key classes documented with params, types, and return values

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Known issues, changelog, cross-references, and final validation

- [x] T044 [P] Write Known Issues page at docs/known-issues.md — PGA autofocus vertical streaks (severity, affected scenarios, workaround), MoCo + GPS noise interaction (severity, affected scenarios, workaround), Numba acceleration deferred status, any other known limitations from current codebase
- [x] T045 [P] Write Changelog at docs/changelog.md — v0.1 entry with date, feature summary (simulation engine, 3 image formation algorithms, 4 autofocus, 2 MoCo, 2 geocoding, 4 polarimetry, GUI, preset system, HDF5 I/O), template for future versions
- [x] T046 Add cross-references between all documentation chapters — ensure math chapters link to corresponding API entries, API entries link to math chapters, getting-started links to configuration and data structures, customization links to API reference
- [x] T047 Validate all 5 runnable code examples execute successfully — run docs/examples/quickstart_stripmap.py, custom_scene.py, batch_simulation.py, custom_algorithm.py, and any inline examples; fix any failures
- [x] T048 Validate MkDocs builds without warnings — run `mkdocs build --strict`, fix broken links, missing pages, LaTeX rendering issues
- [x] T049 Review all LaTeX equations render correctly in MkDocs local preview — spot-check each math chapter, verify inline and display math, verify notation table symbols match usage
- [x] T050 Final review of documentation completeness against contracts/doc-outline.md — verify every chapter contract checklist item is satisfied

**Checkpoint**: Documentation is complete, all examples run, site builds clean, ready for v0.1 release

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (mkdocs.yml must exist)
- **US1 (Phase 3)**: Depends on Phase 2 (needs diagrams, home page for context)
- **US2 (Phase 4)**: Depends on Phase 2 only — can run in parallel with US1
- **US3 (Phase 5)**: Depends on Phase 2 only — can run in parallel with US1/US2
- **US4 (Phase 6)**: Depends on Phase 2 only — can run in parallel with US1/US2/US3
- **US5 (Phase 7)**: Depends on Phase 2 only — can run in parallel, but benefits from US2 (data structures) and US3 (math) being done first for cross-referencing
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Independent after Phase 2
- **US2 (P1)**: Independent after Phase 2
- **US3 (P2)**: Independent after Phase 2
- **US4 (P2)**: Independent after Phase 2; benefits from US3 notation table for consistency
- **US5 (P3)**: Independent after Phase 2; benefits from all other stories for cross-references

### Within Each User Story

- Documentation pages within a story marked [P] can be written in parallel
- Sequential tasks within a story depend on the structure built by prior tasks
- Examples depend on the narrative documentation being written first

### Parallel Opportunities

- T003, T004, T005 can all run in parallel (Setup)
- T007, T008, T009 can all run in parallel (diagrams)
- T016, T020 can run in parallel within US2 (different files)
- T025-T030 can ALL run in parallel within US3 (independent math chapters)
- T032-T035 can ALL run in parallel within US4 (independent guide chapters)
- T038-T042 can ALL run in parallel within US5 (independent API pages)
- T044, T045 can run in parallel in Polish phase

---

## Parallel Example: User Story 3 (Math)

```
# All math chapters can be written simultaneously:
Task T025: "Signal Model & Waveforms at docs/math/signal-model.md"
Task T026: "Image Formation at docs/math/image-formation.md"
Task T027: "Motion Compensation at docs/math/motion-compensation.md"
Task T028: "Autofocus at docs/math/autofocus.md"
Task T029: "Geocoding at docs/math/geocoding.md"
Task T030: "Polarimetry at docs/math/polarimetry.md"

# Then notation table consolidates all symbols:
Task T031: "Notation Table at docs/math/notation.md" (after T025-T030)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T009)
3. Complete Phase 3: User Story 1 (T010-T015)
4. **STOP and VALIDATE**: New user can install and run first simulation using docs alone
5. This alone makes the project usable for newcomers

### Incremental Delivery

1. Setup + Foundational → MkDocs site live with home page and diagrams
2. Add US1 (Getting Started + Architecture) → Users can onboard (MVP!)
3. Add US2 (Data Structures + Configuration) → Engineers can customize
4. Add US3 (Mathematical Principles) → Researchers can trust and verify
5. Add US4 (Customization Guide) → Developers can extend
6. Add US5 (API Reference) → Power users have lookup resource
7. Polish → Cross-references, validation, known issues, changelog

### Recommended Execution Order

Since this is a single-author documentation effort, the recommended order is sequential by priority: P1 stories first, then P2, then P3, then polish. Within each phase, maximize parallel task execution where marked [P].

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- No test tasks included — validation is in Phase 8 (T047-T050)
- LaTeX must be verified to render in both MkDocs preview and GitHub
- Code examples must be validated against shipped presets before finalizing
- When writing math chapters, read the corresponding algorithm source code to ensure equations match the implementation
- Cross-reference notation table (T031) after all math chapters are written
