# Quickstart: GUI Overhaul Implementation

**Branch**: `002-gui-overhaul`

## Prerequisites

- Python 3.14 (at `C:\Users\Xiaoguang\AppData\Local\Programs\Python\Python314\python.exe`)
- PyQt6 >= 6.5, pyqtgraph >= 0.13, matplotlib >= 3.7, PyOpenGL >= 3.1
- New dependencies: `trimesh >= 3.20` (OBJ/STL loading), `platformdirs >= 3.0` (user data dir)

## Key Architecture Decisions

1. **Parameter tree**: QTreeWidget + `setItemWidget()` — tree IS the editor, no separate pane
2. **Tiled visualization**: QSplitter-based — tab bar + splittable content area
3. **Calculated values**: `SARCalculator` in library layer, GUI panel just displays results
4. **Project files**: JSON directory + .pysimsar zip archive + extended HDF5
5. **User data**: `platformdirs` for cross-platform path resolution
6. **Aircraft model**: trimesh to parse OBJ/STL, feed to pyqtgraph GLMeshItem

## Implementation Order

### Phase 1: Foundation (P1 stories)
1. `SARCalculator` class in `pySimSAR/core/` (library, tested first)
2. `ParameterTreeWidget` replacing flat sidebar
3. Calculated values panel (bottom-right)
4. Algorithm parameter exposure in tree
5. Flight path input modes
6. Main window layout restructure

### Phase 2: Visualization & Workflow (P2 stories)
7. New visualization panels (5 panels)
8. Tiled/split display support
9. Pipeline intermediate result capture
10. Image plot tools (find peak, markers)
11. Project creation wizard
12. Data import wizard
13. HDF5 schema extension

### Phase 3: Polish & Extras (P3 stories)
14. Distributed target editor
15. Preset browser with two-tier system
16. .pysimsar archive format
17. User data directory + preferences
19. OBJ aircraft model
20. Parameter tooltips

## File Layout

```
pySimSAR/
├── core/
│   └── calculator.py          # NEW: SARCalculator
├── assets/
│   ├── models/
│   │   └── aircraft.obj       # NEW: 3D aircraft model
│   └── icons/                 # (reserved for future use)
├── gui/
│   ├── app.py                 # MODIFIED: New layout with splitters
│   ├── widgets/
│   │   ├── param_tree.py      # NEW: QTreeWidget-based parameter tree
│   │   ├── param_editor.py    # DEPRECATED: Replaced by param_tree.py
│   │   ├── algorithm_selector.py  # DEPRECATED: Integrated into tree
│   │   ├── calc_panel.py      # NEW: Calculated values panel
│   │   ├── peak_tool.py       # NEW: Find-peak tool for image plots
│   │   └── preset_browser.py  # NEW: Two-tier preset browser dialog
│   ├── panels/
│   │   ├── scene_3d.py        # MODIFIED: OBJ model loading
│   │   ├── image_viewer.py    # MODIFIED: Peak tool integration
│   │   ├── phase_history.py   # NEW: Range-compressed waterfall
│   │   ├── range_profile.py   # NEW: 1D range profile
│   │   ├── azimuth_profile.py # NEW: 1D azimuth profile
│   │   ├── doppler_spectrum.py # NEW: Doppler spectrum
│   │   ├── polarimetry.py     # NEW: Polarimetric decomposition display
│   │   └── tiled_view.py      # NEW: QSplitter-based tiled panel manager
│   ├── wizards/
│   │   ├── __init__.py        # NEW
│   │   ├── project_wizard.py  # NEW: Multi-step project creation
│   │   └── import_wizard.py   # NEW: HDF5 import with preview
│   └── controllers/
│       └── simulation_ctrl.py # MODIFIED: Intermediate result capture
├── io/
│   ├── hdf5_format.py         # MODIFIED: Extended schema v2
│   ├── parameter_set.py       # MODIFIED: Self-contained save
│   ├── archive.py             # NEW: .pysimsar zip handling
│   └── user_data.py           # NEW: User data directory management
└── pipeline/
    └── runner.py              # MODIFIED: Capture intermediate results
```

## Testing Strategy

- **Unit tests**: SARCalculator formulas, parameter tree get/set, HDF5 schema round-trip, archive pack/unpack
- **Widget tests** (pytest-qt): Tree inline editing, calculated values update latency, wizard navigation, preset browser CRUD
- **Integration tests**: Full project save/load cycle across all 3 formats, import wizard with real measurement HDF5
- **Golden tests**: Calculated values verified against hand-computed references (3 configs per SC-003)
