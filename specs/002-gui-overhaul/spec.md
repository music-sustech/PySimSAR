# Feature Specification: GUI Overhaul

**Feature Branch**: `002-gui-overhaul`
**Created**: 2026-03-18
**Status**: Draft
**Input**: User description: "GUI overhaul: tree-based parameters, calculated values panel, new visualizations, project wizards, and full parameter coverage"

## Clarifications

### Session 2026-03-18

- Q: Where should the calculated values panel be placed in the layout? → A: Bottom-right of the main window, below the visualization tabs, above the status bar. The parameter tree is to its left. The status bar spans the full window width at the very bottom.
- Q: How should mode-irrelevant parameters behave when SAR mode changes? → A: Disable (gray out) with a tooltip explaining why, not hidden.
- Q: When applying a preset, should it overwrite all parameters or merge? → A: Full overwrite — all parameters replaced, undefined ones reset to defaults.
- Q: How should 9 visualization tabs be organized? → A: Keep all 9 as flat tabs in a single tab bar, with tiled/split display support so multiple plots can be viewed simultaneously.
- Q: How should distributed target reflectivity be specified in the GUI? → A: Both uniform/noisy (mean + stddev) for quick setup, and file import (CSV/NumPy) for complex patterns.
- Layout reference: Cadence Virtuoso Circuit Explorer (`drafts/wave2-gui-improvment.png`). Key design: parameter tree with inline editing (tree IS the editor), tileable plot area, calculated values in bottom-right.

**Main window layout** (reference diagram):
```
+------------------+--------------------------------+
|                  |                                |
|   Parameter      |   Visualization Tabs           |
|   Tree           |   (tileable/splittable)        |
|   (inline edit)  |                                |
|                  |                                |
|                  +--------------------------------+
|                  | Calculated Values Panel        |
+------------------+--------------------------------+
| Status Bar (full width)                           |
+---------------------------------------------------+
```

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tree-Based Parameter Navigation (Priority: P1)

A SAR engineer opens PySimSAR and sees all simulation parameters organized in a hierarchical tree panel on the left side. The tree has top-level categories (Radar, Antenna, Waveform, Platform, Scene, Simulation, Processing) that expand to reveal sub-groups. For example, expanding "Platform" shows "Motion", "Turbulence", "GPS Sensor", and "IMU Sensor" as child nodes. Parameter values are edited inline directly within the tree rows — each leaf node displays the parameter name alongside its editable value widget (spinbox, dropdown, checkbox, etc.). The tree IS the editor; there is no separate editor pane. Algorithm sub-parameters are dynamically loaded inline when an algorithm is selected (e.g., expanding "Autofocus > PGA" reveals its tunable parameters as child nodes). The tree replaces the current flat stack of collapsible QGroupBox editors, making it easier to locate and navigate between the ~80+ parameters across the system. The layout follows the Cadence Virtuoso Circuit Explorer pattern (see `drafts/wave2-gui-improvment.png`).

**Why this priority**: The current flat sidebar becomes unwieldy as more parameters are added. Tree navigation is the structural foundation that all other stories build on — without it, adding more parameters and panels will make the GUI increasingly cluttered.

**Independent Test**: Can be tested by launching the GUI and verifying that every parameter currently accessible in the flat sidebar is reachable via the tree, and that tree expand/collapse and node selection correctly displays the corresponding editor section.

**Acceptance Scenarios**:

1. **Given** the application is launched, **When** the user views the left panel, **Then** they see a tree with top-level categories for each parameter group (Radar, Antenna, Waveform, Platform, Scene, Simulation, Processing).
2. **Given** a tree category is collapsed, **When** the user clicks to expand it, **Then** child nodes for sub-groups appear (e.g., Platform expands to show Motion, Turbulence, GPS, IMU).
3. **Given** a leaf node is visible in the tree, **When** the user interacts with its inline value widget, **Then** the parameter value can be edited directly in the tree row without navigating to a separate editor pane.
4. **Given** any parameter that was editable in the old flat sidebar, **When** the user navigates the tree, **Then** they can find and edit that same parameter inline with no loss of functionality.
5. **Given** a processing algorithm is selected (e.g., PGA for autofocus), **When** the algorithm node is expanded, **Then** its configurable parameters appear as dynamically loaded child nodes with inline editors.

---

### User Story 2 - Calculated Values Panel (Priority: P1)

While configuring simulation parameters, the engineer sees a live-updating "Calculated Values" panel positioned in the bottom-right of the main window (below the visualization tabs), always visible regardless of which tab is selected. The panel displays derived quantities computed from the current parameter state. This includes values such as: wavelength, pulse width, range resolution, azimuth resolution, unambiguous range, unambiguous Doppler velocity, swath width on ground, noise-equivalent sigma-zero (NESZ), single-look SNR estimate, number of range samples, synthetic aperture length, Doppler bandwidth, and flight path derived values (n_pulses, flight time, track length, heading or stop position depending on input mode). Whenever the user changes a parameter (e.g., carrier frequency, bandwidth, PRF, velocity, antenna beamwidth), the affected calculated values update immediately. Values are displayed with appropriate units and reasonable precision.

**Why this priority**: Engineers need to see the consequences of parameter changes in real time to configure valid simulations. Currently these values must be computed mentally or externally, which is error-prone and slow.

**Independent Test**: Can be tested by changing key parameters (carrier frequency, bandwidth, PRF, platform velocity, antenna beamwidth) and verifying that derived values update correctly against hand-calculated reference values.

**Acceptance Scenarios**:

1. **Given** the application is open with default parameters, **When** the user views the calculated values panel, **Then** they see at least: wavelength, range resolution, azimuth resolution, unambiguous range, pulse width, swath width, and NESZ.
2. **Given** the user changes the carrier frequency, **When** the value is committed, **Then** the wavelength and all frequency-dependent derived values update within 200 milliseconds.
3. **Given** the user changes the bandwidth, **When** the value is committed, **Then** range resolution and sample rate (if auto) update accordingly.
4. **Given** the user enters parameters that produce a physically invalid configuration (e.g., PRF too low for the swath), **When** the calculated values panel updates, **Then** affected values are flagged with a visual warning indicator.

---

### User Story 3 - Full Algorithm Parameter Exposure (Priority: P1)

The engineer selects an image formation algorithm (e.g., Range-Doppler) from a dropdown in the parameter tree, and its configurable parameters dynamically appear as child nodes inline in the tree below the algorithm selection. This applies to every processing step: image formation parameters (RCMC on/off, interpolation order), motion compensation parameters, autofocus parameters (convergence threshold, number of dominant scatterers, window fraction for PGA), geocoding parameters, and polarimetric decomposition parameters. Each algorithm's unique parameters appear conditionally as inline tree children when that algorithm is selected.

**Why this priority**: Many backend algorithm parameters exist but are not exposed in the GUI, forcing users to accept defaults they cannot see or change. Full parameter coverage is essential for a professional simulation tool.

**Independent Test**: Can be tested by selecting each algorithm in each processing step and verifying that all parameters defined in the backend algorithm class appear as editable fields in the GUI.

**Acceptance Scenarios**:

1. **Given** the user selects "Range-Doppler" for image formation, **When** the selection is made, **Then** fields appear for "Apply RCMC" (checkbox) and "RCMC Interpolation Order" (integer).
2. **Given** the user selects "PGA" for autofocus, **When** the selection is made, **Then** fields appear for max_iterations, convergence_threshold, n_dominant, and window_fraction.
3. **Given** the user selects "MinEntropy" for autofocus, **When** the selection is made, **Then** fields appear for max_iterations, convergence_threshold, and poly_order.
4. **Given** the user switches from one algorithm to another in any processing step, **When** the new algorithm is selected, **Then** the parameter fields update to show only the parameters relevant to the newly selected algorithm.
5. **Given** any algorithm in the backend has configurable parameters, **When** that algorithm is selectable in the GUI, **Then** all its parameters are editable.

---

### User Story 4 - Additional Visualization Panels (Priority: P2)

After running a simulation, the engineer can view not just the final focused SAR image, but also intermediate results. New visualization tabs include: (a) a range-compressed phase history waterfall, (b) a range profile plot showing power vs. range for a selected pulse or averaged, (c) an azimuth profile plot showing cross-range response, (d) a Doppler spectrum view, and (e) a polarimetric decomposition display (e.g., Pauli RGB composite). All 9 visualization tabs (4 existing + 5 new) are presented as flat tabs in a single tab bar. The visualization area also supports tiled/split display, allowing the user to view multiple plots side-by-side simultaneously (e.g., SAR image alongside range profile). Each panel has appropriate controls (colormap, dynamic range, slice selection) and updates when new results are available.

**Why this priority**: Intermediate visualizations are essential for diagnosing simulation quality, validating algorithm behavior, and understanding SAR phenomenology. Without them, users can only see the final image and must export data for external analysis.

**Independent Test**: Can be tested by running a simulation and pipeline, then verifying that each new visualization tab displays the correct data with appropriate axes, labels, and interactive controls.

**Acceptance Scenarios**:

1. **Given** a simulation has completed, **When** the user opens the "Phase History" tab, **Then** they see a 2D waterfall of range-compressed data with range on one axis and azimuth on the other.
2. **Given** a focused image exists, **When** the user opens the "Range Profile" tab, **Then** they see a 1D plot of power (dB) vs. range, with an option to select which azimuth line or to average across all.
3. **Given** a focused image exists, **When** the user opens the "Azimuth Profile" tab, **Then** they see a 1D plot of power (dB) vs. azimuth, with an option to select which range bin.
4. **Given** a quad-pol simulation and polarimetric decomposition have completed, **When** the user opens the "Polarimetry" tab, **Then** they see the decomposition results as a color composite image.
5. **Given** no simulation has been run yet, **When** the user views any new visualization tab, **Then** the tab displays a placeholder message indicating no data is available.
6. **Given** results are available in multiple tabs, **When** the user activates tiled/split view, **Then** two or more visualization panels are displayed side-by-side in the same area simultaneously.

---

### User Story 5 - Project Creation Wizard (Priority: P2)

When the engineer starts a new project, a step-by-step wizard guides them through configuring the simulation. The wizard presents a logical sequence of steps: (1) Project metadata and SAR mode selection, (2) Radar and waveform configuration with optional preset selection, (3) Platform and flight geometry, (4) Scene definition including target placement, (5) Processing pipeline configuration. Each step validates its inputs before allowing the user to proceed. The user can also skip the wizard and use direct parameter editing. Completed wizard results populate the parameter tree and editors.

**Why this priority**: New users and even experienced users benefit from a guided workflow when setting up a simulation from scratch. The current approach of resetting to defaults and editing a flat parameter list provides no guidance on what to configure first or what combinations are valid.

**Independent Test**: Can be tested by launching the wizard, completing each step with valid parameters, and verifying that the resulting parameter state matches what was entered. Also test canceling mid-wizard and verifying no state changes.

**Acceptance Scenarios**:

1. **Given** the user clicks "New Project" or uses Ctrl+N, **When** the action is triggered, **Then** a wizard dialog appears with the first step (project metadata / SAR mode).
2. **Given** the user is on step 2 (Radar), **When** they select a preset (e.g., "X-band airborne"), **Then** the radar, antenna, and waveform fields are pre-populated with the preset values.
3. **Given** the user completes all wizard steps, **When** they click "Finish", **Then** the main window's parameter tree and editors reflect all the values entered in the wizard.
4. **Given** the user cancels the wizard at any step, **When** they confirm cancellation, **Then** the application returns to its previous state with no parameter changes.
5. **Given** the user enters invalid values in a wizard step (e.g., near range > far range), **When** they try to proceed to the next step, **Then** a validation message indicates the error and prevents advancement.

---

### User Story 6 - Data Import Wizard (Priority: P2)

The engineer wants to load an existing HDF5 dataset for reprocessing. This covers two use cases: (a) reopening a previous PySimSAR simulation, and (b) importing real measurement data from an actual radar system. An import wizard walks them through: (1) selecting the file, (2) previewing the contents (channels, dimensions, metadata, and which project parameters are present vs. missing), (3) selecting which channels/data to import, (4) for partially-specified files (e.g., real measurement data), prompting the user to supply missing parameters (antenna, scene, etc.), (5) configuring the processing pipeline for the imported data. The wizard replaces the current simple file-picker approach and gives the user visibility into what they are importing before committing.

**Why this priority**: The current import is a blind file-picker with no preview. For HDF5 files that may contain multiple channels, polarizations, or large datasets, users need to inspect contents before importing. Real measurement data additionally requires parameter gap detection to ensure the processing pipeline has everything it needs.

**Independent Test**: Can be tested by importing a known HDF5 file and verifying that the preview correctly displays file contents, and that the selected data appears correctly in the application after import.

**Acceptance Scenarios**:

1. **Given** the user selects "Import Data" (Ctrl+I), **When** the action is triggered, **Then** an import wizard appears with a file selection step.
2. **Given** the user selects a valid HDF5 file, **When** they proceed to the preview step, **Then** they see a summary of the file contents: number of channels, data dimensions, sample rate, carrier frequency, and other metadata.
3. **Given** the file contains multiple polarization channels, **When** the user views the channel selection step, **Then** they can select which channels to import.
4. **Given** the user completes the import wizard, **When** they click "Finish", **Then** the imported data is loaded and the processing pipeline configuration step is shown.
5. **Given** the user selects a file that is not a valid HDF5 or lacks required datasets, **When** preview is attempted, **Then** a clear error message explains what is missing or invalid.
6. **Given** the user imports a real measurement HDF5 that contains raw data and trajectory but is missing antenna/scene parameters, **When** the preview step loads, **Then** the wizard clearly lists which parameters are present (populated from file) and which are missing (need user input), and provides fields or preset selection to fill the gaps before proceeding.
7. **Given** a fully-specified HDF5 file (e.g., from a previous PySimSAR save), **When** imported, **Then** all parameter tree fields are populated from the file with no manual input required.

---

### User Story 7 - Distributed Target Editor (Priority: P3)

The engineer wants to define distributed targets (ground clutter regions) visually rather than through the Python API only. A scene editor allows them to define rectangular distributed target regions with configurable extent, cell size, reflectivity pattern, and optional elevation profile. The editor provides a 2D overhead view of the scene for spatial placement and a preview of the reflectivity pattern.

**Why this priority**: Distributed targets currently require the Python API, which limits the GUI's usefulness for realistic scene modeling. However, point targets cover many use cases, making this lower priority than the structural and visualization improvements.

**Independent Test**: Can be tested by creating a distributed target region in the GUI editor, running a simulation, and verifying the distributed target appears in the 3D scene view and contributes to the simulation output.

**Acceptance Scenarios**:

1. **Given** the user is in the scene editor, **When** they click "Add Distributed Target", **Then** a configuration panel appears for specifying origin, extent, cell size, and reflectivity (either uniform with optional Gaussian noise via mean + standard deviation, or imported from a CSV/NumPy file).
2. **Given** the user defines a distributed target region, **When** the parameters are set, **Then** the 3D scene view shows the region as a surface patch.
3. **Given** a distributed target has been configured, **When** the simulation runs, **Then** the distributed target contributes to the simulated echo data.

---

### User Story 8 - Parameter Preset Browser and Management (Priority: P3)

The engineer wants to quickly load pre-configured parameter sets for common scenarios (e.g., "X-band airborne stripmap", "C-band spaceborne ScanSAR") rather than configuring every parameter from scratch. A preset browser shows available presets organized by category, with a preview of key parameters before applying. Users can also save their current configuration as a custom preset for future reuse.

**Why this priority**: The backend already supports parameter set serialization but the GUI has no access to it. This is a convenience feature that reduces setup time but doesn't block core functionality.

**Independent Test**: Can be tested by loading a preset from the browser, verifying all parameters match the preset definition, then saving a custom preset and reloading it in a new session.

**Acceptance Scenarios**:

1. **Given** the user opens the preset browser, **When** it displays, **Then** available presets are listed with category, name, and brief description.
2. **Given** the user selects a preset, **When** they click "Preview", **Then** a summary of key parameters (frequency, bandwidth, mode, velocity, altitude) is shown.
3. **Given** the user applies a preset, **When** they confirm, **Then** all parameter editors are fully overwritten with the preset values; any parameters not defined in the preset are reset to their defaults.
4. **Given** the user has customized parameters, **When** they click "Save as Preset", **Then** a dialog allows naming and categorizing the preset, and it appears in the browser for future use.

---

### Edge Cases

- What happens when the user resizes the window very small — does the tree panel remain usable with a minimum width, and do parameter editors remain scrollable?
- How does the calculated values panel behave when parameters are partially invalid (e.g., zero bandwidth) — does it show "N/A" or an error indicator rather than crashing?
- Presets perform a full overwrite of all parameters (undefined params reset to defaults), so cross-parameter conflicts from partial application cannot occur. If a preset's own values are internally inconsistent, the calculated values panel flags the issue after application.
- How does the import wizard handle very large HDF5 files (>1 GB) — does the preview load quickly without reading all data into memory?
- When the user changes the SAR mode (stripmap/spotlight/ScanSAR), mode-irrelevant parameters are disabled (grayed out) with a tooltip explaining why they are inactive. They remain visible in the tree to avoid layout jumping and to help users learn which parameters apply to each mode.
- How does the GUI handle parameters with interdependencies (e.g., changing PRF affects unambiguous range and Doppler) — is the calculated values panel the sole indicator, or are parameter fields themselves annotated?

## Requirements *(mandatory)*

### Functional Requirements

**Parameter Navigation & Editing:**

- **FR-001**: The system MUST present all simulation parameters in a hierarchical tree structure with at least two levels of nesting (category > sub-group), with parameter values editable inline directly within tree rows (the tree IS the editor — no separate editor pane).
- **FR-001a**: Algorithm-specific parameters MUST be dynamically loaded as inline child nodes in the tree when an algorithm is selected from its dropdown.
- **FR-002**: The system MUST preserve all existing parameter editing capabilities from the current flat sidebar — no parameter may become inaccessible after the tree migration.
- **FR-002a**: Every parameter in the tree MUST display a descriptive tooltip on mouse hover, explaining what the parameter does, its valid range, and its unit. Tooltips are enabled by default and can be turned off in the Preferences menu.
- **FR-003**: The system MUST support search/filter functionality within the parameter tree, allowing users to find parameters by name or keyword.
- **FR-003a**: When the SAR mode changes, the system MUST disable (gray out) mode-irrelevant parameters in the tree and editors, with a tooltip on each disabled field explaining which mode(s) it applies to. Disabled parameters remain visible but not editable.
- **FR-004**: The system MUST display a live-updating calculated values panel in the bottom-right area of the main window (below the visualization tabs, above the full-width status bar), always visible. The parameter tree is to its left. It shows derived quantities: wavelength, resolutions, unambiguous range/Doppler, NESZ, swath width, pulse width, synthetic aperture length, Doppler bandwidth, number of range samples, single-look SNR estimate, and flight path derived values (n_pulses, flight time, track length, heading or stop position depending on input mode).
- **FR-005**: The calculated values panel MUST update within 200 milliseconds of any parameter change.
- **FR-006**: The system MUST visually flag calculated values that indicate a physically problematic configuration (e.g., PRF too low for swath, range ambiguity).

**Platform Flight Path:**

- **FR-006a**: The system MUST allow the user to specify the platform flight path using one of two modes: (a) **Start + Stop position** — the user provides start and stop coordinates, and heading, flight time, velocity, and n_pulses are derived; or (b) **Start + Heading + Velocity + Flight time** — the user provides these four values, and stop position and n_pulses are derived. The user selects which mode to use.
- **FR-006b**: When the flight path mode is changed or any flight path input is modified, all derived quantities (heading, flight time, n_pulses, stop position, track length) MUST update automatically in the calculated values panel.
- **FR-006c**: The `n_pulses` parameter MUST become a derived (read-only) value computed from `PRF × flight_time`, displayed in the calculated values panel rather than as a user-editable input.

**Algorithm Parameters:**

- **FR-007**: For each selectable algorithm in every processing step (image formation, motion compensation, autofocus, geocoding, polarimetric decomposition), the system MUST expose all configurable parameters defined in the backend algorithm class.
- **FR-008**: Algorithm-specific parameters MUST appear conditionally — only when the corresponding algorithm is selected.
- **FR-009**: Each algorithm parameter MUST have an appropriate input widget (checkbox for booleans, spinner for numerics, dropdown for enums) with valid range constraints matching the backend.

**Visualization:**

- **FR-010**: The system MUST provide a range-compressed phase history visualization as a 2D waterfall display.
- **FR-011**: The system MUST provide a range profile visualization showing power (dB) vs. range with selectable azimuth line or averaging.
- **FR-012**: The system MUST provide an azimuth profile visualization showing power (dB) vs. cross-range with selectable range bin.
- **FR-013**: The system MUST provide a polarimetric decomposition display for quad-pol results.
- **FR-014**: Each visualization panel MUST display a placeholder message when no data is available.
- **FR-015**: The system MUST capture intermediate pipeline results (range-compressed data, per-step outputs) and make them available to visualization panels.
- **FR-015a**: The visualization area MUST support tiled/split display, allowing two or more panels to be viewed side-by-side simultaneously.
- **FR-015b**: The 3D scene viewer MUST use a proper low-poly aircraft model loaded from a mesh file (OBJ or STL) stored in an assets directory, replacing the current crude procedural mesh. The model must be oriented along the platform heading and scaled appropriately to the scene.

**Image Plot Tools:**

- **FR-015c**: The image viewer MUST provide a "Find Peak" tool: the user drags a rectangular region on the plot, and the system finds the peak value within that region, places a marker at the peak location, and displays the x, y, and z (value) coordinates using the axis units.
- **FR-015d**: Peak markers MUST default to a circle shape (hollow, so the underlying data point remains visible). The marker shape MUST be configurable by right-clicking the marker and selecting from a context menu of available shapes (e.g., circle, crosshair, diamond, square, triangle).
- **FR-015e**: Multiple peak markers MAY coexist on the same plot (one per find-peak operation). The user MUST be able to remove individual markers via the right-click context menu or clear all markers at once.

**Project Workflow:**

- **FR-016**: The system MUST provide a multi-step project creation wizard that guides users through SAR mode selection, radar configuration, platform setup, scene definition, and processing pipeline.
- **FR-017**: Each wizard step MUST validate inputs before allowing advancement to the next step.
- **FR-018**: The wizard MUST support loading parameter presets at relevant steps.
- **FR-019**: The system MUST allow users to bypass the wizard and configure parameters directly.
- **FR-020**: The system MUST provide a data import wizard that previews HDF5 file contents (channels, dimensions, metadata) before importing.
- **FR-021**: The import wizard MUST allow selecting which channels to import from multi-channel files.

**Scene Editing:**

- **FR-022**: The system MUST provide a GUI editor for distributed targets with configurable origin, extent, cell size, and reflectivity. Reflectivity input supports two modes: (a) uniform value with optional Gaussian noise (mean + standard deviation), and (b) import from file (CSV or NumPy .npy) with a preview of the loaded pattern.
- **FR-023**: The system MUST display distributed targets in the 3D scene viewer.

**Preset Management:**

- **FR-024**: The system MUST provide a preset browser that lists available parameter presets organized by category, showing both system presets (shipped with the application, read-only) and user presets (created by the user, read-write). The two tiers MUST be visually distinguishable.
- **FR-024a**: System presets reside in the package installation directory and MUST NOT be modifiable by users. User presets reside in a platform-appropriate user data directory (e.g., `%APPDATA%/PySimSAR/presets/` on Windows, `~/.pysimsar/presets/` on Linux/macOS).
- **FR-024b**: Users MUST be able to duplicate a system preset into their user presets for customization.
- **FR-024c**: Users MUST be able to edit and delete their own user presets from the preset browser.
- **FR-025**: Users MUST be able to save their current parameter configuration as a named user preset.
- **FR-026**: Users MUST be able to preview preset parameter values before applying.

**Project File Management:**

- **FR-026a**: A project MUST be stored as a self-contained project directory containing a master `project.json` file, component JSON files, and any binary data files (`.npy`, `.csv`). No saved project may reference external files outside its directory (all `$preset/` references are resolved and copied into the project on save).
- **FR-026b**: The system MUST support packing a project directory into a single `.pysimsar` archive file (zip-based) for sharing/archiving, and unpacking a `.pysimsar` file back into a working project directory on open.
- **FR-026c**: The "Save Project" and "Open Project" workflows MUST support both the project directory format and the `.pysimsar` archive format.

**HDF5 / Real Measurement Data Compatibility:**

- **FR-026d**: The HDF5 file schema MUST be extended to store the complete project parameter set — the same information that `project.json` contains — so that HDF5 and project directory formats are interchangeable representations of the same project state. This includes full radar parameters (transmit power, receiver gain, noise figure, system losses, squint angle, depression angle, look side), antenna parameters (pattern type, beamwidths, peak gain), waveform details (duty cycle, phase noise, window, ramp type), platform parameters (velocity, heading, turbulence model, sensor configs), scene definition (targets, origin), and simulation/processing configuration.
- **FR-026e**: When importing an HDF5 file (from simulation or real measurement), the system MUST populate all matching fields in the parameter tree. Parameters present in the HDF5 populate their corresponding tree entries; parameters absent from the file MUST be clearly indicated as "not provided" (not silently defaulted), allowing the user to fill them in manually before processing.
- **FR-026f**: The import wizard MUST distinguish between a fully-specified HDF5 (all parameters present, ready to process) and a partially-specified HDF5 (e.g., real measurement data with only radar/trajectory metadata), and clearly show the user which parameters are missing and need to be supplied.
- **FR-026g**: When saving a project as HDF5, the system MUST write the complete parameter set so that the file can be re-opened on any machine and fully reconstruct the project state without any external dependencies.

**Preferences:**

- **FR-027**: The system MUST provide a Preferences menu (accessible from the menu bar) for application-wide settings.
- **FR-028**: The Preferences menu MUST include an option to enable/disable parameter hover tooltips (enabled by default).
- **FR-029**: User preference settings MUST persist across application sessions, stored in the user data directory alongside user presets (e.g., `%APPDATA%/PySimSAR/preferences.json`).

### Key Entities

- **Parameter Tree**: Hierarchical organization of all configurable parameters, with categories, sub-groups, and individual parameter entries. Each entry maps to a backend parameter with type, range, unit, and default value.
- **Calculated Value**: A derived quantity computed from one or more input parameters. Has a name, formula/dependency list, display unit, precision, and optional validity range with warning thresholds.
- **Parameter Preset**: A named, categorized collection of parameter values that can be saved, loaded, and applied to the parameter tree. Two tiers: system presets (read-only, shipped with the application in the package directory) and user presets (read-write, stored in the user data directory).
- **Project**: A self-contained directory with a master `project.json`, component JSON files, and binary data. Can be packed into a `.pysimsar` archive for sharing. All external references are resolved on save so projects are fully portable.
- **User Data Directory**: Platform-specific directory for persistent user data: user presets, application preferences, and other user-level configuration. Separate from project directories and the package installation.
- **Wizard Step**: A discrete stage in a multi-step workflow (project creation or data import) with its own parameter subset, validation rules, and navigation controls.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every parameter accessible via the backend configuration classes is reachable and editable through the GUI — zero parameters are API-only (excluding custom antenna pattern arrays and distributed target reflectivity arrays exceeding a simple grid).
- **SC-002**: Users can locate any parameter in the tree within 3 clicks or via search in under 5 seconds.
- **SC-003**: The calculated values panel correctly displays at least 12 derived quantities, verified against hand-calculated reference values for 3 different parameter configurations.
- **SC-004**: A new user can configure and run a basic stripmap SAR simulation using the project wizard in under 5 minutes, without consulting documentation.
- **SC-005**: All 5 new visualization panels (phase history, range profile, azimuth profile, Doppler spectrum, polarimetry) display correct data verified against independently computed reference values.
- **SC-006**: The import wizard correctly previews and imports HDF5 files produced by the application's own save function, with no data loss or misinterpretation.
- **SC-007**: Parameter presets can be saved and reloaded across application sessions with 100% fidelity.
- **SC-008**: The GUI remains responsive (no perceptible lag >200ms) during parameter editing and tree navigation for parameter sets of any size supported by the backend.

## Assumptions

- The application will continue to use the existing GUI framework (PyQt6 + pyqtgraph + matplotlib) — this is a GUI restructuring, not a framework migration.
- The project supports three file formats: JSON-based project directory, `.pysimsar` archive, and HDF5 (extended to store the complete parameter set). HDF5 serves as both a save format and the import format for real measurement data. External SAR formats (SICD, NITF, GeoTIFF) are out of scope.
- Distributed target reflectivity arrays are defined numerically (grid values) in the GUI; procedural/generative clutter models remain API-only for this iteration.
- The existing backend parameter validation and unit conversion logic is correct and will be reused.
- Parameter presets are stored locally: system presets in the package directory (read-only), user presets in the user data directory (read-write). Cloud sync or multi-user preset sharing is out of scope.

## Scope Boundaries

**In scope:**
- Tree-based parameter panel replacing flat sidebar
- Calculated values panel with live updates and validation warnings
- Full algorithm parameter exposure for all processing steps
- 5 new visualization panels (phase history, range profile, azimuth profile, Doppler spectrum, polarimetry) with tiled/split display support
- Project creation wizard with preset support
- Data import wizard with HDF5 preview
- Distributed target GUI editor (basic grid-based)
- Two-tier preset system (system read-only + user read-write) with browser, duplicate, edit, delete
- Self-contained project directory format with `.pysimsar` archive support
- User data directory for presets and preferences
- HDF5 schema extended to full project parameter parity
- Real measurement data import with parameter gap detection
- Parameter hover tooltips with toggle in Preferences menu
- Preferences menu with persistent user settings
- Proper low-poly 3D aircraft model (OBJ/STL) replacing crude procedural mesh

**Out of scope:**
- Backend algorithm changes or new algorithm development
- New SAR modes or signal generation features
- External file format import/export (SICD, NITF, GeoTIFF)
- Custom antenna pattern design tool (complex 2D array editor)
- Multi-user or networked preset sharing
- Automated parameter optimization or sweep
- Performance profiling or GPU acceleration
