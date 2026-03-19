# Contract: Project File Format

## Project Directory Structure

```
my_project/
├── project.json              # Master manifest
├── scene.json                # Scene definition ($ref'd)
├── radar.json                # Radar config ($ref'd, includes waveform/antenna refs)
├── waveform.json             # Waveform parameters ($ref'd by radar.json)
├── antenna.json              # Antenna parameters ($ref'd by radar.json)
├── platform.json             # Platform/flight path ($ref'd)
├── processing.json           # Processing pipeline config ($ref'd, optional)
├── *.npy                     # Binary data (large target arrays, patterns)
└── metadata.json             # Archive metadata (only in .pysimsar)
```

## project.json Schema

```json
{
  "format_version": "1.0",
  "metadata": {
    "created_at": "ISO8601",
    "last_modified_at": "ISO8601",
    "pysimsar_version": "0.2.0"
  },
  "name": "Project Name",
  "description": "Optional description",
  "scene": {"$ref": "scene.json"},
  "radar": {"$ref": "radar.json"},
  "platform": {"$ref": "platform.json"},
  "simulation": {
    "seed": 42,
    "sample_rate_hz": null,
    "scene_center_m": null,
    "n_subswaths": 3,
    "burst_length": 20,
    "swath_range_m": null
  },
  "processing": {"$ref": "processing.json"}
}
```

Note: `n_pulses` is no longer stored — it is derived from `PRF * flight_time`.

## .pysimsar Archive

- File extension: `.pysimsar`
- Format: Standard ZIP (Python `zipfile` module, `ZIP_DEFLATED`)
- Contents: Exact same files as project directory (no nesting — files at zip root)
- No external references: All `$preset/` refs resolved before archiving

## Self-Containment Rule

A saved project (directory or archive) MUST NOT reference any file outside its boundary. On save:
1. Resolve all `$preset/...` references by copying preset content inline
2. Resolve all `$ref` to files within the project directory
3. Write all binary data as `.npy` files within the project directory

## Interchangeability with HDF5

The same project state can be represented as:
- Project directory (JSON + binary files)
- .pysimsar archive (zip of the above)
- HDF5 file (structured `/parameters` group + data groups)

All three formats MUST produce identical parameter state when loaded.
