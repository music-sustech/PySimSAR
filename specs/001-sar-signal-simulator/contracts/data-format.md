# Contract: HDF5 Data Format Specification

## Overview

All PySimSAR data is stored in HDF5 files (`.h5`) via the h5py library.
HDF5 provides hierarchical structure, self-describing metadata via
attributes, efficient storage of large numerical arrays, and default
compression.

## File Structure

```text
pySimSAR_data.h5
├── /metadata
│   ├── @software_version      # str: "pySimSAR x.y.z"
│   ├── @creation_date         # str: ISO 8601 datetime
│   ├── @coordinate_system     # str: "ENU"
│   ├── @origin_lat            # float: WGS84 latitude of ENU origin
│   ├── @origin_lon            # float: WGS84 longitude of ENU origin
│   └── @origin_alt            # float: WGS84 altitude of ENU origin (m)
│
├── /config
│   ├── @simulation_config     # str: JSON-serialized SimulationConfig
│   └── @processing_config     # str: JSON-serialized ProcessingConfig (if processed)
│
├── /raw_data
│   └── /{channel}             # channel = "hh", "hv", "vh", "vv", or "single"
│       ├── echo               # dataset: complex64/128, shape (n_range, n_azimuth)
│       ├── @carrier_freq      # float: Hz
│       ├── @bandwidth         # float: Hz
│       ├── @prf               # float: Hz
│       ├── @sample_rate       # float: Hz
│       ├── @waveform          # str: waveform name
│       ├── @sar_mode          # str: "stripmap", "spotlight", "scanmar"
│       └── @polarization      # str: channel label
│
├── /navigation
│   ├── /trajectory
│   │   ├── time               # dataset: float64, shape (n_pulses,), seconds
│   │   ├── position           # dataset: float64, shape (n_pulses, 3), ENU meters
│   │   ├── velocity           # dataset: float64, shape (n_pulses, 3), m/s
│   │   └── attitude           # dataset: float64, shape (n_pulses, 3), Euler rad
│   │
│   ├── /gps
│   │   ├── time               # dataset: float64, shape (n_gps,)
│   │   ├── position           # dataset: float64, shape (n_gps, 3)
│   │   ├── @accuracy_rms      # float: meters
│   │   ├── @update_rate       # float: Hz
│   │   └── @rtk_mode          # bool
│   │
│   └── /imu
│       ├── time               # dataset: float64, shape (n_imu,)
│       ├── acceleration       # dataset: float64, shape (n_imu, 3), m/s^2
│       ├── angular_rate       # dataset: float64, shape (n_imu, 3), rad/s
│       ├── @bias_stability_accel  # float: m/s^2
│       ├── @bias_stability_gyro   # float: rad/s
│       └── @sample_rate       # float: Hz
│
└── /images
    └── /{name}                # e.g., "rda_stripmap", "csa_spotlight"
        ├── data               # dataset: complex64/128 or float32
        ├── @algorithm         # str: algorithm name
        ├── @pixel_spacing_range   # float: meters
        ├── @pixel_spacing_azimuth # float: meters
        ├── @geometry          # str: "slant_range", "ground_range", "geographic"
        ├── @polarization      # str: channel label
        ├── @geo_transform     # float64[6]: affine transform (if georeferenced)
        └── @projection_wkt   # str: WKT projection string (if georeferenced)
```

## Conventions

- **Attribute prefix `@`** denotes HDF5 attributes (as opposed to datasets)
- **Complex data**: stored as native HDF5 complex type (`complex64` or `complex128`)
- **Compression**: gzip level 4 for all datasets > 1 MB
- **Chunk size**: auto-determined by h5py for datasets > 1 MB
- **Units**: SI throughout (meters, seconds, Hz, radians)
- **Time reference**: seconds since simulation start (epoch stored in config)

## Round-Trip Fidelity

All read/write operations MUST preserve bit-exact fidelity. This is
verified by SC-004: saving and reloading any data type produces
identical arrays (byte-for-byte comparison via `np.array_equal`).

## Extensibility

Additional groups or datasets can be added to the file without breaking
existing readers. Readers MUST ignore unrecognized groups/datasets.
All required fields are listed above; any additional fields are optional.
