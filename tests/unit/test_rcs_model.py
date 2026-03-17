"""Unit tests for RCS model ABC and StaticRCS."""

import numpy as np
import pytest

from pySimSAR.core.rcs_model import RCSModel, StaticRCS


class TestRCSModelABC:
    """Tests for the RCSModel abstract base class."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            RCSModel()

    def test_static_rcs_is_rcs_model(self):
        model = StaticRCS()
        assert isinstance(model, RCSModel)

    def test_parameter_schema_returns_empty_dict(self):
        assert StaticRCS.parameter_schema() == {}


class TestStaticRCS:
    """Tests for the StaticRCS (non-fluctuating) model."""

    def test_name(self):
        assert StaticRCS.name == "static"
        assert StaticRCS().name == "static"

    def test_apply_scalar(self):
        model = StaticRCS()
        assert model.apply(10.0) == 10.0

    def test_apply_scalar_with_seed(self):
        model = StaticRCS()
        assert model.apply(5.0, seed=42) == 5.0

    def test_apply_scattering_matrix(self):
        model = StaticRCS()
        matrix = np.array([[1.0 + 0j, 0.1 + 0.05j], [0.1 - 0.05j, 0.3 + 0j]])
        result = model.apply(matrix)
        np.testing.assert_array_equal(result, matrix)

    def test_apply_preserves_type_scalar(self):
        model = StaticRCS()
        result = model.apply(7.5)
        assert isinstance(result, float)

    def test_apply_preserves_type_array(self):
        model = StaticRCS()
        matrix = np.eye(2, dtype=complex)
        result = model.apply(matrix)
        assert isinstance(result, np.ndarray)
