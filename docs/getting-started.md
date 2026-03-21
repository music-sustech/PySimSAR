# Getting Started

This guide walks you through installing PySimSAR, running your first simulation
through the GUI, and executing a headless simulation from Python code.

## Prerequisites

**Python 3.10 or later** is required. The project is developed and tested on
Python 3.14, but any version from 3.10 onward will work.

PySimSAR runs on **Windows**, **macOS**, and **Linux**.

The following core dependencies are installed automatically when you install the
package:

- **numpy** — array computation
- **scipy** — signal processing and interpolation
- **h5py** — HDF5 file I/O
- **platformdirs** — cross-platform user data directories

For the graphical interface, these additional dependencies are needed (installed
with the `[gui]` extra):

- **PyQt6** — application framework
- **matplotlib** — 2-D plotting
- **pyqtgraph** — fast interactive plots
- **PyOpenGL** — 3-D scene rendering
- **trimesh** — 3-D mesh utilities

## Installation

Install from PyPI:

```bash
pip install pySimSAR          # core library only
pip install pySimSAR[gui]     # with GUI support
pip install pySimSAR[dev]     # development (includes GUI + pytest + ruff)
```

For development from source:

```bash
git clone https://github.com/your-org/PySimSAR.git
cd PySimSAR
pip install -e ".[dev]"
```

## First Simulation via GUI

1. **Launch the application.** Run `python -m pySimSAR.gui` from a terminal, or
   use the `pysimsar` command that is installed with the package.

2. **Explore the main window.** The interface is divided into three areas: a
   left panel containing the `ParameterTreeWidget` for editing all simulation
   parameters, a right panel with tabbed visualization panels, and a status bar
   along the bottom.

3. **Load a preset.** Go to **File > Load Preset** and select
   **default_stripmap**. This loads a stripmap SAR configuration with default
   radar parameters, a scene containing a single point target, and a straight-
   and-level platform trajectory.

4. **Run the simulation.** Open the **Simulation** menu and click
   **Run Simulation**. A progress bar in the status bar tracks signal generation
   and processing.

5. **View results.** When processing completes, switch to the **Image Viewer**
   tab in the right panel to see the focused SAR image.

6. **Explore other tabs.** The right panel provides several additional
   visualization tabs:

   - **Phase History** — raw or range-compressed phase history
   - **Range Profile** — range-direction cut through the image
   - **Azimuth Profile** — azimuth-direction cut through the image
   - **Doppler Spectrum** — Doppler frequency content
   - **Trajectory** — platform flight path
   - **Scene 3D** — three-dimensional view of the scene geometry
   - **Beam Animation** — animated radar beam footprint
   - **Polarimetry** — polarimetric decomposition results

7. **Save your project.** Go to **File > Save Project** to write all
   configuration, raw data, and processed results to an HDF5 project file.

## Headless Quickstart (Library-Only)

The following script runs a complete simulation and image formation pipeline
without the GUI. It is also available as a standalone file at
[`docs/examples/headless_quickstart.py`](examples/headless_quickstart.py).

```python
"""Headless simulation quickstart — no GUI required."""
from pySimSAR import (
    Scene, PointTarget, Radar, Platform,
    SimulationEngine, PipelineRunner,
)
from pySimSAR.core.types import RawData, SARModeConfig
from pySimSAR.io.config import ProcessingConfig
from pySimSAR.waveforms.lfm import LFMWaveform
from pySimSAR.core.radar import create_antenna_from_preset

# 1. Define scene with a single point target
scene = Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=0.0)
scene.add_target(PointTarget(position=[0, 0, 0], rcs=1.0))

# 2. Configure radar
waveform = LFMWaveform(bandwidth=50e6, duty_cycle=0.1, prf=500)
antenna = create_antenna_from_preset("sinc", az_beamwidth=0.05, el_beamwidth=0.1)
radar = Radar(
    carrier_freq=9.65e9,    # X-band
    transmit_power=1000,
    waveform=waveform,
    antenna=antenna,
    polarization="single",
    sar_mode_config=SARModeConfig(mode="stripmap"),
)

# 3. Configure platform
platform = Platform(velocity=100, altitude=5000, heading=0)

# 4. Run simulation
engine = SimulationEngine(scene=scene, radar=radar, n_pulses=256, platform=platform)
result = engine.run()

# 5. Process into focused image
config = ProcessingConfig(image_formation="range_doppler")
runner = PipelineRunner(config)
raw_data = {}
for ch, echo in result.echo.items():
    raw_data[ch] = RawData(
        echo=echo, channel=ch, sample_rate=result.sample_rate,
        carrier_freq=radar.carrier_freq, bandwidth=radar.bandwidth,
        prf=waveform.prf, waveform_name="lfm", sar_mode="stripmap",
        gate_delay=result.gate_delay,
    )
trajectory = result.true_trajectory or result.ideal_trajectory
pipeline_result = runner.run(raw_data, radar, trajectory,
                             ideal_trajectory=result.ideal_trajectory)

# 6. Access the focused image
image = pipeline_result.images["single"]
print(f"Image shape: {image.data.shape}")
print(f"Range resolution: {image.pixel_spacing_range:.2f} m")
```

## Troubleshooting

**`ModuleNotFoundError: No module named 'PyQt6'`**
You installed the core-only package. Run `pip install pySimSAR[gui]` for GUI
support. The library works headless without PyQt6.

**`ImportError: cannot import name ...`**
Ensure you have the correct version. Run `pip install --upgrade pySimSAR`.

**`FileNotFoundError: preset not found`**
Presets are shipped with the package. If installing from source, ensure
`pip install -e .` was run from the repo root.

**Windows path issues**
PySimSAR uses `platformdirs` for cross-platform paths. User data is stored in
`%LOCALAPPDATA%/pySimSAR/` on Windows and `~/.local/share/pySimSAR/` on Linux.

**Large simulation runs out of memory**
Reduce `n_pulses` or scene size. For large scenes, consider distributed targets
with coarser cell size.
