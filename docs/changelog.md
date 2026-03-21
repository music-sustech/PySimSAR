# Changelog

All notable changes to PySimSAR are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-03-21

Initial public release of PySimSAR.

### Added

**Signal Simulation**

- Pulse-by-pulse SAR echo generation with `SimulationEngine`
- Point target and distributed target scene models
- Antenna pattern modeling (flat, sinc, Gaussian presets)
- Platform trajectory generation with optional Dryden turbulence perturbation
- GPS and IMU sensor models for navigation data

**Waveforms**

- Linear Frequency Modulated (LFM) chirp waveform
- Frequency Modulated Continuous Wave (FMCW) waveform with up/down/triangle ramps
- Composite PSD phase noise model

**Image Formation (3 algorithms)**

- Range-Doppler Algorithm (RDA) with RCMC via sinc interpolation
- Chirp Scaling Algorithm (CSA)
- Omega-K Algorithm (wavenumber domain)

**Motion Compensation (2 algorithms)**

- First-order MoCo — bulk phase correction to scene center
- Second-order MoCo — range-dependent correction

**Autofocus (4 algorithms)**

- Phase Gradient Autofocus (PGA)
- Map Drift Autofocus (MDA)
- Minimum Entropy Autofocus (MEA)
- Prominent Point Processing (PPP)

**Geocoding (2 algorithms)**

- Slant-to-ground range projection
- Geographic georeferencing with trajectory-based pixel mapping

**Polarimetry (4 decompositions)**

- Pauli decomposition
- Freeman-Durden 3-component decomposition
- Yamaguchi 4-component decomposition
- Cloude-Pottier eigenvalue decomposition (H/A/Alpha)

**I/O and Configuration**

- HDF5 read/write for raw data, focused images, trajectory, and navigation data
- JSON parameter set system with `$ref`/`$data` resolution
- Project archive pack/unpack
- Shipped preset: `default_stripmap`

**GUI**

- PyQt6 main window with parameter tree editor and tabbed visualization
- 10 visualization panels: Image Viewer, Phase History, Range Profile, Azimuth Profile, Doppler Spectrum, Trajectory, Scene 3D, Beam Animation, Polarimetry, Tiled View
- Project creation wizard and HDF5 import wizard
- Preset browser and calculated values panel

**Processing Pipeline**

- `PipelineRunner` orchestrating: MoCo → Range Compression → Autofocus → Azimuth Compression → Geocoding → Polarimetry
- Configurable `ProcessingConfig` for algorithm selection and parameters

**Infrastructure**

- Algorithm registry system for extensible plugin architecture
- `SARCalculator` for derived system parameter computation
- Comprehensive type system (SARMode, PolarizationMode, LookSide, ImageGeometry, etc.)

### Known Issues

- PGA autofocus may produce vertical streaks with certain spotlight configurations
- MoCo + GPS noise interaction can degrade second-order compensation
- ScanSAR mode partially implemented
- See [Known Issues](known-issues.md) for details and workarounds
