# API Reference: I/O

## ProcessingConfig

`pySimSAR.io.config.ProcessingConfig`

Configuration for the SAR processing pipeline. Controls algorithm selection
for each processing step, decoupled from simulation configuration.

### Constructor

```python
ProcessingConfig(
    image_formation: str,
    image_formation_params: dict | None = None,
    moco: str | None = None,
    moco_params: dict | None = None,
    autofocus: str | None = None,
    autofocus_params: dict | None = None,
    geocoding: str | None = None,
    geocoding_params: dict | None = None,
    polarimetric_decomposition: str | None = None,
    polarimetric_decomposition_params: dict | None = None,
    description: str = "",
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `image_formation` | `str` | (required) | Image formation algorithm name (e.g. `"range_doppler"`, `"chirp_scaling"`, `"omega_k"`). |
| `image_formation_params` | `dict \| None` | `None` | Algorithm constructor kwargs (e.g. `{"apply_rcmc": True}`). |
| `moco` | `str \| None` | `None` | Motion compensation algorithm name. None = skip. |
| `moco_params` | `dict \| None` | `None` | MoCo constructor kwargs. |
| `autofocus` | `str \| None` | `None` | Autofocus algorithm name. None = skip. |
| `autofocus_params` | `dict \| None` | `None` | Autofocus constructor kwargs. |
| `geocoding` | `str \| None` | `None` | Geocoding algorithm name. None = skip. |
| `geocoding_params` | `dict \| None` | `None` | Geocoding constructor kwargs. |
| `polarimetric_decomposition` | `str \| None` | `None` | Polarimetric decomposition name. None = skip. |
| `polarimetric_decomposition_params` | `dict \| None` | `None` | Decomposition constructor kwargs. |
| `description` | `str` | `""` | Description of this processing configuration. |

### Properties

All constructor parameters are exposed as read-only properties:
`image_formation`, `image_formation_params`, `moco`, `moco_params`,
`autofocus`, `autofocus_params`, `geocoding`, `geocoding_params`,
`polarimetric_decomposition`, `polarimetric_decomposition_params`,
`description`.

### Methods

| Method | Signature | Returns | Description |
|---|---|---|---|
| `to_json()` | `()` | `str` | Serialize to JSON string. |
| `from_json()` | `(json_str: str)` | `ProcessingConfig` | Class method. Deserialize from JSON. |

---

## write_hdf5

`pySimSAR.io.hdf5_format.write_hdf5`

Write PySimSAR data to an HDF5 file.

```python
write_hdf5(
    filepath: str | Path,
    *,
    raw_data: dict[str, RawData] | None = None,
    trajectory: Trajectory | None = None,
    navigation_data: list[NavigationData] | None = None,
    images: dict[str, SARImage] | None = None,
    simulation_config_json: str | None = None,
    processing_config_json: str | None = None,
    origin_lat: float = 0.0,
    origin_lon: float = 0.0,
    origin_alt: float = 0.0,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `filepath` | `str \| Path` | (required) | Output HDF5 file path. |
| `raw_data` | `dict[str, RawData] \| None` | `None` | Raw echo data keyed by channel name. |
| `trajectory` | `Trajectory \| None` | `None` | Platform trajectory. |
| `navigation_data` | `list \| None` | `None` | Sensor measurement objects. |
| `images` | `dict[str, SARImage] \| None` | `None` | Focused images keyed by name. |
| `simulation_config_json` | `str \| None` | `None` | JSON-serialized SimulationConfig. |
| `processing_config_json` | `str \| None` | `None` | JSON-serialized ProcessingConfig. |
| `origin_lat`, `origin_lon`, `origin_alt` | `float` | `0.0` | WGS84 origin for ENU reference. |

### HDF5 file structure

```
/metadata/           -- software_version, creation_date, coordinate_system, origin_*
/config/             -- simulation_config, processing_config (JSON attrs)
/raw_data/{channel}/ -- echo (dataset), carrier_freq, bandwidth, prf, sample_rate (attrs)
/navigation/trajectory/  -- time, position, velocity, attitude (datasets)
/navigation/{source}/    -- time, position, acceleration, angular_rate (datasets)
/images/{name}/      -- data (dataset), algorithm, pixel_spacing_*, geometry (attrs)
```

Arrays larger than 1 MB are gzip-compressed.

---

## read_hdf5

`pySimSAR.io.hdf5_format.read_hdf5`

Read PySimSAR data from an HDF5 file.

```python
read_hdf5(filepath: str | Path) -> dict
```

**Returns** a dictionary with keys:

| Key | Type | Description |
|---|---|---|
| `"metadata"` | `dict` | Metadata attributes. |
| `"config"` | `dict` | JSON config strings (`"simulation_config"`, `"processing_config"`). |
| `"raw_data"` | `dict[str, RawData]` | Raw data keyed by channel. |
| `"trajectory"` | `Trajectory \| None` | Platform trajectory. |
| `"navigation_data"` | `list[NavigationData]` | Sensor measurements. |
| `"images"` | `dict[str, SARImage]` | Images keyed by name. |

---

## import_data

`pySimSAR.io.hdf5_format.import_data`

Convenience wrapper around `read_hdf5` for processing-only workflows.

```python
import_data(filepath: str | Path) -> dict
```

**Returns** a dictionary with keys:

| Key | Type | Description |
|---|---|---|
| `"raw_data"` | `dict[str, RawData]` | Raw echo data. |
| `"trajectory"` | `Trajectory \| None` | Platform trajectory. |
| `"navigation_data"` | `list[NavigationData]` | Sensor measurements. |
| `"radar_params"` | `dict` | Extracted radar parameters (`carrier_freq`, `bandwidth`, `prf`, `sample_rate`, `waveform_name`, `sar_mode`). |

**Raises** `ValueError` if the file contains no raw data.

---

## Parameter set functions

`pySimSAR.io.parameter_set`

### resolve_refs

```python
resolve_refs(data: dict | list, base_dir: Path) -> dict | list
```

Recursively resolve all `$ref` and `$data` entries in a nested JSON
structure.

| Feature | Syntax | Description |
|---|---|---|
| JSON reference | `{"$ref": "radar.json"}` | Replace with contents of the referenced file. |
| Preset reference | `{"$ref": "$preset/waveforms/lfm.json"}` | Resolve from the built-in presets directory. |
| Binary data | `{"$data": "targets.npy"}` | Load `.npy`, `.npz`, or `.csv` files as numpy arrays. |

Circular references are detected and raise `ValueError`.

### load_parameter_set

```python
load_parameter_set(project_path: str | Path) -> dict
```

Load a parameter set from a project directory. Reads `project.json`,
resolves all `$ref` and `$data` entries, strips unit suffixes from keys,
and converts degree values to radians.

| Parameter | Type | Description |
|---|---|---|
| `project_path` | `str \| Path` | Path to project directory (containing `project.json`) or to a `project.json` file directly. |

**Returns** a fully resolved parameter dictionary.

### build_simulation

```python
build_simulation(params: dict) -> dict
```

Construct simulation objects from a resolved parameter dictionary.

**Returns** a dictionary with keys:

| Key | Type | Description |
|---|---|---|
| `"scene"` | `Scene` | Constructed scene with targets. |
| `"radar"` | `Radar` | Configured radar system. |
| `"platform"` | `Platform` | Platform configuration. |
| `"engine_kwargs"` | `dict` | Keyword arguments for `SimulationEngine` (`n_pulses`, `seed`, `sample_rate`, `sar_mode_config`, `swath_range`). |
| `"processing_config"` | `ProcessingConfig \| None` | Processing pipeline configuration. |

### save_parameter_set

```python
save_parameter_set(
    output_dir: str | Path,
    *,
    scene: Scene,
    radar: Radar,
    platform: Platform,
    seed: int,
    sample_rate: float | None = None,
    swath_range: tuple[float, float] | None = None,
    processing_config: ProcessingConfig | None = None,
    name: str = "",
    description: str = "",
    flight_time: float = 0.5,
) -> Path
```

Serialize a complete simulation setup to a project directory. Creates
`project.json` with `$ref` links to component files (`scene.json`,
`radar.json`, `sarmode.json`, `platform.json`, `processing.json`).

**Returns** the output directory path.

### make_window

```python
make_window(window_name: str | None, window_params: dict | None = None) -> Callable | None
```

Create a window function callable from a name string. Returns
`f(n) -> np.ndarray` or `None`.

Supported names: `"hamming"`, `"hanning"`, `"blackman"`, `"kaiser"` (param: `beta`), `"tukey"` (param: `alpha`).

---

## pack_project / unpack_project

`pySimSAR.io.archive`

### pack_project

```python
pack_project(dir_path: str | Path, archive_path: str | Path) -> Path
```

Create a `.pysimsar` archive (ZIP) from a project directory.

| Parameter | Type | Description |
|---|---|---|
| `dir_path` | `Path` | Project directory containing `project.json`. |
| `archive_path` | `Path` | Destination archive path (should end with `.pysimsar`). |

**Returns** the archive path.

### unpack_project

```python
unpack_project(archive_path: str | Path, dir_path: str | Path) -> Path
```

Extract a `.pysimsar` archive to a directory.

| Parameter | Type | Description |
|---|---|---|
| `archive_path` | `Path` | Path to the `.pysimsar` archive. |
| `dir_path` | `Path` | Destination directory (created if needed). |

**Returns** the destination directory path.
