# PySimSAR v0.1 Documentation

**Python SAR Raw Signal Simulator with Modular Processing Algorithms**

---

PySimSAR is an open-source synthetic aperture radar (SAR) simulation and processing toolkit. It generates realistic raw SAR echo signals from user-defined scenes and processes them into focused images using industry-standard algorithms — all in pure Python with NumPy/SciPy.

## Feature Highlights

- **Signal Simulation** — Pulse-by-pulse echo generation with LFM and FMCW waveforms, antenna pattern modeling, and platform motion
- **Image Formation** — Range-Doppler, Chirp Scaling, and Omega-K algorithms for stripmap and spotlight modes
- **Motion Compensation** — First-order and second-order MoCo with GPS/IMU navigation data
- **Autofocus** — PGA, Map Drift, Minimum Entropy, and Prominent Point Processing
- **Geocoding** — Slant-to-ground range projection and geographic georeferencing
- **Polarimetry** — Pauli, Freeman-Durden, Yamaguchi, and Cloude-Pottier decompositions
- **GUI** — Interactive PyQt6 application for parameter editing, simulation control, and visualization
- **Extensible** — Registry-based plugin architecture for adding custom algorithms, waveforms, and sensors

## Quick Install

```bash
pip install pySimSAR
```

For GUI support:

```bash
pip install pySimSAR[gui]
```

## Documentation Guide

| Section | What you'll learn |
|---------|-------------------|
| [Getting Started](getting-started.md) | Installation, first simulation, GUI walkthrough |
| [Architecture](architecture.md) | Program organization, module map, data flow |
| [Data Structures](data-structures.md) | All user-facing types and their fields |
| [Configuration](configuration.md) | JSON parameter sets, presets, HDF5 format |
| [Mathematical Principles](math/signal-model.md) | Equations and derivations for all algorithms |
| [Customization Guide](customization/scripting.md) | Scripting, extending algorithms, custom waveforms |
| [API Reference](api/core.md) | Class and method reference for key types |
| [Known Issues](known-issues.md) | Current limitations and workarounds |
| [Changelog](changelog.md) | Version history |

## License

PySimSAR is released under the MIT License.
