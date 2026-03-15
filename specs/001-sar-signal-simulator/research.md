# Research: SAR Raw Signal Simulator

## 1. Data Format

**Decision**: HDF5 via h5py

**Rationale**: HDF5 is the de facto standard for scientific computing
with large array data. It supports hierarchical structure (groups map
naturally to our data model), rich metadata via attributes, native
complex number storage, gzip compression, and partial I/O (reading
subsets without loading entire files). h5py provides a NumPy-native
Python interface. HDF5 files are self-describing, satisfying FR-010.

**Alternatives Considered**:
- **NumPy .npz**: Simple but no metadata, no hierarchical structure, no
  partial I/O. Unsuitable for self-describing data requirement.
- **NetCDF4**: Built on HDF5 but adds CF convention overhead and
  dimension-centric model that doesn't map well to SAR echo matrices
  with mixed metadata types.
- **Custom binary**: Maximum performance but no self-describing metadata,
  requires custom reader/writer maintenance, poor interoperability.
- **GeoTIFF**: Good for final image products but cannot store complex
  echo data, navigation time series, or simulation configs.

## 2. GUI Framework

**Decision**: PyQt6

**Rationale**: PyQt6 provides the most mature and feature-rich widget
toolkit for Python desktop applications. It has excellent integration
with matplotlib (via `matplotlib.backends.backend_qtagg`) and pyqtgraph
for real-time plotting. The signal/slot mechanism maps well to simulation
parameter updates. Large community and extensive documentation.

**Alternatives Considered**:
- **PySide6**: Nearly identical API (same Qt6 bindings) but LGPL vs GPL
  license. Either works; PyQt6 chosen for broader community adoption and
  more third-party examples.
- **Tkinter**: Too limited for complex scientific visualization. No
  default 3D support, poor widget variety.
- **Web-based (Streamlit/Gradio)**: Poor fit for interactive 3D
  visualization, real-time animation, and desktop integration. No
  fine-grained control over layout.

## 3. 3D Visualization

**Decision**: pyqtgraph with OpenGL backend for 3D scene/trajectory,
matplotlib for 2D image display

**Rationale**: pyqtgraph's `GLViewWidget` provides hardware-accelerated
3D rendering that integrates natively with PyQt6. It supports scatter
plots (point targets), line plots (trajectories), mesh surfaces
(distributed targets), and custom OpenGL items (beam footprint).
Performance is sufficient for real-time rotation/zoom of scenes with
thousands of targets. matplotlib handles 2D SAR image display with its
mature colormap, colorbar, and interactive zoom capabilities.

**Alternatives Considered**:
- **VTK (via pyvista)**: Extremely powerful but heavyweight dependency
  (~100 MB), steep learning curve, complex PyQt integration. Overkill
  for our visualization needs.
- **vispy**: Good OpenGL wrapper but less mature PyQt integration and
  fewer high-level primitives than pyqtgraph.
- **matplotlib 3D (mplot3d)**: Too slow for interactive 3D with many
  objects. No hardware acceleration. Acceptable for static plots but
  not for real-time beam animation.

## 4. Plugin Architecture

**Decision**: Python ABC (Abstract Base Class) + manual registry pattern

**Rationale**: ABC enforces interface contracts at class definition time
(missing methods raise `TypeError`). A simple registry dict per
algorithm type (`AlgorithmRegistry`) provides explicit, debuggable
plugin discovery. This is the lightest approach that satisfies the
modularization principle — no external dependencies, no magic, easy to
understand for contributors adding new algorithms. The architecture
supports 10 plugin interface types (Waveform, PhaseNoiseModel,
ClutterModel, GPSErrorModel, IMUErrorModel, ImageFormationAlgorithm,
MotionCompensationAlgorithm, AutofocusAlgorithm,
ImageTransformationAlgorithm, PolarimetricDecomposition).

**Alternatives Considered**:
- **pluggy**: Full-featured plugin system (used by pytest) but adds a
  dependency and concept overhead (hook specs, hook impls) that is
  excessive for our use case.
- **entry_points (setuptools)**: Good for installed packages but
  requires `setup.cfg`/`pyproject.toml` configuration per plugin. Too
  heavy for algorithms that live within the same package.
- **importlib auto-discovery**: Scanning directories for modules is
  fragile and makes dependencies implicit. Explicit registration is
  clearer.

## 5. Unified Waveform Interface

**Decision**: `Waveform` ABC with unified `generate()` and
`range_compress()` methods. Active signal duration derived from
`duty_cycle / Radar.prf`.

**Rationale**: Each waveform type has a fundamentally different range
compression method: LFM uses frequency-domain matched filtering, FMCW
uses dechirp + FFT, phase-coded waveforms use correlation, etc. Rather
than branching on `waveform_type` in the simulation engine, each
waveform encapsulates both signal generation and range compression.
The engine just calls `generate()` and `range_compress()` without
knowing the waveform type.

The waveform stores its transmit signal internally after `generate()`
so that `range_compress()` can use it (e.g., as the dechirp reference
for FMCW). This eliminates the need to pass tx references externally.

Duration is derived from `duty_cycle / prf` rather than specified
directly, ensuring consistency between waveform and radar timing and
preventing invalid configurations where pulse duration exceeds PRI.

Waveforms generate baseband signals (centered at 0 Hz). The carrier
frequency is applied by the simulation engine from `Radar.carrier_freq`.

**Alternatives Considered**:
- **Separate `matched_filter()` and `dechirp()` methods with
  `waveform_type` branching**: Requires the engine to know about
  waveform types. Violates the modularization principle. Adding a new
  waveform type would require engine changes.
- **Absolute duration parameter**: Risk of invalid configs where
  duration > PRI. Duty cycle is more intuitive and safe by construction.

## 6. FMCW Waveform Support

**Decision**: `FMCWWaveform` class with configurable ramp type
(up/down/triangle) and duty cycle

**Rationale**: FMCW is fundamentally different from pulsed radar —
it transmits continuously and uses dechirp processing instead of
matched filtering. The `FMCWWaveform` implementation handles:

- **Ramp types**: Up-ramp, down-ramp, and triangle (up then down).
  Triangle ramp enables unambiguous velocity estimation by resolving
  the range-Doppler coupling from two ramps.
- **Duty cycle**: When < 1.0, models pulsed/duty-cycled FMCW systems
  where the chirp occupies only a fraction of the PRI.
- **Dechirp processing**: `range_compress()` mixes the received signal
  with the stored transmit reference (s_rx · s_tx*), applies a window,
  and FFTs to produce range-compressed output.

The beat signal phase after dechirp contains:
1. Range beat frequency: f_r = 2KR₀/c
2. Doppler shift: f_d = 2v/λ
3. Range-Doppler coupling: 2Kv/c (quadratic phase term)
4. Residual video phase: -πKτ²
5. Phase noise residual: Δφ_pn(t) = φ_pn(t) - φ_pn(t - τ)

Reference: `specs/001-sar-signal-simulator/references/` contains a
Gemini-generated report and Python code demonstrating FMCW signal
simulation with phase noise and target velocity. The mathematical
model has been verified as correct.

## 7. Phase Noise Modeling

**Decision**: Modular `PhaseNoiseModel` ABC with `CompositePSDPhaseNoise`
as the default implementation

**Rationale**: Oscillator phase noise is critical for FMCW radar
performance and affects pulsed systems at long ranges. The phase noise
PSD of real oscillators is a composite of multiple noise processes:

- 1/f³ (flicker FM noise) — dominant close to carrier
- 1/f² (white FM noise / random walk)
- 1/f (flicker PM noise)
- White noise floor — dominant far from carrier

The `CompositePSDPhaseNoise` model parameterizes each component
independently (in dBc/Hz), generates the composite PSD in the
frequency domain, shapes white noise with it, and IFFTs to produce a
time-domain phase noise vector φ_pn(t).

**Range correlation effect**: The simulation engine handles this by:
1. Generating φ_pn(t) once per pulse/chirp via the phase noise model
2. Adding φ_pn(t) to the transmit signal phase
3. For each target at delay τ, interpolating φ_pn(t - τ) for the
   received signal
4. After mixing/compression: Δφ_pn = φ_pn(t) - φ_pn(t - τ) emerges

Close targets (small τ) → phase noise cancels → clean signal.
Far targets (large τ) → noise decorrelates → elevated noise floor.

Phase noise is applied at baseband, which is physically equivalent to
applying it at the carrier — the phase noise term is independent of
the signal representation domain.

## 8. Radar Range Equation and Receiver Noise

**Decision**: Full radar range equation for amplitude scaling, additive
complex Gaussian thermal noise

**Rationale**: Physically correct received power requires the full link
budget:

P_r = (P_t · G² · λ² · σ) / ((4π)³ · R⁴)

where P_t is transmit power, G is two-way antenna gain, λ is
wavelength, σ is target RCS, and R is range. System losses (cable,
radome, T/R switch) are applied as an aggregate dB attenuation factor.

Receiver thermal noise power is:

N = k · T · B · F

where k is Boltzmann's constant, T is reference temperature (default
290 K), B is receiver bandwidth, and F is noise figure (default 3 dB).
Noise is added as complex Gaussian (independent I and Q channels) after
summing all target echoes.

These parameters (noise_figure, system_losses, reference_temp) live on
the `Radar` entity with sensible defaults.

## 9. Target Velocity Effects

**Decision**: Full within-pulse motion modeling for FMCW, start-stop
approximation for pulsed (with future option to remove it)

**Rationale**: Target motion affects the echo signal through:

1. **Time-varying delay**: τ(t) = 2(R₀ + v·t) / c, where v is the
   radial velocity between target and platform
2. **Doppler shift**: f_d = 2v/λ — frequency offset in the echo
3. **Range-Doppler coupling**: 2Kv/c — a small chirp rate in the beat
   signal caused by the changing delay during the chirp. Significant
   for fast targets or long chirps (especially FMCW).
4. **Within-pulse motion**: For FMCW (long continuous chirps), the
   delay varies continuously within a single chirp. The simulation
   uses τ(t) directly without start-stop approximation. For pulsed
   waveforms (short pulses), start-stop is valid and used by default.

The radial velocity accounts for both target motion and platform
motion — it is the relative velocity along the line of sight.

## 10. Motion Perturbation Model

**Decision**: Dryden turbulence model as default, Von Kármán as optional

**Rationale**: The Dryden model uses rational transfer functions that
can be implemented as linear filters driven by white noise —
computationally efficient and produces realistic turbulence spectra for
low-altitude airborne/UAV platforms. It is the MIL-HDBK-1797 standard.
Von Kármán is more physically accurate (irrational spectrum) but harder
to implement as a time-domain filter. Both should be available; Dryden
is the default.

**Alternatives Considered**:
- **Von Kármán only**: More accurate spectral shape but requires
  approximation for time-domain generation (fractional-order filters
  or frequency-domain methods). Better as an advanced option.
- **Simple sinusoidal**: Too simplistic, doesn't capture broadband
  turbulence character. Unsuitable for realistic motion error studies.
- **Recorded flight data replay**: Useful for validation but doesn't
  allow parametric studies. Could be added as a future data source.

## 11. Sensor Error Model Architecture

**Decision**: Modular error model ABCs (`GPSErrorModel`, `IMUErrorModel`)
with simplest-possible defaults; advanced models as future modules

**Rationale**: GPS and IMU error characteristics vary enormously by
grade (MEMS vs tactical vs navigation) and mode (standalone vs RTK).
Rather than building a complex error model upfront, we define the
plugin interface now and ship the simplest implementations:

- **GPS default (`GaussianGPSError`)**: Additive white Gaussian noise
  with configurable RMS. No temporal correlation. Sufficient for basic
  MoCo testing and algorithm development.
- **IMU default (`WhiteNoiseIMUError`)**: Additive white noise on
  accelerometer and gyroscope with configurable noise density. No bias
  drift, scale factor, or quantization.

Future advanced models can add:
- GPS: RTK with integer ambiguity resolution, Gauss-Markov correlated
  errors, multipath, position-domain Markov chain state transitions
- IMU: IEEE-STD-952 five-term model (bias instability, random walk,
  scale factor, quantization, rate ramp)

The `GPSSensor` and `IMUSensor` configuration entities hold references
to their error model instances, following the same pattern as
`Radar` → `Waveform`.

## 12. Two-Step Image Formation and Autofocus

**Decision**: Image formation exposes `range_compress()` →
`PhaseHistoryData` → `azimuth_compress()` → `SARImage`, with
autofocus operating on the intermediate `PhaseHistoryData`

**Rationale**: Most autofocus algorithms operate on the range-compressed
phase history — the intermediate data between range compression and
azimuth compression. They estimate residual phase errors (remaining
after first-stage MoCo) and correct them in the phase history domain
before re-running azimuth compression.

This requires splitting image formation into two explicit steps and
introducing `PhaseHistoryData` as a first-class intermediate data type.
The autofocus algorithm receives `azimuth_compress` as a callback,
decoupling it from any specific image formation algorithm.

The `process()` convenience method runs both steps end-to-end for cases
where autofocus is not needed.

**Default autofocus algorithms**:
- **PGA (Phase Gradient Autofocus)**: Selects dominant scatterers,
  estimates phase gradient, integrates to get error. Best all-round
  default.
- **MDA (Map Drift Autofocus)**: Splits aperture into sub-images,
  measures drift. Best for low-order phase errors.
- **Minimum Entropy Autofocus**: Optimizes image sharpness via entropy
  minimization. Best for distributed scenes without point targets.
- **PPP (Prominent Point Processing)**: Extracts phase histories from
  isolated scatterers. Works directly in the phase history domain.

Whether to run autofocus is a `ProcessingConfig` setting
(`autofocus: AutofocusAlgorithm | None`).

## 13. Clutter Model Architecture

**Decision**: Modular `ClutterModel` ABC with `UniformClutter` as the
simplest default

**Rationale**: Distributed target reflectivity can be provided directly
as an array or generated by a clutter model. The default
`UniformClutter` provides constant reflectivity (no statistical texture)
— suitable for basic testing. Statistical models (K-distribution,
log-normal, Weibull) can be added as future modules for more realistic
clutter simulation.

The clutter model is referenced by `DistributedTarget` via an optional
`clutter_model` field. When set, it overrides the `reflectivity` array
and generates texture at simulation time using the configured seed.

## 14. SimulationConfig / ProcessingConfig Split

**Decision**: Separate configurations for signal generation and
processing pipeline

**Rationale**: A researcher often wants to re-process the same raw data
with different algorithm selections (e.g., compare RDA vs Omega-K, test
with/without autofocus, try different MoCo algorithms). Splitting the
config enables this without re-running the expensive signal simulation.

- **SimulationConfig**: scene, radar (including waveform), platform
  (including sensors), n_pulses, seed. Controls signal generation.
- **ProcessingConfig**: moco, image_formation, autofocus, geocoding,
  polarimetric_decomposition. Controls the processing pipeline. Each
  field is an algorithm module instance or None (skip that step).

Both configs are independently serializable to JSON/HDF5 for
reproducibility.

## 15. Coordinate System

**Decision**: Local East-North-Up (ENU) with WGS84 reference point

**Rationale**: ENU is the standard local tangent plane frame for
airborne radar geometry. East (x), North (y), Up (z) provides
intuitive 3D coordinates. A WGS84 origin (lat, lon, alt) anchors the
local frame to the globe for georeferencing. The flat-earth
approximation is valid for typical SAR scene extents (< 50 km). For
larger scenes or precise georeferencing, the geodetic transforms in
`coordinates.py` handle ENU ↔ WGS84 conversion.

## 16. SAR Signal Simulation Approach

**Decision**: Time-domain echo generation with start-stop approximation
(pulsed) or continuous delay (FMCW)

**Rationale**: Time-domain simulation computes the received echo for
each pulse by summing contributions from all targets at their
instantaneous range. This is conceptually simple, physically
transparent, and naturally handles arbitrary 3D target positions,
motion perturbation, antenna pattern weighting, and the radar range
equation.

For pulsed waveforms, the start-stop approximation (platform stationary
during each pulse) is standard and valid when platform velocity << c.
For FMCW, the delay τ(t) varies continuously within the chirp —
start-stop is not applied within a chirp.

The echo for pulse `n` is:

  `s(t,n) = Σ_k √(P_r,k) · a(θ_k) · w(t - τ_k) · exp(-j4πf_c R_k/c) + n(t)`

where `P_r,k` is the received power from target k (radar range
equation), `a(θ_k)` is two-way antenna pattern gain, `w(t)` is the
waveform, `τ_k` is the round-trip delay, and `n(t)` is receiver noise.

Vectorization over targets using NumPy ensures performance. For large
scenes (>10k targets), the target sum is the bottleneck and can be
parallelized.

**Alternatives Considered**:
- **Frequency-domain simulation**: Faster for uniform grids but less
  flexible for arbitrary 3D point targets and non-linear motion. Can
  be added as an optimization for distributed targets on regular grids.
- **Stop-and-go removal for pulsed**: Adds intra-pulse motion effects.
  Important for very fast platforms or long pulses but adds complexity.
  Can be an optional mode in the future.

## 17. Multipath (Future Architecture)

**Decision**: Not modeled in initial version. Architecture supports
future ray-tracing-based extension.

**Rationale**: Multipath (ground-bounce, multi-bounce) is important for
low-altitude UAV SAR over smooth surfaces but requires:
- A `SurfaceModel` entity (reflection coefficient, roughness) on `Scene`
- Ray tracing to compute indirect paths (direct, ground-bounce,
  target-ground-bounce) with their own delays, amplitudes, and phases
- Summing all path contributions per target in the echo computation

The simulation engine's per-target echo computation loop is structured
to accommodate additional path contributions without architectural
changes. Each path would contribute an additional term to the echo sum
with its own range, amplitude (reflection loss), and phase.

No implementation in this phase; the architecture is ready for it.
