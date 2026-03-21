# Geocoding

This chapter describes the geocoding algorithms in PySimSAR: slant-to-ground range projection and georeferencing (pixel-to-lat/lon mapping).

---

## 1. Slant-Range to Ground-Range Projection

**Source:** `algorithms/geocoding/slant_to_ground.py`

SAR image formation algorithms produce images in **slant-range geometry**, where the range axis represents the line-of-sight distance from the platform. Geocoding transforms this to **ground-range geometry**, where the range axis represents horizontal distance on the ground.

### Flat-Earth Model

For a platform at altitude $h$ above a flat ground plane, the ground range $R_g$ corresponding to slant range $R_s$ is:

$$
\boxed{R_g = \sqrt{R_s^2 - h^2}}
$$

**Derivation.** The slant range $R_s$, altitude $h$, and ground range $R_g$ form a right triangle (flat-earth assumption):

$$
R_s^2 = R_g^2 + h^2 \quad \Longrightarrow \quad R_g = \sqrt{R_s^2 - h^2}
$$

This requires $R_s \geq h$; the implementation clamps $R_s \geq h + \epsilon$ to avoid numerical issues.

### Near Slant Range

The near slant range (range of the first sample) is computed from the depression angle $\psi$:

$$
R_{s,\text{near}} = \frac{h}{\sin \psi}
$$

The slant range for range bin $b$ is:

$$
R_s(b) = R_{s,\text{near}} + b \cdot \Delta r_s, \qquad \Delta r_s = \frac{c}{2 f_s}
$$

### Non-Uniform to Uniform Resampling

The mapping $R_s \mapsto R_g$ is nonlinear, so the ground-range samples are non-uniformly spaced. The algorithm resamples to a uniform ground-range grid:

1. Compute ground range for each slant-range bin: $R_g(b) = \sqrt{R_s(b)^2 - h^2}$.
2. Determine ground-range spacing at mid-swath using the Jacobian:

$$
\Delta r_g = \Delta r_s \cdot \frac{R_{s,\text{mid}}}{\sqrt{R_{s,\text{mid}}^2 - h^2}} = \Delta r_s \cdot \frac{R_{s,\text{mid}}}{R_{g,\text{mid}}}
$$

**Derivation of the Jacobian.** Differentiating $R_g = \sqrt{R_s^2 - h^2}$:

$$
\frac{dR_g}{dR_s} = \frac{R_s}{\sqrt{R_s^2 - h^2}}
$$

So a uniform slant-range spacing $\Delta r_s$ maps to a ground-range spacing of $\Delta r_s \cdot R_s / R_g$, which varies with range (ground-range pixels are wider in near range).

3. Create a uniform ground-range grid with spacing $\Delta r_g$ evaluated at mid-swath.
4. Interpolate each azimuth line from the non-uniform $R_g(b)$ grid to the uniform grid using linear interpolation.

---

## 2. Georeferencing

**Source:** `algorithms/geocoding/georeferencing.py`

Georeferencing maps SAR image pixels to geographic (latitude/longitude) coordinates using the platform trajectory and radar geometry.

### Pixel-to-ENU Mapping

For a given pixel at (range bin $b$, azimuth line $a$):

1. **Platform position**: Interpolate the trajectory to the azimuth time of line $a$.
2. **Slant range**: $R_s = R_{s,\text{near}} + b \cdot \Delta r_s$.
3. **Ground range**: $R_g = \sqrt{R_s^2 - h^2}$ where $h$ is the platform altitude.
4. **Look direction**: Compute the platform heading $\psi_h = \arctan(v_E / v_N)$ from the velocity vector. The cross-track direction depends on the look side:

$$
\theta_{\text{cross}} = \begin{cases}
\psi_h + \pi/2 & \text{(right-looking)} \\
\psi_h - \pi/2 & \text{(left-looking)}
\end{cases}
$$

5. **Ground position in ENU**:

$$
E_t = E_p + R_g \sin\theta_{\text{cross}}, \qquad
N_t = N_p + R_g \cos\theta_{\text{cross}}, \qquad
U_t = 0
$$

### ENU-to-Geodetic Transform

The ENU ground position is converted to geodetic coordinates (latitude, longitude) using the inverse of the standard ENU projection. Given a reference origin $(\phi_0, \lambda_0, h_0)$ in WGS84:

**Step 1: ENU to ECEF.** The rotation from ENU to ECEF at reference point $(\phi_0, \lambda_0)$ is:

$$
\begin{bmatrix} \Delta X \\ \Delta Y \\ \Delta Z \end{bmatrix} = \mathbf{R}^T \begin{bmatrix} E \\ N \\ U \end{bmatrix}
$$

where

$$
\mathbf{R} = \begin{bmatrix}
-\sin\lambda_0 & -\sin\phi_0 \cos\lambda_0 & \cos\phi_0 \cos\lambda_0 \\
\cos\lambda_0 & -\sin\phi_0 \sin\lambda_0 & \cos\phi_0 \sin\lambda_0 \\
0 & \cos\phi_0 & \sin\phi_0
\end{bmatrix}
$$

**Step 2: ECEF to geodetic.** Convert ECEF coordinates $(X_0 + \Delta X, Y_0 + \Delta Y, Z_0 + \Delta Z)$ to $(\phi, \lambda, h)$ using Bowring's iterative method on the WGS84 ellipsoid:

$$
\phi = \arctan\!\left(\frac{Z + e'^2 b \sin^3\theta}{p - e^2 a \cos^3\theta}\right), \qquad
\lambda = \arctan\!\left(\frac{Y}{X}\right)
$$

where $\theta = \arctan(Z a / (p b))$, $p = \sqrt{X^2 + Y^2}$, $a$ and $b$ are the WGS84 semi-major and semi-minor axes, and $e^2 = 2f - f^2$ is the first eccentricity squared ($f = 1/298.257223563$).

### Affine Geo-Transform

The georeferencing output includes a GDAL-style affine transform that maps pixel indices to geographic coordinates:

$$
\begin{bmatrix} \lambda \\ \phi \end{bmatrix} = \begin{bmatrix} \lambda_0 \\ \phi_0 \end{bmatrix} + \begin{bmatrix} \partial\lambda/\partial c & \partial\lambda/\partial r \\ \partial\phi/\partial c & \partial\phi/\partial r \end{bmatrix} \begin{bmatrix} \text{col} \\ \text{row} \end{bmatrix}
$$

The partial derivatives are estimated from the four image corners. This affine model is accurate for small scenes but introduces errors for large swaths where the Earth's curvature is significant.

---

## References

1. Cumming, I.G. and Wong, F.H. (2005). *Digital Processing of Synthetic Aperture Radar Data*. Artech House, Ch. 12.
2. Schreier, G. (ed.) (1993). *SAR Geocoding: Data and Systems*. Wichmann Verlag.
