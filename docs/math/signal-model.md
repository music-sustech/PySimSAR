# Signal Model & Waveforms

This chapter describes the mathematical foundation of the PySimSAR echo signal simulator, covering the SAR geometry, waveform generation, received echo model, and phase noise.

---

## 1. SAR Geometry & Coordinate System

PySimSAR uses an **East-North-Up (ENU)** local Cartesian coordinate frame. The platform position at slow time $\eta$ is $\mathbf{p}(\eta) = [x_p, y_p, z_p]^T$ and the target position is $\mathbf{p}_t = [x_t, y_t, z_t]^T$, both in metres.

The **slant range** from platform to target is

$$
R(\eta) = \|\mathbf{p}_t - \mathbf{p}(\eta)\| = \sqrt{(x_t - x_p)^2 + (y_t - y_p)^2 + (z_t - z_p)^2}
$$

which is computed directly in three dimensions without flat-earth simplification (see `compute_range()` in `simulation/signal.py`).

The **depression angle** $\psi$ relates altitude $h = z_p$ and ground range $R_g$:

$$
\psi = \arctan\!\left(\frac{h}{R_g}\right), \qquad R_g = \sqrt{(x_t - x_p)^2 + (y_t - y_p)^2}
$$

Look angles are computed in a velocity-aligned local frame. The **along-track** unit vector is the horizontal projection of the velocity vector, the **cross-track** vector is $\hat{x} \times \hat{z}$ (pointing right of the flight track for right-looking), and the **azimuth angle** and **elevation angle** of a target are

$$
\theta_{az} = \arctan\!\left(\frac{\ell_{\text{along}}}{\ell_{\text{cross}}}\right), \qquad
\theta_{el} = \arctan\!\left(\frac{\ell_{\text{up}}}{\sqrt{\ell_{\text{along}}^2 + \ell_{\text{cross}}^2}}\right)
$$

where $\ell_{\text{along}}, \ell_{\text{cross}}, \ell_{\text{up}}$ are the projections of the line-of-sight vector onto the local frame axes.

---

## 2. Point Target Range Equation

For a platform moving along a straight track at constant velocity $v$ (the nominal stripmap case), the instantaneous slant range to a stationary target at closest approach range $R_0$ and zero-Doppler time $\eta_c$ is

$$
R(\eta) = \sqrt{R_0^2 + v^2(\eta - \eta_c)^2}
$$

**Derivation.** Place the coordinate origin at the target's ground position. The platform travels along the $y$-axis at speed $v$, so its position at slow time $\eta$ is $\mathbf{p}(\eta) = [x_0, v(\eta - \eta_c), h]$ where $x_0$ is the cross-track offset. At closest approach ($\eta = \eta_c$), the along-track component vanishes and $R_0 = \sqrt{x_0^2 + h^2}$. Substituting:

$$
R(\eta) = \sqrt{x_0^2 + h^2 + v^2(\eta - \eta_c)^2} = \sqrt{R_0^2 + v^2(\eta - \eta_c)^2}
$$

The **round-trip delay** is

$$
\tau_d(\eta) = \frac{2 R(\eta)}{c}
$$

where $c = 299\,792\,458$ m/s is the speed of light (defined as `C_LIGHT` in `core/radar.py`).

---

## 3. LFM (Chirp) Waveform

### Transmit Signal

The baseband Linear Frequency Modulated (LFM) chirp signal is (from `LFMWaveform.generate()`):

$$
s_{tx}(\tau) = \operatorname{rect}\!\left(\frac{\tau}{T_p}\right) \exp\!\left(j\pi K_r \tau^2\right)
$$

where:

- $T_p = \delta / \text{PRF}$ is the pulse duration ($\delta$ is the duty cycle),
- $K_r = B / T_p$ is the chirp rate (Hz/s),
- $B$ is the waveform bandwidth.

The time-bandwidth product $B T_p$ determines the range compression gain.

### Range Compression (Matched Filtering)

Range compression is performed in the frequency domain. The matched filter is the conjugate of the transmit spectrum:

$$
H_{rc}(f_\tau) = S_{tx}^*(f_\tau)
$$

The range-compressed output for a single point target at delay $\tau_0$ is:

$$
s_{rc}(\tau) = \mathcal{F}^{-1}\!\left\{S_{rx}(f_\tau) \cdot S_{tx}^*(f_\tau)\right\}
$$

**Intermediate steps.** The spectrum of the LFM chirp is approximately:

$$
S_{tx}(f_\tau) \approx \frac{1}{\sqrt{K_r}} \operatorname{rect}\!\left(\frac{f_\tau}{B}\right) \exp\!\left(-j\frac{\pi f_\tau^2}{K_r}\right)
$$

The received echo from a point at range $R$ has spectrum $S_{rx}(f_\tau) = S_{tx}(f_\tau) \exp(-j 2\pi f_\tau \cdot 2R/c)$. Multiplying by the matched filter:

$$
S_{rx} \cdot S_{tx}^* = \frac{1}{K_r} \operatorname{rect}\!\left(\frac{f_\tau}{B}\right) \exp\!\left(-j 2\pi f_\tau \frac{2R}{c}\right)
$$

Inverse Fourier transform yields a sinc impulse at delay $2R/c$ with mainlobe width $\Delta\tau = 1/B$, giving a range resolution of

$$
\delta_r = \frac{c}{2B}
$$

In the implementation (`LFMWaveform.range_compress()`), an optional window function is applied to $H_{rc}$ before the inverse FFT for sidelobe control at the cost of a slight resolution loss.

---

## 4. FMCW Waveform

The Frequency Modulated Continuous Wave (FMCW) waveform is generated identically to the LFM chirp in baseband form (see `FMCWWaveform.generate()`):

$$
s_{tx}(\tau) = \exp\!\left(j\pi K_r \tau^2\right), \qquad K_r = \frac{B}{T_{\text{ramp}}}
$$

The `FMCWWaveform` supports three ramp types:

| Ramp Type | Signal |
|-----------|--------|
| **Up** | $\exp(+j\pi K_r \tau^2)$ |
| **Down** | $\exp(-j\pi K_r \tau^2)$ |
| **Triangle** | Up-ramp for $\tau < T/2$, down-ramp for $\tau \geq T/2$ (doubled chirp rate $K_r = 2B/T$) |

### Dechirp (Stretch) Processing

In classical FMCW operation, the received signal is mixed with the transmit signal. For a target at range $R$, the dechirp operation produces a beat signal at constant frequency:

$$
f_b = K_r \cdot \frac{2R}{c}
$$

In PySimSAR's implementation, both LFM and FMCW use the same frequency-domain matched filtering approach for range compression (`range_compress()` applies $S_{tx}^*(f_\tau) \cdot S_{rx}(f_\tau)$ via FFT), which correctly handles echoes at arbitrary delays regardless of the duty cycle.

---

## 5. Received Echo Model

The complete echo signal from a single point target at position $\mathbf{p}_t$ with radar cross section $\sigma$ is assembled in `compute_target_echo()`:

$$
s_{rx}(\tau, \eta) = A(R) \cdot \sqrt{\sigma} \cdot \sqrt{G^2(\theta_{az}, \theta_{el})} \cdot s_{tx}\!\left(\tau - \frac{2R(\eta)}{c} + \tau_{\text{gate}}\right) \cdot \exp\!\left(-j\frac{4\pi f_c R(\eta)}{c}\right) \cdot \exp\!\left(j\phi_{\text{Doppler}}\right)
$$

where:

- $A(R)$ is the path loss amplitude factor (Section 6),
- $G^2(\theta_{az}, \theta_{el})$ is the two-way antenna gain pattern (linear),
- $\tau_{\text{gate}}$ is the range gate start delay,
- $f_c$ is the carrier frequency,
- $\phi_{\text{Doppler}}$ accounts for target motion.

### Doppler Phase from Target Motion

For a moving target with velocity $\mathbf{v}_t$, the additional Doppler phase is (from `compute_doppler_phase()`):

$$
\phi_{\text{Doppler}}(\eta) = -\frac{4\pi v_r \eta}{\lambda}
$$

where $v_r = \mathbf{v}_t \cdot \hat{\mathbf{r}}$ is the radial velocity (projection of target velocity onto the unit range vector $\hat{\mathbf{r}}$) and $\lambda = c / f_c$.

### Echo Phase

The total echo phase is the sum of the range-dependent phase and the Doppler phase:

$$
\phi_{\text{total}}(\eta) = -\frac{4\pi f_c R(\eta)}{c} + \phi_{\text{Doppler}}(\eta)
$$

### Multi-Target Superposition

The total received signal is a coherent sum over all targets:

$$
s(\tau, \eta) = \sum_{k=1}^{N_t} s_{rx,k}(\tau, \eta) + n(\tau, \eta)
$$

where $n(\tau, \eta)$ is complex Gaussian receiver noise with power $\sigma_n^2 = k_B T_s B_n$ (implemented in `SimulationEngine._generate_receiver_noise()`).

---

## 6. Radar Range Equation / Path Loss

The received power from a point target with RCS $\sigma$ is given by the radar range equation:

$$
P_r = \frac{P_t G_t G_r \lambda^2 \sigma}{(4\pi)^3 R^4 L}
$$

where $P_t$ is transmit power, $G_t G_r$ is the antenna gain product, $\lambda$ is wavelength, $R$ is slant range, and $L$ is system losses.

In the implementation (`compute_path_loss()`), the amplitude scaling factor (excluding RCS and antenna gain) is:

$$
A(R) = \sqrt{\frac{P_t \cdot G_{rx} \cdot \lambda^2}{(4\pi)^3 R^4 \cdot L}}
$$

The full echo amplitude including RCS and two-way gain becomes:

$$
A_{\text{total}} = A(R) \cdot \sqrt{\sigma} \cdot \sqrt{G^2_{\text{two-way}}}
$$

The two-way antenna gain is computed in `compute_two_way_gain()` as:

$$
G^2_{\text{two-way}} = 10^{2 G_{\text{dB}}(\Delta\theta_{az}, \Delta\theta_{el}) / 10}
$$

where $G_{\text{dB}}$ is the one-way gain pattern evaluated at the angular offset from the beam steering direction.

---

## 7. Phase Noise Model

Oscillator phase noise is modelled as a composite power spectral density (PSD) with four standard noise processes (from `CompositePSDPhaseNoise`):

$$
\mathcal{L}(f) = \frac{h_{-3}}{f^3} + \frac{h_{-2}}{f^2} + \frac{h_{-1}}{f} + h_0
$$

where:

| Component | Slope | Parameter | Default (dBc/Hz) |
|-----------|-------|-----------|-------------------|
| Flicker FM | $1/f^3$ | `flicker_fm_level` | $-80$ |
| White FM | $1/f^2$ | `white_fm_level` | $-100$ |
| Flicker PM | $1/f$ | `flicker_pm_level` | $-120$ |
| White PM | $f^0$ | `white_floor` | $-150$ |

Each level $h_k$ is converted from dBc/Hz: $h_k = 10^{L_k / 10}$ where $L_k$ is the level in dBc/Hz.

### Noise Generation

Phase noise samples are generated via spectral shaping:

1. Compute the one-sided PSD $\mathcal{L}(f_k)$ at each FFT frequency bin $f_k$.
2. Generate white complex Gaussian noise $W(f_k) \sim \mathcal{CN}(0, 1)$.
3. Shape: $\Phi(f_k) = \sqrt{\mathcal{L}(f_k) \cdot f_s / 2} \cdot W(f_k)$
4. Inverse FFT to time domain: $\phi(n) = \text{IRFFT}[\Phi(f_k)]$

### Range Decorrelation

Phase noise causes range-dependent degradation. For a target at round-trip delay $\tau_d$ (in samples), the residual phase noise after dechirp/compression is (from `compute_phase_noise_decorrelation()`):

$$
\Delta\phi(n) = \phi(n) - \phi(n - \tau_d)
$$

Close-range targets ($\tau_d \to 0$): noise samples are highly correlated, so $\Delta\phi \approx 0$ (noise cancels). Far-range targets ($\tau_d$ large): noise decorrelates, elevating the noise floor.

### Slow-Time Phase Noise

In `SimulationEngine`, phase noise is generated at the PRF rate (one scalar per pulse) rather than at the fast-time sample rate. This correctly captures the low-offset-frequency noise (Hz to kHz offsets) that dominates the composite PSD. The per-pulse phase noise is applied as a multiplicative phase term:

$$
s_{\text{corrupted}}(\tau, \eta_n) = s(\tau, \eta_n) \cdot \exp\!\left(j\phi_{\text{PN}}(\eta_n)\right)
$$

---

## References

1. Cumming, I.G. and Wong, F.H. (2005). *Digital Processing of Synthetic Aperture Radar Data: Algorithms and Implementation*. Artech House, Ch. 2--4.
2. Richards, M.A. (2014). *Fundamentals of Radar Signal Processing*, 2nd ed. McGraw-Hill.
3. Stove, A.G. (1992). "Linear FMCW radar techniques," *IEE Proceedings F*, 139(5), 343--350.
4. Skolnik, M.I. (2008). *Radar Handbook*, 3rd ed. McGraw-Hill, Ch. 1--2.
