# Research: GUI Overhaul

**Branch**: `002-gui-overhaul` | **Date**: 2026-03-18

## R1: Parameter Tree with Inline Editing (QTreeWidget vs QTreeView)

**Decision**: QTreeWidget with `setItemWidget()` for embedding inline editors.

**Rationale**: QTreeWidget is simpler, matches the existing UnitSpinBox/CleanDoubleSpinBox composite widget pattern already used in param_editor.py. Parameter trees are typically 50-100 items — well within QTreeWidget's performance envelope. The `setItemWidget(item, column, widget)` API allows embedding arbitrary QWidgets (spinboxes, combos, checkboxes) directly in tree rows, matching the Cadence Virtuoso pattern.

**Alternatives considered**:
- QTreeView + QStyledItemDelegate: More efficient for 1000+ items, but requires model/delegate boilerplate. Overkill for our scale. Would not reuse existing UnitSpinBox widgets.
- QTreeView + QAbstractItemModel: Maximum flexibility but maximum complexity. Better suited to future plugin system (deferred).

**Key patterns**:
- Reuse `UnitSpinBox`, `_CleanDoubleSpinBox`, `_no_scroll_unless_focused()` from param_editor.py
- Algorithm parameters dynamically added/removed via `QTreeWidgetItem` child manipulation
- Search/filter via simple recursive item hiding (adequate for <200 items)

## R2: Tiled/Split Visualization Display

**Decision**: QSplitter-based manual tiling with tab-bar header.

**Rationale**: QSplitter is lightweight, already used in app.py (line 203) for the sidebar/main split. Both `GLViewWidget` (pyqtgraph) and `FigureCanvasQTAgg` (matplotlib) are standard QWidgets that work correctly in QSplitter. Each split pane gets its own panel instance.

**Alternatives considered**:
- QMdiArea (MDI subwindows): Adds window decoration overhead, less suitable for scientific plots where screen area is precious.
- QDockWidget: Good for tool panels but adds floating/docking complexity. Overkill for equivalent-importance visualization tabs.

**Implementation**: Tab bar remains as a header; "Split" action (button or drag) inserts a QSplitter divider, creating a second pane with its own tab selector. Recursive splitting supported (2, 3, 4+ panes).

## R3: OBJ/STL Model Loading in pyqtgraph

**Decision**: Use `trimesh` library to parse OBJ/STL files, feed vertices/faces to `GLMeshItem`.

**Rationale**: pyqtgraph's `GLMeshItem` does not load mesh files directly — it only accepts numpy vertex/face arrays. trimesh is MIT-licensed, well-maintained, and handles OBJ, STL, PLY, and GLTF. It extracts vertices, faces, and normals which map directly to `gl.MeshData()`.

**Alternatives considered**:
- numpy-stl: STL-only, too limited (no OBJ support).
- pywavefront: OBJ-only parser, fewer features than trimesh.
- Keep procedural mesh: Spec explicitly requires a proper aircraft model.

**Asset storage**: `pySimSAR/assets/models/aircraft.obj` (or .stl). Resolved via `Path(__file__)` relative paths. Procedural mesh retained as fallback.

**New dependency**: `trimesh>=3.20` added to `gui` optional dependencies.

## R4: Project File Format (.pysimsar Archive)

**Decision**: Zip-based archive containing the project directory structure. Extension `.pysimsar`.

**Rationale**: Python's built-in `zipfile` module handles this with zero new dependencies. The archive contains exactly what the project directory contains: `project.json`, component JSONs, and binary data files. This is the same pattern used by `.docx`, `.xlsx`, and other modern file formats.

**Implementation**:
- Save: `zipfile.ZipFile(path, 'w', ZIP_DEFLATED)` with all project dir contents
- Open: Extract to temp/working directory, load as normal project
- All `$preset/` references resolved and copied before archiving (self-contained)

## R5: HDF5 Schema Extension

**Decision**: Add `/parameters` group to HDF5 storing the complete project parameter set as structured HDF5 groups/attributes, mirroring project.json content.

**Rationale**: Current HDF5 stores only raw data + trajectory + images + opaque JSON config strings. For real measurement data import and full project reconstruction, the HDF5 must store the same information as project.json. Using structured HDF5 groups (not just JSON strings) enables partial reads and tool interoperability.

**Schema additions**:
- `/parameters/scene` — origin, point targets (positions/rcs/velocities arrays), distributed targets
- `/parameters/radar` — all radar params as attributes + waveform/antenna sub-groups
- `/parameters/platform` — velocity, heading, start_position, perturbation, sensors
- `/parameters/simulation` — n_pulses, seed, swath_range, sample_rate, etc.
- `/parameters/processing` — algorithm selections and params

**Backwards compatibility**: Old HDF5 files without `/parameters` group still load via existing `/config` JSON strings. Import wizard detects which format and fills gaps.

## R6: User Data Directory

**Decision**: Use `platformdirs` library for cross-platform user data directory resolution.

**Rationale**: Provides correct platform-specific paths (Windows `%APPDATA%`, macOS `~/Library/Application Support`, Linux `~/.local/share`). Small, well-maintained dependency (pure Python). The alternative of hardcoding `~/.pysimsar/` works on Unix but is non-standard on Windows.

**Structure**:
```
{user_data_dir}/PySimSAR/
├── presets/
│   ├── antennas/
│   ├── waveforms/
│   ├── platforms/
│   └── sensors/
└── preferences.json
```

**New dependency**: `platformdirs>=3.0` added to core dependencies.

## R7: Calculated Values — SAR Equations

**Decision**: Implement a `SARCalculator` class in the library layer (not GUI) that computes all derived quantities from input parameters.

**Rationale**: Constitution principle II (Library-First) requires all computation in the library, not the GUI. The calculator takes a parameter dict and returns all derived values. The GUI panel simply displays the results.

**Derived quantities** (minimum 12 per SC-003):
1. Wavelength: `c / carrier_freq`
2. Pulse width: `duty_cycle / prf`
3. Range resolution: `c / (2 * bandwidth)`
4. Azimuth resolution: `antenna_length / 2` (stripmap) or custom for spotlight
5. Unambiguous range: `c / (2 * prf)`
6. Unambiguous Doppler velocity: `wavelength * prf / 4`
7. Swath width on ground: `(far_range - near_range) / sin(depression_angle)`
8. NESZ: thermal noise / (antenna gain * transmit power * ...)
9. Single-look SNR estimate
10. Number of range samples: `ceil(2 * bandwidth * swath_width / c * sample_rate)`
11. Synthetic aperture length: `wavelength * R / D` (D = antenna length)
12. Doppler bandwidth: `2 * velocity / az_resolution`
13. n_pulses: `prf * flight_time` (derived from flight path)
14. Flight time, track length, heading/stop position (from flight path mode)

**Validation warnings**: NESZ below threshold, PRF vs swath ambiguity, range/Doppler ambiguity zones.
