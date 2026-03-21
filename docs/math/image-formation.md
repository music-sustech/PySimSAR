# Image Formation Algorithms

This chapter derives the key equations for the three SAR image formation algorithms implemented in PySimSAR: Range-Doppler (RDA), Chirp Scaling (CSA), and Omega-K.

All three share the same core pipeline: range compression, RCMC, and azimuth compression. They differ in how RCMC is performed.

---

## Common Definitions

Throughout this chapter:

- $f_\tau$ : range (fast-time) frequency
- $f_\eta$ : azimuth (Doppler) frequency
- $V$ : effective platform velocity (mean speed from trajectory)
- $\lambda = c / f_c$ : radar wavelength
- $R_0$ : closest approach slant range for a given range bin
- $\text{PRF}$ : pulse repetition frequency

The **range-Doppler domain** is reached by azimuth FFT of the range-compressed data. The Doppler frequency axis is:

$$
f_\eta(k) = \text{fftfreq}(N_{az},\; 1/\text{PRF}), \qquad k = 0, \ldots, N_{az}-1
$$

The **migration factor** that appears in all three algorithms is:

$$
D(f_\eta) = \sqrt{1 - \left(\frac{\lambda f_\eta}{2V}\right)^2}
$$

This factor arises from the exact 2D transfer function of the point target response. For small squint angles, $D \approx 1$.

---

## 1. Range-Doppler Algorithm (RDA)

**Source:** `algorithms/image_formation/range_doppler.py`

The RDA is the simplest frequency-domain SAR processor, operating in the range-Doppler (range-time, Doppler-frequency) domain.

### Step 1: Range Compression

Apply the matched filter in the range frequency domain for each azimuth line:

$$
s_{rc}(\tau, \eta) = \mathcal{F}_\tau^{-1}\!\left\{S_{rx}(f_\tau, \eta) \cdot H_{rc}(f_\tau)\right\}
$$

where $H_{rc}(f_\tau) = S_{tx}^*(f_\tau)$ is the conjugate of the transmit spectrum. This is delegated to the waveform's `range_compress()` method.

### Step 2: Azimuth FFT

Transform to the range-Doppler domain:

$$
S_{rc}(\tau, f_\eta) = \mathcal{F}_\eta\!\left\{s_{rc}(\tau, \eta)\right\}
$$

### Step 3: Range Cell Migration Correction (RCMC)

In the range-Doppler domain, a point target at range $R_0$ occupies range bin

$$
R(f_\eta) = \frac{R_0}{D(f_\eta)}
$$

The range migration relative to the zero-Doppler position is:

$$
\Delta R(f_\eta) = R_0 \left(\frac{1}{D(f_\eta)} - 1\right)
$$

**Implementation.** For each Doppler line $k$, the source (migrated) position of each range bin $b$ at absolute range $R_{\text{abs}} = R_{\text{near}} + b \cdot \Delta r$ is:

$$
b_{\text{src}}(k) = \frac{R_{\text{abs}}}{D(f_\eta[k]) \cdot \Delta r} - \frac{R_{\text{near}}}{\Delta r}
$$

where $\Delta r = c / (2 f_s)$ is the range bin spacing and $R_{\text{near}}$ is the near range from the gate delay. Sinc interpolation (order 8) maps data from the migrated positions back to the uniform range grid.

### Step 4: Azimuth Compression

After RCMC, apply an azimuth matched filter for each range bin. The azimuth FM rate is:

$$
K_a = -\frac{2V^2}{\lambda R_0}
$$

The azimuth matched filter in the Doppler domain is:

$$
H_{az}(f_\eta) = \exp\!\left(j\pi \frac{f_\eta^2}{K_a}\right)
$$

**Derivation.** The azimuth phase history of a point target at range $R_0$ is $\phi(\eta) = -4\pi R(\eta) / \lambda$. Using $R(\eta) \approx R_0 + v^2 \eta^2 / (2R_0)$ (parabolic approximation), the azimuth signal is a chirp with rate $K_a = -2V^2 / (\lambda R_0)$. The matched filter is the conjugate of this chirp's spectrum: $H_{az} = \exp(j\pi f_\eta^2 / K_a)$.

### Step 5: Azimuth IFFT

$$
s_{\text{focused}}(\tau, \eta) = \mathcal{F}_\eta^{-1}\!\left\{S_{rc}(\tau, f_\eta) \cdot H_{az}(f_\eta)\right\}
$$

The output pixel spacings are:

$$
\Delta x_r = \frac{c}{2 f_s}, \qquad \Delta x_{az} = \frac{V}{\text{PRF}}
$$

---

## 2. Chirp Scaling Algorithm (CSA)

**Source:** `algorithms/image_formation/chirp_scaling.py`

The CSA avoids per-bin interpolation-based RCMC by performing a **bulk RCMC** via phase multiplication in the 2D frequency domain, followed by a small **residual RCMC** correction.

### Step 1: Range Compression

Identical to RDA (waveform matched filter).

### Step 2: Azimuth FFT

Transform to range-Doppler domain.

### Step 3: Bulk RCMC at Reference Range

The range swath is divided into blocks (controlled by `n_iterations`). For each block, a reference range $R_{\text{ref}}$ is chosen at the block centre. In the 2D frequency domain $(f_\tau, f_\eta)$, the bulk RCMC phase function is:

$$
\phi_{\text{bulk}}(f_\tau, f_\eta) = \frac{4\pi R_{\text{ref}}}{c} \cdot a(f_\eta) \cdot f_\tau
$$

where the migration coefficient is:

$$
a(f_\eta) = \frac{1}{D(f_\eta)} - 1
$$

**Derivation.** In the 2D frequency domain, the range migration at $R_{\text{ref}}$ manifests as a linear phase ramp in $f_\tau$: $\exp(-j 4\pi R_{\text{ref}} a(f_\eta) f_\tau / c)$. The bulk correction multiplies by the conjugate: $\exp(+j 4\pi R_{\text{ref}} a(f_\eta) f_\tau / c)$.

The correction is applied per Doppler line $k$:

$$
S_{\text{bulk}}(f_\tau, k) = S_{rd}(f_\tau, k) \cdot \exp\!\left(j \frac{4\pi R_{\text{ref}} \cdot a_k \cdot f_\tau}{c}\right)
$$

### Step 4: Residual RCMC

After bulk correction at $R_{\text{ref}}$, a target at range $R_0 \neq R_{\text{ref}}$ retains a residual migration:

$$
\Delta R_{\text{res}}(f_\eta) = (R_0 - R_{\text{ref}}) \cdot a(f_\eta)
$$

This is corrected via sinc interpolation in the range-Doppler domain. The source positions are:

$$
b_{\text{src}}(k) = \frac{R_{\text{abs}}}{D(f_\eta[k]) \cdot \Delta r} - \frac{R_{\text{ref}}}{\Delta r} \cdot a_k - \frac{R_{\text{near}}}{\Delta r}
$$

### Step 5: Azimuth Compression

Same as RDA: per-range-bin matched filter $H_{az}(f_\eta) = \exp(j\pi f_\eta^2 / K_a)$ with $K_a = -2V^2 / (\lambda R_0)$.

### Step 6: Azimuth IFFT

Identical to RDA.

### Multi-Block Processing

When `n_iterations > 1`, the range swath is partitioned into blocks. Each block uses a local $R_{\text{ref}}$ at its centre, reducing the maximum residual RCMC error from $|R_0 - R_{\text{ref}}| \cdot a_{\max}$ (full swath) to $|\Delta R_{\text{block}}/2| \cdot a_{\max}$. This is important for wide-swath or high-squint geometries.

---

## 3. Omega-K Algorithm

**Source:** `algorithms/image_formation/omega_k.py`

The Omega-K algorithm uses the **exact** wavenumber-domain migration factor for RCMC, making it suitable for wide-aperture modes (spotlight) where the narrowband Doppler approximation breaks down.

### Wavenumber Domain Analysis

The 2D SAR signal can be expressed in the wavenumber domain $(K_x, K_R)$ where:

- $K_x = 2\pi f_\eta / V$ is the along-track wavenumber
- $K_R = 4\pi (f_c + f_\tau) / c$ is the range wavenumber

The point-target phase in the wavenumber domain is:

$$
\Phi(K_x, K_R) = -R_0 \sqrt{K_R^2 - K_x^2}
$$

The along-track wavenumber $K_Y$ is:

$$
K_Y = \sqrt{K_R^2 - K_x^2}
$$

This is equivalent to the migration factor $D(f_\eta)$ relationship. Converting to the frequency-domain variables used in the implementation:

$$
D(f_\eta) = \sqrt{1 - \left(\frac{\lambda f_\eta}{2V}\right)^2}
$$

### Implementation

The Omega-K algorithm in PySimSAR follows the same processing pipeline as RDA, using the exact $D(f_\eta)$ factor for RCMC:

**Step 1: Range Compression** -- matched filter via waveform.

**Step 2: Azimuth FFT** to range-Doppler domain.

**Step 3: RCMC** using the exact wavenumber migration. For each Doppler line $k$, the migrated source position of range bin $b$ is:

$$
b_{\text{src}}(k) = \frac{R_{\text{near}} + b \cdot \Delta r}{D(f_\eta[k]) \cdot \Delta r} - \frac{R_{\text{near}}}{\Delta r}
$$

This is identical in form to the RDA RCMC but uses the full $D(f_\eta)$ without approximation. Sinc interpolation (order 8) performs the resampling.

**Step 4: Azimuth Compression** -- per-range-bin matched filter:

$$
H_{az}(f_\eta) = \exp\!\left(j\pi \frac{f_\eta^2}{K_a}\right), \qquad K_a = -\frac{2V^2}{\lambda R_0}
$$

**Step 5: Azimuth IFFT** to focused image.

### Spotlight Mode Support

The Omega-K algorithm supports spotlight mode because the exact $D(f_\eta)$ accommodates the wider Doppler bandwidth that results from beam steering. In spotlight mode, the Doppler bandwidth exceeds the PRF (after deramping), and the narrowband approximation $D \approx 1 - \lambda^2 f_\eta^2 / (8V^2)$ introduces non-negligible errors.

---

## Algorithm Comparison

| Property | RDA | CSA | Omega-K |
|----------|-----|-----|---------|
| **RCMC method** | Sinc interpolation | Bulk phase + residual interp | Sinc interpolation (exact $D$) |
| **Supported modes** | Stripmap | Stripmap, ScanSAR | Stripmap, Spotlight |
| **Computational cost** | Low | Medium | Medium |
| **Range-dependent accuracy** | Exact per-bin | Block-level + residual | Exact per-bin |
| **Wide Doppler bandwidth** | Limited | Limited | Full support |

---

## References

1. Cumming, I.G. and Wong, F.H. (2005). *Digital Processing of Synthetic Aperture Radar Data*. Artech House, Ch. 6 (RDA), Ch. 7 (CSA), Ch. 9 (Omega-K).
2. Raney, R.K., Runge, H., Bamler, R., Cumming, I.G., and Wong, F.H. (1994). "Precision SAR Processing Using Chirp Scaling," *IEEE Trans. Geosci. Remote Sens.*, 32(4), 786--799.
3. Cafforio, C., Prati, C., and Rocca, F. (1991). "SAR data focusing using seismic migration techniques," *IEEE Trans. Aerosp. Electron. Syst.*, 27(2), 194--207.
