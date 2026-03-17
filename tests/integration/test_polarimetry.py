"""Integration tests for polarimetric decomposition algorithms (Phase 10 — US7).

T102: Pauli decomposition — component verification
T103: Freeman-Durden — power conservation
T104: Yamaguchi — 4-component
T105: Cloude-Pottier — H/A/Alpha

Tests use canonical scattering scenarios with known analytical results.
"""

from __future__ import annotations

import numpy as np
import pytest

from pySimSAR.core.types import SARImage


def _make_quad_pol(
    s_hh: np.ndarray,
    s_hv: np.ndarray,
    s_vh: np.ndarray,
    s_vv: np.ndarray,
) -> tuple[SARImage, SARImage, SARImage, SARImage]:
    """Create quad-pol SARImage set from scattering matrices."""
    kw = dict(pixel_spacing_range=1.0, pixel_spacing_azimuth=1.0, geometry="slant_range")
    return (
        SARImage(data=s_hh, channel="hh", **kw),
        SARImage(data=s_hv, channel="hv", **kw),
        SARImage(data=s_vh, channel="vh", **kw),
        SARImage(data=s_vv, channel="vv", **kw),
    )


def _uniform_scene(value_hh, value_hv, value_vh, value_vv, size=(16, 16)):
    """Create uniform quad-pol scene with constant scattering values."""
    s_hh = np.full(size, value_hh, dtype=complex)
    s_hv = np.full(size, value_hv, dtype=complex)
    s_vh = np.full(size, value_vh, dtype=complex)
    s_vv = np.full(size, value_vv, dtype=complex)
    return _make_quad_pol(s_hh, s_hv, s_vh, s_vv)


class TestPauliDecomposition:
    """T102: Integration test for Pauli decomposition."""

    def test_pure_surface_scatterer(self):
        """S = [1,0;0,1] (surface/trihedral): surface component dominates."""
        from pySimSAR.algorithms.polarimetry.pauli import PauliDecomposition

        img_hh, img_hv, img_vh, img_vv = _uniform_scene(1.0, 0.0, 0.0, 1.0)
        pauli = PauliDecomposition()
        result = pauli.decompose(img_hh, img_hv, img_vh, img_vv)

        assert "surface" in result
        assert "double_bounce" in result
        assert "volume" in result

        # Surface should dominate, double-bounce and volume near zero
        assert np.mean(result["surface"]) > 0
        assert np.mean(result["double_bounce"]) < 1e-10
        assert np.mean(result["volume"]) < 1e-10

    def test_pure_double_bounce(self):
        """S = [1,0;0,-1] (dihedral): double-bounce component dominates."""
        from pySimSAR.algorithms.polarimetry.pauli import PauliDecomposition

        img_hh, img_hv, img_vh, img_vv = _uniform_scene(1.0, 0.0, 0.0, -1.0)
        pauli = PauliDecomposition()
        result = pauli.decompose(img_hh, img_hv, img_vh, img_vv)

        assert np.mean(result["double_bounce"]) > 0
        assert np.mean(result["surface"]) < 1e-10
        assert np.mean(result["volume"]) < 1e-10

    def test_pure_volume_scatterer(self):
        """S = [0,1;1,0] (oriented dipole): volume component dominates."""
        from pySimSAR.algorithms.polarimetry.pauli import PauliDecomposition

        img_hh, img_hv, img_vh, img_vv = _uniform_scene(0.0, 1.0, 1.0, 0.0)
        pauli = PauliDecomposition()
        result = pauli.decompose(img_hh, img_hv, img_vh, img_vv)

        assert np.mean(result["volume"]) > 0
        assert np.mean(result["surface"]) < 1e-10
        assert np.mean(result["double_bounce"]) < 1e-10

    def test_mixed_scattering_power_conservation(self):
        """Total Pauli power equals span for reciprocal medium (HV=VH)."""
        from pySimSAR.algorithms.polarimetry.pauli import PauliDecomposition

        rng = np.random.default_rng(42)
        size = (16, 16)
        s_hh = rng.standard_normal(size) + 1j * rng.standard_normal(size)
        s_hv = rng.standard_normal(size) + 1j * rng.standard_normal(size)
        s_vh = s_hv.copy()  # reciprocal: HV = VH
        s_vv = rng.standard_normal(size) + 1j * rng.standard_normal(size)

        img_hh, img_hv, img_vh, img_vv = _make_quad_pol(s_hh, s_hv, s_vh, s_vv)
        pauli = PauliDecomposition()
        result = pauli.decompose(img_hh, img_hv, img_vh, img_vv)

        # For reciprocal medium (HV=VH), 3-component Pauli span equals full span:
        # |a|² + |b|² + |c|² = |HH|² + |VV|² + 2|HV|²
        total_pauli = result["surface"] + result["double_bounce"] + result["volume"]
        span = np.abs(s_hh)**2 + 2 * np.abs(s_hv)**2 + np.abs(s_vv)**2

        np.testing.assert_allclose(total_pauli, span, rtol=1e-10)

    def test_n_components(self):
        from pySimSAR.algorithms.polarimetry.pauli import PauliDecomposition
        assert PauliDecomposition().n_components == 3

    def test_name(self):
        from pySimSAR.algorithms.polarimetry.pauli import PauliDecomposition
        assert PauliDecomposition().name == "pauli"

    def test_validate_input_rejects_none(self):
        from pySimSAR.algorithms.polarimetry.pauli import PauliDecomposition
        pauli = PauliDecomposition()
        with pytest.raises(ValueError, match="Missing HH"):
            pauli.validate_input(None, None, None, None)


class TestFreemanDurdenDecomposition:
    """T103: Integration test for Freeman-Durden decomposition."""

    def test_three_components_returned(self):
        """Returns surface, double_bounce, volume components."""
        from pySimSAR.algorithms.polarimetry.freeman_durden import FreemanDurdenDecomposition

        img_hh, img_hv, img_vh, img_vv = _uniform_scene(1.0, 0.1, 0.1, 0.8)
        fd = FreemanDurdenDecomposition()
        result = fd.decompose(img_hh, img_hv, img_vh, img_vv)

        assert "surface" in result
        assert "double_bounce" in result
        assert "volume" in result
        assert all(v.shape == (16, 16) for v in result.values())

    def test_power_conservation(self):
        """All components non-negative; total power is finite and reasonable."""
        from pySimSAR.algorithms.polarimetry.freeman_durden import FreemanDurdenDecomposition

        rng = np.random.default_rng(42)
        size = (16, 16)
        s_hh = rng.standard_normal(size) + 1j * rng.standard_normal(size)
        s_hv = 0.3 * (rng.standard_normal(size) + 1j * rng.standard_normal(size))
        s_vh = s_hv.copy()  # reciprocity
        s_vv = rng.standard_normal(size) + 1j * rng.standard_normal(size)

        img_hh, img_hv, img_vh, img_vv = _make_quad_pol(s_hh, s_hv, s_vh, s_vv)
        fd = FreemanDurdenDecomposition()
        result = fd.decompose(img_hh, img_hv, img_vh, img_vv)

        # All components should be non-negative
        assert np.all(result["surface"] >= -1e-10)
        assert np.all(result["double_bounce"] >= -1e-10)
        assert np.all(result["volume"] >= -1e-10)

        # Total power should be finite
        total = result["surface"] + result["double_bounce"] + result["volume"]
        assert np.all(np.isfinite(total))

        # Total should be on the same order as span
        span = np.abs(s_hh)**2 + 2 * np.abs(s_hv)**2 + np.abs(s_vv)**2
        assert np.mean(total) < 5 * np.mean(span)

    def test_pure_cross_pol_gives_volume(self):
        """Strong cross-pol with weak co-pol → volume dominates."""
        from pySimSAR.algorithms.polarimetry.freeman_durden import FreemanDurdenDecomposition

        img_hh, img_hv, img_vh, img_vv = _uniform_scene(0.1, 1.0, 1.0, 0.1)
        fd = FreemanDurdenDecomposition()
        result = fd.decompose(img_hh, img_hv, img_vh, img_vv)

        # Volume should dominate
        assert np.mean(result["volume"]) > np.mean(result["surface"])
        assert np.mean(result["volume"]) > np.mean(result["double_bounce"])

    def test_n_components(self):
        from pySimSAR.algorithms.polarimetry.freeman_durden import FreemanDurdenDecomposition
        assert FreemanDurdenDecomposition().n_components == 3

    def test_name(self):
        from pySimSAR.algorithms.polarimetry.freeman_durden import FreemanDurdenDecomposition
        assert FreemanDurdenDecomposition().name == "freeman_durden"


class TestYamaguchiDecomposition:
    """T104: Integration test for Yamaguchi 4-component decomposition."""

    def test_four_components_returned(self):
        """Returns surface, double_bounce, volume, helix components."""
        from pySimSAR.algorithms.polarimetry.yamaguchi import YamaguchiDecomposition

        img_hh, img_hv, img_vh, img_vv = _uniform_scene(1.0, 0.1, 0.1, 0.8)
        yam = YamaguchiDecomposition()
        result = yam.decompose(img_hh, img_hv, img_vh, img_vv)

        assert "surface" in result
        assert "double_bounce" in result
        assert "volume" in result
        assert "helix" in result
        assert all(v.shape == (16, 16) for v in result.values())

    def test_reciprocal_medium_zero_helix(self):
        """For reciprocal scattering (HV=VH), helix component is near zero."""
        from pySimSAR.algorithms.polarimetry.yamaguchi import YamaguchiDecomposition

        # Reciprocal medium: HV = VH
        img_hh, img_hv, img_vh, img_vv = _uniform_scene(1.0, 0.3, 0.3, 0.8)
        yam = YamaguchiDecomposition()
        result = yam.decompose(img_hh, img_hv, img_vh, img_vv)

        assert np.all(np.abs(result["helix"]) < 1e-10)

    def test_non_reciprocal_has_helix(self):
        """For non-reciprocal scattering (HV != VH), helix component is non-zero."""
        from pySimSAR.algorithms.polarimetry.yamaguchi import YamaguchiDecomposition

        img_hh, img_hv, img_vh, img_vv = _uniform_scene(1.0, 0.5+0.3j, 0.1-0.2j, 0.8)
        yam = YamaguchiDecomposition()
        result = yam.decompose(img_hh, img_hv, img_vh, img_vv)

        assert np.mean(result["helix"]) > 1e-6

    def test_power_non_negative(self):
        """All decomposition components should be non-negative."""
        from pySimSAR.algorithms.polarimetry.yamaguchi import YamaguchiDecomposition

        rng = np.random.default_rng(42)
        size = (16, 16)
        s_hh = rng.standard_normal(size) + 1j * rng.standard_normal(size)
        s_hv = 0.3 * (rng.standard_normal(size) + 1j * rng.standard_normal(size))
        s_vh = s_hv.copy()
        s_vv = rng.standard_normal(size) + 1j * rng.standard_normal(size)

        img_hh, img_hv, img_vh, img_vv = _make_quad_pol(s_hh, s_hv, s_vh, s_vv)
        yam = YamaguchiDecomposition()
        result = yam.decompose(img_hh, img_hv, img_vh, img_vv)

        for name, component in result.items():
            assert np.all(component >= -1e-10), f"{name} has negative values"

    def test_n_components(self):
        from pySimSAR.algorithms.polarimetry.yamaguchi import YamaguchiDecomposition
        assert YamaguchiDecomposition().n_components == 4

    def test_name(self):
        from pySimSAR.algorithms.polarimetry.yamaguchi import YamaguchiDecomposition
        assert YamaguchiDecomposition().name == "yamaguchi"


class TestCloudePottierDecomposition:
    """T105: Integration test for Cloude-Pottier (H/A/Alpha) decomposition."""

    def test_three_components_returned(self):
        """Returns entropy, anisotropy, alpha components."""
        from pySimSAR.algorithms.polarimetry.cloude_pottier import CloudePottierDecomposition

        img_hh, img_hv, img_vh, img_vv = _uniform_scene(1.0, 0.1, 0.1, 0.8)
        cp = CloudePottierDecomposition()
        result = cp.decompose(img_hh, img_hv, img_vh, img_vv)

        assert "entropy" in result
        assert "anisotropy" in result
        assert "alpha" in result

    def test_single_mechanism_low_entropy(self):
        """Pure surface scattering (single mechanism) → low entropy."""
        from pySimSAR.algorithms.polarimetry.cloude_pottier import CloudePottierDecomposition

        # Pure surface: S = [1,0;0,1] — single dominant mechanism
        img_hh, img_hv, img_vh, img_vv = _uniform_scene(1.0, 0.0, 0.0, 1.0)
        cp = CloudePottierDecomposition()
        result = cp.decompose(img_hh, img_hv, img_vh, img_vv)

        # Entropy should be low (single mechanism → one dominant eigenvalue)
        assert np.mean(result["entropy"]) < 0.5

    def test_random_scattering_high_entropy(self):
        """Random scattering → high entropy (multiple mechanisms)."""
        from pySimSAR.algorithms.polarimetry.cloude_pottier import CloudePottierDecomposition

        # Random scattering with equal power in all channels
        rng = np.random.default_rng(42)
        size = (32, 32)
        s_hh = rng.standard_normal(size) + 1j * rng.standard_normal(size)
        s_hv = rng.standard_normal(size) + 1j * rng.standard_normal(size)
        s_vh = rng.standard_normal(size) + 1j * rng.standard_normal(size)
        s_vv = rng.standard_normal(size) + 1j * rng.standard_normal(size)

        img_hh, img_hv, img_vh, img_vv = _make_quad_pol(s_hh, s_hv, s_vh, s_vv)
        cp = CloudePottierDecomposition(window_size=5)
        result = cp.decompose(img_hh, img_hv, img_vh, img_vv)

        # Entropy should be high for random scattering (> 0.5)
        valid = result["entropy"][2:-2, 2:-2]  # avoid window edge effects
        assert np.mean(valid) > 0.5

    def test_entropy_in_range(self):
        """Entropy should be in [0, 1]."""
        from pySimSAR.algorithms.polarimetry.cloude_pottier import CloudePottierDecomposition

        rng = np.random.default_rng(42)
        size = (16, 16)
        s_hh = rng.standard_normal(size) + 1j * rng.standard_normal(size)
        s_hv = 0.3 * (rng.standard_normal(size) + 1j * rng.standard_normal(size))
        s_vh = s_hv.copy()
        s_vv = rng.standard_normal(size) + 1j * rng.standard_normal(size)

        img_hh, img_hv, img_vh, img_vv = _make_quad_pol(s_hh, s_hv, s_vh, s_vv)
        cp = CloudePottierDecomposition()
        result = cp.decompose(img_hh, img_hv, img_vh, img_vv)

        assert np.all(result["entropy"] >= -1e-10)
        assert np.all(result["entropy"] <= 1.0 + 1e-10)

    def test_alpha_in_range(self):
        """Alpha angle should be in [0, pi/2]."""
        from pySimSAR.algorithms.polarimetry.cloude_pottier import CloudePottierDecomposition

        rng = np.random.default_rng(42)
        size = (16, 16)
        s_hh = rng.standard_normal(size) + 1j * rng.standard_normal(size)
        s_hv = 0.3 * (rng.standard_normal(size) + 1j * rng.standard_normal(size))
        s_vh = s_hv.copy()
        s_vv = rng.standard_normal(size) + 1j * rng.standard_normal(size)

        img_hh, img_hv, img_vh, img_vv = _make_quad_pol(s_hh, s_hv, s_vh, s_vv)
        cp = CloudePottierDecomposition()
        result = cp.decompose(img_hh, img_hv, img_vh, img_vv)

        assert np.all(result["alpha"] >= -1e-10)
        assert np.all(result["alpha"] <= np.pi / 2 + 1e-10)

    def test_anisotropy_in_range(self):
        """Anisotropy should be in [0, 1]."""
        from pySimSAR.algorithms.polarimetry.cloude_pottier import CloudePottierDecomposition

        rng = np.random.default_rng(42)
        size = (16, 16)
        s_hh = rng.standard_normal(size) + 1j * rng.standard_normal(size)
        s_hv = 0.3 * (rng.standard_normal(size) + 1j * rng.standard_normal(size))
        s_vh = s_hv.copy()
        s_vv = rng.standard_normal(size) + 1j * rng.standard_normal(size)

        img_hh, img_hv, img_vh, img_vv = _make_quad_pol(s_hh, s_hv, s_vh, s_vv)
        cp = CloudePottierDecomposition()
        result = cp.decompose(img_hh, img_hv, img_vh, img_vv)

        assert np.all(result["anisotropy"] >= -1e-10)
        assert np.all(result["anisotropy"] <= 1.0 + 1e-10)

    def test_n_components(self):
        from pySimSAR.algorithms.polarimetry.cloude_pottier import CloudePottierDecomposition
        assert CloudePottierDecomposition().n_components == 3

    def test_name(self):
        from pySimSAR.algorithms.polarimetry.cloude_pottier import CloudePottierDecomposition
        assert CloudePottierDecomposition().name == "cloude_pottier"


class TestPolarimetryRegistry:
    """Test that polarimetry algorithms are properly registered."""

    def test_registry_contains_all(self):
        from pySimSAR.algorithms.polarimetry import polarimetry_registry

        assert "pauli" in polarimetry_registry
        assert "freeman_durden" in polarimetry_registry
        assert "yamaguchi" in polarimetry_registry
        assert "cloude_pottier" in polarimetry_registry

    def test_registry_count(self):
        from pySimSAR.algorithms.polarimetry import polarimetry_registry
        assert len(polarimetry_registry) == 4
