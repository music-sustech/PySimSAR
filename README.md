# PySimSAR

**Python SAR Raw Signal Simulator with Modular Processing Algorithms**

PySimSAR is an open-source synthetic aperture radar (SAR) simulation and
processing toolkit. It generates realistic raw SAR echo signals from
user-defined scenes and processes them into focused images using
industry-standard algorithms — all in pure Python with NumPy/SciPy.

## Features

- **Signal Simulation** — Pulse-by-pulse echo generation with LFM and FMCW waveforms, antenna pattern modeling, and platform motion
- **Image Formation** — Range-Doppler, Chirp Scaling, and Omega-K algorithms for stripmap and spotlight modes
- **Motion Compensation** — First-order and second-order MoCo with GPS/IMU navigation data
- **Autofocus** — PGA, Map Drift, Minimum Entropy, and Prominent Point Processing
- **Geocoding** — Slant-to-ground range projection and geographic georeferencing
- **Polarimetry** — Pauli, Freeman-Durden, Yamaguchi, and Cloude-Pottier decompositions
- **GUI** — Interactive PyQt6 application for parameter editing, simulation control, and visualization
- **Extensible** — Registry-based plugin architecture for adding custom algorithms, waveforms, and sensors

## Installation

```bash
pip install pySimSAR          # core library only
pip install pySimSAR[gui]     # with GUI support
pip install pySimSAR[dev]     # development (includes GUI + pytest + ruff)
```

**Requirements:** Python 3.10+

## Quick Start

```python
import pySimSAR as ps

# Define a scene with point targets
scene = ps.Scene()
scene.add_target(ps.PointTarget(x=0, y=0, z=0, rcs=1.0))

# Configure radar and platform
radar = ps.Radar.from_preset("default_radar")
platform = ps.Platform.from_preset("default_platform")

# Simulate raw SAR signal
config = ps.SimulationConfig(radar=radar, platform=platform, scene=scene)
engine = ps.SimulationEngine(config)
result = engine.run()

# Form image using Range-Doppler Algorithm
proc_config = ps.ProcessingConfig(algorithm="rda")
pipeline = ps.PipelineRunner(proc_config)
output = pipeline.run(result.raw_data)
```

## GUI

Launch the interactive application:

```bash
pysimsar
```

The GUI provides parameter editing, real-time visualization panels (SAR image,
range/azimuth profiles, Doppler spectrum, phase history, 3D scene, trajectory),
and one-click simulation with configurable processing pipelines.

## Documentation

Full documentation is available via MkDocs:

```bash
pip install pySimSAR[docs]
mkdocs serve
```

Documentation covers:

- [Getting Started](docs/getting-started.md) — Installation and first simulation
- [Architecture](docs/architecture.md) — Module organization and data flow
- [Data Structures](docs/data-structures.md) — All user-facing types
- [Configuration](docs/configuration.md) — JSON parameter sets, presets, HDF5 format
- [Mathematical Principles](docs/math/signal-model.md) — Equations and derivations
- [Customization](docs/customization/scripting.md) — Scripting and extending algorithms
- [API Reference](docs/api/core.md) — Class and method reference
- [Known Issues](docs/known-issues.md) — Current limitations

## Project Structure

```
pySimSAR/           # Main package
├── algorithms/     # Image formation, MoCo, autofocus, geocoding, polarimetry
├── core/           # Platform, radar, scene, types, calculator
├── gui/            # PyQt6 application (panels, widgets, controllers, wizards)
├── io/             # HDF5, config, parameter sets, archive
├── motion/         # Trajectory and perturbation models
├── pipeline/       # Processing pipeline runner
├── presets/        # Built-in sensor, antenna, waveform, and platform presets
├── sensors/        # GPS and IMU sensor models
├── simulation/     # Signal generation engine
├── tools/          # CLI utilities (view_array)
└── waveforms/      # LFM, FMCW, phase noise models
tests/              # Unit, integration, contract, golden, performance, GUI tests
examples/           # Golden reference tests and scenario configurations
docs/               # MkDocs documentation
specs/              # Feature specifications (Speckit workflow)
```

## Development

```bash
git clone https://github.com/YOUR_USERNAME/PySimSAR.git
cd PySimSAR
pip install -e ".[dev]"
python -m pytest tests/
ruff check . --fix
```

## License

[MIT](LICENSE)
