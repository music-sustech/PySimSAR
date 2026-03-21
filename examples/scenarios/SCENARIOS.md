# Algorithm Scenario Test Suite

This directory contains 19 end-to-end test scenarios exercising every valid algorithm combination in PySimSAR. Each scenario is a self-contained project directory loadable via `load_parameter_set()` and the GUI.

## Shared Configuration

All scenarios (except `scansar_csa`) share the **SUSTech target pattern** (`_scene.json`): 93 point targets spelling "SUSTech" on a 4 m grid, centered at ground range ~1000 m. Target range extent: 908 m to 1092 m, azimuth extent: -12 m to +12 m.

### Base Parameters (unless overridden)

| Parameter        | Value                          |
|------------------|--------------------------------|
| Carrier freq     | 9.65 GHz (X-band)             |
| Tx power         | 1 W                            |
| Bandwidth        | 300 MHz                        |
| Duty cycle       | 1% (LFM) / 10% (FMCW)        |
| PRF              | 1000 Hz (stripmap/scansar)     |
| Antenna          | Flat preset, 10 deg az/el (gain derived) |
| Platform velocity| 100 m/s                        |
| Altitude         | 1000 m                         |
| Depression angle | 45 deg, right-looking          |
| Flight time      | 0.5 s (500 pulses at 1 kHz)   |
| Swath range      | 1350-1500 m                    |
| Seed             | 42                             |

### Perturbation defaults (Groups C-E)

| Parameter           | Value   |
|---------------------|---------|
| Dryden sigma_u      | 1.5 m/s |
| Dryden sigma_v      | 1.5 m/s |
| Dryden sigma_w      | 0.75 m/s|
| GPS accuracy RMS    | 1.0 m   |
| GPS update rate     | 10 Hz   |
| IMU accel noise density | 0.003 |
| IMU gyro noise density  | 0.0005|
| IMU sample rate     | 100 Hz  |

---

## Group A: Ideal Trajectory, Varying IF Algorithm & Mode

These scenarios validate each image formation algorithm on its supported SAR modes with an ideal (unperturbed) trajectory.

### 1. `stripmap_rda`

**Purpose:** Baseline validation of the Range-Doppler Algorithm on stripmap mode.

| Parameter | Value |
|-----------|-------|
| Mode | Stripmap |
| IF Algorithm | `range_doppler` |
| Waveform | LFM, 300 MHz BW, 1% duty |
| MoCo | None |
| Autofocus | None |
| Scene | SUSTech 93 targets |
| Flight time | 0.5 s (500 pulses) |

**Expected:** Clear SUSTech pattern in focused image with all 93 targets above noise floor.

### 2. `stripmap_csa`

**Purpose:** Validate the Chirp Scaling Algorithm on stripmap mode.

| Parameter | Value |
|-----------|-------|
| Mode | Stripmap |
| IF Algorithm | `chirp_scaling` |
| Waveform | LFM, 300 MHz BW, 1% duty |
| MoCo | None |
| Autofocus | None |

**Expected:** Comparable image quality to RDA. CSA handles range-variant azimuth FM rate more accurately.

### 3. `stripmap_omegak`

**Purpose:** Validate the Omega-K (Stolt interpolation) algorithm on stripmap mode.

| Parameter | Value |
|-----------|-------|
| Mode | Stripmap |
| IF Algorithm | `omega_k` |
| Waveform | LFM, 300 MHz BW, 1% duty |
| MoCo | None |
| Autofocus | None |

**Expected:** Focused SUSTech image. Omega-K provides exact focusing for all target ranges.

### 4. `spotlight_omegak`

**Purpose:** Spotlight mode baseline with Omega-K processing.

| Parameter | Value |
|-----------|-------|
| Mode | Spotlight |
| IF Algorithm | `omega_k` |
| PRF | 2000 Hz |
| Scene center | [1000, 0, 0] m |
| Flight time | 0.5 s (1000 pulses) |

**Expected:** Higher azimuth resolution than stripmap due to continuous beam steering. Scene center must be set for spotlight steering geometry.

### 5. `scansar_csa`

**Purpose:** Scan-SAR mode with burst cycling across 3 sub-swaths, processed by CSA.

| Parameter | Value |
|-----------|-------|
| Mode | ScanSAR (scanmar) |
| IF Algorithm | `chirp_scaling` |
| n_subswaths | 3 |
| burst_length | 20 pulses |
| Flight time | 0.6 s (600 pulses, 10 burst cycles) |
| Swath range | 600-1600 m |

**Scene (dedicated):** 81 targets total:
- Sub-swath 0 (ground range ~700 m): 3 point targets at y = -5, 0, +5 m
- Sub-swath 1 (ground range ~1000 m): Full SUSTech pattern (93 targets)
- Sub-swath 2 (ground range ~1428 m): 3 point targets at y = -5, 0, +5 m

**Expected:** All sub-swaths produce focused imagery. Reduced azimuth resolution due to burst cycling.

---

## Group B: Waveform & Window Variants

These scenarios test alternative waveform types and window functions on the baseline stripmap/RDA configuration.

### 6. `stripmap_rda_fmcw`

**Purpose:** Validate FMCW (Frequency-Modulated Continuous Wave) dechirp processing.

| Parameter | Value |
|-----------|-------|
| Mode | Stripmap |
| IF Algorithm | `range_doppler` |
| Waveform type | FMCW |
| Ramp type | Up |
| Duty cycle | 10% |
| Bandwidth | 300 MHz |

**Expected:** FMCW dechirp-on-receive produces a focused image. Range processing differs from pulsed LFM (beat frequency extraction instead of matched filtering).

### 7. `stripmap_rda_hamming`

**Purpose:** Validate Hamming window effect on sidelobe reduction.

| Parameter | Value |
|-----------|-------|
| Mode | Stripmap |
| IF Algorithm | `range_doppler` |
| Waveform type | LFM |
| Window | Hamming |

**Expected:** Lower range sidelobes compared to rectangular window (stripmap_rda), at the cost of slightly wider mainlobe. Peak target response should still exceed noise floor.

---

## Group C: Perturbed Trajectory, MoCo Only

These scenarios add Dryden turbulence and navigation sensors, then apply motion compensation without autofocus. Validates MoCo algorithms in isolation.

### 8. `stripmap_rda_dryden_moco1`

**Purpose:** First-order (bulk) motion compensation on stripmap/RDA.

| Parameter | Value |
|-----------|-------|
| Mode | Stripmap |
| IF Algorithm | `range_doppler` |
| Perturbation | Dryden turbulence |
| Sensors | GPS + IMU |
| MoCo | `first_order` |
| Autofocus | None |

**Expected:** MoCo corrects bulk trajectory deviations. Image quality improves over uncompensated processing.

### 9. `stripmap_rda_dryden_moco2`

**Purpose:** Second-order (range-dependent) motion compensation.

| Parameter | Value |
|-----------|-------|
| Mode | Stripmap |
| IF Algorithm | `range_doppler` |
| Perturbation | Dryden turbulence |
| Sensors | GPS + IMU |
| MoCo | `second_order` |
| Autofocus | None |

**Expected:** Second-order MoCo provides range-dependent correction beyond bulk phase. May improve near/far-range targets compared to first-order.

### 10. `stripmap_csa_dryden_moco1`

**Purpose:** First-order MoCo combined with CSA image formation.

| Parameter | Value |
|-----------|-------|
| Mode | Stripmap |
| IF Algorithm | `chirp_scaling` |
| Perturbation | Dryden turbulence |
| Sensors | GPS + IMU |
| MoCo | `first_order` |

**Expected:** Validates MoCo→CSA pipeline compatibility.

### 11. `spotlight_omegak_dryden_moco1`

**Purpose:** First-order MoCo with spotlight mode and Omega-K.

| Parameter | Value |
|-----------|-------|
| Mode | Spotlight |
| IF Algorithm | `omega_k` |
| PRF | 2000 Hz |
| Scene center | [1000, 0, 0] m |
| Perturbation | Dryden turbulence |
| Sensors | GPS + IMU |
| MoCo | `first_order` |

**Expected:** Validates MoCo→Omega-K pipeline in spotlight geometry.

---

## Group D: MoCo + Autofocus

These scenarios combine motion compensation with each of the four autofocus algorithms. All use stripmap/RDA with Dryden perturbation, GPS+IMU sensors.

### 12. `stripmap_rda_dryden_moco1_pga`

**Purpose:** Phase Gradient Autofocus (PGA) after first-order MoCo.

| Parameter | Value |
|-----------|-------|
| MoCo | `first_order` |
| Autofocus | `pga` |

**Expected:** PGA estimates and corrects residual phase errors after MoCo. Iterative algorithm converges to improved focus.

### 13. `stripmap_rda_dryden_moco1_mda`

**Purpose:** Map Drift Autofocus (MDA) after first-order MoCo.

| Parameter | Value |
|-----------|-------|
| MoCo | `first_order` |
| Autofocus | `mda` |

**Expected:** MDA estimates quadratic phase error from sub-aperture correlation. Effective for correcting low-order phase errors.

### 14. `stripmap_rda_dryden_moco1_entropy`

**Purpose:** Minimum Entropy Autofocus after first-order MoCo.

| Parameter | Value |
|-----------|-------|
| MoCo | `first_order` |
| Autofocus | `min_entropy` |

**Expected:** Optimizes phase to minimize image entropy (maximize focus sharpness). Computationally more expensive but handles higher-order errors.

### 15. `stripmap_rda_dryden_moco1_ppp`

**Purpose:** Prominent Point Processing (PPP) autofocus after first-order MoCo.

| Parameter | Value |
|-----------|-------|
| MoCo | `first_order` |
| Autofocus | `ppp` |

**Expected:** PPP selects bright isolated targets and estimates phase from their defocusing. Works well when strong point scatterers exist (as in SUSTech pattern).

### 16. `stripmap_rda_dryden_moco2_pga`

**Purpose:** PGA after second-order MoCo.

| Parameter | Value |
|-----------|-------|
| MoCo | `second_order` |
| Autofocus | `pga` |

**Expected:** Second-order MoCo leaves smaller residual errors for PGA to correct. Tests the full MoCo2→PGA chain.

---

## Group E: Sensor Variants

These scenarios test different navigation sensor configurations under identical perturbation conditions. All use stripmap/RDA with Dryden turbulence and first-order MoCo.

### 17. `stripmap_rda_dryden_moco1_gps_only`

**Purpose:** MoCo with GPS navigation only (no IMU).

| Parameter | Value |
|-----------|-------|
| Sensors | GPS only (1.0 m RMS, 10 Hz) |
| MoCo | `first_order` |

**Expected:** GPS provides absolute position but at lower update rate. MoCo quality depends on interpolation between GPS fixes. No attitude correction without IMU.

### 18. `stripmap_rda_dryden_moco1_imu_only`

**Purpose:** MoCo with IMU navigation only (no GPS).

| Parameter | Value |
|-----------|-------|
| Sensors | IMU only (100 Hz) |
| MoCo | `first_order` |

**Expected:** IMU provides high-rate relative motion but drifts over time. Short aperture (0.5 s) limits drift impact. Position errors accumulate without GPS absolute reference.

### 19. `stripmap_rda_dryden_moco1_gps_outage`

**Purpose:** MoCo with GPS outage interval (GPS drops out from t=0.1 to t=0.3 s).

| Parameter | Value |
|-----------|-------|
| Sensors | GPS (with outage 0.1-0.3 s) + IMU |
| GPS outage | 0.1 s to 0.3 s (40% of aperture) |
| MoCo | `first_order` |

**Expected:** Navigation solution degrades during GPS outage, relying on IMU alone. MoCo quality may vary across azimuth. Tests sensor fusion robustness.

---

## Algorithm Compatibility Matrix

| IF Algorithm     | Stripmap | Spotlight | ScanSAR |
|------------------|----------|-----------|---------|
| `range_doppler`  | Yes      | No        | No      |
| `chirp_scaling`  | Yes      | No        | Yes     |
| `omega_k`        | Yes      | Yes       | No      |

## Test Assertions

Each scenario runs through 6 test functions:

1. **`test_load_and_build`** — Parameter set loads from JSON and builds simulation objects without error.
2. **`test_simulation_produces_echo`** — SimulationEngine produces non-empty, non-zero echo data.
3. **`test_pipeline_produces_image`** — Full processing pipeline (MoCo → IF → autofocus) produces a focused image.
4. **`test_target_detected`** — At least one pixel exceeds 3x the median noise floor (target is visible).
5. **`test_perturbed_trajectory_diverges`** — (Skipped for ideal cases) True trajectory differs from ideal by > 0.01 m.
6. **`test_moco_improves_image`** — (Skipped for non-MoCo cases) MoCo'd peak-to-noise ratio is at least 90% of uncompensated.

## File Structure

Each scenario directory contains 7-8 JSON files:

```
<scenario_name>/
  project.json      — Top-level project with $ref links
  scene.json        — Either $ref to ../_scene.json or inline targets
  radar.json        — Carrier freq, PRF, $ref to waveform + antenna
  waveform.json     — Waveform type, bandwidth, duty cycle, window
  antenna.json      — Antenna preset, beamwidths, gain
  sarmode.json      — SAR mode, look side, depression angle
  platform.json     — Velocity, altitude, heading, flight_time, perturbation, sensors
  processing.json   — Image formation, MoCo, autofocus algorithm selection
```

## Running the Tests

```bash
# All scenarios
python -m pytest tests/integration/ -v

# Single scenario
python -m pytest tests/integration/ -v -k stripmap_rda

# Only load/build (fast)
python -m pytest tests/integration/test_scenarios.py::test_load_and_build

# Only pipeline tests
python -m pytest tests/integration/test_scenarios.py::test_pipeline_produces_image
```
