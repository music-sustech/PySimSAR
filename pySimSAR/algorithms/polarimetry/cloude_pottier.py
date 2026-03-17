"""Cloude-Pottier eigenvalue-based polarimetric decomposition.

Computes the coherency matrix T3 from the Pauli basis target vector,
then extracts three parameters via eigenvalue decomposition:

    H (entropy)    — randomness of scattering, [0, 1]
    A (anisotropy) — relative importance of 2nd vs 3rd eigenvalue, [0, 1]
    alpha          — mean scattering mechanism angle, [0, pi/2]

Uses spatial averaging (boxcar filter) to estimate the coherency matrix,
as single-pixel coherency matrices have rank 1 (entropy=0 always).

Reference:
    Cloude, S.R. and Pottier, E. (1997). An entropy based classification
    scheme for land applications of polarimetric SAR. IEEE TGRS, 35(1).
"""

from __future__ import annotations

import numpy as np

from pySimSAR.algorithms.base import PolarimetricDecomposition


class CloudePottierDecomposition(PolarimetricDecomposition):
    """Cloude-Pottier H/A/Alpha eigenvalue decomposition.

    Parameters
    ----------
    window_size : int
        Spatial averaging window size for coherency matrix estimation.
        Must be odd and >= 1. Default 3.
    """

    name = "cloude_pottier"

    def __init__(self, window_size: int = 3) -> None:
        if window_size < 1 or window_size % 2 == 0:
            raise ValueError(f"window_size must be odd and >= 1, got {window_size}")
        self._window_size = window_size

    @property
    def n_components(self) -> int:
        return 3

    def decompose(
        self,
        image_hh: object,
        image_hv: object,
        image_vh: object,
        image_vv: object,
    ) -> dict[str, np.ndarray]:
        self.validate_input(image_hh, image_hv, image_vh, image_vv)

        s_hh = image_hh.data.astype(complex)
        s_hv = image_hv.data.astype(complex)
        s_vh = image_vh.data.astype(complex)
        s_vv = image_vv.data.astype(complex)

        n_rows, n_cols = s_hh.shape

        # Pauli target vector: k = [HH+VV, HH-VV, HV+VH]^T / sqrt(2)
        sqrt2 = np.sqrt(2.0)
        k1 = (s_hh + s_vv) / sqrt2
        k2 = (s_hh - s_vv) / sqrt2
        k3 = (s_hv + s_vh) / sqrt2

        # Compute coherency matrix elements T_ij = <k_i * k_j*>
        # with spatial averaging via boxcar filter
        t11 = self._spatial_average(k1 * np.conj(k1))
        t12 = self._spatial_average(k1 * np.conj(k2))
        t13 = self._spatial_average(k1 * np.conj(k3))
        t22 = self._spatial_average(k2 * np.conj(k2))
        t23 = self._spatial_average(k2 * np.conj(k3))
        t33 = self._spatial_average(k3 * np.conj(k3))

        # Eigenvalue decomposition per pixel
        entropy = np.zeros((n_rows, n_cols))
        anisotropy = np.zeros((n_rows, n_cols))
        alpha = np.zeros((n_rows, n_cols))

        for i in range(n_rows):
            for j in range(n_cols):
                T = np.array([
                    [t11[i, j], t12[i, j], t13[i, j]],
                    [np.conj(t12[i, j]), t22[i, j], t23[i, j]],
                    [np.conj(t13[i, j]), np.conj(t23[i, j]), t33[i, j]],
                ])

                # Eigenvalue decomposition (T is Hermitian positive semi-definite)
                eigenvalues, eigenvectors = np.linalg.eigh(T)

                # Sort descending
                idx = np.argsort(eigenvalues)[::-1]
                eigenvalues = eigenvalues[idx]
                eigenvectors = eigenvectors[:, idx]

                # Clamp eigenvalues to non-negative
                eigenvalues = np.maximum(eigenvalues, 0.0)

                # Pseudo-probabilities
                total = np.sum(eigenvalues)
                if total < 1e-30:
                    entropy[i, j] = 0.0
                    anisotropy[i, j] = 0.0
                    alpha[i, j] = 0.0
                    continue

                p = eigenvalues / total

                # Entropy: H = -sum(p_i * log3(p_i))
                h = 0.0
                for k in range(3):
                    if p[k] > 1e-30:
                        h -= p[k] * np.log(p[k]) / np.log(3.0)
                entropy[i, j] = np.clip(h, 0.0, 1.0)

                # Anisotropy: A = (lambda_2 - lambda_3) / (lambda_2 + lambda_3)
                denom = eigenvalues[1] + eigenvalues[2]
                if denom > 1e-30:
                    anisotropy[i, j] = np.clip(
                        (eigenvalues[1] - eigenvalues[2]) / denom, 0.0, 1.0
                    )

                # Alpha angle: weighted mean of eigenvector alpha angles
                # alpha_i = arccos(|e_i1|) where e_i1 is the first component
                alpha_val = 0.0
                for k in range(3):
                    cos_alpha_k = np.abs(eigenvectors[0, k])
                    cos_alpha_k = np.clip(cos_alpha_k, 0.0, 1.0)
                    alpha_val += p[k] * np.arccos(cos_alpha_k)
                alpha[i, j] = np.clip(alpha_val, 0.0, np.pi / 2)

        return {
            "entropy": entropy,
            "anisotropy": anisotropy,
            "alpha": alpha,
        }

    def _spatial_average(self, data: np.ndarray) -> np.ndarray:
        """Apply boxcar spatial averaging."""
        if self._window_size <= 1:
            return data.copy()

        from scipy.ndimage import uniform_filter
        # uniform_filter handles complex by filtering real and imag separately
        result = uniform_filter(data.real, size=self._window_size, mode="nearest")
        if np.iscomplexobj(data):
            result = result + 1j * uniform_filter(
                data.imag, size=self._window_size, mode="nearest"
            )
        return result


__all__ = ["CloudePottierDecomposition"]
