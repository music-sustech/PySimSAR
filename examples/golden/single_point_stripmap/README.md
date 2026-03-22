# Golden Case 1: Single Point Target, Stripmap

## Purpose

This is the simplest possible end-to-end validation of the PySimSAR pipeline.
By using a single point target, ideal flight (no perturbation), no windowing,
and the simplest image formation algorithm (Range-Doppler), we isolate the
core signal generation and focusing path from all optional features. If this
test fails, the fundamental physics model is broken.

## What This Test Proves

1. **Parameter set I/O** works end-to-end: JSON files load, `$ref` resolves,
   unit suffixes strip, degrees convert to radians, and `build_simulation()`
   constructs valid Scene/Radar/Platform objects.

2. **Echo signal generation** places the target echo at the correct round-trip
   delay with correct phase from the range equation.

3. **Platform geometry** is correct: the broadside slant range to the target
   matches the analytical value sqrt(2000^2 + 2000^2) = 2828.4 m.

4. **Range-Doppler image formation** (range compression + azimuth matched
   filter + RCMC) produces a focused point target response that is detectable
   above the thermal noise floor.

## Geometry

```
                Platform (0, y, 2000) ──> North (y+)
                |
                |  45 deg depression
                |  \
       2000 m   |   \  R0 = 2828.4 m
                |    \
                |     \
     -----------+------*--- Target (2000, 0, 0)
               2000 m East (x+)
```

The platform flies North at altitude 2000 m. The radar looks right (East) at
45 deg depression angle. The target sits on the ground at (2000, 0, 0) ENU --
directly East of the sub-track point, placing it at beam center when the
platform passes y = 0.

## Parameter Choices and Rationale

### Scene

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| origin | (34.05, -118.25, 0) | Geographic reference point for future geocoding (Phase 9: pixel-to-lat/lon mapping). Currently unused in ENU-based simulation calculations -- all echo computation operates in local ENU meters relative to (0,0,0). Included here to exercise the Scene constructor and to ensure the parameter set I/O correctly handles geographic coordinates (degree values that must NOT be converted to radians) |
| target position | (2000, 0, 0) m | Places target at exactly 2000 m cross-track. Combined with 2000 m altitude and 45 deg depression, the target sits at beam center. The round number makes analytical calculations trivial |
| target RCS | 1.0 m^2 | Unit RCS so signal amplitude = path_loss * sqrt(1) * sqrt(gain) -- simplifies power budget verification |
| rcs_model | static | Non-fluctuating. Ensures deterministic echo amplitude across pulses (no stochastic variation to confuse analysis) |
| velocity | null | Stationary target. Eliminates Doppler from target motion so the only Doppler is from platform motion (the SAR signal itself) |

### Radar

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| carrier_freq | 9.65 GHz | X-band, standard airborne SAR frequency. Wavelength = 0.03107 m |
| PRF | 1000 Hz | Gives pulse spacing = V/PRF = 100/1000 = 0.1 m. Clean integer ratio simplifies aperture length calculation |
| transmit_power | 1000 W | Round number; combined with other parameters yields ~6 dB single-pulse SNR at R0 = 2828 m |
| receiver_gain | 0 dB | No receiver amplification. The cascade noise model reduces to F_total = L_sys * F_rx, isolating the noise figure and system loss effects |
| noise_figure | 3.0 dB | Typical X-band receiver. F_rx = 2.0 linear |
| system_losses | 2.0 dB | Typical pre-receiver losses (cables, radome, switches). L_sys = 1.585 linear |
| reference_temp | 290 K | IEEE standard reference temperature |
| polarization | single | One channel. Eliminates cross-pol complexity |
| mode | stripmap | Fixed beam direction. The simplest SAR mode -- beam always points broadside |
| look_side | right | Beam looks East (positive x in ENU for North-heading flight) |
| depression_angle | 45 deg | Creates a symmetric geometry: ground_range = altitude = 2000 m. Slant range = altitude * sqrt(2) |
| squint_angle | 0 deg | Pure broadside imaging. No along-track beam squint |

### Waveform

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| type | LFM | Linear Frequency Modulated chirp -- the standard SAR waveform |
| bandwidth | 150 MHz | Gives range resolution = c/(2B) = 1.0 m exactly. A round number that makes resolution verification trivial |
| duty_cycle | 0.1 | 10% duty. Chirp duration = 0.1/PRF = 100 us. Standard for pulsed SAR |
| window | null | No windowing. Preserves the theoretical sinc impulse response with first sidelobe at -13.3 dB. Windowing would broaden the main lobe and change resolution |
| phase_noise | null | No oscillator phase noise. Ensures the echo phase is purely deterministic from the range equation |

### Antenna

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| type | preset/flat | Rectangular beam with uniform gain inside and -60 dB floor outside. The simplest pattern -- eliminates gain variation within the beam so all pulses illuminate the target with equal gain |
| az_beamwidth | 3.0 deg | Beam footprint at R0 = 2828 m is R0 * theta = 2828 * 0.0524 = 148 m. The synthetic aperture (25.6 m) fits well within this footprint, so all 256 pulses illuminate the target |
| el_beamwidth | 10.0 deg | Wide enough to illuminate the target without elevation-dependent gain variation |
| peak_gain (derived) | ~29.2 dB | Automatically computed from beamwidths: G = 4π·0.6 / (0.052 × 0.175) = 824 → 29.2 dB. Two-way gain ≈ 58.3 dB |

### Platform

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| velocity | 100 m/s | Typical slow-flying airborne platform. Gives pulse spacing = 0.1 m and Doppler bandwidth = 2V/lambda = 6436 Hz (well below PRF, no aliasing) |
| altitude | 2000 m | Combined with 45 deg depression, creates 2828 m slant range -- close enough for reasonable SNR with 1 kW transmit power |
| heading | 0 deg | North. Platform moves along y-axis in ENU |
| start_position | (0, -12.8, 2000) | **Critical**: centers the synthetic aperture on the target's azimuth position (y=0). Aperture length = 256 * 0.1 = 25.6 m, so starting at y = -12.8 places the midpoint at y = 0. This ensures the target is at the center of the aperture for maximum integration gain |
| perturbation | null | Ideal straight-line flight. Eliminates motion errors so the test validates the signal model without MoCo corrections |
| sensors | null | No GPS/IMU. Consistent with no perturbation -- there are no motion errors to measure |

### Simulation

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| n_pulses | 256 | Synthetic aperture = 256 * 0.1 = 25.6 m. Gives azimuth resolution = lambda*R0/(2*L) = 0.031*2828/(2*25.6) = 1.72 m. A power of 2 makes FFT-based processing efficient |
| seed | 42 | Deterministic noise generation for reproducibility |
| sample_rate | null (auto) | Defaults to 3 * bandwidth = 450 MHz. The 3x oversampling (1.5x Nyquist) provides margin for anti-aliasing, reduces interpolation errors in RCMC, and improves range sidelobe fidelity compared to the theoretical minimum of 2x |
| swath_range | (2600, 3100) m | Range gate limits the receive window to echoes from 2600-3100 m slant range. The target at R0=2828 m sits near the center with ~230 m margin on each side. This keeps the echo array compact (~46k range bins instead of ~405k for the full PRI) while capturing the complete chirp echo from the target |

### Processing

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| image_formation | range_doppler | The simplest and most transparent image formation algorithm. Range compression via matched filter, azimuth compression via FFT + matched filter. If RDA fails on this geometry, the fundamental SAR processing chain is broken |
| moco | null | No motion compensation. The ideal flight has no motion errors to correct |
| autofocus | null | No autofocus. There are no residual phase errors to estimate |

## Analytical Calculations

| Quantity | Formula | Value |
|----------|---------|-------|
| Wavelength | c / f_c | 0.03107 m |
| Slant range (broadside) | sqrt(2000^2 + 2000^2) | 2828.4 m |
| Pulse spacing | V / PRF | 0.1 m |
| Synthetic aperture length | n_pulses * pulse_spacing | 25.6 m |
| Range resolution | c / (2*B) | 1.0 m |
| Range sample spacing | c / (2 * f_s) | 0.333 m (at 450 MHz) |
| Beam footprint (azimuth) | R0 * theta_az | 148.2 m |
| Target fully illuminated? | 25.6 m < 148.2 m | Yes, all 256 pulses |
| Azimuth resolution | lambda*R0 / (2*L_sa) | 1.72 m |
| Azimuth Doppler bandwidth | V / delta_az | 58.3 Hz (well below PRF) |
| Noise power | k*T*B*F_total*G_rx | 3.8e-12 W |
| Single-pulse SNR (est.) | P_t*G^2*lambda^2*sigma / ((4pi)^3*R^4*L*P_noise) | ~6 dB |
| Integration gain | 10*log10(256) | 24.1 dB |
| Integrated SNR | ~6 + 24.1 | ~30 dB |

## Pass Criteria

1. **Parameter set loads** without errors and `build_simulation()` constructs
   valid objects with correct field values.

2. **Echo matrix shape** is (256, n_range) with n_range > 0 in channel "single".

3. **Broadside slant range** matches analytical 2828.4 m within 5 m tolerance.
   This validates platform trajectory generation, target geometry, and the
   closest-approach calculation.

4. **Image formation** produces a focused image where the target peak is at
   least 3x the median noise floor. This validates the complete signal chain:
   echo generation -> range compression -> azimuth compression -> focused image.

## Diagnostic Plots

The following plots provide visual confirmation that the simulation and
processing are physically correct. They should be generated from the test
outputs and reviewed when tuning parameters or diagnosing failures.

### Plot 1: Range-Time Diagram (Echo Magnitude)

- **What**: 2D image of |echo(pulse, range_bin)| in dB, with slow time
  (pulse index) on the vertical axis and fast time (range bin) on the
  horizontal axis.
- **What to look for**: A bright hyperbolic arc centered at the broadside
  pulse (pulse ~128) and the target delay bin (~8491 at 450 MHz). The arc
  curvature is the range migration: R(t) = sqrt(R0^2 + V^2*t^2). For 256
  pulses at 100 m/s, the migration span is R(edge) - R0 ~ V^2*T^2/(2*R0)
  = 100^2 * 0.128^2 / (2*2828) ~ 0.03 m -- less than one range bin, so the
  arc should appear nearly vertical (minimal migration for this short
  aperture).
- **Failure signature**: No visible arc (target not generated), arc at wrong
  delay (range equation error), or arc with breaks (beam pattern clipping).

### Plot 2: Range-Compressed Broadside Pulse

- **What**: 1D plot of |range_compressed(range_bin)| in dB for the broadside
  pulse (pulse 128). Horizontal axis is range bin, vertical axis is magnitude
  in dB.
- **What to look for**: A sharp sinc-like peak at the target delay bin with
  -13.3 dB first sidelobes (no window applied). The -3 dB main lobe width
  should correspond to ~1.0 m range resolution (3 bins at 0.333 m spacing).
  The noise floor should be ~30 dB below the peak.
- **Failure signature**: No peak (matched filter broken), broadened peak
  (bandwidth mismatch), asymmetric sidelobes (chirp slope error), or peak at
  wrong bin (delay calculation error).

### Plot 3: Focused SAR Image (2D Magnitude, dB)

- **What**: 2D image of 20*log10(|image|) with range on horizontal axis and
  azimuth on vertical axis. Use a dynamic range of 30-40 dB (clip below
  peak - 40 dB).
- **What to look for**: A single bright point at the target location with a
  cross-shaped sidelobe pattern (sinc in range x sinc in azimuth). The
  background should be uniform noise. No ghost targets or processing
  artifacts.
- **Failure signature**: Smeared peak (azimuth compression failed), split
  peak (RCMC error), ghost targets (aliasing), or tilted sidelobes (squint
  not handled).

### Plot 4: Range Impulse Response (Cut Through Peak)

- **What**: 1D plot of |image(peak_azimuth, range)| in dB, extracted along
  the range dimension at the peak's azimuth row.
- **What to look for**: A sinc-like profile. Measure the -3 dB width and
  verify it matches the expected 1.0 m range resolution (within 5%). The
  first sidelobes should be at -13.3 dB (unwindowed sinc). The PSLR
  (peak-to-sidelobe ratio) and ISLR (integrated sidelobe ratio) can be
  measured from this cut.
- **Failure signature**: Main lobe wider than expected (bandwidth loss during
  processing), sidelobes higher than -13.3 dB (windowing applied
  unexpectedly), or asymmetric profile (range-dependent phase error).

### Plot 5: Azimuth Impulse Response (Cut Through Peak)

- **What**: 1D plot of |image(azimuth, peak_range)| in dB, extracted along
  the azimuth dimension at the peak's range column.
- **What to look for**: A sinc-like profile. The -3 dB width should
  correspond to the expected 1.72 m azimuth resolution. Sidelobes should be
  symmetric, confirming correct Doppler centroid estimation and azimuth
  matched filter design.
- **Failure signature**: Broadened main lobe (insufficient aperture or
  incorrect Doppler rate), asymmetric sidelobes (Doppler centroid error), or
  paired echoes (PRF ambiguity).

## Design Decisions

- **Why 45 deg depression?** Creates a symmetric right triangle (altitude =
  ground_range = 2000 m) making the slant range trivially calculable. Also
  avoids near-grazing (low depression) or near-nadir (high depression) edge
  cases.

- **Why no window?** Windows broaden the main lobe by a factor of 1.2-1.5x.
  By omitting the window, the theoretical resolution matches c/(2B) exactly,
  making resolution verification straightforward. Windowed cases are tested
  in Golden Case 2.

- **Why flat antenna?** The sinc and gaussian patterns introduce gain variation
  across pulses at different look angles. The flat pattern provides uniform
  illumination, isolating the signal processing from antenna pattern effects.
  Non-flat patterns are tested in Golden Case 2.

- **Why start_position = (0, -12.8, 2000)?** The aperture center must align
  with the target's azimuth position for maximum coherent integration. With
  256 pulses at 0.1 m spacing, the aperture spans 25.6 m. Starting at
  y = -12.8 centers the aperture at y = 0, where the target sits.

- **Why RCS = 1.0?** Unit RCS means the target echo amplitude is purely
  determined by the radar range equation path loss and antenna gain, without
  an additional scaling factor. This makes it easier to verify power levels
  analytically.

- **Why 3x noise threshold (not 10x)?** The single-pulse SNR at 2828 m with
  1 kW and 1 m^2 RCS is only ~6 dB. After 256-pulse coherent integration,
  the image-domain SNR is ~30 dB. However, the image formation process
  distributes energy across range-Doppler cells, and the effective SNR at the
  focused peak depends on processing gain, sidelobe levels, and noise
  statistics across a large image. A 3x threshold (9.5 dB) is conservative
  enough to catch true failures while accommodating the noise statistics.

- **Why does the Scene origin exist if it's unused?** The `origin_lat`,
  `origin_lon`, `origin_alt` fields define the geographic reference point for
  the local ENU coordinate system. They are not used in echo computation
  (which operates entirely in ENU meters), but they are required for Phase 9
  geocoding (SlantToGroundRange and Georeferencing algorithms that map image
  pixels back to latitude/longitude). Including them in the golden test
  validates that the parameter set I/O correctly preserves geographic
  coordinates without erroneously converting degrees to radians.
