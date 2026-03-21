# Data Model: GUI Overhaul

**Branch**: `002-gui-overhaul` | **Date**: 2026-03-18

## Entities

### ParameterNode

Represents a single node in the parameter tree hierarchy.

**Fields**:
- `key` (str) — Unique identifier within parent scope (e.g., "carrier_freq")
- `display_name` (str) — Human-readable label (e.g., "Carrier Frequency")
- `node_type` (enum) — CATEGORY, GROUP, PARAMETER, ALGORITHM_SELECTOR
- `value_type` (enum) — FLOAT, INT, BOOL, ENUM, VECTOR3, NONE (for categories)
- `value` — Current parameter value (type depends on value_type)
- `default` — Default value
- `unit` (str, optional) — Display unit (e.g., "GHz", "m/s")
- `si_multiplier` (float) — Multiplier to convert display value to SI
- `min_value`, `max_value` (optional) — Valid range constraints
- `enum_choices` (list[str], optional) — For ENUM type
- `tooltip` (str) — Description for hover tooltip
- `enabled` (bool) — Whether editable (false when mode-irrelevant)
- `disabled_reason` (str, optional) — Tooltip explaining why disabled
- `children` (list[ParameterNode]) — Child nodes in hierarchy

**Relationships**: Tree structure — each node has 0-1 parent and 0-N children.

**Validation**: `min_value <= value <= max_value` when value_type is numeric. Enum values must be in `enum_choices`.

### CalculatedValue

A derived quantity computed from input parameters.

**Fields**:
- `key` (str) — Unique identifier (e.g., "range_resolution")
- `display_name` (str) — Human-readable label
- `value` (float) — Current computed value
- `unit` (str) — Display unit
- `precision` (int) — Decimal places for display
- `formula_description` (str) — Brief description of how it's computed
- `dependencies` (list[str]) — Parameter keys this value depends on
- `warning_condition` (callable, optional) — Returns warning message if problematic
- `warning_active` (bool) — Whether currently flagged

**Lifecycle**: Recomputed on any dependency change. Warning state checked after each recomputation.

### ParameterPreset

A named, categorized collection of parameter values.

**Fields**:
- `name` (str) — Display name
- `category` (str) — Category for grouping (e.g., "antennas", "waveforms", "platforms", "sensors", "full-scenario")
- `description` (str) — Brief description
- `tier` (enum) — SYSTEM (read-only, package dir) or USER (read-write, user data dir)
- `file_path` (Path) — Location of the preset JSON file
- `parameters` (dict) — Flat or nested parameter key-value pairs

**Validation**: Name must be unique within category+tier. USER presets are mutable; SYSTEM presets are not.

### Project

A self-contained simulation/processing configuration with optional results.

**Fields**:
- `name` (str) — Project name
- `description` (str, optional)
- `format_version` (str) — Schema version (currently "1.0")
- `directory` (Path) — Working directory on disk
- `parameters` (dict) — Complete resolved parameter set
- `has_results` (bool) — Whether simulation/pipeline results exist
- `metadata` (dict) — created_at, last_modified_at, pysimsar_version

**State transitions**:
- NEW → created via wizard or direct editing (parameters only)
- CONFIGURED → all required parameters set, ready to run
- SIMULATED → simulation complete, raw data available
- PROCESSED → pipeline complete, images available
- SAVED → persisted to directory or .pysimsar archive

**Formats**:
- Project directory: `project.json` + component JSONs + binary data
- `.pysimsar` archive: Zip of project directory
- HDF5: Complete parameter set in `/parameters` + data in other groups

### WizardState

Tracks progress through a multi-step wizard.

**Fields**:
- `wizard_type` (enum) — PROJECT_CREATION, DATA_IMPORT
- `current_step` (int) — 0-indexed current step
- `total_steps` (int) — Total number of steps
- `step_data` (dict[int, dict]) — Validated data collected per step
- `step_valid` (dict[int, bool]) — Validation status per step
- `completed` (bool) — Whether wizard finished successfully
- `cancelled` (bool) — Whether wizard was cancelled

**State transitions**:
- INIT → step 0 displayed
- STEP_N → user advances (requires step_valid[N] = True)
- COMPLETE → user clicks Finish on last step → parameters applied
- CANCELLED → user cancels at any step → no changes applied

### UserPreferences

Application-wide persistent settings.

**Fields**:
- `tooltips_enabled` (bool, default True)
- `recent_projects` (list[Path], max 10)
- `window_geometry` (dict) — x, y, width, height, splitter positions
- `default_colormap` (str, default "gray")
- `default_dynamic_range_dB` (float, default 40.0)

**Storage**: `{user_data_dir}/PySimSAR/preferences.json`

## Relationships Diagram

```
Project
  ├── ParameterNode (tree root)
  │     ├── Radar (category)
  │     │     ├── carrier_freq (parameter)
  │     │     ├── prf (parameter)
  │     │     └── ...
  │     ├── Antenna (category)
  │     ├── Waveform (category)
  │     ├── Platform (category)
  │     │     ├── Flight Path (group)
  │     │     │     ├── mode (enum: start-stop / heading-time)
  │     │     │     ├── start_position (vector3)
  │     │     │     ├── stop_position (vector3, conditional)
  │     │     │     ├── heading (vector3, conditional)
  │     │     │     ├── velocity (float)
  │     │     │     └── flight_time (float, conditional)
  │     │     ├── Turbulence (group, optional)
  │     │     ├── GPS Sensor (group, optional)
  │     │     └── IMU Sensor (group, optional)
  │     ├── Scene (category)
  │     ├── Simulation (category)
  │     └── Processing (category)
  │           ├── Image Formation (algorithm_selector)
  │           │     └── [dynamic children based on selection]
  │           ├── Motion Compensation (algorithm_selector)
  │           ├── Autofocus (algorithm_selector)
  │           ├── Geocoding (algorithm_selector)
  │           └── Polarimetric Decomposition (algorithm_selector)
  ├── CalculatedValue[] (derived from ParameterNode values)
  └── SimulationResult / PipelineResult (after execution)

ParameterPreset
  ├── SYSTEM tier (read-only, in package)
  └── USER tier (read-write, in user data dir)

UserPreferences (singleton, in user data dir)
```
