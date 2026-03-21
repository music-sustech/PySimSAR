# Autofocus Algorithms

Autofocus algorithms estimate and correct residual phase errors that remain after motion compensation. PySimSAR implements four complementary approaches: Phase Gradient Autofocus (PGA), Map Drift Autofocus (MDA), Minimum Entropy Autofocus (MEA), and Prominent Point Processing (PPP).

All four share a common iterative structure: estimate phase error $\hat{\phi}(n)$, apply correction $\exp(-j\hat{\phi}(n))$ to each azimuth line, re-focus, and repeat until convergence ($\max|\hat{\phi}| < \epsilon$, default $\epsilon = 0.01$ rad).

---

## 1. Phase Gradient Autofocus (PGA)

**Source:** `algorithms/autofocus/pga.py`

PGA is a non-parametric autofocus method that makes no assumption about the functional form of the phase error. It estimates the phase gradient from dominant scatterers and integrates to recover the phase error.

### Algorithm Steps

**Step 1: Dominant scatterer selection.** For each range bin, compute the peak azimuth power $P_{\max}(r) = \max_n |I(n, r)|^2$. Select the $N_d$ range bins with the highest peak power (default: $N_d = N_r / 4$).

**Step 2: Circular shifting and windowing.** For each selected range bin $r_k$:

1. Find the azimuth peak index $n_{\text{peak}}$.
2. Circularly shift the column so the peak is centred: $g_k(n) = I\!\left((n - \text{shift}) \bmod N_{az},\; r_k\right)$.
3. Estimate the mainlobe half-width $w_{\text{ML}}$ as the distance from the peak to the $-6$ dB point.
4. Apply a rectangular window of width $4 w_{\text{ML}}$ (capped at `window_fraction` of $N_{az}$) centred on the peak.

**Step 3: Phase gradient estimation.** FFT each windowed column to the Doppler domain: $G_k(m) = \text{FFT}\{g_k(n)\}$. The phase gradient is estimated via the conjugate-product method:

$$
\boxed{\hat{\phi}'(m) = \arg\!\left\{\sum_k G_k(m) \, G_k^*(m-1) \, w_k(m)\right\}}
$$

where $w_k(m) = |G_k(m)| \cdot |G_k(m-1)|$ is the magnitude weighting.

**Centering bias removal.** Circular shifting by $s$ samples introduces a linear phase $\exp(-j 2\pi k s / N)$ in the Doppler domain. The conjugate product picks up a constant factor $\exp(-j 2\pi s / N)$, which must be removed to ensure gradients from scatterers at different azimuth positions add coherently:

$$
\hat{\phi}'_{\text{corrected}}(m) = \hat{\phi}'(m) \cdot \exp\!\left(+j \frac{2\pi s}{N_{az}}\right)
$$

**Step 4: Integration.** The phase error is recovered by cumulative summation of the gradient:

$$
\hat{\phi}(m) = \sum_{i=0}^{m} \hat{\phi}'(i) - \text{mean}
$$

The mean is subtracted since a constant phase offset is ambiguous.

### Sharpness Guard

PGA uses image sharpness (intensity kurtosis) as a quality metric:

$$
S = \frac{\sum_{n,r} |I(n,r)|^4}{\left(\sum_{n,r} |I(n,r)|^2\right)^2}
$$

If a correction degrades sharpness ($S_{\text{new}} < S_{\text{best}}$), the iteration is undone and the best image is returned. This prevents divergence on scenes where multi-target interference biases the gradient estimate.

---

## 2. Map Drift Autofocus (MDA)

**Source:** `algorithms/autofocus/mda.py`

MDA is a parametric autofocus method that models the phase error as a low-order polynomial. It estimates the Doppler centroid drift across sub-apertures and fits a polynomial to characterise defocus and drift.

### Doppler Centroid Estimation

For each sub-aperture $s$ (with ~50% overlap), the Doppler centroid is estimated via the conjugate-product (phase-difference) estimator:

$$
\hat{f}_c = \frac{\text{PRF}}{2\pi} \arg\!\left\{\sum_r \sum_n s(n+1, r) \, s^*(n, r)\right\}
$$

**Derivation.** The expected value of the conjugate product $\langle s(n+1) s^*(n) \rangle$ for a signal with Doppler centroid $f_c$ is proportional to $\exp(j 2\pi f_c / \text{PRF})$. Taking the argument and scaling by $\text{PRF}/(2\pi)$ recovers $f_c$.

### Polynomial Fit and Phase Error

The centroid values from all sub-apertures are fitted with a polynomial of order $p$ (default $p=2$, quadratic):

$$
\hat{f}_c(t) = \sum_{k=0}^{p} a_k \, t^k
$$

where $t$ is the normalised azimuth coordinate.

The phase error is obtained by integrating the instantaneous frequency offset:

$$
\hat{\phi}(n) = 2\pi \sum_{i=0}^{n} \frac{\hat{f}_c(i)}{\text{PRF}} - \text{mean}
$$

**Derivation.** The instantaneous frequency is related to the phase by $f(n) = \frac{1}{2\pi} \frac{d\phi}{dn}$. Discretising: $\phi(n) = 2\pi \sum_{i=0}^{n} f(i) / f_s$ where $f_s = \text{PRF}$.

### Limitations

MDA is effective for low-order (linear, quadratic) phase errors such as defocus and Doppler centroid drift. It cannot capture high-order or rapidly varying phase errors.

---

## 3. Minimum Entropy Autofocus (MEA)

**Source:** `algorithms/autofocus/min_entropy.py`

MEA optimises a parametric phase model by minimising the image entropy. Lower entropy corresponds to sharper focus. Unlike PGA, MEA works well on distributed scenes without dominant scatterers.

### Image Entropy

The entropy of the focused image is defined as:

$$
\boxed{H = -\sum_k p_k \ln p_k}
$$

where $p_k$ is the normalised power at pixel $k$:

$$
p_k = \frac{|I_k|^2}{\sum_j |I_j|^2}, \qquad p_k > 0
$$

### Polynomial Phase Model

The phase error is modelled as a polynomial (excluding orders 0 and 1, which represent ambiguous constant phase and image shift):

$$
\phi(t) = \sum_{m=2}^{M} a_m \, t^m, \qquad t \in [-1, 1]
$$

where $M$ is the polynomial order (default $M=4$) and $t$ is the normalised azimuth coordinate.

### Optimisation

The cost function is:

$$
\hat{\mathbf{a}} = \arg\min_{\mathbf{a}} \; H\!\left[\mathcal{F}\!\left\{s(\cdot, r) \cdot \exp\!\left(-j\sum_m a_m t^m\right)\right\}\right]
$$

averaged over all range bins. Azimuth compression is performed via FFT for computational efficiency.

PySimSAR uses **coordinate descent**: each coefficient $a_m$ is optimised independently via bounded scalar search (`scipy.optimize.minimize_scalar`, bounds $[-10, 10]$), with three full sweeps over all coefficients to capture interaction effects.

### Entropy Gradient (Theoretical)

The gradient of entropy with respect to coefficient $a_m$ is:

$$
\frac{\partial H}{\partial a_m} = -\sum_k \frac{\partial p_k}{\partial a_m} (1 + \ln p_k)
$$

While this analytic gradient could accelerate optimisation, the implementation uses derivative-free scalar search for robustness.

---

## 4. Prominent Point Processing (PPP)

**Source:** `algorithms/autofocus/ppp.py`

PPP identifies isolated prominent scatterers in the range-compressed domain, extracts their azimuth phase histories, and estimates the common phase error from the residual after removing the expected Doppler trend.

### Prominent Point Selection

1. Compute per-range-bin energy: $E(r) = \sum_n |s(n, r)|^2$.
2. Select bins by energy contrast: $E(r) > \gamma \cdot \text{median}(E)$, where $\gamma$ is the contrast threshold (default $\gamma = 3$).
3. Take the top $N_s$ bins (default $N_s = N_r / 4$).

### Phase History Extraction

For each selected range bin $r_k$:

1. Extract the complex azimuth history: $s_k(n) = s(n, r_k)$.
2. Unwrap the phase: $\phi_k(n) = \text{unwrap}(\arg\{s_k(n)\})$.
3. Remove the expected linear Doppler trend via least-squares line fit:
$$
\text{residual}_k(n) = \phi_k(n) - (a_k n + b_k)
$$
4. Remove the mean of the residual.

### Phase Error Estimation

The common phase error is the energy-weighted average of residual phases across all selected scatterers:

$$
\hat{\phi}(n) = \frac{\sum_k E(r_k) \cdot \text{residual}_k(n)}{\sum_k E(r_k)} - \text{mean}
$$

**Rationale.** For a point target at range $R_0$, the expected azimuth phase is a quadratic chirp $-4\pi R(\eta) / \lambda$, which after azimuth matched filtering appears as a linear Doppler ramp. Any deviation from this linear trend is due to motion-induced phase error (common to all range bins) or target-specific effects. Averaging over multiple prominent points suppresses target-specific effects and isolates the common phase error.

### Comparison with PGA

PPP operates in the range-compressed (pre-focus) domain, while PGA operates on the focused image. PPP removes a linear trend (expected Doppler ramp) explicitly, while PGA uses circular shifting and windowing to isolate the mainlobe. PGA is generally more robust because the adaptive windowing suppresses sidelobe and clutter interference, while PPP requires well-isolated prominent scatterers.

---

## Algorithm Selection Guide

| Algorithm | Phase Error Model | Best For | Limitations |
|-----------|-------------------|----------|-------------|
| **PGA** | Non-parametric | Any scene with point-like scatterers | May struggle on purely distributed scenes |
| **MDA** | Low-order polynomial | Linear/quadratic errors (defocus, drift) | Cannot capture high-order errors |
| **MEA** | Polynomial (order 2--4) | Distributed scenes, no dominant scatterers | Computationally expensive, local minima risk |
| **PPP** | Non-parametric | Scenes with isolated strong scatterers | Requires high contrast ratio |

---

## References

1. Wahl, D.E., Eichel, P.H., Ghiglia, D.C., and Jakowatz, C.V. (1994). "Phase Gradient Autofocus -- A Robust Tool for High Resolution SAR Phase Correction," *IEEE Trans. Aerosp. Electron. Syst.*, 30(3), 827--835.
2. Calloway, T.M. and Donohoe, G.W. (1994). "Subaperture Autofocus for Synthetic Aperture Radar," *IEEE Trans. Aerosp. Electron. Syst.*, 30(2), 617--621.
3. Kragh, T.J. (2006). "Minimum-Entropy Autofocus for Synthetic Aperture Radar," PhD thesis, Washington University in St. Louis.
4. Eichel, P.H. and Jakowatz, C.V. (1989). "Phase-gradient autofocus for SAR phase correction: explanation and demonstration of algorithmic steps," *Proc. SPIE*, 1101, 46--56.
5. Bamler, R. and Eineder, M. (1996). "ScanSAR processing using standard high precision SAR algorithms," *IEEE Trans. Geosci. Remote Sens.*, 34(1), 212--218.
