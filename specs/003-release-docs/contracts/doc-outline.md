# Documentation Outline Contract

**Branch**: `003-release-docs` | **Date**: 2026-03-21

This defines the table of contents and section contracts for each documentation chapter. Each chapter contract specifies what must be present for the chapter to be considered complete.

## MkDocs Navigation Structure

```yaml
nav:
  - Home: index.md
  - Getting Started: getting-started.md
  - Architecture: architecture.md
  - Configuration: configuration.md
  - Data Structures: data-structures.md
  - Mathematical Principles:
    - Signal Model & Waveforms: math/signal-model.md
    - Image Formation: math/image-formation.md
    - Motion Compensation: math/motion-compensation.md
    - Autofocus: math/autofocus.md
    - Geocoding: math/geocoding.md
    - Polarimetry: math/polarimetry.md
    - Notation Table: math/notation.md
  - Customization Guide:
    - Scripting Simulations: customization/scripting.md
    - Extending Algorithms: customization/algorithms.md
    - Custom Waveforms: customization/waveforms.md
    - Custom Sensors: customization/sensors.md
  - API Reference:
    - Core: api/core.md
    - Simulation: api/simulation.md
    - Algorithms: api/algorithms.md
    - I/O: api/io.md
    - Pipeline: api/pipeline.md
  - Known Issues: known-issues.md
  - Changelog: changelog.md
```

## Chapter Contracts

### index.md — Home Page
- [ ] Project description (what PySimSAR is, what it does)
- [ ] Version badge (v0.1)
- [ ] Feature highlights (simulation, image formation, GUI, extensibility)
- [ ] Quick links to key sections
- [ ] Installation one-liner

### getting-started.md — Getting Started Tutorial
- [ ] Prerequisites (Python version, OS support)
- [ ] Installation instructions (pip install, from source)
- [ ] Core vs. GUI dependencies distinction
- [ ] First simulation walkthrough:
  - [ ] Launch GUI
  - [ ] Load default stripmap preset
  - [ ] Run simulation
  - [ ] View focused image
  - [ ] Save results
- [ ] Headless quickstart (3-line Python script)
- [ ] Troubleshooting section (common errors)

### architecture.md — Program Organization
- [ ] Package directory tree with descriptions
- [ ] Module responsibility matrix (module → what it does)
- [ ] Data flow diagram (Mermaid): Scene+Radar+Platform → SimulationEngine → RawData → PipelineRunner → SARImage
- [ ] Processing pipeline stages diagram
- [ ] SAR imaging geometry diagram (PNG)
- [ ] Registry/plugin architecture overview

### configuration.md — Configuration Guide
- [ ] JSON parameter set format
- [ ] Preset system (`$preset/` paths, shipped presets)
- [ ] `$ref` and `$data` resolution mechanism
- [ ] Project file structure (project.json, radar.json, scene.json, etc.)
- [ ] HDF5 output format (groups, datasets, metadata)
- [ ] Complete example: creating a project from JSON files

### data-structures.md — Data Structures Reference
- [ ] SARModeConfig (all fields, valid values, examples)
- [ ] RawData (fields, shape conventions, I/O methods)
- [ ] PhaseHistoryData (fields, relationship to RawData)
- [ ] SARImage (fields, geometry types, I/O methods)
- [ ] PointTarget (position, RCS scalar vs. matrix, velocity)
- [ ] DistributedTarget (origin, extent, reflectivity grid)
- [ ] Scene (container, add methods)
- [ ] Radar (constructor params, derived properties)
- [ ] AntennaPattern (array vs. callable, presets)
- [ ] Platform (velocity, altitude, heading, sensors, perturbation)
- [ ] Trajectory (time, position, velocity, attitude arrays)
- [ ] NavigationData (sensor measurements, uncertainty)
- [ ] Enums: SARMode, PolarizationMode, LookSide, RampType, ImageGeometry

### math/signal-model.md — Signal Model & Waveforms
- [ ] SAR geometry and coordinate system
- [ ] Point target range equation: $R(\eta) = \sqrt{R_0^2 + v^2\eta^2}$
- [ ] Transmitted LFM signal: $s_{tx}(t) = \exp(j\pi K_r t^2)$
- [ ] Received echo model with delay and Doppler
- [ ] FMCW dechirp processing model
- [ ] Antenna pattern integration
- [ ] Path loss (radar range equation)
- [ ] Phase noise model
- [ ] All equations numbered, all variables defined, all references cited

### math/image-formation.md — Image Formation Algorithms
- [ ] Range-Doppler Algorithm:
  - [ ] Range compression (matched filter)
  - [ ] Azimuth FFT
  - [ ] RCMC (sinc interpolation)
  - [ ] Azimuth compression
- [ ] Chirp Scaling Algorithm:
  - [ ] Chirp scaling function
  - [ ] Range-dependent phase multiply
  - [ ] Bulk range compression
  - [ ] Residual phase correction
- [ ] Omega-K Algorithm:
  - [ ] 2D FFT to wavenumber domain
  - [ ] Stolt interpolation
  - [ ] Reference function multiply
- [ ] Each: 2-3 derivation steps, final transfer functions, literature refs

### math/motion-compensation.md — Motion Compensation
- [ ] First-order MoCo: bulk phase correction to scene center
- [ ] Second-order MoCo: range-dependent correction
- [ ] Phase error model from trajectory deviations
- [ ] Residual phase terms

### math/autofocus.md — Autofocus Algorithms
- [ ] PGA: dominant scatterer selection, phase gradient estimation, iterative convergence
- [ ] MDA: sub-aperture Doppler centroid drift
- [ ] MEA: entropy cost function, polynomial phase model, optimization
- [ ] PPP: prominent point extraction, phase history fitting
- [ ] Each: convergence criteria, parameter sensitivity

### math/geocoding.md — Geocoding
- [ ] Slant-to-ground range projection (flat earth model)
- [ ] Georeferencing: pixel-to-lat/lon mapping
- [ ] Coordinate transformations (ENU ↔ geodetic)

### math/polarimetry.md — Polarimetric Decompositions
- [ ] Scattering matrix $[S]$ and coherency matrix $[T]$
- [ ] Pauli decomposition: $|S_{HH} + S_{VV}|$, $|S_{HH} - S_{VV}|$, $|2S_{HV}|$
- [ ] Freeman-Durden: surface, double-bounce, volume model fitting
- [ ] Yamaguchi: 4-component with helix scattering term
- [ ] Cloude-Pottier: eigenvalue decomposition, H/A/Alpha parameters

### math/notation.md — Notation Table
- [ ] Complete symbol → code variable mapping
- [ ] Organized by domain (geometry, waveform, processing)
- [ ] Module path for each code variable

### customization/scripting.md — Scripting Guide
- [ ] Minimal headless simulation example (end-to-end)
- [ ] Batch simulation pattern
- [ ] Custom scene construction
- [ ] Accessing raw data and focused images programmatically
- [ ] Saving/loading results

### customization/algorithms.md — Extending Algorithms
- [ ] Registry pattern explanation
- [ ] Step-by-step: creating a new ImageFormationAlgorithm
  - [ ] Subclass, implement process/range_compress/azimuth_compress/supported_modes
  - [ ] Register in registry
  - [ ] Use in ProcessingConfig
- [ ] Same pattern for MoCo, autofocus, geocoding, polarimetry
- [ ] `parameter_schema()` convention

### customization/waveforms.md — Custom Waveforms
- [ ] Waveform base class contract (generate, range_compress, bandwidth, duty_cycle, prf)
- [ ] Step-by-step: creating a custom waveform
- [ ] Registration in waveform_registry
- [ ] Integration with SimulationEngine

### customization/sensors.md — Custom Sensors
- [ ] GPS/IMU error model interfaces
- [ ] Step-by-step: creating a custom error model
- [ ] Registration in sensor registry
- [ ] Integration with Platform perturbation

### api/*.md — API Reference
- [ ] Each of the 27 key classes documented with:
  - [ ] Class description
  - [ ] Constructor parameters (name, type, default, description)
  - [ ] Public methods (signature, return type, description)
  - [ ] Properties
  - [ ] Usage example (where appropriate)

### known-issues.md — Known Issues
- [ ] PGA autofocus vertical streaks: severity, affected scenarios, workaround
- [ ] MoCo + GPS noise interaction: severity, affected scenarios, workaround
- [ ] Numba acceleration: deferred status, impact
- [ ] Any other known limitations

### changelog.md — Changelog
- [ ] v0.1 entry with date
- [ ] Feature summary (simulation, image formation, GUI, etc.)
- [ ] Template for future versions
