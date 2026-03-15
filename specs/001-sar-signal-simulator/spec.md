# Feature Specification: SAR Raw Signal Simulator

**Feature Branch**: `001-sar-signal-simulator`
**Created**: 2026-03-14
**Status**: Draft
**Input**: User description: "SAR raw signal simulator with point target and distributed target support. 3D target scene. Airborne/UAV SAR with motion perturbation modeling, GPS/RTK and IMU sensor simulation, common data format, modular algorithms for motion compensation and image formation, interactive GUI with 3D visualization."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Simulate SAR Raw Signal from 3D Scene (Priority: P1)

A SAR researcher defines a 3D target scene containing point targets and
distributed targets, configures radar parameters (carrier frequency,
bandwidth, PRF, antenna pattern, polarization mode) and a nominal
straight-line flight path. The system generates raw SAR echo data
(range-compressed or uncompressed) for single or fully polarimetric
(HH, HV, VH, VV) configurations, which can be saved to a standard data
format for later processing.

**Why this priority**: Raw signal generation is the foundational capability.
Without it, no other feature (image formation, motion compensation, GUI)
has data to operate on.

**Independent Test**: Can be tested by generating echo data for a known
point target grid and verifying the phase history matches the analytical
range equation to within numerical precision.

**Acceptance Scenarios**:

1. **Given** a scene with a single point target at known 3D coordinates and
   a straight-line flight path, **When** the user runs the simulation,
   **Then** the generated raw data phase history matches the expected
   range-to-target equation within 0.01 radians.
2. **Given** a scene with multiple distributed targets of varying
   reflectivity, **When** the simulation completes, **Then** each target's
   contribution is superimposed in the raw data with correct amplitude
   scaling and delay.
3. **Given** configured radar parameters, **When** the user saves the
   output, **Then** the data is written in the project's standard data
   format and can be reloaded without loss.

---

### User Story 2 - Model Airborne/UAV Motion and Sensor Errors (Priority: P1)

A researcher configures an airborne or UAV platform with realistic motion
perturbation (turbulence, vibration, drift). The system models the
platform's actual flight trajectory deviating from the ideal path. GPS/RTK
and IMU sensors of configurable precision and error characteristics measure
the trajectory, producing navigation data with realistic noise, bias, and
drift that can be used downstream by motion compensation algorithms.

**Why this priority**: Motion perturbation and sensor modeling are equally
foundational — airborne/UAV SAR processing is meaningless without them.
This story can be developed in parallel with US1 since it concerns the
platform/sensor side rather than the signal side.

**Independent Test**: Can be tested by generating a perturbed trajectory
and verifying that sensor measurements match the true trajectory within
configured error bounds (e.g., GPS position error RMS matches spec).

**Acceptance Scenarios**:

1. **Given** a nominal flight path and motion perturbation parameters
   (amplitude, spectrum), **When** the motion model runs, **Then** the
   perturbed trajectory deviates from the ideal path with statistics
   matching the configured perturbation model.
2. **Given** a GPS sensor with configured position accuracy RMS (e.g.,
   0.02 m for high-precision, 2.0 m for standard), **When** the sensor
   error model samples the true trajectory, **Then** the position
   measurement error RMS matches the configured accuracy within 10%.
3. **Given** an IMU with configurable noise density for accelerometer
   and gyroscope, **When** the IMU error model runs, **Then** the
   acceleration and angular rate outputs exhibit the specified noise
   characteristics.

---

### User Story 3 - Standard Data Format for Interoperability (Priority: P1)

The system uses a well-defined data format for storing and exchanging all
simulation artifacts: raw echo data, navigation data, sensor measurements,
SAR images, and simulation configuration. All modules read and write this
format, enabling pipeline composition and data sharing between users.

**Why this priority**: A common data format is foundational infrastructure
that all other components depend on for interoperability.

**Independent Test**: Can be tested by writing data in the format, reading
it back, and verifying bit-exact round-trip fidelity.

**Acceptance Scenarios**:

1. **Given** any simulation artifact (raw data, nav data, image), **When**
   it is saved and reloaded, **Then** the data is bit-exact identical.
2. **Given** a data file, **When** it is inspected, **Then** all metadata
   (radar parameters, coordinate system, timestamps, units) is
   self-describing and accessible without external documentation.
3. **Given** data produced by one module, **When** it is consumed by
   another module, **Then** no format conversion is needed.

---

### User Story 4 - Form SAR Image with Modular Algorithms (Priority: P2)

A researcher selects an image formation algorithm (e.g., Range-Doppler,
Chirp Scaling, Omega-K) from the available modules, feeds it raw SAR data,
and obtains a focused SAR image. The user can swap algorithms to compare
results. New algorithms can be added by implementing a standard interface
without modifying existing code.

**Why this priority**: Image formation is the core processing step but
depends on having raw data (US1) available first.

**Independent Test**: Can be tested by forming an image from simulated
point-target data and measuring the impulse response (3 dB width,
peak sidelobe ratio) against theoretical values.

**Acceptance Scenarios**:

1. **Given** raw SAR data from a point target scene, **When** the user
   selects the Range-Doppler algorithm and runs image formation, **Then**
   the output image shows focused point targets with measurable impulse
   response metrics (resolution, PSLR, ISLR).
2. **Given** two different image formation algorithms, **When** the user
   runs both on the same data, **Then** results can be compared
   side-by-side and metrics are reported for each.
3. **Given** a new algorithm module implementing the standard interface,
   **When** it is placed in the algorithms directory, **Then** it appears
   as a selectable option without any code changes to the core system.

---

### User Story 5 - Apply Motion Compensation with Modular Algorithms (Priority: P2)

A researcher selects a motion compensation algorithm, provides it with raw
SAR data and navigation data (from GPS/IMU sensors), and obtains
motion-compensated data ready for image formation. Different MoCo
algorithms can be swapped and compared. Like image formation, new MoCo
algorithms follow a standard interface.

**Why this priority**: Motion compensation depends on both raw data (US1)
and navigation/sensor data (US2). It is a prerequisite for high-quality
image formation from perturbed platforms.

**Independent Test**: Can be tested by applying MoCo to data with known
motion errors and measuring residual phase error reduction.

**Acceptance Scenarios**:

1. **Given** raw data with known motion errors and corresponding navigation
   data, **When** the user applies a first-order MoCo algorithm, **Then**
   the residual phase error is reduced by at least the expected amount for
   that algorithm.
2. **Given** a new MoCo algorithm implementing the standard interface,
   **When** it is registered, **Then** it is available for selection
   without modifying existing code.

---

### User Story 5a - Autofocus for Residual Phase Error Correction (Priority: P2)

After first-stage motion compensation (US5) and range compression,
residual phase errors may remain due to navigation sensor inaccuracies.
A researcher applies a data-driven autofocus algorithm to the
range-compressed phase history data to estimate and correct these
residual errors, producing a sharper focused image. Autofocus algorithms
operate without requiring navigation data — they extract phase error
estimates directly from the data. Different autofocus algorithms can be
swapped and compared via a standard interface.

**Why this priority**: Autofocus is essential for airborne/UAV SAR where
navigation sensor quality is limited. It depends on image formation
(US4) being split into range compression + azimuth compression steps.

**Independent Test**: Can be tested by simulating data with known
residual phase errors (after MoCo), applying autofocus, and measuring
improvement in image focus metrics (entropy, contrast, impulse response
width).

**Acceptance Scenarios**:

1. **Given** range-compressed phase history with known residual phase
   errors, **When** the user applies PGA autofocus, **Then** the focused
   image shows measurably improved sharpness (lower entropy, narrower
   impulse response) compared to the image without autofocus.
2. **Given** a scene with strong point scatterers and moderate motion
   errors, **When** autofocus converges, **Then** the estimated phase
   error matches the injected error within the convergence threshold.
3. **Given** a new autofocus algorithm implementing the standard
   interface, **When** it is registered, **Then** it is available for
   selection without modifying existing code.

---

### User Story 6 - Image Geocoding and Rectification (Priority: P2)

A researcher takes a focused SAR image (in slant-range/azimuth geometry)
and transforms it into a 2D rectangular ground-range image suitable for
geographic analysis. The system provides modular image transformation
algorithms — including slant-to-ground range projection, georeferencing,
and map projection — that convert SAR imagery from radar coordinates to
standard geographic coordinates. Like other algorithm modules, new
transformation methods can be added via a standard interface.

**Why this priority**: Formed SAR images are in radar geometry (slant
range x azimuth), which is not directly usable for geographic analysis or
overlay with other geospatial data. Image transformation is essential for
producing usable output products.

**Independent Test**: Can be tested by transforming a known point-target
image from slant-range to ground-range and verifying that target positions
match their known geographic coordinates within expected accuracy.

**Acceptance Scenarios**:

1. **Given** a focused SAR image in slant-range/azimuth geometry, **When**
   the user applies slant-to-ground range projection, **Then** the output
   is a 2D rectangular image in ground-range coordinates with correct
   spatial scaling.
2. **Given** a ground-range image and platform/radar metadata, **When**
   the user applies georeferencing, **Then** each pixel is mapped to
   geographic coordinates (lat/lon) with accuracy consistent with the
   input navigation data quality.
3. **Given** a new image transformation module implementing the standard
   interface, **When** it is registered, **Then** it is available for
   selection without modifying existing code.

---

### User Story 7 - Polarimetric Decomposition (Priority: P2)

A researcher working with fully polarimetric SAR data (HH, HV, VH, VV
channels) applies polarimetric decomposition methods to extract
scattering mechanism information. The system provides modular
decomposition algorithms (e.g., Pauli, Freeman-Durden, Yamaguchi,
Cloude-Pottier H/A/Alpha) that operate on the scattering matrix or
covariance/coherency matrices. New decomposition methods can be added
via a standard interface.

**Why this priority**: Polarimetric decomposition is a key analysis
capability for SAR data, but depends on having multi-polarization raw
data simulation (US1) and image formation (US4) working first.

**Independent Test**: Can be tested by simulating known canonical
scattering scenarios (e.g., single-bounce, double-bounce, volume
scattering) and verifying that decomposition results correctly identify
the dominant scattering mechanism.

**Acceptance Scenarios**:

1. **Given** a fully polarimetric SAR image (all four polarization
   channels), **When** the user applies Pauli decomposition, **Then**
   the output contains three components (surface, double-bounce, volume)
   with values matching analytical expectations for known targets.
2. **Given** fully polarimetric data, **When** the user applies
   Freeman-Durden decomposition, **Then** the power contributions from
   surface, double-bounce, and volume scattering sum to the total span
   within numerical precision.
3. **Given** a new polarimetric decomposition module implementing the
   standard interface, **When** it is registered, **Then** it is
   available for selection without modifying existing code.

---

### User Story 8 - Processing Pipeline and Project Model (Priority: P2)

A researcher configures a processing pipeline by selecting algorithms
(MoCo, image formation, autofocus, geocoding, polarimetric decomposition)
via a ProcessingConfig, and runs the pipeline on raw data. The pipeline
orchestrates the configured steps in order: MoCo → range compression →
autofocus → azimuth compression → geocoding → polsar decomposition,
skipping any step set to None. The same raw data can be re-processed
with different algorithm selections without re-running the simulation.
Users can also import external HDF5 data files to run processing without
a simulation step, enabling a project-based workflow.

**Why this priority**: The pipeline runner is the glue that connects all
algorithm modules into an end-to-end workflow. It depends on all P2
algorithm stories (US4-US7) being available. The data import capability
validates the Library-First principle and SimulationConfig/ProcessingConfig
split.

**Independent Test**: Can be tested by running the full pipeline via
ProcessingConfig, then re-processing the same raw data with a different
config and verifying different results.

**Acceptance Scenarios**:

1. **Given** raw data and a ProcessingConfig with all steps configured,
   **When** the user runs the pipeline, **Then** the output is a focused,
   geocoded SAR image with correct processing applied at each step.
2. **Given** the same raw data and a different ProcessingConfig (e.g.,
   different image formation algorithm, autofocus disabled), **When** the
   user runs the pipeline, **Then** a different result is produced
   without re-running the simulation.
3. **Given** an external HDF5 file containing raw data and navigation
   data, **When** the user imports it, **Then** the data is loaded and
   available for processing via ProcessingConfig.
4. **Given** a ProcessingConfig with some steps set to None, **When**
   the pipeline runs, **Then** those steps are skipped and the remaining
   steps execute correctly.

---

### User Story 9 - Interactive GUI for Simulation and Visualization (Priority: P3)

A researcher uses a desktop GUI to set up simulation parameters (scene,
radar, platform, sensors), run the simulation pipeline, and visualize
results interactively. The GUI displays the 3D target scene, the flight
trajectory (ideal and perturbed), an animation of the radar beam sweeping
the scene, and the formed SAR image. Parameters can be adjusted and the
simulation re-run without restarting the application.

**Why this priority**: The GUI is a productivity layer on top of the
library. All underlying functionality must work via Python API first
(Library-First principle). The GUI is valuable but not required for core
SAR simulation research.

**Independent Test**: Can be tested by launching the GUI, configuring a
simple point-target scene, running the full pipeline, and verifying that
all visualization panels display correct data.

**Acceptance Scenarios**:

1. **Given** the GUI is launched, **When** the user configures radar and
   scene parameters using the interface controls, **Then** all parameters
   are validated and stored for simulation.
2. **Given** a configured simulation, **When** the user clicks "Run",
   **Then** the simulation executes and progress is displayed.
3. **Given** simulation results are available, **When** the user views the
   3D scene panel, **Then** point and distributed targets are rendered at
   their 3D positions with reflectivity-based coloring.
4. **Given** simulation results, **When** the user views the trajectory
   panel, **Then** both ideal and perturbed flight paths are displayed in
   3D with the ability to rotate and zoom.
5. **Given** a completed simulation, **When** the user activates beam
   animation, **Then** the radar beam footprint sweeps along the flight
   path at controllable playback speed.
6. **Given** a formed SAR image, **When** the user views the image panel,
   **Then** the image is displayed with adjustable dynamic range,
   colormap, and zoom controls.

---

### Edge Cases

- What happens when the target scene is empty (no targets defined)?
  The simulation produces noise-only raw data and warns the user.
- What happens when GPS signal is configured as lost for a time interval?
  The sensor model outputs a gap in GPS data, and MoCo algorithms
  handle or report the gap.
- What happens when motion perturbation is so large that targets leave the
  antenna beam? The simulation models this correctly (reduced or zero
  return) and warns the user.
- What happens when the user provides an image formation algorithm that
  does not match the data geometry (e.g., stripmap algorithm on spotlight
  data)? The system validates compatibility and reports a clear error.
- What happens when simulation parameters produce data too large for
  available memory? The system estimates memory requirements before
  execution and warns the user.
- What happens when an image formation algorithm does not support the
  selected waveform's matched filter? The system validates compatibility
  and reports a clear error suggesting compatible algorithms.
- What happens when the user applies polarimetric decomposition to
  single-polarization data? The system validates that all required
  polarization channels are present and reports a clear error.
- What happens when image transformation is applied without sufficient
  navigation metadata for georeferencing? The system falls back to
  ground-range projection without geographic coordinates and warns
  the user.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST simulate SAR raw echo signals for point targets
  at arbitrary 3D positions with configurable radar cross section.
- **FR-002**: System MUST simulate distributed targets with spatially
  varying reflectivity in 3D space.
- **FR-003**: System MUST model configurable radar parameters: carrier
  frequency, bandwidth, pulse repetition frequency, antenna pattern,
  transmit power, noise figure, system losses, and reference temperature.
- **FR-003a**: System MUST support modular radar waveforms via a unified
  interface where each waveform handles both signal generation and range
  compression internally. Built-in waveforms MUST include LFM (pulsed)
  and FMCW (continuous). New waveform types (NLFM, phase-coded,
  stepped-frequency, OFDM, custom) MUST be addable by implementing the
  waveform interface without modifying existing code or the simulation
  engine. Active signal duration MUST be derived from duty cycle and
  Radar PRF, not specified directly.
- **FR-003b**: The FMCW waveform MUST support configurable ramp type
  (up, down, triangle), duty cycle (fraction of PRI with active chirp
  for pulsed/duty-cycled FMCW), and de-chirp processing.
- **FR-003c**: System MUST support modular oscillator phase noise models
  via a standard interface. At minimum a composite PSD model with
  configurable 1/f³, 1/f², 1/f, and white noise floor components MUST
  be provided. Phase noise MUST be applicable to both pulsed and FMCW
  waveforms.
- **FR-003d**: The simulation engine MUST correctly model the range
  correlation effect: phase noise cancellation at short target ranges
  and decorrelation at long ranges, computed per-target based on
  round-trip delay.
- **FR-003e**: The simulation engine MUST account for target velocity
  (relative radial speed between target and platform), including Doppler
  shift, range-Doppler coupling, and within-pulse motion effects for
  FMCW waveforms.
- **FR-003f**: The simulation engine MUST apply the radar range equation
  to compute physically correct received signal amplitude per target:
  P_r = (P_t · G² · λ² · σ) / ((4π)³ · R⁴), accounting for transmit
  power, two-way antenna gain, wavelength, target RCS, and range.
  System losses MUST be applied as an aggregate attenuation factor.
- **FR-003g**: The simulation engine MUST add receiver thermal noise to
  the raw echo data based on the radar's noise figure, reference
  temperature, and receiver bandwidth (noise power = k·T·B·F). The
  noise MUST be complex Gaussian (I and Q channels).
- **FR-004**: System MUST generate platform trajectories with configurable
  nominal path (velocity, altitude, heading) and motion perturbation
  models (turbulence spectrum, vibration, drift).
- **FR-005**: System MUST model GPS sensors with configurable position
  accuracy, update rate, and outage behavior via a modular error model
  interface. The default implementation MUST use simple additive
  Gaussian noise with configurable RMS. Advanced models (RTK, correlated
  errors) can be added as modules.
- **FR-006**: System MUST model IMU sensors with configurable noise
  density via a modular error model interface. The default implementation
  MUST use simple additive white noise with configurable noise density
  for accelerometer and gyroscope. Advanced models (bias drift, scale
  factor, IEEE-STD-952 five-term) can be added as modules.
- **FR-007**: System MUST support at least three image formation algorithms
  (Range-Doppler, Chirp Scaling, Omega-K) as interchangeable modules.
  Each algorithm MUST expose a two-step interface: range compression
  (producing PhaseHistoryData) and azimuth compression (producing
  SARImage), as well as a convenience end-to-end process() method.
- **FR-007a**: System MUST define PhaseHistoryData as a first-class
  intermediate data type representing range-compressed phase history,
  usable by autofocus algorithms and for sub-aperture analysis.
- **FR-007b**: System MUST support modular autofocus algorithms via a
  standard interface. Default implementations MUST include Phase
  Gradient Autofocus (PGA), Map Drift Autofocus (MDA), Minimum
  Entropy Autofocus, and Prominent Point Processing (PPP). Autofocus
  algorithms MUST operate on PhaseHistoryData and use the image
  formation algorithm's azimuth compression as a callback for
  iterative refinement.
- **FR-008**: System MUST support modular motion compensation algorithms
  with at least first-order and second-order MoCo as default options.
- **FR-009**: New image formation, motion compensation, and autofocus
  algorithms MUST
  be addable by implementing a standard interface, without modifying
  existing code.
- **FR-010**: System MUST define and use a common data format for all
  simulation artifacts with self-describing metadata.
- **FR-011**: System MUST provide a GUI that displays the 3D target scene,
  flight trajectory, radar beam animation, and formed SAR image.
- **FR-012**: System MUST allow all simulation parameters to be configured
  through the GUI.
- **FR-013**: All functionality accessible through the GUI MUST also be
  accessible through the Python API.
- **FR-014**: System MUST support saving and loading complete simulation
  and processing configurations for reproducibility. SimulationConfig
  (scene, radar, platform, seed) and ProcessingConfig (algorithm
  selections and parameters) MUST be independently serializable so that
  the same raw data can be re-processed with different algorithms
  without re-running the simulation.
- **FR-015**: System MUST support stripmap, spotlight, and scan-SAR
  imaging modes, including appropriate beam steering models and
  mode-specific signal generation for each.
- **FR-016**: System MUST support fully polarimetric simulation (HH, HV,
  VH, VV channels) with configurable polarimetric scattering matrices
  for each target.
- **FR-017**: System MUST provide modular image transformation algorithms
  (slant-to-ground range projection, georeferencing, map projection) to
  convert SAR images from radar geometry to 2D rectangular ground-range
  or geographic coordinates.
- **FR-018**: System MUST provide modular polarimetric decomposition
  algorithms (at minimum Pauli, Freeman-Durden, Yamaguchi, and
  Cloude-Pottier H/A/Alpha) as interchangeable modules.
- **FR-019**: New image transformation and polarimetric decomposition
  algorithms MUST be addable by implementing a standard interface,
  without modifying existing code.
- **FR-020**: System MUST provide modular clutter models for generating
  distributed target reflectivity via a standard interface. The default
  implementation MUST provide uniform (constant) reflectivity. Statistical
  models (K-distribution, log-normal, etc.) can be added as modules.
- **FR-021**: The distributed target data structure MUST be designed to
  allow future extension to 3D volumetric targets (vertical structures)
  without breaking the existing interface.

### Key Entities

- **Target**: A reflector in 3D space. Point targets have a single
  position and RCS. Distributed targets have spatial extent and
  reflectivity distribution.
- **Scene**: A collection of targets in a defined 3D coordinate system
  with a ground reference.
- **Radar**: The SAR sensor with parameters defining the antenna
  characteristics, transmit power, and selected waveform module.
- **Waveform**: A pluggable module defining the transmitted signal and
  its range compression method. Default types include LFM (pulsed) and
  FMCW (continuous). Active duration is derived from duty cycle and
  Radar PRF. Custom waveforms implement a standard interface.
- **Platform**: The aircraft/UAV carrying the radar, with nominal flight
  path and motion perturbation model.
- **NavigationSensor**: GPS/RTK or IMU sensor attached to the platform,
  with configurable error model producing measurement data.
- **RawData**: The simulated SAR echo data matrix (fast-time x slow-time)
  with associated metadata.
- **NavigationData**: Time-stamped position, velocity, and attitude
  measurements from navigation sensors.
- **SARImage**: A focused SAR image produced by an image formation
  algorithm, with georeferencing metadata. May contain single or
  multiple polarization channels.
- **PhaseHistoryData**: Range-compressed phase history — the intermediate
  representation between range compression and azimuth compression.
  First-class data type consumed by autofocus algorithms.
- **ImageFormationAlgorithm**: A pluggable module that exposes a two-step
  interface (range compression → PhaseHistoryData → azimuth compression
  → SARImage) as well as an end-to-end process() method.
- **AutofocusAlgorithm**: A pluggable module that estimates and corrects
  residual phase errors in PhaseHistoryData, using the image formation
  algorithm's azimuth compression as a callback for iterative
  refinement. Data-driven — requires no navigation data.
- **MotionCompensationAlgorithm**: A pluggable module that takes raw data
  and navigation data and produces motion-compensated data.
- **ImageTransformationAlgorithm**: A pluggable module that converts a
  SAR image from radar geometry (slant-range/azimuth) to ground-range
  or geographic coordinates, producing a 2D rectangular output.
- **PolarimetricDecomposition**: A pluggable module that takes fully
  polarimetric SAR data (scattering matrix or covariance/coherency
  matrix) and extracts scattering mechanism components.
- **ClutterModel**: A pluggable module that generates statistical
  reflectivity distributions for distributed targets (e.g.,
  K-distribution for sea/terrain clutter).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Point target impulse response in formed images matches
  theoretical resolution (3 dB main lobe width) within 5% for all
  default image formation algorithms.
- **SC-002**: Simulated sensor errors (GPS, IMU) match configured
  statistical parameters (mean, RMS, PSD) within 10% over 1000-sample
  ensemble.
- **SC-003**: A new image formation or motion compensation algorithm can
  be integrated by a developer familiar with the interface in under
  1 hour, requiring zero changes to existing code.
- **SC-004**: Round-trip save/load of all data types preserves bit-exact
  fidelity.
- **SC-005**: Users can configure, run, and visualize a basic point-target
  simulation through the GUI in under 5 minutes on first use.
- **SC-006**: The full simulation pipeline (signal generation, MoCo, image
  formation) for a 1024x1024 scene completes within 60 seconds on a
  modern desktop.

## Assumptions

- The coordinate system uses a local East-North-Up (ENU) reference frame
  with a configurable origin (latitude, longitude, altitude).
- The radar operates in monostatic side-looking configuration.
- The simulation uses start-stop approximation unless explicitly
  configured otherwise.
- Atmospheric propagation effects (tropospheric delay, attenuation) are
  not modeled in the initial version.
- Terrain elevation is flat (zero height) by default; terrain models may
  be supported in future versions.
- The modular plugin architecture (standardized ABCs, typed inputs/outputs,
  runtime registry) is designed to support a future drag-and-drop visual
  pipeline editor in the GUI, where users can compose processing chains
  by connecting module blocks. This is not in scope for the initial
  version.
- Multipath propagation (ground-bounce, multi-bounce) is not modeled in
  the initial version. The simulation engine's per-target echo
  computation loop is structured so that a future ray-tracing-based
  multipath model can add additional path contributions per target
  without architectural changes. This would require adding a
  SurfaceModel (reflection coefficient, roughness) to the Scene entity.
