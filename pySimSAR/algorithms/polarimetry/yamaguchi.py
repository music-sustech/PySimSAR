"""Yamaguchi 4-component polarimetric decomposition.

Extends Freeman-Durden by adding a helix scattering component that
accounts for non-reciprocal scattering (HV != VH). The helix power
is estimated from the imaginary part of the HV-VH cross-correlation.

Components:
1. Surface (Bragg) scattering
2. Double-bounce (dihedral) scattering
3. Volume (random dipole cloud) scattering
4. Helix scattering (non-reciprocal component)

Reference:
    Yamaguchi, Y., et al. (2005). Four-component scattering model for
    polarimetric SAR image decomposition. IEEE TGRS, 43(8), 1699-1706.
"""

from __future__ import annotations

import numpy as np

from pySimSAR.algorithms.base import PolarimetricDecomposition


class YamaguchiDecomposition(PolarimetricDecomposition):
    """Yamaguchi 4-component polarimetric decomposition."""

    name = "yamaguchi"

    @property
    def n_components(self) -> int:
        return 4

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

        shape = s_hh.shape

        # Step 1: Helix scattering from non-reciprocal component
        # Helix power: P_h = 2 * |Im(S_HV - S_VH)|²
        # = 2 * |Im(C_hv_vh)|  where C_hv_vh = <HV * VH*>
        hv_vh_cross = s_hv * np.conj(s_vh)
        p_h = 2.0 * np.abs(np.imag(hv_vh_cross))

        # Step 2: Covariance matrix elements
        c11 = np.abs(s_hh) ** 2
        c22 = (np.abs(s_hv) ** 2 + np.abs(s_vh) ** 2) / 2.0
        c33 = np.abs(s_vv) ** 2
        c13 = s_hh * np.conj(s_vv)

        # Step 3: Subtract helix contribution
        # Helix model contributes to C11, C22, C33
        c22_r = np.maximum(c22 - p_h / 4.0, 0.0)

        # Step 4: Volume from remaining cross-pol (same as Freeman-Durden)
        p_v = (8.0 / 3.0) * c22_r

        # Step 5: Subtract volume from co-pol
        c11_r = np.maximum(c11 - c22_r - p_h / 4.0, 0.0)
        c33_r = np.maximum(c33 - c22_r - p_h / 4.0, 0.0)
        c13_r = c13 - c22_r / 3.0

        # Step 6: Solve for surface and double-bounce (same logic as Freeman-Durden)
        re_c13 = np.real(c13_r)
        p_s = np.zeros(shape)
        p_d = np.zeros(shape)

        surf_mask = re_c13 > 0
        if np.any(surf_mask):
            safe = surf_mask & (c11_r > 1e-30)
            p_s[safe] = c33_r[safe] + np.abs(c13_r[safe]) ** 2 / c11_r[safe]
            p_d[surf_mask] = np.maximum(c11_r[surf_mask] + c33_r[surf_mask] - p_s[surf_mask], 0.0)

        dbl_mask = ~surf_mask
        if np.any(dbl_mask):
            safe = dbl_mask & (c33_r > 1e-30)
            p_d[safe] = c11_r[safe] + np.abs(c13_r[safe]) ** 2 / c33_r[safe]
            p_s[dbl_mask] = np.maximum(c11_r[dbl_mask] + c33_r[dbl_mask] - p_d[dbl_mask], 0.0)

        p_s = np.maximum(p_s, 0.0)
        p_d = np.maximum(p_d, 0.0)
        p_v = np.maximum(p_v, 0.0)
        p_h = np.maximum(p_h, 0.0)

        return {
            "surface": p_s,
            "double_bounce": p_d,
            "volume": p_v,
            "helix": p_h,
        }


__all__ = ["YamaguchiDecomposition"]
