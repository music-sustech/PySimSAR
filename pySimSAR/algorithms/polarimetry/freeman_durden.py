"""Freeman-Durden model-based 3-component polarimetric decomposition.

Decomposes the covariance matrix into three scattering models:
1. Surface (Bragg) scattering
2. Double-bounce (dihedral) scattering
3. Volume (random cloud of dipoles) scattering

The volume contribution is estimated from cross-pol power, then
subtracted from the covariance matrix to solve for surface and
double-bounce contributions from the remaining co-pol terms.

Reference:
    Freeman, A. and Durden, S.L. (1998). A three-component scattering
    model for polarimetric SAR data. IEEE TGRS, 36(3), 963-973.
"""

from __future__ import annotations

import numpy as np

from pySimSAR.algorithms.base import PolarimetricDecomposition


class FreemanDurdenDecomposition(PolarimetricDecomposition):
    """Freeman-Durden model-based 3-component decomposition."""

    name = "freeman_durden"

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
        s_vv = image_vv.data.astype(complex)

        shape = s_hh.shape

        # Covariance matrix elements (pixel-level, no spatial averaging)
        c11 = np.abs(s_hh) ** 2       # <|HH|²>
        c22 = np.abs(s_hv) ** 2       # <|HV|²>
        c33 = np.abs(s_vv) ** 2       # <|VV|²>
        c13 = s_hh * np.conj(s_vv)    # <HH·VV*>

        # Step 1: Volume scattering power from cross-pol
        # For random volume: C22 = f_v / 4, so f_v = 4 * C22
        # Volume power P_v = 8/3 * C22 (accounts for all volume terms)
        p_v = (8.0 / 3.0) * c22

        # Step 2: Subtract volume contribution from co-pol
        # Volume model contributes to C11, C33, and C13
        # C11_vol = 3/8 * P_v = C22, C33_vol = 3/8 * P_v = C22
        # C13_vol = 1/8 * P_v = C22/3
        c11_r = c11 - c22
        c33_r = c33 - c22
        c13_r = c13 - c22 / 3.0

        # Clamp to non-negative
        c11_r = np.maximum(c11_r, 0.0)
        c33_r = np.maximum(c33_r, 0.0)

        # Step 3: Determine surface vs double-bounce dominance
        # If Re(C13_r) > 0: surface dominates, solve for surface first
        # If Re(C13_r) <= 0: double-bounce dominates
        re_c13 = np.real(c13_r)

        p_s = np.zeros(shape)
        p_d = np.zeros(shape)

        # Surface-dominant pixels
        surf_mask = re_c13 > 0
        if np.any(surf_mask):
            # Surface model: P_s = C33_r + |C13_r|²/C11_r (when C11_r > 0)
            safe = surf_mask & (c11_r > 1e-30)
            p_s[safe] = c33_r[safe] + np.abs(c13_r[safe]) ** 2 / c11_r[safe]
            p_d[surf_mask] = np.maximum(c11_r[surf_mask] + c33_r[surf_mask] - p_s[surf_mask], 0.0)

        # Double-bounce-dominant pixels
        dbl_mask = ~surf_mask
        if np.any(dbl_mask):
            safe = dbl_mask & (c33_r > 1e-30)
            p_d[safe] = c11_r[safe] + np.abs(c13_r[safe]) ** 2 / c33_r[safe]
            p_s[dbl_mask] = np.maximum(c11_r[dbl_mask] + c33_r[dbl_mask] - p_d[dbl_mask], 0.0)

        # Clamp all to non-negative
        p_s = np.maximum(p_s, 0.0)
        p_d = np.maximum(p_d, 0.0)
        p_v = np.maximum(p_v, 0.0)

        return {
            "surface": p_s,
            "double_bounce": p_d,
            "volume": p_v,
        }


__all__ = ["FreemanDurdenDecomposition"]
