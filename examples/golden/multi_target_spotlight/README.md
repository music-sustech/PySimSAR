# Golden Case 2: Multi-Target Spotlight

## Purpose

This case exercises features that Case 1 deliberately omitted: multiple
targets at different ranges and RCS values, spotlight mode with beam steering,
Hamming windowing, a non-uniform (sinc) antenna pattern, and the Omega-K
image formation algorithm. Together, these validate that the simulator handles
realistic multi-target scenes and that the more advanced processing modes
produce correct results.

## What This Test Proves

1. **Multiple target handling** -- the simulation engine correctly sums echo
   contributions from three targets at different positions and RCS values
   without cross-contamination.

2. **Spotlight mode beam steering** -- the antenna beam tracks the scene center
   across all 512 pulses, keeping all three targets illuminated despite the
   narrower instantaneous beam footprint.

3. **Omega-K image formation** -- the wavenumber-domain algorithm correctly
   focuses the spotlight geometry, resolving three targets that are separated
   in both range and azimuth.

4. **Windowed waveform** -- the Hamming window is applied during range
   compression, trading main-lobe width for sidelobe suppression (-42 dB
   first sidelobe vs -13.3 dB for unwindowed sinc).

5. **Sinc antenna pattern** -- a physically meaningful beam shape (approximate
   uniform aperture radiation pattern) introduces gain variation with look
   angle. Targets at different azimuth offsets receive different illumination
   weights.

## Geometry

```
        Platform (0, y, 3000) ──> North
              \  45 deg depression
               \
                \  R ~ 4243 m
                 \
    ──────────────*──────── Ground (z=0)
              3000 m East

    Targets (3000 m cross-track baseline):
      T1: (2950, -5, 0)  RCS = 1 m^2   (near range, slight south)
      T2: (3000,  0, 0)  RCS = 5 m^2   (scene center)
      T3: (3060,  5, 0)  RCS = 10 m^2  (far range, slight north)
```

The platform flies North at 3000 m altitude. The scene center is at
(3000, 0, 0) -- 3000 m East on the ground. At 45 deg depression the slant
range to scene center is sqrt(3000^2 + 3000^2) = 4243 m. The three targets
are spread around the scene center with range separations of 50-60 m and
azimuth separations of 5 m, ensuring all targets are well within the
synthetic aperture during the 512-pulse integration.

## Differences from Case 1

| Aspect | Case 1 | Case 2 | Why changed |
|--------|--------|--------|-------------|
| Targets | 1 | 3 | Tests multi-target summation and resolution |
| SAR mode | Stripmap | Spotlight | Tests beam steering to scene center |
| Waveform BW | 150 MHz | 300 MHz | Finer range resolution (0.5 m) to resolve closely spaced targets |
| Window | None | Hamming | Tests windowed impulse response and sidelobe control |
| Antenna | Flat | Sinc | Tests physically realistic gain pattern with nulls |
| Algorithm | Range-Doppler | Omega-K | Tests wavenumber-domain migration for spotlight geometry |
| PRF | 1000 Hz | 2000 Hz | Spotlight wider Doppler bandwidth needs higher sampling rate |
| Altitude | 2000 m | 3000 m | Different slant range exercises geometry at a new operating point |
| n_pulses | 256 | 512 | More pulses for finer azimuth resolution in spotlight mode |

## Parameter Choices and Rationale

### Scene

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| origin | (34.05, -118.25, 0) | Same geographic reference as Case 1. Unused in ENU simulation; reserved for Phase 9 geocoding |
| T1 position | (2950, -5, 0) | 50 m closer in range and 5 m south of center. Well separated in range from T2 (35 m slant range difference >> 0.75 m resolution) |
| T1 RCS | 1.0 m^2 | Weakest target. Tests whether a dim target is still detectable alongside brighter ones |
| T2 position | (3000, 0, 0) | Scene center. The reference target for amplitude comparison |
| T2 RCS | 5.0 m^2 | Mid-brightness. Provides a 7 dB amplitude ratio relative to T1 for verifying RCS-dependent amplitude |
| T3 position | (3060, 5, 0) | 60 m farther in range and 5 m north. Tests near-to-far resolution |
| T3 RCS | 10.0 m^2 | Brightest target (10 dB above T1). Tests dynamic range -- all three must appear in the same image |
| rcs_model | static (all) | Deterministic echo for reproducibility |

**Target separation design**: The three targets form a triangle in the
range-azimuth plane. No two targets share the same range bin or the same
azimuth bin. The azimuth separations are kept small (5 m) so that all
targets remain well within the synthetic aperture (25.6 m traverse) during
the 512-pulse integration, while the range separations (50-60 m) are large
enough to be clearly resolved.

### Radar

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| carrier_freq | 9.65 GHz | Same X-band as Case 1 for comparison. Lambda = 0.03107 m |
| PRF | 2000 Hz | Doubled from Case 1. In spotlight mode the beam steers to track scene center, causing wider Doppler bandwidth. At 2000 Hz PRF the Doppler band is well within Nyquist |
| transmit_power | 1000 W | Same as Case 1 |
| mode | spotlight | The beam steers per pulse to keep scene center illuminated, extending the effective integration time beyond the physical beam footprint |
| depression_angle | 45 deg | Same symmetric geometry as Case 1, at higher altitude |

### Waveform

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| bandwidth | 300 MHz | Doubled from Case 1. Unwindowed range resolution = c/(2B) = 0.5 m. With Hamming, resolution broadens by factor ~1.5 to ~0.75 m. The 50-60 m target separations are far above this, ensuring resolution is not the limiting factor |
| window | hamming | Hamming is the most common SAR window choice. Tests the window factory (string name -> callable) and verifies that the windowed impulse response has suppressed sidelobes (-42 dB). Case 1 uses no window, so this covers the complementary path |
| duty_cycle | 0.1 | Same as Case 1 |

### Antenna

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| preset | sinc | The sinc pattern approximates a uniformly illuminated rectangular aperture -- the textbook SAR antenna. It has nulls and sidelobes, introducing gain variation that the simulator must handle correctly. Case 1 uses flat (no variation), so this tests a different code path in compute_two_way_gain |
| az_beamwidth | 5.0 deg | Wider than Case 1 (3 deg) to ensure all three targets fall within the main beam. At 4243 m range, the 3 dB footprint is 4243 * 0.087 = 370 m -- well beyond the 10 m target azimuth spread |
| el_beamwidth | 15.0 deg | Wide elevation beam to avoid clipping targets at slightly different elevation angles |
| peak_gain (derived) | ~25.2 dB | Automatically computed from beamwidths: G = 4π·0.6 / (0.087 × 0.262) = 330 → 25.2 dB |

### Platform

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| velocity | 100 m/s | Same as Case 1 |
| altitude | 3000 m | Higher altitude than Case 1 (2000 m). Tests a different slant range operating point (4243 m vs 2828 m). Higher altitude means weaker signal (R^4 falloff) but also wider swath |
| start_position | (0, -6.4, 3000) | In spotlight mode the beam steers to track scene_center, so exact centering of the physical aperture over the target is less critical than in stripmap. The platform starts slightly south so that the scene center passes through the aperture |
| perturbation | null | Ideal flight. Isolates spotlight mode and Omega-K processing from motion error effects |

### Simulation

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| n_pulses | 512 | Integration time = 512/2000 = 0.256 s. Platform traverse = 25.6 m. Angular subtent = L/R = 25.6/4243 = 0.00603 rad. Azimuth resolution = lambda/(4*delta_theta) = 0.031/(4*0.00603) = 1.29 m |
| sample_rate | null (auto) | Defaults to 3 * bandwidth = 900 MHz. The 3x oversampling provides anti-aliasing margin and better interpolation accuracy for the Omega-K Stolt mapping |
| swath_range | (4000, 4500) m | Range gate covering all three targets (R=4207-4285 m) with ~200 m near margin and ~215 m far margin. Keeps the echo array compact (~48k range bins) |
| scene_center | (3000, 0, 0) | Required for spotlight mode. The beam steering logic points the antenna toward this location each pulse. Matches T2's position (the central target) |

### Processing

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| algorithm | omega_k | The Omega-K (wavenumber domain) algorithm handles range-dependent migration exactly through Stolt interpolation. It is the natural choice for spotlight SAR where the wide Doppler bandwidth makes the RDA's RCMC approximation less accurate. Testing Omega-K on this geometry validates a different image formation code path from Case 1's RDA |

## Analytical Calculations

| Quantity | Formula | Value |
|----------|---------|-------|
| Wavelength | c / f_c | 0.03107 m |
| Slant range to T1 | sqrt(2950^2 + 5^2 + 3000^2) | 4207.4 m |
| Slant range to T2 | sqrt(3000^2 + 3000^2) | 4242.6 m |
| Slant range to T3 | sqrt(3060^2 + 5^2 + 3000^2) | 4285.3 m |
| T1-T2 slant range separation | R_T2 - R_T1 | 35.2 m |
| T2-T3 slant range separation | R_T3 - R_T2 | 42.7 m |
| Unwindowed range resolution | c / (2*B) | 0.5 m |
| Hamming broadening factor | ~1.5 | ~1.5x |
| Windowed range resolution | 1.5 * 0.5 | ~0.75 m |
| Range sample spacing | c / (2 * f_s) | 0.167 m (at 900 MHz) |
| Integration time | 512 / 2000 | 0.256 s |
| Platform traverse | 100 * 0.256 | 25.6 m |
| Angular subtent | L / R | 0.00603 rad |
| Spotlight azimuth resolution | lambda / (4 * delta_theta) | 1.29 m |
| T1-T2 azimuth separation | 5 m | >> 1.29 m (well resolved) |
| T2-T3 azimuth separation | 5 m | >> 1.29 m (well resolved) |

## Pass Criteria

1. **Echo matrix shape** is (512, n_range) in channel "single".

2. **Three resolved targets** -- after Omega-K image formation, the image
   contains at least 3 pixels above 10% of the peak magnitude. This validates
   that all three targets produce distinct focused peaks and that none are
   lost to noise, sidelobes, or processing artifacts.

## Diagnostic Plots

### Plot 1: Range-Time Diagram (Echo Magnitude)

- **What**: 2D image of |echo(pulse, range_bin)| in dB.
- **What to look for**: Three hyperbolic arcs, one per target. In spotlight
  mode the arcs should be more symmetric (the beam tracks scene center) than
  in stripmap. The arcs for T1 (near range) and T3 (far range) should be
  offset in the range dimension, with T2 in between.
- **Failure signature**: Fewer than 3 arcs (target missing), arcs at wrong
  delays (geometry error), or arcs that fade in/out (beam steering failure).

### Plot 2: Focused SAR Image (2D Magnitude, dB)

- **What**: 2D image of 20*log10(|image|) with 40 dB dynamic range.
- **What to look for**: Three distinct bright points at the expected
  range-azimuth positions. T3 (10 m^2) should be brightest, T2 (5 m^2)
  intermediate, T1 (1 m^2) dimmest. The sidelobes from Hamming windowing
  should be low enough that no target's sidelobes obscure another target.
- **Failure signature**: Merged peaks (resolution failure), missing peaks
  (signal too weak), ghost targets (aliasing or processing artifact), or
  incorrect relative brightness (RCS scaling error).

### Plot 3: Range Cut Through T3 (Brightest Target)

- **What**: 1D plot of |image(T3_azimuth, range)| in dB, with ground truth
  slant ranges for all three targets marked.
- **What to look for**: A main lobe at T3's slant range (4285.3 m) with
  -3 dB width matching the Hamming-windowed resolution (~0.75 m = ~4.5
  range bins at 0.167 m spacing). First sidelobes at -42 dB (Hamming).
  T2's peak should be visible at 4242.6 m (~25-30 dB below T3 in this
  azimuth cut, since T2 is at a different azimuth position).
- **Failure signature**: Main lobe width significantly different from 0.75 m
  (windowing not applied or applied incorrectly), sidelobes higher than
  -42 dB (wrong window), or asymmetric profile.

### Plot 4: Relative Amplitude Comparison

- **What**: Bar chart or annotated scatter plot of the three target peak
  magnitudes in dB, with expected values overlaid.
- **What to look for**: The relative amplitudes should follow the RCS ratio
  corrected for range difference (R^-4) and antenna gain difference. T3/T2
  ratio should be approximately sqrt(10/5) * (R_T2/R_T3)^2 * G_ratio.
  T2/T1 ratio should be approximately sqrt(5/1) * (R_T1/R_T2)^2 * G_ratio.
- **Failure signature**: Amplitude ratios that deviate from expected by more
  than ~2 dB indicate errors in the radar range equation, RCS handling, or
  antenna gain computation.

## Design Decisions

- **Why 3 targets, not 2?** Two targets could accidentally align along a range
  line or azimuth line, testing only one dimension of resolution. Three targets
  in a triangular arrangement guarantee that both range and azimuth resolution
  are exercised.

- **Why different RCS values?** Uniform RCS would only test whether peaks
  exist, not whether their relative amplitudes are correct. The 1:5:10 ratio
  (0 dB : 7 dB : 10 dB) spans a useful dynamic range while keeping all targets
  detectable.

- **Why Omega-K instead of Chirp Scaling?** Omega-K is the algorithm most
  naturally suited to spotlight mode (exact wavenumber-domain migration). CSA
  is designed for stripmap/scanmar. Testing Omega-K on spotlight complements
  Case 1's RDA on stripmap, covering two of the three algorithm-mode
  combinations.

- **Why PRF 2000?** In spotlight mode the beam steers across a wider angular
  range during the aperture, causing the instantaneous Doppler to span a wider
  band. PRF = 2000 Hz provides adequate margin against Doppler aliasing. Case 1
  uses 1000 Hz for stripmap where the Doppler bandwidth is narrower.

- **Why separate from Case 1 geometry?** Using a different altitude (3000 m
  vs 2000 m) and longer slant range (4243 m vs 2828 m) exercises the simulator
  at a different operating point. If a bug only manifests at certain range-
  altitude ratios, having two different geometries increases the chance of
  catching it.
