# Motion Compensation

This chapter describes the first- and second-order motion compensation (MoCo) algorithms in PySimSAR. MoCo corrects phase errors arising from deviations of the actual platform trajectory from the ideal (straight-line) track assumed by image formation algorithms.

---

## Overview

Platform motion errors introduce position-dependent phase errors that degrade SAR image focus. The motion error can be decomposed into:

- **Range-independent component** (first-order): phase error that is constant across all range bins for a given pulse. Dominated by the radial component of the trajectory deviation toward a reference point.
- **Range-dependent component** (second-order): residual phase error that varies across range bins, arising from the quadratic approximation of the slant-range perturbation.

---

## 1. First-Order Motion Compensation

**Source:** `algorithms/moco/first_order.py`

### Reference Track Estimation

A straight-line reference trajectory is fitted to the GPS-measured (and Savitzky-Golay smoothed) positions via least-squares:

$$
\hat{\mathbf{p}}_{\text{ref}}(n) = \mathbf{p}_0 + \mathbf{v}_{\text{fit}} \cdot t_n
$$

where $\mathbf{p}_0$ and $\mathbf{v}_{\text{fit}}$ are solved by minimizing $\sum_n \|\mathbf{p}_{\text{nav}}(n) - \hat{\mathbf{p}}_{\text{ref}}(n)\|^2$.

### Range Error Computation

For each pulse $n$, the slant-range deviation to a scene centre reference point $\mathbf{p}_{\text{sc}}$ is:

$$
\Delta R(n) = \|\mathbf{p}_{\text{sc}} - \mathbf{p}_{\text{nav}}(n)\| - \|\mathbf{p}_{\text{sc}} - \mathbf{p}_{\text{ref}}(n)\|
$$

where $\mathbf{p}_{\text{nav}}(n)$ is the (smoothed) measured position and $\mathbf{p}_{\text{ref}}(n)$ is the fitted reference position.

### Phase Correction

The first-order correction applies a bulk phase shift to the entire range line of each pulse:

$$
\boxed{\phi_{\text{moco},1}(n) = \frac{4\pi}{\lambda} \Delta R(n)}
$$

$$
s_{\text{corrected}}(\tau, n) = s(\tau, n) \cdot \exp\!\left(+j \, \phi_{\text{moco},1}(n)\right)
$$

**Derivation.** The echo phase from a target at range $R$ is $\phi = -4\pi f_c R / c = -4\pi R / \lambda$. A perturbation $\Delta R$ in the platform position changes the round-trip path by $2\Delta R$ (one-way deviation appears twice), producing a phase error of $-4\pi \Delta R / \lambda$. The correction is the negative of this error: $+4\pi \Delta R / \lambda$.

### Scene Centre Estimation

If no scene centre is provided, it is estimated from the reference trajectory at mid-aperture. The scene centre is placed on the ground ($z = 0$) in the cross-track direction at a ground range equal to the platform altitude:

$$
\mathbf{p}_{\text{sc}} = \mathbf{p}_{\text{mid}} + R_g \cdot \hat{\mathbf{c}} \big|_{z=0}, \qquad R_g = \max(h, 1000\text{ m})
$$

where $\hat{\mathbf{c}}$ is the cross-track unit vector (right of the velocity direction for right-looking radar).

---

## 2. Second-Order Motion Compensation

**Source:** `algorithms/moco/second_order.py`

### Approach

Second-order MoCo first applies the full first-order correction, then applies a range-dependent residual correction. The residual arises because the first-order correction is exact only at the scene centre range $R_{\text{ref}}$ and introduces a quadratic error at other ranges.

### Position Deviation Decomposition

The position deviation $\Delta\mathbf{p}(n) = \mathbf{p}_{\text{nav}}(n) - \mathbf{p}_{\text{ref}}(n)$ is decomposed into:

- **Cross-track component**: $\Delta x_c(n) = \Delta\mathbf{p}(n) \cdot \hat{\mathbf{c}}$
- **Vertical component**: $\Delta z(n) = \Delta p_z(n)$

The perpendicular deviation magnitude squared is:

$$
\Delta p_\perp^2(n) = \Delta x_c^2(n) + \Delta z^2(n)
$$

### Residual Range Error

The second-order (range-dependent) residual range error at pulse $n$ and range bin corresponding to slant range $R$ is:

$$
\boxed{\Delta R_{\text{res}}(n, R) = \Delta p_\perp^2(n) \cdot \left(\frac{1}{2R} - \frac{1}{2R_{\text{ref}}(n)}\right)}
$$

where $R_{\text{ref}}(n) = \|\mathbf{p}_{\text{sc}} - \mathbf{p}_{\text{ref}}(n)\|$ is the reference slant range for pulse $n$.

**Derivation.** Consider a target at range $R$ and the platform displaced by $\Delta\mathbf{p}$ from the reference position. The perturbed range is:

$$
R' = \|\mathbf{p}_t - (\mathbf{p}_{\text{ref}} + \Delta\mathbf{p})\|
$$

Expanding to second order in $\Delta\mathbf{p}$ (the first-order term was already corrected):

$$
R' \approx R - \hat{\mathbf{r}} \cdot \Delta\mathbf{p} + \frac{\Delta p_\perp^2}{2R}
$$

The first-order MoCo corrected the radial term $\hat{\mathbf{r}} \cdot \Delta\mathbf{p}$ at the reference range. The residual at range $R$ is the difference of the quadratic terms:

$$
\Delta R_{\text{res}} = \frac{\Delta p_\perp^2}{2R} - \frac{\Delta p_\perp^2}{2R_{\text{ref}}} = \Delta p_\perp^2 \left(\frac{1}{2R} - \frac{1}{2R_{\text{ref}}}\right)
$$

### Phase Correction

The second-order phase correction is applied per range bin:

$$
\phi_{\text{moco},2}(n, R) = \frac{4\pi}{\lambda} \Delta R_{\text{res}}(n, R)
$$

$$
s_{\text{corrected}}(\tau, n) = s_{1\text{st}}(\tau, n) \cdot \exp\!\left(+j \, \phi_{\text{moco},2}(n, R(\tau))\right)
$$

where $s_{1\text{st}}$ is the output of first-order MoCo and $R(\tau)$ maps the fast-time sample to slant range.

---

## Phase Error Model from Trajectory Deviations

The total phase error at pulse $n$ and range $R$ is:

$$
\phi_{\text{error}}(n, R) = -\frac{4\pi}{\lambda}\left[\Delta R_{\text{radial}}(n) + \frac{\Delta p_\perp^2(n)}{2R}\right]
$$

After first-order correction (which removes $\Delta R_{\text{radial}}$ at $R_{\text{ref}}$), the residual is purely range-dependent. For a swath of width $\Delta R_{\text{swath}}$, the maximum uncorrected second-order phase error scales as:

$$
|\phi_{\text{res,max}}| \approx \frac{4\pi}{\lambda} \cdot \frac{\Delta p_{\perp,\max}^2 \cdot \Delta R_{\text{swath}}}{2 R_{\text{ref}}^2}
$$

This sets the requirement for second-order MoCo: when $|\phi_{\text{res,max}}| > \pi/4$ (quarter-wavelength criterion), second-order correction is needed.

---

## References

1. Moreira, A. and Huang, Y. (1994). "Airborne SAR processing of highly squinted data using a chirp scaling approach with integrated motion compensation," *IEEE Trans. Geosci. Remote Sens.*, 32(5), 1029--1040.
2. Fornaro, G. (1999). "Trajectory deviations in airborne SAR: Analysis and compensation," *IEEE Trans. Aerosp. Electron. Syst.*, 35(3), 997--1009.
