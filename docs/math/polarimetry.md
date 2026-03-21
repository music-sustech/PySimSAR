# Polarimetric Decompositions

This chapter describes the polarimetric decomposition algorithms in PySimSAR: Pauli, Freeman-Durden, Yamaguchi, and Cloude-Pottier.

---

## Preliminaries

### Scattering Matrix

A fully polarimetric SAR measures the $2 \times 2$ complex scattering matrix:

$$
[S] = \begin{bmatrix} S_{HH} & S_{HV} \\ S_{VH} & S_{VV} \end{bmatrix}
$$

where $S_{XY}$ is the complex scattering amplitude for transmit polarisation $Y$ and receive polarisation $X$. For a reciprocal medium (monostatic radar), $S_{HV} = S_{VH}$.

### Pauli Target Vector

The Pauli basis target vector is formed as:

$$
\mathbf{k} = \frac{1}{\sqrt{2}} \begin{bmatrix} S_{HH} + S_{VV} \\ S_{HH} - S_{VV} \\ S_{HV} + S_{VH} \end{bmatrix}
$$

### Coherency Matrix

The $3 \times 3$ coherency matrix is the outer product of the Pauli vector, spatially averaged:

$$
[T] = \langle \mathbf{k} \, \mathbf{k}^{*T} \rangle = \begin{bmatrix}
T_{11} & T_{12} & T_{13} \\
T_{12}^* & T_{22} & T_{23} \\
T_{13}^* & T_{23}^* & T_{33}
\end{bmatrix}
$$

where $\langle \cdot \rangle$ denotes spatial (boxcar) averaging. Without averaging, single-pixel coherency matrices have rank 1.

### Covariance Matrix

The $3 \times 3$ covariance matrix is formed from the lexicographic target vector $\mathbf{k}_L = [S_{HH}, \sqrt{2} S_{HV}, S_{VV}]^T$:

$$
[C] = \langle \mathbf{k}_L \, \mathbf{k}_L^{*T} \rangle
$$

Key elements used in the decompositions:

$$
C_{11} = \langle|S_{HH}|^2\rangle, \quad C_{22} = \langle|S_{HV}|^2\rangle, \quad C_{33} = \langle|S_{VV}|^2\rangle, \quad C_{13} = \langle S_{HH} S_{VV}^*\rangle
$$

---

## 1. Pauli Decomposition

**Source:** `algorithms/polarimetry/pauli.py`

The Pauli decomposition expresses the scattering matrix in the three orthogonal Pauli basis components:

$$
\boxed{a = \frac{S_{HH} + S_{VV}}{\sqrt{2}}, \qquad b = \frac{S_{HH} - S_{VV}}{\sqrt{2}}, \qquad c = \frac{S_{HV} + S_{VH}}{\sqrt{2}}}
$$

| Component | Power | Physical Mechanism |
|-----------|-------|--------------------|
| $\|a\|^2$ | Surface | Odd-bounce (single bounce, e.g. Bragg surface) |
| $\|b\|^2$ | Double-bounce | Even-bounce (dihedral, e.g. building-ground) |
| $\|c\|^2$ | Volume | 45-degree oriented dipole (e.g. vegetation canopy) |

The Pauli decomposition is **coherent** (operates on complex amplitudes, not averaged power) and is commonly visualised as an RGB composite: $R = |b|^2$, $G = |c|^2$, $B = |a|^2$.

---

## 2. Freeman-Durden Decomposition

**Source:** `algorithms/polarimetry/freeman_durden.py`

The Freeman-Durden decomposition fits a three-component physical scattering model to the covariance matrix. Each component corresponds to a canonical scattering mechanism.

### Scattering Models

**Volume** (random cloud of thin dipoles):

$$
[C]_v = \frac{f_v}{4} \begin{bmatrix} 3 & 0 & 1 \\ 0 & 2 & 0 \\ 1 & 0 & 3 \end{bmatrix}
$$

**Surface** (Bragg scattering):

$$
[C]_s = f_s \begin{bmatrix} |\beta|^2 & 0 & \beta \\ 0 & 0 & 0 \\ \beta^* & 0 & 1 \end{bmatrix}
$$

**Double-bounce** (dihedral):

$$
[C]_d = f_d \begin{bmatrix} |\alpha|^2 & 0 & \alpha \\ 0 & 0 & 0 \\ \alpha^* & 0 & 1 \end{bmatrix}
$$

### Solution Procedure

**Step 1: Volume power from cross-pol.**

$$
P_v = \frac{8}{3} C_{22}
$$

This follows from the volume model: $C_{22,v} = f_v / 4$, so $f_v = 4 C_{22}$, and $P_v = f_v (3 + 2 + 3)/12 = 8 f_v / 12 \cdot 4 = 8 C_{22} / 3$.

**Step 2: Subtract volume contribution from co-pol elements.**

$$
C_{11}' = C_{11} - C_{22}, \qquad C_{33}' = C_{33} - C_{22}, \qquad C_{13}' = C_{13} - C_{22}/3
$$

**Step 3: Solve for surface and double-bounce.** The sign of $\operatorname{Re}(C_{13}')$ determines the dominant mechanism:

- If $\operatorname{Re}(C_{13}') > 0$ (surface-dominant):
$$
P_s = C_{33}' + \frac{|C_{13}'|^2}{C_{11}'}, \qquad P_d = C_{11}' + C_{33}' - P_s
$$

- If $\operatorname{Re}(C_{13}') \leq 0$ (double-bounce-dominant):
$$
P_d = C_{11}' + \frac{|C_{13}'|^2}{C_{33}'}, \qquad P_s = C_{11}' + C_{33}' - P_d
$$

All powers are clamped to non-negative values.

---

## 3. Yamaguchi Decomposition

**Source:** `algorithms/polarimetry/yamaguchi.py`

The Yamaguchi decomposition extends Freeman-Durden by adding a fourth component: **helix scattering**, which accounts for non-reciprocal scattering ($S_{HV} \neq S_{VH}$).

### Helix Scattering Power

The helix component is estimated from the imaginary part of the cross-polarisation correlation:

$$
\boxed{P_h = 2 \left|\operatorname{Im}(S_{HV} \cdot S_{VH}^*)\right|}
$$

For a reciprocal medium ($S_{HV} = S_{VH}$), the product $S_{HV} \cdot S_{VH}^*$ is real, giving $P_h = 0$. Helix scattering arises from targets with a preferred rotational sense (e.g., helical structures in urban areas).

### Modified Solution

After extracting the helix component:

1. Subtract helix contribution from cross-pol: $C_{22}' = C_{22} - P_h/4$.
2. Compute volume power: $P_v = (8/3) C_{22}'$.
3. Subtract both helix and volume from co-pol:
$$
C_{11}' = C_{11} - C_{22}' - P_h/4, \qquad C_{33}' = C_{33} - C_{22}' - P_h/4
$$
4. Solve for $P_s$ and $P_d$ as in Freeman-Durden (Step 3).

The total scattered power is $P_{\text{total}} = P_s + P_d + P_v + P_h$.

---

## 4. Cloude-Pottier Decomposition

**Source:** `algorithms/polarimetry/cloude_pottier.py`

The Cloude-Pottier decomposition performs eigenvalue analysis of the coherency matrix $[T]$ to extract three physically meaningful parameters: entropy $H$, anisotropy $A$, and mean alpha angle $\bar{\alpha}$.

### Eigenvalue Decomposition

The spatially averaged coherency matrix is decomposed as:

$$
[T] = \sum_{i=1}^{3} \lambda_i \, \mathbf{e}_i \, \mathbf{e}_i^{*T}
$$

where $\lambda_1 \geq \lambda_2 \geq \lambda_3 \geq 0$ are the eigenvalues and $\mathbf{e}_i$ are the corresponding eigenvectors. The pseudo-probabilities are:

$$
p_i = \frac{\lambda_i}{\lambda_1 + \lambda_2 + \lambda_3}
$$

### Entropy

$$
\boxed{H = -\sum_{i=1}^{3} p_i \log_3 p_i}
$$

Entropy ranges from 0 (single deterministic scattering mechanism, rank-1 coherency matrix) to 1 (completely random, equal eigenvalues). The base-3 logarithm normalises $H$ to $[0, 1]$ for a $3 \times 3$ matrix.

**Interpretation:**

| $H$ Range | Scattering |
|-----------|------------|
| $H \approx 0$ | Single dominant mechanism |
| $H \approx 0.5$ | Two competing mechanisms |
| $H \approx 1$ | Completely random (depolarising) |

### Anisotropy

$$
\boxed{A = \frac{\lambda_2 - \lambda_3}{\lambda_2 + \lambda_3}}
$$

Anisotropy measures the relative importance of the second and third eigenvalues. It is most informative when $H$ is moderate (two or more competing mechanisms). When $H$ is low, only $\lambda_1$ is significant and $A$ is unreliable.

### Mean Alpha Angle

Each eigenvector $\mathbf{e}_i = [e_{i1}, e_{i2}, e_{i3}]^T$ defines a scattering mechanism angle:

$$
\alpha_i = \arccos(|e_{i1}|)
$$

The mean alpha is the probability-weighted average:

$$
\boxed{\bar{\alpha} = \sum_{i=1}^{3} p_i \, \alpha_i}
$$

**Interpretation:**

| $\bar{\alpha}$ | Mechanism |
|-----------------|-----------|
| $\bar{\alpha} \approx 0$ | Surface / trihedral (isotropic odd-bounce) |
| $\bar{\alpha} \approx \pi/4$ | Dipole / volume scattering |
| $\bar{\alpha} \approx \pi/2$ | Dihedral / double-bounce |

### Spatial Averaging

The implementation uses a boxcar (uniform) filter of configurable window size (default $3 \times 3$) for estimating the coherency matrix elements $T_{ij} = \langle k_i k_j^* \rangle$. This is essential because a single-look coherency matrix is always rank-1 ($H = 0$), regardless of the underlying scattering physics.

### H-Alpha Classification Plane

The $(H, \bar{\alpha})$ plane is partitioned into nine zones corresponding to distinct scattering categories (Cloude & Pottier, 1997). This classification is not implemented in PySimSAR but can be applied to the output arrays.

---

## Summary of Decompositions

| Decomposition | Components | Type | Averaging Required |
|---------------|------------|------|--------------------|
| **Pauli** | 3 (surface, double-bounce, volume) | Coherent | No |
| **Freeman-Durden** | 3 (surface, double-bounce, volume) | Model-based | Optional |
| **Yamaguchi** | 4 (+helix) | Model-based | Optional |
| **Cloude-Pottier** | 3 ($H$, $A$, $\bar{\alpha}$) | Eigenvalue | Required |

---

## References

1. Lee, J.-S. and Pottier, E. (2009). *Polarimetric Radar Imaging: From Basics to Applications*. CRC Press.
2. Freeman, A. and Durden, S.L. (1998). "A three-component scattering model for polarimetric SAR data," *IEEE Trans. Geosci. Remote Sens.*, 36(3), 963--973.
3. Yamaguchi, Y., Moriyama, T., Ishido, M., and Yamada, H. (2005). "Four-component scattering model for polarimetric SAR image decomposition," *IEEE Trans. Geosci. Remote Sens.*, 43(8), 1699--1706.
4. Cloude, S.R. and Pottier, E. (1997). "An entropy based classification scheme for land applications of polarimetric SAR," *IEEE Trans. Geosci. Remote Sens.*, 35(1), 68--78.
