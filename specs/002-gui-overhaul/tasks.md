# Tasks: GUI Overhaul

**Input**: Design documents from `/specs/002-gui-overhaul/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Constitution III (TDD) requires tests before implementation. Test tasks included per story.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, new dependencies, directory structure

- [X] T001 Add `trimesh>=3.20` and `platformdirs>=3.0` to pyproject.toml dependencies (trimesh in gui extras, platformdirs in core)
- [X] T002 [P] Create assets directory structure: `pySimSAR/assets/models/` and `pySimSAR/assets/icons/`
- [X] T003 [P] Create `pySimSAR/gui/wizards/__init__.py` package directory
- [X] T004 [P] Create `pySimSAR/io/user_data.py` with `UserDataDir` class using platformdirs to resolve cross-platform user data paths (`%APPDATA%/PySimSAR/` on Windows), create directory structure on first access (presets/, preferences.json)
- [X] T005 [P] Create `pySimSAR/io/archive.py` with `pack_project(dir_path, archive_path)` and `unpack_project(archive_path, dir_path)` using Python zipfile module for `.pysimsar` format

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core library components that MUST be complete before ANY user story GUI work

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Create `pySimSAR/core/calculator.py` with `SARCalculator` class implementing all 15 derived quantities (wavelength, pulse_width, range_resolution, azimuth_resolution, unambiguous_range, unambiguous_doppler, swath_width_ground, nesz, snr_single_look, n_range_samples, synthetic_aperture, doppler_bandwidth, n_pulses, flight_time, track_length) per contracts/calculated-values.md. Include warning condition checks.
- [X] T007 Write tests for SARCalculator in `tests/unit/test_calculator.py` — verify all 15 formulas against hand-calculated reference values for 3 parameter configurations (X-band airborne stripmap, C-band spaceborne, W-band UAV FMCW). Test warning conditions.
- [X] T008 [P] Define hardcoded algorithm parameter schemas as dicts in `pySimSAR/gui/widgets/_algo_schemas.py` — one schema per algorithm across all 5 registries (image formation: range_doppler, chirp_scaling, omega_k; moco: first_order, second_order; autofocus: pga, min_entropy, mda, ppp; geocoding: slant_to_ground, georeferencing; polarimetry: pauli, freeman_durden, cloude_pottier, yamaguchi). Each schema entry: name, type, default, min, max, description, unit.
- [X] T009 [P] Implement flight path computation helper in `pySimSAR/core/flight_path.py` — two modes: (a) start+stop position → derive heading, velocity-dependent flight_time, n_pulses; (b) start+heading+velocity+flight_time → derive stop_position, n_pulses. Uses PRF from radar params.
- [X] T010 Write tests for flight path computation in `tests/unit/test_flight_path.py` — test both modes, verify derived quantities, edge cases (zero distance, zero velocity).
- [X] T011 [P] Write tests for .pysimsar archive round-trip in `tests/unit/test_archive.py` — pack a sample project directory, unpack to new location, verify all files identical.
- [X] T012 [P] Write tests for user data directory in `tests/unit/test_user_data.py` — verify directory creation, preferences read/write, preset path resolution.

**Checkpoint**: Foundation ready — core library, schemas, and I/O tested. User story implementation can begin.

---

## Phase 3: User Story 1 — Tree-Based Parameter Navigation (Priority: P1) MVP

**Goal**: Replace the flat sidebar with a hierarchical inline-editing parameter tree (Cadence Virtuoso style). All existing parameters accessible. SAR mode disables irrelevant params. Search/filter.

**Independent Test**: Launch GUI, verify every parameter from old sidebar is reachable in tree, edit values inline, expand/collapse categories, search by keyword.

### Tests for User Story 1

- [X] T013 [P] [US1] Write widget test in `tests/widget/test_param_tree.py` — test tree population (7 top-level categories), inline widget creation (spinbox, combo, checkbox), get_all_parameters/set_all_parameters round-trip, search/filter showing matching items and hiding non-matching.
- [X] T014 [P] [US1] Write widget test for mode constraints in `tests/widget/test_param_tree.py` — test that switching SAR mode disables mode-irrelevant parameters (e.g., scene_center disabled in stripmap, burst_length disabled in spotlight) with tooltip.

### Implementation for User Story 1

- [X] T015 [US1] Create `pySimSAR/gui/widgets/param_tree.py` — implement `ParameterTreeWidget(QTreeWidget)` with: 2-column layout (Parameter Name | Value Widget), `setItemWidget()` for inline editors (reuse UnitSpinBox, _CleanDoubleSpinBox, _no_scroll_unless_focused from param_editor.py), 7 top-level category nodes (bold text, no icons), expandable sub-groups, `parameter_changed(key, value)` signal, `get_all_parameters()` and `set_all_parameters(params)` methods. Per contracts/parameter-tree.md.
- [X] T016 [US1] Populate the parameter tree with all current parameters — map every field from RadarParamEditor, AntennaParamEditor, WaveformParamEditor, PlatformParamEditor, SceneParamEditor, SimulationParamEditor into tree nodes. Include conditional visibility (FMCW ramp_type, phase noise sub-params, turbulence, GPS, IMU).
- [X] T017 [US1] Implement flight path input modes in the Platform section of the tree — add mode selector (start-stop / heading-time), conditionally show/hide stop_position vs heading+velocity+flight_time fields. Remove n_pulses from editable params (now derived). Wire to flight_path.py helper.
- [X] T018 [US1] Implement SAR mode constraint logic in param_tree.py — when mode dropdown changes, call `set_mode_constraints(mode)` to disable/enable mode-irrelevant parameters (scene_center, n_subswaths, burst_length) with explanatory tooltips.
- [X] T019 [US1] Implement search/filter in param_tree.py — add QLineEdit above tree, filter by recursive item hiding (case-insensitive match on parameter name), show parent if any child matches.
- [X] T020 [US1] ~~Add category icons~~ — REMOVED: category icons dropped from scope per user request. Section headings use bold text only.
- [X] T021 [US1] Restructure main window layout in `pySimSAR/gui/app.py` — replace current flat sidebar + tab area with: left panel = ParameterTreeWidget (scrollable), right panel = visualization tabs (top) + calculated values placeholder (bottom), full-width status bar at bottom. Use nested QSplitters. Remove old param editor imports and sidebar construction.
- [X] T022 [US1] Wire parameter tree to simulation controller in `pySimSAR/gui/app.py` — connect `parameter_changed` signal to model update, connect Run action to `get_all_parameters()` → build ProjectModel, connect project load to `set_all_parameters()`. Preserve live scene preview on param change.

**Checkpoint**: Tree-based parameter navigation fully functional. All old parameters accessible inline. Mode constraints work. Search works. Ready to test independently.

---

## Phase 4: User Story 2 — Calculated Values Panel (Priority: P1)

**Goal**: Live-updating panel in bottom-right showing 15+ derived quantities with warning flags.

**Independent Test**: Change carrier frequency → wavelength updates. Change bandwidth → range resolution updates. Set PRF too low for swath → warning flag appears. All values match hand calculations.

### Tests for User Story 2

- [X] T023 [P] [US2] Write widget test in `tests/widget/test_calc_panel.py` — test panel displays all 15 values, test update latency < 200ms, test warning flag appearance when NESZ or ambiguity conditions triggered.

### Implementation for User Story 2

- [X] T024 [US2] Create `pySimSAR/gui/widgets/calc_panel.py` — implement `CalculatedValuesPanel(QWidget)` displaying a scrollable grid of Name | Value | Unit rows, grouped by category (Radar, Geometry, Performance, Flight). Warning icon (yellow/red) on flagged values. `update(params: dict)` method calls `SARCalculator.compute()`.
- [X] T025 [US2] Integrate calc panel into main window layout in `pySimSAR/gui/app.py` — place in bottom-right (below viz tabs, above status bar). Connect `parameter_changed` signal from tree to `calc_panel.update()`.
- [X] T026 [US2] Create 3 golden test configurations in `examples/golden/calculated_values/` — X-band airborne stripmap, C-band spaceborne, W-band UAV FMCW — each with hand-calculated expected values for all 15 quantities. Verify SARCalculator matches within tolerance.

**Checkpoint**: Calculated values panel live-updates on parameter change, correct formulas, warnings visible.

---

## Phase 5: User Story 3 — Full Algorithm Parameter Exposure (Priority: P1)

**Goal**: Every backend algorithm parameter appears as an editable inline tree child when that algorithm is selected.

**Independent Test**: Select Range-Doppler → see apply_rcmc + rcmc_interp_order. Select PGA → see max_iterations, convergence_threshold, n_dominant, window_fraction. Switch algorithms → params update.

### Tests for User Story 3

- [X] T027 [P] [US3] Write widget test in `tests/widget/test_param_tree.py` — test that selecting each algorithm in each processing step loads correct parameter children from _algo_schemas.py. Test switching algorithms clears old params and loads new ones.

### Implementation for User Story 3

- [X] T028 [US3] Implement dynamic algorithm parameter loading in `pySimSAR/gui/widgets/param_tree.py` — for each ALGORITHM_SELECTOR node (5 processing steps), on dropdown change: clear existing child nodes, look up schema from _algo_schemas.py, create child QTreeWidgetItems with inline widgets (spinbox/checkbox/combo) per schema entry. Wire child value changes to `parameter_changed` signal.
- [X] T029 [US3] Add algorithm parameter collection to `get_all_parameters()` in param_tree.py — include algorithm-specific params in the returned dict under `processing_config.{step}_params`. Ensure `set_all_parameters()` restores algorithm selections and their params.

**Checkpoint**: All backend algorithm parameters editable in tree. Switching algorithms dynamically updates params.

---

## Phase 6: User Story 4 — Additional Visualization Panels (Priority: P2)

**Goal**: 5 new viz panels + tiled display + pipeline intermediate result capture + find-peak tool.

**Independent Test**: Run simulation → Phase History tab shows waterfall. Range/Azimuth Profile tabs show 1D plots. Tile two panels side-by-side. Use find-peak to mark a point.

### Tests for User Story 4

- [X] T030 [P] [US4] Write widget test in `tests/widget/test_viz_panels.py` — test each new panel displays placeholder when no data, test update with mock SARImage/PhaseHistoryData, test find-peak tool returns correct coordinates.

### Implementation for User Story 4

- [X] T031 [P] [US4] Create `pySimSAR/gui/panels/phase_history.py` — `PhaseHistoryPanel(QWidget)` using matplotlib FigureCanvasQTAgg. Display range-compressed 2D waterfall (range x azimuth) with dB colorbar, dynamic range control, colormap selector. `update(phd: PhaseHistoryData)` and `clear()` methods.
- [X] T032 [P] [US4] Create `pySimSAR/gui/panels/range_profile.py` — `RangeProfilePanel(QWidget)` using matplotlib. 1D power (dB) vs range. Controls: azimuth line selector (spinbox) or "Average All" checkbox. `update(image: SARImage)` and `clear()` methods.
- [X] T033 [P] [US4] Create `pySimSAR/gui/panels/azimuth_profile.py` — `AzimuthProfilePanel(QWidget)` using matplotlib. 1D power (dB) vs azimuth. Controls: range bin selector (spinbox). `update(image: SARImage)` and `clear()` methods.
- [X] T034 [P] [US4] Create `pySimSAR/gui/panels/doppler_spectrum.py` — `DopplerSpectrumPanel(QWidget)` using matplotlib. FFT of echo data along azimuth. Controls: range bin selector, window function selector. `update(raw_data: RawData, radar)` and `clear()` methods.
- [X] T035 [P] [US4] Create `pySimSAR/gui/panels/polarimetry.py` — `PolarimetryPanel(QWidget)` using matplotlib. Display decomposition results as RGB composite (Pauli) or power maps. Controls: decomposition type selector, component visibility. `update(decomposition: dict)` and `clear()` methods.
- [X] T036 [US4] Create `pySimSAR/gui/panels/tiled_view.py` — `TiledViewManager(QWidget)` managing a tab bar + QSplitter content area. Support split (horizontal/vertical) via toolbar button or tab context menu. Each pane has its own tab selector. Recursive splitting for 2-4 panes.
- [X] T037 [US4] Create `pySimSAR/gui/widgets/peak_tool.py` — `PeakFinder` tool for matplotlib axes: mouse drag to select rectangular region, find max value within region, place `PeakMarker` (hollow circle default) with x/y/z annotation. Right-click context menu: change shape (circle, crosshair, diamond, square, triangle), remove marker. `clear_all_markers()` method.
- [X] T038 [US4] Integrate peak tool into `pySimSAR/gui/panels/image_viewer.py` — add "Find Peak" toggle button to toolbar. When active, mouse drag triggers PeakFinder. Markers persist across zoom/pan.
- [X] T039 [US4] Modify `pySimSAR/pipeline/runner.py` to capture intermediate results — store range-compressed PhaseHistoryData in PipelineResult. Add `phase_history: dict[str, PhaseHistoryData]` field to PipelineResult dataclass. Capture raw_data reference for Doppler spectrum.
- [X] T040 [US4] Integrate all new panels and TiledViewManager into `pySimSAR/gui/app.py` — replace QTabWidget with TiledViewManager, register all 9 panels (4 existing + 5 new), wire simulation controller finished signal to update all panels with available data. Show placeholder for panels with no data.

**Checkpoint**: 9 visualization tabs, tiled display, intermediate results visible, find-peak tool functional.

---

## Phase 7: User Story 5 — Project Creation Wizard (Priority: P2)

**Goal**: Step-by-step wizard for new project setup: mode → radar → platform → scene → processing.

**Independent Test**: Launch wizard via Ctrl+N, complete all 5 steps with valid params, verify parameter tree populated. Cancel mid-wizard, verify no changes.

### Tests for User Story 5

- [X] T041 [P] [US5] Write widget test in `tests/widget/test_wizards.py` — test wizard step navigation (next/back/cancel/finish), test validation prevents invalid advancement, test finish populates parameter tree correctly, test cancel leaves state unchanged.

### Implementation for User Story 5

- [X] T042 [US5] Create `pySimSAR/gui/wizards/project_wizard.py` — `ProjectCreationWizard(QWizard)` with 5 pages: (1) ProjectMetadataPage: name, description, SAR mode; (2) RadarConfigPage: radar params + preset selector; (3) PlatformPage: flight path mode, start/stop or heading/time, velocity, altitude; (4) ScenePage: origin lat/lon/alt, point target table; (5) ProcessingPage: algorithm selections. Each page implements `validatePage()`. Finish emits `wizard_completed(params: dict)` signal.
- [X] T043 [US5] Wire wizard to main window in `pySimSAR/gui/app.py` — Ctrl+N triggers `ProjectCreationWizard.exec()`. On accepted, call `param_tree.set_all_parameters(params)`. On rejected, no action.

**Checkpoint**: Wizard guides project setup, validates inputs, populates tree on finish.

---

## Phase 8: User Story 6 — Data Import Wizard (Priority: P2)

**Goal**: HDF5 import with preview, channel selection, parameter gap detection for real measurement data.

**Independent Test**: Import a fully-specified HDF5 → all params populated. Import a partial HDF5 (raw data + trajectory only) → wizard shows missing params, user fills gaps.

### Tests for User Story 6

- [X] T044 [P] [US6] Write unit test in `tests/unit/test_hdf5_v2.py` — test write/read of extended HDF5 schema v2 (/parameters group), test backwards compat with v1 files (no /parameters), test partial file detection (which params present vs missing).
- [X] T045 [P] [US6] Write widget test in `tests/widget/test_wizards.py` — test import wizard preview shows file contents, test channel selection, test gap detection lists missing params.

### Implementation for User Story 6

- [X] T046 [US6] Extend `pySimSAR/io/hdf5_format.py` — add `write_parameters(h5file, params)` and `read_parameters(h5file) -> dict | None` for the `/parameters` group per contracts/hdf5-schema.md. Add `@schema_version` attribute to `/metadata`. Modify `write_hdf5()` to always write /parameters. Modify `read_hdf5()` to read /parameters if present, fall back to /config JSON.
- [X] T047 [US6] Add parameter completeness checker in `pySimSAR/io/hdf5_format.py` — `check_parameter_completeness(params: dict) -> dict[str, list[str]]` returns {"present": [...], "missing": [...]} by comparing against the full parameter schema.
- [X] T048 [US6] Create `pySimSAR/gui/wizards/import_wizard.py` — `ImportWizard(QWizard)` with pages: (1) FileSelectionPage: file picker with HDF5 filter; (2) PreviewPage: display file contents tree (channels, dimensions, metadata), show present/missing parameters with color coding (green=present, red=missing); (3) ChannelSelectionPage: checkboxes for each channel; (4) GapFillingPage: parameter editors for missing params, with preset selector option (shown only if gaps exist); (5) ProcessingPage: algorithm selection. Finish loads data + fills tree.
- [X] T049 [US6] Wire import wizard to main window in `pySimSAR/gui/app.py` — Ctrl+I triggers `ImportWizard.exec()`. On accepted, load HDF5 data into ProjectModel, populate parameter tree with present params + user-filled gaps.

**Checkpoint**: HDF5 import works for both full (simulation) and partial (real measurement) files. Gap detection guides user.

---

## Phase 9: User Story 7 — Distributed Target Editor (Priority: P3)

**Goal**: GUI editor for distributed targets with uniform/noisy reflectivity or file import.

**Independent Test**: Add a distributed target in scene editor, configure reflectivity (uniform + noise), run simulation, verify target appears in 3D scene and contributes to echo.

### Implementation for User Story 7

- [X] T050 [P] [US7] Add distributed target section to the Scene category in `pySimSAR/gui/widgets/param_tree.py` — "Distributed Targets" group node with "Add" / "Remove" buttons. Each target as a sub-group with: origin (x,y,z), extent (dx,dy), cell_size, reflectivity mode (uniform/file), mean/stddev (uniform mode), file path + preview (file mode).
- [X] T051 [US7] Wire distributed target data to `get_all_parameters()` and `set_all_parameters()` in param_tree.py — serialize distributed targets as list of dicts in the parameter output. Support .npy and .csv reflectivity file import with preview thumbnail.

**Checkpoint**: Distributed targets configurable in GUI, saved/loaded with project.

---

## Phase 10: User Story 8 — Parameter Preset Browser (Priority: P3)

**Goal**: Two-tier preset browser (system read-only + user read-write) with preview, apply, save, duplicate, edit, delete.

**Independent Test**: Open preset browser, see system presets listed. Apply a preset → all params overwritten. Save current config as user preset. Duplicate system preset to user. Delete user preset.

### Tests for User Story 8

- [X] T052 [P] [US8] Write widget test in `tests/widget/test_preset_browser.py` — test preset listing (system + user tiers), test apply overwrites all params, test save creates file in user data dir, test duplicate copies system to user, test delete removes user preset file.

### Implementation for User Story 8

- [X] T053 [US8] Create `pySimSAR/gui/widgets/preset_browser.py` — `PresetBrowserDialog(QDialog)` with: left panel = category tree (antennas, waveforms, platforms, sensors, full-scenario), right panel = preset list with tier badges (system=lock icon, user=edit icon). Preview panel shows key params. Buttons: Apply, Save Current, Duplicate to User, Edit (user only), Delete (user only). Apply emits `preset_applied(params: dict)` signal with full overwrite semantics.
- [X] T054 [US8] Implement preset file I/O in `pySimSAR/io/user_data.py` — `list_presets(category, tier) -> list[PresetInfo]`, `load_preset(path) -> dict`, `save_user_preset(category, name, params)`, `delete_user_preset(path)`, `duplicate_to_user(system_path, new_name)`. System presets read from `pySimSAR/presets/`, user presets from user data dir.
- [X] T055 [US8] Wire preset browser to main window in `pySimSAR/gui/app.py` — add "Presets" menu item or toolbar button. On `preset_applied`, call `param_tree.set_all_parameters(params)`.

**Checkpoint**: Two-tier preset system functional. User presets persist across sessions.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Project file management, preferences, tooltips, visual polish

- [X] T056 [P] Implement Preferences menu in `pySimSAR/gui/app.py` — add Edit > Preferences menu item opening `PreferencesDialog(QDialog)` with: tooltips toggle (FR-028), default colormap, default dynamic range. Save to `preferences.json` via user_data.py. Load on startup. Apply tooltip visibility globally.
- [X] T057 [P] Add parameter tooltips to all tree nodes in `pySimSAR/gui/widgets/param_tree.py` — set `QTreeWidgetItem.setToolTip(0, ...)` on every PARAMETER node with: description, valid range, default value, unit. Respect `UserPreferences.tooltips_enabled` toggle.
- [X] T058 [P] Implement self-contained project save in `pySimSAR/io/parameter_set.py` — modify `save_parameter_set()` to resolve all `$preset/` references by copying preset content inline. Ensure no external references remain in saved project directory.
- [X] T059 [P] Add Save/Open support for .pysimsar archives in `pySimSAR/gui/app.py` — extend file dialog filters to include `.pysimsar`. On save: pack via archive.py. On open: unpack to temp dir, load.
- [X] T060 [P] Add Save/Open support for extended HDF5 in `pySimSAR/gui/app.py` — extend Save Project to write HDF5 with complete /parameters group. Extend Open Project to read HDF5 v2 and populate tree.
- [X] T061 [P] Replace procedural airplane mesh with OBJ model in `pySimSAR/gui/panels/scene_3d.py` — add `_load_aircraft_mesh()` using trimesh to parse `pySimSAR/assets/models/aircraft.obj`, extract vertices/faces, create GLMeshItem. Fall back to procedural `_create_airplane_mesh()` if file not found. Source or create a low-poly aircraft OBJ file (~500 faces).
- [X] T062 Deprecate old parameter editors — remove imports of `SimulationParamEditor`, `RadarParamEditor`, `AntennaParamEditor`, `WaveformParamEditor`, `PlatformParamEditor`, `SceneParamEditor`, `AlgorithmSelector` from `pySimSAR/gui/app.py`. Keep old files for reference but they should no longer be instantiated.
- [X] T063 Run quickstart.md validation — execute the full test suite, verify all golden tests pass, launch GUI and manually verify layout matches the reference diagram in spec.md clarifications.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 (needs flight_path.py, algo schemas)
- **US2 (Phase 4)**: Depends on Phase 2 (needs SARCalculator) + US1 (needs tree for signal source)
- **US3 (Phase 5)**: Depends on Phase 2 (needs algo schemas) + US1 (needs tree widget)
- **US4 (Phase 6)**: Depends on US1 (needs main window layout restructure)
- **US5 (Phase 7)**: Depends on US1 (wizard populates tree)
- **US6 (Phase 8)**: Depends on US1 (populates tree) + Phase 2 (HDF5 extension)
- **US7 (Phase 9)**: Depends on US1 (tree widget)
- **US8 (Phase 10)**: Depends on US1 (tree widget) + T004 (user data dir)
- **Polish (Phase 11)**: Depends on all desired stories being complete

### User Story Dependencies

```
Phase 1 (Setup)
  └── Phase 2 (Foundational)
        ├── US1 (Tree) ← MVP
        │     ├── US2 (Calc Panel)
        │     ├── US3 (Algo Params)
        │     ├── US4 (Viz Panels)
        │     ├── US5 (Project Wizard)
        │     ├── US6 (Import Wizard)
        │     ├── US7 (Distributed Targets)
        │     └── US8 (Presets)
        └── Phase 11 (Polish) ← after all stories
```

### Within Each User Story

- Tests written FIRST, ensure they FAIL before implementation
- Library/core code before GUI widgets
- Widgets before main window integration
- Core implementation before cross-story integration

### Parallel Opportunities

- All Setup tasks T002-T005 marked [P] can run in parallel
- Foundational tasks T008-T012 marked [P] can run in parallel (after T006-T007)
- Within US4: All 5 new panel tasks (T031-T035) can run in parallel
- US7, US8 can run in parallel with each other (both depend only on US1)
- All Polish tasks T056-T061 marked [P] can run in parallel

---

## Parallel Example: User Story 4

```
# Launch all 5 new visualization panels in parallel (different files):
Task T031: "Phase History panel in pySimSAR/gui/panels/phase_history.py"
Task T032: "Range Profile panel in pySimSAR/gui/panels/range_profile.py"
Task T033: "Azimuth Profile panel in pySimSAR/gui/panels/azimuth_profile.py"
Task T034: "Doppler Spectrum panel in pySimSAR/gui/panels/doppler_spectrum.py"
Task T035: "Polarimetry panel in pySimSAR/gui/panels/polarimetry.py"

# Then sequentially (depends on panels):
Task T036: "Tiled view manager" (needs panels to exist)
Task T040: "Integrate into main window" (needs all above)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T012)
3. Complete Phase 3: US1 — Tree-Based Parameter Navigation (T013-T022)
4. **STOP and VALIDATE**: Launch GUI, verify all parameters accessible in tree, mode constraints work, search works
5. This alone delivers significant value — the core GUI restructure

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 (Tree) → Test independently → **MVP!**
3. US2 (Calc Panel) + US3 (Algo Params) → Test independently → P1 complete
4. US4 (Viz) + US5 (Wizard) + US6 (Import) → Test independently → P2 complete
5. US7 (Distributed) + US8 (Presets) → Test independently → P3 complete
6. Polish → Final validation

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Constitution III (TDD): Tests written before implementation in each story phase
- Deferred to future wave: Algorithm plugin system (entry-point discovery + enforced parameter_schema())
