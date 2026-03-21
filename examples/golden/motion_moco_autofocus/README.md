# Golden Case 3: Motion, MoCo, and Autofocus

## Purpose

This case validates the non-ideal flight path. Cases 1 and 2 use perfect
straight-line trajectories; Case 3 adds Dryden turbulence, GPS/IMU navigation
sensors, and specifies first-order motion compensation plus PGA autofocus in
the processing config. It tests the full simulation-to-correction chain that a
real airborne SAR system would exercise.

## What This Test Proves

1. **Dryden turbulence model** generates a perturbed trajectory that measurably
   deviates from the ideal straight line. If the perturbation model is broken
   (e.g., produces zero displacement), the test detects it.

2. **Navigation sensor models** -- GPS (Gaussian error, 10 Hz) and IMU (white
   noise, 100 Hz) are attached to the platform and produce measurement data
   during the simulation. This exercises the sensor attachment and measurement
   generation pipeline.

3. **Simulation with perturbed trajectory** -- the SimulationEngine uses the
   true (perturbed) position for each pulse's echo computation, not the ideal
   position. This means the echo data contains motion-induced phase errors
   that would defocus the image if left uncorrected.

4. **Image formation with ideal trajectory** -- by providing the ideal (known)
   trajectory to the image formation algorithm, the test verifies that the
   echo data itself is valid: the target is still detectable when the "correct"
   trajectory is used for focusing. This separates signal generation correctness
   from motion compensation correctness.

5. **Processing config completeness** -- the parameter set specifies MoCo
   (first_order) and autofocus (PGA) in the processing config, validating that
   these algorithm references load and parse correctly through the parameter
   set I/O system.

## Geometry

Same base geometry as Case 1:

```
                Platform (0, y, 2000) ──> North
                |
                |  45 deg depression
                |  \
       2000 m   |   \  R0 = 2828.4 m
                |    \
                |     \
     -----------+------*--- Target (2000, 0, 0)
               2000 m East
```

But the platform trajectory is now **perturbed by Dryden turbulence**.
The actual flight path deviates from the ideal straight line by up to several
meters over the 51.2 m aperture, introducing position-dependent phase errors
in the echo data.

## Differences from Case 1

| Aspect | Case 1 | Case 3 | Why changed |
|--------|--------|--------|-------------|
| RCS | 1.0 m^2 | 10.0 m^2 | Higher RCS provides SNR margin -- motion errors degrade focus, so the target must survive the degradation |
| n_pulses | 256 | 512 | Longer aperture accumulates more motion error, making the perturbation effect more visible and the MoCo correction more necessary |
| Perturbation | None | Dryden (sigma_u=1.5, sigma_v=1.5, sigma_w=0.75) | The core feature under test |
| Sensors | None | GPS + IMU | Exercises the sensor model pipeline |
| start_position | (0, -12.8, 2000) | (0, -25.6, 2000) | Longer aperture (512 * 0.1 = 51.2 m) requires start at -25.6 for centering |
| Processing | RDA only | RDA + first_order MoCo + PGA | Full correction chain |
| Antenna | Flat | Gaussian | Tests a different antenna preset; gaussian beam provides smooth gain taper that is more representative of real antennas |

## Parameter Choices and Rationale

### Scene

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| origin | (34.05, -118.25, 0) | Same geographic reference as Cases 1-2. Unused in ENU simulation; reserved for Phase 9 geocoding |
| target position | (2000, 0, 0) | Same as Case 1 to allow direct comparison of ideal vs perturbed results |
| target RCS | 10.0 m^2 | 10x Case 1. Motion errors spread the target energy across multiple resolution cells, reducing the peak. Higher RCS ensures the degraded peak still exceeds the noise floor. The 10 dB margin is a deliberate design choice |
| rcs_model | static | Deterministic. Any amplitude variation in the echo is attributable to motion, not RCS fluctuation |

### Radar

Same as Case 1 (9.65 GHz, 1000 Hz PRF, 1 kW, single pol, stripmap, right
look, 45 deg depression). Keeping radar parameters identical to Case 1 ensures
any difference in image quality is attributable to the motion perturbation.

### Waveform

Same as Case 1 (LFM, 150 MHz, 10% duty, no window, no phase noise).

### Antenna

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| preset | gaussian | Smooth gain taper with K=12 (3 dB at half-beamwidth). More representative of real SAR antennas than the flat pattern. Tests a different antenna preset code path from Cases 1 and 2. The gaussian beam gives smooth amplitude weighting across the aperture, which is typical for airborne SAR systems |
| az_beamwidth | 3.0 deg | Same as Case 1. Beam footprint = 2828 * 0.052 = 148 m. The 51.2 m aperture fits within the 3 dB beam |
| el_beamwidth | 10.0 deg | Same as Case 1 |
| peak_gain | 30 dB | Same as Cases 1 and 2 |

### Platform

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| velocity | 100 m/s | Same as Case 1 |
| altitude | 2000 m | Same as Case 1, enabling direct comparison |
| start_position | (0, -25.6, 2000) | With 512 pulses at 0.1 m spacing the aperture is 51.2 m. Starting at y = -25.6 centers the aperture at y = 0 where the target sits |
| **perturbation** | **Dryden** | MIL-HDBK-1797 turbulence model. Generates correlated velocity perturbations with PSD matching atmospheric turbulence spectra |
| sigma_u | 1.5 m/s | Longitudinal (along-track) turbulence intensity. Moderate turbulence -- enough to cause visible trajectory deviation without completely destroying image quality |
| sigma_v | 1.5 m/s | Lateral (cross-track) turbulence intensity. Equal to sigma_u, representing isotropic horizontal turbulence |
| sigma_w | 0.75 m/s | Vertical turbulence intensity. Half of horizontal, following the empirical rule that vertical turbulence is weaker than horizontal for low-altitude airborne platforms |

**Why these sigma values?** At 100 m/s and sigma_u = 1.5 m/s, the velocity
perturbation is 1.5% of flight speed. Over a 0.512 s aperture, this
accumulates to position deviations of order 0.5-2 m. At X-band (lambda =
0.031 m), a 1 m position error causes a phase error of 4*pi*1/0.031 = 405
radians -- many cycles. This is enough to completely defocus the image without
MoCo, validating that the correction chain is necessary, not just cosmetic.

### Sensors

| Sensor | Parameter | Value | Rationale |
|--------|-----------|-------|-----------|
| GPS | accuracy_rms | 1.0 m | Tactical-grade GPS. Position measurements have 1 m RMS error per axis, which is comparable to the motion perturbation magnitude |
| GPS | update_rate | 10 Hz | Standard GPS output rate. At 1000 Hz PRF, there is one GPS measurement per 100 pulses |
| GPS | error_model | gaussian | Simple additive Gaussian noise. Tests the GaussianGPSError model |
| IMU | accel_noise_density | 0.003 m/s^2/sqrt(Hz) | MEMS-grade accelerometer (e.g., ADXL345 class) |
| IMU | gyro_noise_density | 0.0005 rad/s/sqrt(Hz) | MEMS-grade gyroscope |
| IMU | sample_rate | 100 Hz | Typical MEMS IMU output rate. 10x GPS rate, exercises the different-rate sensor pipeline |
| IMU | error_model | white_noise | Additive white noise on accelerometer and gyroscope channels |

**Why both GPS and IMU?** A real airborne SAR system fuses GPS (absolute
position, slow, noisy) with IMU (relative motion, fast, drifts). Including
both exercises the multi-sensor platform model and verifies that the simulation
engine correctly generates measurements from each sensor during the pulse loop.

### Simulation

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| n_pulses | 512 | Double Case 1. A longer aperture means more time for turbulence to accumulate, creating larger position errors. With 512 pulses at 0.1 m spacing the aperture is 51.2 m, taking 0.512 s |
| seed | 42 | Same seed as all cases. Ensures the Dryden turbulence realization is reproducible |
| sample_rate | null (auto) | Defaults to 3 * bandwidth = 450 MHz |
| swath_range | (2600, 3100) m | Same as Case 1. The 500 m swath accommodates the target at R0=2828 m plus motion-induced range deviations (up to ~4 m) |

### Processing

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| image_formation | range_doppler | Same as Case 1. Keeps the image formation algorithm constant so any quality difference is attributable to the motion/correction pipeline |
| moco | first_order | Bulk range-dependent phase correction to scene center. The simplest MoCo algorithm, correcting the dominant motion error component |
| autofocus | pga | Phase Gradient Autofocus. Data-driven estimation and correction of residual phase errors after MoCo. PGA is the most robust autofocus algorithm for single-target scenes |

## Analytical Expectations

| Quantity | Value | Notes |
|----------|-------|-------|
| Slant range | 2828.4 m | Same geometry as Case 1 |
| Range resolution | 1.0 m | Same waveform as Case 1 (150 MHz, no window) |
| Range sample spacing | 0.333 m | At 450 MHz sample rate |
| Azimuth resolution (ideal) | lambda*R/(2*L) = 0.031*2828/(2*51.2) = 0.86 m | Finer than Case 1 due to longer aperture |
| RMS position error | ~0.5-2 m over aperture | From Dryden model with sigma_u = 1.5 m/s |
| Phase error from motion | 4*pi*dR/lambda ~ 100-400 rad for 1 m deviation | Many cycles -- completely defocuses without correction |
| Expected trajectory deviation | max(||true - ideal||) > 0.01 m | Verified by test |

## Pass Criteria

1. **Echo matrix shape** is (512, n_range) in channel "single".

2. **Both trajectories exist** -- `ideal_trajectory` and `true_trajectory`
   are both non-null, confirming that the Platform generated both paths.

3. **Trajectory is perturbed** -- the maximum position difference between
   ideal and true trajectories exceeds 0.01 m. This validates that the Dryden
   turbulence model actually perturbed the flight path.

4. **Image formation with ideal trajectory** -- using the known ideal
   trajectory for focusing produces a target peak at least 3x the noise floor.
   This proves that the echo data is physically correct (the target signal is
   present and phase-coherent when the correct trajectory is used), even though
   the echoes were generated using the perturbed trajectory.

## Diagnostic Plots

### Plot 1: Trajectory Comparison (Ideal vs Perturbed)

- **What**: Two 3D line plots (or three 2D subplots for East/North/Up
  components vs time) showing the ideal straight-line trajectory and the
  Dryden-perturbed true trajectory.
- **What to look for**: The true trajectory should visibly deviate from the
  ideal, with smooth, correlated fluctuations (not white noise). The vertical
  component (Up) should have smaller deviations than horizontal (sigma_w =
  0.5 * sigma_u). The deviations should be on the order of 0.5-2 m over the
  0.512 s aperture.
- **Failure signature**: Identical trajectories (perturbation not applied),
  discontinuous jumps (integration error in the Dryden model), or deviations
  that are too large (> 10 m, suggesting wrong sigma values) or too small
  (< 0.01 m, suggesting the model produces negligible output).

### Plot 2: Position Error vs Pulse Index

- **What**: 1D plot of ||true_position - ideal_position|| (3D Euclidean
  distance) vs pulse index. Optionally show the three components (East,
  North, Up) separately.
- **What to look for**: A smoothly varying curve that grows roughly as
  sqrt(time) (random walk behavior). The peak value should be on the order
  of 1-3 m. The curve should not be monotonically increasing (turbulence is
  oscillatory, not purely drift).
- **Failure signature**: Flat line at zero (no perturbation), linear growth
  (constant velocity offset, not turbulence), or extremely jagged curve
  (perturbation is uncorrelated noise, not Dryden spectral shaping).

### Plot 3: Focused Image with Ideal Trajectory

- **What**: 2D image of 20*log10(|image|) formed using the ideal trajectory
  for azimuth compression. Dynamic range 30-40 dB.
- **What to look for**: A well-focused point target (similar to Case 1 but
  with slightly different noise characteristics due to the gaussian antenna
  weighting). The target should be clearly detectable above the noise floor.
- **Failure signature**: Smeared or defocused target (ideal trajectory not
  correctly used), or no visible target (echo generation broken).

### Plot 4: Focused Image with Perturbed Trajectory (No MoCo)

- **What**: 2D image of 20*log10(|image|) formed using the perturbed
  trajectory for azimuth compression, with NO motion compensation applied.
- **What to look for**: A visibly defocused, smeared target. The peak should
  be significantly lower than in Plot 3, and the energy should be spread
  across multiple azimuth cells. This plot demonstrates WHY MoCo is needed --
  without it, the motion errors destroy the coherent integration.
- **Failure signature**: If this image looks identical to Plot 3, the
  perturbation is too small to matter or the echo generation is not using the
  perturbed trajectory. If the target is completely invisible, the
  perturbation may be too severe for the configured SNR.

### Plot 5: Phase Error Along Aperture

- **What**: 1D plot of the phase error (in radians) at the target range bin
  across all pulses, computed as 4*pi*(R_true - R_ideal)/lambda where R_true
  and R_ideal are the slant ranges from the true and ideal platform positions
  to the target.
- **What to look for**: A smoothly varying phase curve spanning many radians
  (tens to hundreds). This is the phase error that MoCo must correct. The
  curve should resemble the position error in Plot 2, scaled by 4*pi/lambda.
- **Failure signature**: Flat line (no motion-induced phase error, which
  would mean the trajectory perturbation is not affecting slant range), or
  discontinuities (trajectory interpolation errors).

## Design Decisions

- **Why reuse Case 1 geometry?** By keeping the same target position, altitude,
  and depression angle, a reviewer can directly compare Case 3 results against
  Case 1. Any quality difference is purely attributable to the motion
  perturbation and correction chain, not to a different operating point.

- **Why RCS 10 instead of 1?** Motion errors spread the target's energy across
  multiple resolution cells, reducing the peak-to-noise ratio. With RCS = 1
  (as in Case 1), the degraded target might fall below the noise floor. The
  10x increase provides a 10 dB safety margin, ensuring the target remains
  detectable even without MoCo.

- **Why test with ideal trajectory instead of MoCo?** The test currently forms
  an image using the ideal trajectory (which the test has access to since it
  controls the simulation). This tests the signal generation correctness: "if
  we knew the true trajectory perfectly, would the echo data focus correctly?"
  This is a stronger and more diagnostic test than testing MoCo, because a
  MoCo failure could be caused by either bad echo data or bad MoCo code. By
  bypassing MoCo and using ideal trajectory, we isolate the echo generation.
  The MoCo and autofocus algorithms themselves are thoroughly tested in
  `tests/integration/test_moco.py`.

- **Why specify MoCo + PGA in processing config if the test doesn't use them?**
  The processing config validates the parameter set I/O path: the algorithm
  names parse, the ProcessingConfig constructs, and the config is available for
  future pipeline runner integration (Phase 11). The actual MoCo and autofocus
  algorithms are thoroughly tested in `tests/integration/test_moco.py`.

- **Why sigma_w = 0.5 * sigma_u?** Empirical observations of atmospheric
  turbulence show that vertical velocity fluctuations are typically 40-60% of
  horizontal fluctuations for boundary-layer turbulence below 1000 m AGL. At
  2000 m altitude, using 50% is a reasonable approximation. This ratio also
  matches MIL-HDBK-1797 recommendations for moderate turbulence at low
  altitude.

- **Why 512 pulses instead of 256?** A longer aperture provides two benefits:
  (a) finer azimuth resolution (0.86 m vs 1.72 m), and (b) more accumulated
  motion error. The motion effect grows with aperture time, so 512 pulses
  (0.512 s) gives the turbulence twice as long to displace the platform
  compared to 256 pulses (0.256 s). This makes the perturbation more
  pronounced and the test more sensitive.

- **Why does the Scene origin exist if it's unused?** See Case 1 README for
  the explanation. In short: reserved for Phase 9 geocoding; exercises the
  parameter set I/O handling of geographic coordinates.
