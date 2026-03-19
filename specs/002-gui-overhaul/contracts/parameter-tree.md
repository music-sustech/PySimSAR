# Contract: Parameter Tree Widget

## Interface

The parameter tree widget is the primary configuration interface. It replaces the current flat sidebar of QGroupBox editors.

### Tree Structure

```
Column 0: Parameter Name (with icon for categories)
Column 1: Value Widget (inline editor)
```

### Node Types

| Type | Column 0 | Column 1 | Expandable |
|------|----------|----------|------------|
| CATEGORY | Icon + bold name | Empty | Yes |
| GROUP | Name | Empty | Yes |
| PARAMETER | Name | Widget (spinbox/combo/checkbox) | No |
| ALGORITHM_SELECTOR | Name | Dropdown | Yes (dynamic children) |

### Signals

- `parameter_changed(key: str, value: Any)` — Emitted when any parameter value changes. Key is the full dot-path (e.g., "radar.carrier_freq").
- `tree_ready()` — Emitted after tree is fully populated.

### Methods

- `get_all_parameters() -> dict` — Returns complete parameter dict (nested, matching project.json structure).
- `set_all_parameters(params: dict)` — Populates tree from parameter dict.
- `set_parameter(key: str, value: Any)` — Sets a single parameter by dot-path.
- `set_mode_constraints(mode: str)` — Enables/disables parameters based on SAR mode.
- `filter(text: str)` — Shows only parameters matching search text.
- `clear_filter()` — Restores all parameters to visible.

### Scroll/Focus Protection

All embedded widgets MUST use `_no_scroll_unless_focused()` to prevent accidental value changes during panel scrolling.

### Tooltip Contract

Every PARAMETER node MUST set `QTreeWidgetItem.setToolTip(0, ...)` with:
- Parameter description (1 sentence)
- Valid range: "Range: [min, max] {unit}"
- Default value: "Default: {value} {unit}"

Tooltips are globally togglable via `UserPreferences.tooltips_enabled`.
