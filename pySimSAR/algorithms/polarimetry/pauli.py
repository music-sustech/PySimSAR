"""Pauli polarimetric decomposition.

Decomposes the scattering matrix S into three orthogonal Pauli basis
components representing surface (odd-bounce), double-bounce (even-bounce),
and volume (45-degree oriented dipole) scattering mechanisms.

    a = (S_HH + S_VV) / sqrt(2)   — surface / odd-bounce
    b = (S_HH - S_VV) / sqrt(2)   — double-bounce / even-bounce
    c = (S_HV + S_VH) / sqrt(2)   — volume / 45-degree dipole

Output powers: |a|², |b|², |c|²
"""

from __future__ import annotations

import numpy as np

from pySimSAR.algorithms.base import PolarimetricDecomposition


class PauliDecomposition(PolarimetricDecomposition):
    """Pauli basis polarimetric decomposition (3 components)."""

    name = "pauli"

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

        sqrt2 = np.sqrt(2.0)

        a = (s_hh + s_vv) / sqrt2       # surface
        b = (s_hh - s_vv) / sqrt2       # double-bounce
        c = (s_hv + s_vh) / sqrt2       # volume

        return {
            "surface": np.abs(a) ** 2,
            "double_bounce": np.abs(b) ** 2,
            "volume": np.abs(c) ** 2,
        }


__all__ = ["PauliDecomposition"]
