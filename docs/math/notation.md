# Notation Reference

This page maps mathematical symbols used in the documentation to their corresponding code variables and modules in PySimSAR.

---

## Geometry & Radar Parameters

| Symbol | Description | Code Variable | Module |
|--------|-------------|---------------|--------|
| $f_c$ | Carrier frequency (Hz) | `carrier_freq` | `core/radar.py` |
| $\lambda$ | Wavelength (m), $\lambda = c / f_c$ | `wavelength` | `core/radar.py` |
| $c$ | Speed of light (m/s) | `C_LIGHT` | `core/radar.py` |
| $R$ | Slant range (m) | `slant_range` | `simulation/signal.py` |
| $R_0$ | Closest approach range (m) | `R0` | `algorithms/image_formation/*.py` |
| $R_g$ | Ground range (m) | `ground_range` | `algorithms/geocoding/slant_to_ground.py` |
| $v$, $V$ | Platform velocity (m/s) | `velocity`, `V` | `core/platform.py`, `algorithms/image_formation/*.py` |
| $h$ | Platform altitude (m) | `altitude` | `core/platform.py` |
| $\psi$ | Depression angle (rad) | `depression_angle` | `core/radar.py` |
| $\theta_{sq}$ | Squint angle (rad) | `squint_angle` | `core/radar.py` |
| $\theta_{az}$ | Azimuth look angle (rad) | `azimuth` | `simulation/antenna.py` |
| $\theta_{el}$ | Elevation look angle (rad) | `elevation` | `simulation/antenna.py` |
| $\eta$ | Slow time / azimuth time (s) | `time`, `t` | `simulation/engine.py` |
| $\tau$ | Fast time / range time (s) | `tau`, `t` | `waveforms/lfm.py` |
| $\mathbf{p}(\eta)$ | Platform position in ENU (m) | `platform_pos`, `pos` | `simulation/signal.py` |
| $\mathbf{p}_t$ | Target position in ENU (m) | `target_pos` | `simulation/signal.py` |

---

## Waveform Parameters

| Symbol | Description | Code Variable | Module |
|--------|-------------|---------------|--------|
| $B$ | Bandwidth (Hz) | `bandwidth` | `waveforms/base.py` |
| $K_r$ | Chirp rate (Hz/s), $K_r = B / T_p$ | `K` | `waveforms/lfm.py`, `waveforms/fmcw.py` |
| $T_p$ | Pulse duration (s) | `duration` | `waveforms/base.py` |
| $\delta$ | Duty cycle | `duty_cycle` | `waveforms/base.py` |
| $f_s$ | Range sampling rate (Hz) | `sample_rate` | `simulation/engine.py` |
| $\text{PRF}$ | Pulse repetition frequency (Hz) | `prf` | `waveforms/base.py` |
| $\text{PRI}$ | Pulse repetition interval (s), $1/\text{PRF}$ | `pri` | `core/radar.py` |
| $P_t$ | Transmit power (W) | `transmit_power` | `core/radar.py` |
| $L$ | System losses (dB) | `system_losses` | `core/radar.py` |
| $G_t$, $G_r$ | Transmit/receive antenna gain | `gain()` | `core/antenna.py` |
| $\sigma$ | Radar cross section (m$^2$) | `rcs`, `target_rcs` | `core/scene.py` |
| $f_b$ | FMCW beat frequency (Hz) | (computed) | `waveforms/fmcw.py` |

---

## Processing & Image Formation

| Symbol | Description | Code Variable | Module |
|--------|-------------|---------------|--------|
| $f_\eta$ | Doppler frequency (Hz) | `f_eta` | `algorithms/image_formation/*.py` |
| $f_\tau$ | Range frequency (Hz) | `f_tau`, `f_tau_blk` | `algorithms/image_formation/chirp_scaling.py` |
| $D(f_\eta)$ | Migration factor | `D_k`, `D_f_eta` | `algorithms/image_formation/*.py` |
| $\Delta R$ | Range cell migration (m) | `delta_r` | `algorithms/moco/first_order.py` |
| $K_a$ | Azimuth FM rate (Hz/s) | `K_a` | `algorithms/image_formation/*.py` |
| $H_{rc}$ | Range compression filter | `ref_fft` | `waveforms/lfm.py` |
| $H_{az}$ | Azimuth compression filter | `H_az` | `algorithms/image_formation/*.py` |
| $\Delta r$ | Range bin spacing (m), $c / (2 f_s)$ | `range_bin_spacing` | `algorithms/image_formation/*.py` |
| $R_{\text{ref}}$ | Reference range for CSA (m) | `R_ref` | `algorithms/image_formation/chirp_scaling.py` |
| $R_{\text{near}}$ | Near range from gate delay (m) | `near_range` | `algorithms/image_formation/*.py` |
| $\tau_{\text{gate}}$ | Range gate start delay (s) | `gate_delay` | `core/types.py` |

---

## Motion Compensation

| Symbol | Description | Code Variable | Module |
|--------|-------------|---------------|--------|
| $\Delta R(n)$ | Range error per pulse (m) | `delta_r` | `algorithms/moco/first_order.py` |
| $\phi_{\text{moco}}$ | MoCo phase correction (rad) | `phase_correction` | `algorithms/moco/first_order.py` |
| $\Delta\mathbf{p}$ | Position deviation (m) | `dp` | `algorithms/moco/second_order.py` |
| $\Delta p_\perp$ | Perpendicular deviation (m) | `dp_perp_sq` (squared) | `algorithms/moco/second_order.py` |
| $\Delta x_c$ | Cross-track deviation (m) | `dx_cross` | `algorithms/moco/second_order.py` |
| $\Delta z$ | Vertical deviation (m) | `dz` | `algorithms/moco/second_order.py` |
| $\mathbf{p}_{\text{ref}}$ | Reference track position (m) | `ref_pos` | `algorithms/moco/first_order.py` |
| $\mathbf{p}_{\text{sc}}$ | Scene centre (m) | `scene_center` | `algorithms/moco/first_order.py` |

---

## Autofocus

| Symbol | Description | Code Variable | Module |
|--------|-------------|---------------|--------|
| $\hat{\phi}'(m)$ | Estimated phase gradient (rad) | `avg_gradient` | `algorithms/autofocus/pga.py` |
| $\hat{\phi}(n)$ | Estimated phase error (rad) | `phase_error` | `algorithms/autofocus/*.py` |
| $S$ | Image sharpness (kurtosis) | `sharpness` | `algorithms/autofocus/pga.py` |
| $H$ | Image entropy | `_entropy_cost()` return | `algorithms/autofocus/min_entropy.py` |
| $\hat{f}_c$ | Doppler centroid estimate (Hz) | `fc` | `algorithms/autofocus/mda.py` |
| $N_d$ | Number of dominant scatterers | `n_dom` | `algorithms/autofocus/pga.py` |
| $\gamma$ | Contrast threshold | `contrast_threshold` | `algorithms/autofocus/ppp.py` |

---

## Polarimetry

| Symbol | Description | Code Variable | Module |
|--------|-------------|---------------|--------|
| $[S]$ | Scattering matrix | `s_hh`, `s_hv`, `s_vh`, `s_vv` | `algorithms/polarimetry/*.py` |
| $\mathbf{k}$ | Pauli target vector | `k1`, `k2`, `k3` | `algorithms/polarimetry/cloude_pottier.py` |
| $[T]$ | Coherency matrix ($3 \times 3$) | `T`, `t11`...`t33` | `algorithms/polarimetry/cloude_pottier.py` |
| $[C]$ | Covariance matrix ($3 \times 3$) | `c11`, `c22`, `c33`, `c13` | `algorithms/polarimetry/freeman_durden.py` |
| $a$, $b$, $c$ | Pauli components | `a`, `b`, `c` | `algorithms/polarimetry/pauli.py` |
| $P_s$ | Surface scattering power | `p_s` | `algorithms/polarimetry/freeman_durden.py` |
| $P_d$ | Double-bounce scattering power | `p_d` | `algorithms/polarimetry/freeman_durden.py` |
| $P_v$ | Volume scattering power | `p_v` | `algorithms/polarimetry/freeman_durden.py` |
| $P_h$ | Helix scattering power | `p_h` | `algorithms/polarimetry/yamaguchi.py` |
| $H$ | Entropy $\in [0, 1]$ | `entropy` | `algorithms/polarimetry/cloude_pottier.py` |
| $A$ | Anisotropy $\in [0, 1]$ | `anisotropy` | `algorithms/polarimetry/cloude_pottier.py` |
| $\bar{\alpha}$ | Mean alpha angle (rad) $\in [0, \pi/2]$ | `alpha` | `algorithms/polarimetry/cloude_pottier.py` |
| $\lambda_i$ | Eigenvalues of $[T]$ | `eigenvalues` | `algorithms/polarimetry/cloude_pottier.py` |
| $p_i$ | Pseudo-probabilities | `p` | `algorithms/polarimetry/cloude_pottier.py` |

---

## Phase Noise

| Symbol | Description | Code Variable | Module |
|--------|-------------|---------------|--------|
| $\mathcal{L}(f)$ | Phase noise PSD (dBc/Hz) | `psd` | `waveforms/phase_noise.py` |
| $h_{-3}$ | Flicker FM level | `flicker_fm_level` | `waveforms/phase_noise.py` |
| $h_{-2}$ | White FM level | `white_fm_level` | `waveforms/phase_noise.py` |
| $h_{-1}$ | Flicker PM level | `flicker_pm_level` | `waveforms/phase_noise.py` |
| $h_0$ | White PM floor | `white_floor` | `waveforms/phase_noise.py` |
| $\phi_{\text{PN}}$ | Phase noise realisation (rad) | `phase_noise` | `simulation/signal.py` |
| $\Delta\phi$ | Residual phase noise after decorrelation | `residual_pn` | `simulation/signal.py` |

---

## Constants

| Symbol | Value | Code Variable | Module |
|--------|-------|---------------|--------|
| $c$ | $299\,792\,458$ m/s | `C_LIGHT` | `core/radar.py` |
| $a$ | $6\,378\,137$ m (WGS84 semi-major) | `WGS84_A` | `core/coordinates.py` |
| $f$ | $1/298.257223563$ (WGS84 flattening) | `WGS84_F` | `core/coordinates.py` |
| $e^2$ | $2f - f^2$ (first eccentricity squared) | `WGS84_E2` | `core/coordinates.py` |
