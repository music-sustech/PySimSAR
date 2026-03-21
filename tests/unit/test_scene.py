"""Unit tests for PointTarget, DistributedTarget, Scene, and UniformClutter.

Covers tasks T023 (scene model) and T029 (uniform clutter model).
"""

from __future__ import annotations

import numpy as np
import pytest

from pySimSAR.clutter.uniform import UniformClutter
from pySimSAR.core.scene import DistributedTarget, PointTarget, Scene

# ---------------------------------------------------------------------------
# PointTarget tests
# ---------------------------------------------------------------------------

class TestPointTarget:
    """Test PointTarget creation and validation."""

    def test_create_with_scalar_rcs(self):
        pt = PointTarget(position=np.array([1.0, 2.0, 3.0]), rcs=10.0)
        np.testing.assert_array_equal(pt.position, [1.0, 2.0, 3.0])
        assert pt.rcs == 10.0
        assert pt.velocity is None

    def test_create_with_scattering_matrix_rcs(self):
        smat = np.array([[1 + 0j, 0.1 + 0.2j], [0.1 - 0.2j, 0.8 + 0j]])
        pt = PointTarget(position=np.array([0.0, 0.0, 0.0]), rcs=smat)
        np.testing.assert_array_equal(pt.rcs, smat)

    def test_create_with_velocity(self):
        vel = np.array([5.0, -3.0, 0.0])
        pt = PointTarget(
            position=np.array([0.0, 0.0, 0.0]), rcs=1.0, velocity=vel
        )
        np.testing.assert_array_equal(pt.velocity, vel)

    def test_position_wrong_shape_raises(self):
        with pytest.raises(ValueError, match="position.*shape"):
            PointTarget(position=np.array([1.0, 2.0]), rcs=1.0)

    def test_position_wrong_shape_4d_raises(self):
        with pytest.raises(ValueError, match="position.*shape"):
            PointTarget(position=np.array([1.0, 2.0, 3.0, 4.0]), rcs=1.0)

    def test_rcs_array_wrong_shape_raises(self):
        with pytest.raises(ValueError, match="rcs.*shape"):
            PointTarget(
                position=np.array([0.0, 0.0, 0.0]),
                rcs=np.array([1.0, 2.0]),
            )

    def test_velocity_wrong_shape_raises(self):
        with pytest.raises(ValueError, match="velocity.*shape"):
            PointTarget(
                position=np.array([0.0, 0.0, 0.0]),
                rcs=1.0,
                velocity=np.array([1.0, 2.0]),
            )

    def test_position_coerced_from_list(self):
        pt = PointTarget(position=[10.0, 20.0, 30.0], rcs=1.0)
        assert pt.position.shape == (3,)

    def test_scalar_rcs_must_be_positive(self):
        with pytest.raises(ValueError, match="rcs must be > 0"):
            PointTarget(position=[0.0, 0.0, 0.0], rcs=0.0)
        with pytest.raises(ValueError, match="rcs must be > 0"):
            PointTarget(position=[0.0, 0.0, 0.0], rcs=-5.0)

    def test_position_must_be_finite(self):
        with pytest.raises(ValueError, match="finite"):
            PointTarget(position=[np.inf, 0.0, 0.0], rcs=1.0)
        with pytest.raises(ValueError, match="finite"):
            PointTarget(position=[np.nan, 0.0, 0.0], rcs=1.0)

    def test_velocity_must_be_finite(self):
        with pytest.raises(ValueError, match="finite"):
            PointTarget(
                position=[0.0, 0.0, 0.0], rcs=1.0,
                velocity=[np.inf, 0.0, 0.0],
            )

    def test_default_rcs_model_is_static(self):
        """Default rcs_model is StaticRCS."""
        from pySimSAR.core.rcs_model import StaticRCS
        pt = PointTarget(position=[0.0, 0.0, 0.0], rcs=1.0)
        assert isinstance(pt.rcs_model, StaticRCS)

    def test_custom_rcs_model(self):
        """Custom rcs_model is stored correctly."""
        from pySimSAR.core.rcs_model import RCSModel
        class MockRCSModel(RCSModel):
            name = "mock"
            def apply(self, rcs, seed=None):
                return rcs * 2.0
        model = MockRCSModel()
        pt = PointTarget(position=[0.0, 0.0, 0.0], rcs=5.0, rcs_model=model)
        assert pt.rcs_model is model
        assert pt.rcs_model.apply(5.0) == 10.0


# ---------------------------------------------------------------------------
# DistributedTarget tests
# ---------------------------------------------------------------------------

class TestDistributedTarget:
    """Test DistributedTarget creation and grid dimension derivation."""

    def test_create_with_reflectivity(self):
        refl = np.ones((5, 10))
        dt = DistributedTarget(
            origin=np.array([0.0, 0.0, 0.0]),
            extent=np.array([100.0, 50.0]),
            cell_size=10.0,
            reflectivity=refl,
        )
        assert dt.nx == 10
        assert dt.ny == 5
        np.testing.assert_array_equal(dt.reflectivity, refl)

    def test_grid_dimensions_from_extent_and_cell_size(self):
        dt = DistributedTarget(
            origin=np.array([0.0, 0.0, 0.0]),
            extent=np.array([200.0, 100.0]),
            cell_size=20.0,
            reflectivity=np.zeros((5, 10)),
        )
        assert dt.nx == 10  # 200 / 20
        assert dt.ny == 5   # 100 / 20

    def test_optional_scattering_matrix(self):
        nx, ny = 4, 3
        smat = np.zeros((ny, nx, 2, 2), dtype=complex)
        dt = DistributedTarget(
            origin=np.array([0.0, 0.0, 0.0]),
            extent=np.array([40.0, 30.0]),
            cell_size=10.0,
            reflectivity=np.ones((ny, nx)),
            scattering_matrix=smat,
        )
        assert dt.scattering_matrix.shape == (ny, nx, 2, 2)

    def test_optional_elevation(self):
        nx, ny = 4, 3
        elev = np.random.default_rng(0).uniform(0, 10, (ny, nx))
        dt = DistributedTarget(
            origin=np.array([0.0, 0.0, 0.0]),
            extent=np.array([40.0, 30.0]),
            cell_size=10.0,
            reflectivity=np.ones((ny, nx)),
            elevation=elev,
        )
        np.testing.assert_array_equal(dt.elevation, elev)

    def test_with_clutter_model_no_reflectivity(self):
        clutter = UniformClutter(mean_intensity=2.0)
        dt = DistributedTarget(
            origin=np.array([0.0, 0.0, 0.0]),
            extent=np.array([40.0, 30.0]),
            cell_size=10.0,
            clutter_model=clutter,
        )
        assert dt.reflectivity is None
        assert dt.clutter_model is clutter

    def test_with_clutter_model_and_reflectivity(self):
        clutter = UniformClutter(mean_intensity=1.0)
        nx, ny = 4, 3
        dt = DistributedTarget(
            origin=np.array([0.0, 0.0, 0.0]),
            extent=np.array([40.0, 30.0]),
            cell_size=10.0,
            reflectivity=np.ones((ny, nx)),
            clutter_model=clutter,
        )
        assert dt.reflectivity is not None
        assert dt.clutter_model is clutter

    def test_extent_must_be_positive(self):
        with pytest.raises(ValueError, match="extent"):
            DistributedTarget(
                origin=np.array([0.0, 0.0, 0.0]),
                extent=np.array([0.0, 50.0]),
                cell_size=10.0,
                reflectivity=np.ones((5, 0)),
            )

    def test_cell_size_must_be_positive(self):
        with pytest.raises(ValueError, match="cell_size"):
            DistributedTarget(
                origin=np.array([0.0, 0.0, 0.0]),
                extent=np.array([100.0, 50.0]),
                cell_size=0.0,
                reflectivity=np.ones((5, 10)),
            )

    def test_reflectivity_shape_mismatch_raises(self):
        with pytest.raises(ValueError, match="reflectivity shape"):
            DistributedTarget(
                origin=np.array([0.0, 0.0, 0.0]),
                extent=np.array([100.0, 50.0]),
                cell_size=10.0,
                reflectivity=np.ones((3, 3)),  # should be (5, 10)
            )

    def test_no_reflectivity_no_clutter_raises(self):
        with pytest.raises(ValueError, match="reflectivity or clutter_model"):
            DistributedTarget(
                origin=np.array([0.0, 0.0, 0.0]),
                extent=np.array([100.0, 50.0]),
                cell_size=10.0,
            )

    def test_negative_reflectivity_raises(self):
        with pytest.raises(ValueError, match="reflectivity.*>= 0"):
            DistributedTarget(
                origin=np.array([0.0, 0.0, 0.0]),
                extent=np.array([100.0, 50.0]),
                cell_size=10.0,
                reflectivity=np.full((5, 10), -1.0),
            )


# ---------------------------------------------------------------------------
# Scene tests
# ---------------------------------------------------------------------------

class TestScene:
    """Test Scene creation and target management."""

    def test_create_scene(self):
        scene = Scene(origin_lat=40.0, origin_lon=-105.0, origin_alt=1600.0)
        assert scene.origin_lat == 40.0
        assert scene.origin_lon == -105.0
        assert scene.origin_alt == 1600.0
        assert scene.point_targets == []
        assert scene.distributed_targets == []

    def test_add_point_target(self):
        scene = Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=0.0)
        pt = PointTarget(position=np.array([0.0, 0.0, 0.0]), rcs=1.0)
        scene.add_target(pt)
        assert len(scene.point_targets) == 1
        assert scene.point_targets[0] is pt
        assert len(scene.distributed_targets) == 0

    def test_add_distributed_target(self):
        scene = Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=0.0)
        dt = DistributedTarget(
            origin=np.array([0.0, 0.0, 0.0]),
            extent=np.array([100.0, 50.0]),
            cell_size=10.0,
            reflectivity=np.ones((5, 10)),
        )
        scene.add_target(dt)
        assert len(scene.distributed_targets) == 1
        assert scene.distributed_targets[0] is dt
        assert len(scene.point_targets) == 0

    def test_add_invalid_target_raises(self):
        scene = Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=0.0)
        with pytest.raises(TypeError, match="PointTarget or DistributedTarget"):
            scene.add_target("not a target")

    def test_lat_out_of_range_raises(self):
        with pytest.raises(ValueError, match="origin_lat"):
            Scene(origin_lat=91.0, origin_lon=0.0, origin_alt=0.0)
        with pytest.raises(ValueError, match="origin_lat"):
            Scene(origin_lat=-91.0, origin_lon=0.0, origin_alt=0.0)

    def test_lon_out_of_range_raises(self):
        with pytest.raises(ValueError, match="origin_lon"):
            Scene(origin_lat=0.0, origin_lon=181.0, origin_alt=0.0)
        with pytest.raises(ValueError, match="origin_lon"):
            Scene(origin_lat=0.0, origin_lon=-181.0, origin_alt=0.0)

    def test_alt_non_finite_raises(self):
        with pytest.raises(ValueError, match="origin_alt"):
            Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=float("inf"))
        with pytest.raises(ValueError, match="origin_alt"):
            Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=float("nan"))

    def test_boundary_lat_lon_values(self):
        """Boundary values should be accepted."""
        scene = Scene(origin_lat=90.0, origin_lon=180.0, origin_alt=0.0)
        assert scene.origin_lat == 90.0
        assert scene.origin_lon == 180.0

        scene2 = Scene(origin_lat=-90.0, origin_lon=-180.0, origin_alt=0.0)
        assert scene2.origin_lat == -90.0
        assert scene2.origin_lon == -180.0


# ---------------------------------------------------------------------------
# UniformClutter tests
# ---------------------------------------------------------------------------

class TestUniformClutter:
    """Test UniformClutter model."""

    def test_generate_correct_shape(self):
        clutter = UniformClutter(mean_intensity=2.5)
        result = clutter.generate((3, 4))
        assert result.shape == (3, 4)

    def test_generate_all_values_equal_mean(self):
        clutter = UniformClutter(mean_intensity=3.7)
        result = clutter.generate((5, 6))
        np.testing.assert_array_equal(result, np.full((5, 6), 3.7))

    def test_generate_default_mean_intensity(self):
        clutter = UniformClutter()
        result = clutter.generate((2, 2))
        np.testing.assert_array_equal(result, np.ones((2, 2)))

    def test_seed_has_no_effect(self):
        """Uniform output is deterministic regardless of seed."""
        clutter = UniformClutter(mean_intensity=1.5)
        r1 = clutter.generate((3, 3), seed=42)
        r2 = clutter.generate((3, 3), seed=99)
        np.testing.assert_array_equal(r1, r2)

    def test_negative_mean_intensity_raises(self):
        with pytest.raises(ValueError, match="mean_intensity"):
            UniformClutter(mean_intensity=-1.0)

    def test_zero_mean_intensity_allowed(self):
        clutter = UniformClutter(mean_intensity=0.0)
        result = clutter.generate((2, 2))
        np.testing.assert_array_equal(result, np.zeros((2, 2)))

    def test_name_attribute(self):
        assert UniformClutter.name == "uniform"

    def test_registered_in_clutter_registry(self):
        from pySimSAR.clutter.registry import clutter_model_registry

        assert "uniform" in clutter_model_registry
        assert clutter_model_registry.get("uniform") is UniformClutter
