"""Contract tests for all algorithm ABCs and registry extensibility.

Verifies that:
1. Each ABC enforces the required interface (cannot be instantiated directly)
2. Concrete mock implementations satisfy the contracts
3. Registry registration and lookup work for all algorithm types
4. Plugin extensibility: register a mock algorithm, verify it appears in
   registry and is callable without modifying existing code (SC-003)
"""

import numpy as np
import pytest

from pySimSAR.algorithms.base import (
    AlgorithmModeError,
    AutofocusAlgorithm,
    ImageFormationAlgorithm,
    ImageTransformationAlgorithm,
    MotionCompensationAlgorithm,
    PolarimetricDecomposition,
)
from pySimSAR.algorithms.registry import AlgorithmRegistry
from pySimSAR.clutter.base import ClutterModel
from pySimSAR.core.types import ImageGeometry, SARMode
from pySimSAR.sensors.gps import GPSErrorModel
from pySimSAR.sensors.imu import IMUErrorModel

# ---------------------------------------------------------------------------
# Mock implementations
# ---------------------------------------------------------------------------

class MockImageFormation(ImageFormationAlgorithm):
    name = "mock_rda"

    def process(self, raw_data, radar, trajectory):
        return {"data": np.ones((10, 10), dtype=complex)}

    def range_compress(self, raw_data, radar):
        return {"data": np.ones((10, 10), dtype=complex)}

    def azimuth_compress(self, phase_history, radar, trajectory):
        return {"data": np.ones((10, 10), dtype=complex)}

    def supported_modes(self):
        return [SARMode.STRIPMAP, SARMode.SPOTLIGHT]


class MockMoCo(MotionCompensationAlgorithm):
    name = "mock_moco"

    @property
    def order(self):
        return 1

    def compensate(self, raw_data, nav_data, reference_track):
        return raw_data


class MockAutofocus(AutofocusAlgorithm):
    name = "mock_pga"
    max_iterations = 5
    convergence_threshold = 0.02

    def focus(self, phase_history, azimuth_compressor):
        return {"data": np.ones((10, 10), dtype=complex)}

    def estimate_phase_error(self, phase_history):
        return np.zeros(10)


class MockGeoTransform(ImageTransformationAlgorithm):
    name = "mock_slant_to_ground"

    @property
    def output_geometry(self):
        return ImageGeometry.GROUND_RANGE

    def transform(self, image, radar, trajectory):
        return {"data": np.ones((10, 10)), "geometry": ImageGeometry.GROUND_RANGE}


class MockPolSAR(PolarimetricDecomposition):
    name = "mock_pauli"

    @property
    def n_components(self):
        return 3

    def decompose(self, image_hh, image_hv, image_vh, image_vv):
        self.validate_input(image_hh, image_hv, image_vh, image_vv)
        shape = (10, 10)
        return {
            "surface": np.ones(shape),
            "double_bounce": np.ones(shape),
            "volume": np.ones(shape),
        }


class MockClutter(ClutterModel):
    name = "mock_uniform"

    def generate(self, shape, seed=None):
        rng = np.random.default_rng(seed)
        return rng.uniform(0.5, 1.5, shape)


class MockGPSError(GPSErrorModel):
    name = "mock_gps_gaussian"

    def apply(self, true_positions, time, seed=None):
        rng = np.random.default_rng(seed)
        noise = rng.normal(0, 0.02, true_positions.shape)
        return true_positions + noise


class MockIMUError(IMUErrorModel):
    name = "mock_imu_white"

    def apply(self, true_acceleration, true_angular_rate, time, seed=None):
        rng = np.random.default_rng(seed)
        accel_noise = rng.normal(0, 0.001, true_acceleration.shape)
        gyro_noise = rng.normal(0, 1e-5, true_angular_rate.shape)
        return true_acceleration + accel_noise, true_angular_rate + gyro_noise


# ---------------------------------------------------------------------------
# ImageFormationAlgorithm contract
# ---------------------------------------------------------------------------

class TestImageFormationABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            ImageFormationAlgorithm()

    def test_concrete_implementation(self):
        algo = MockImageFormation()
        assert isinstance(algo, ImageFormationAlgorithm)
        assert algo.name == "mock_rda"

    def test_process_returns_result(self):
        algo = MockImageFormation()
        result = algo.process(None, None, None)
        assert "data" in result

    def test_two_step_pipeline(self):
        algo = MockImageFormation()
        phd = algo.range_compress(None, None)
        assert "data" in phd
        image = algo.azimuth_compress(phd, None, None)
        assert "data" in image

    def test_supported_modes(self):
        algo = MockImageFormation()
        modes = algo.supported_modes()
        assert SARMode.STRIPMAP in modes
        assert isinstance(modes, list)


class TestAlgorithmModeError:
    def test_is_exception(self):
        assert issubclass(AlgorithmModeError, Exception)

    def test_can_be_raised(self):
        with pytest.raises(AlgorithmModeError):
            raise AlgorithmModeError("SCANMAR not supported by RDA")


# ---------------------------------------------------------------------------
# MotionCompensationAlgorithm contract
# ---------------------------------------------------------------------------

class TestMotionCompensationABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            MotionCompensationAlgorithm()

    def test_concrete_implementation(self):
        algo = MockMoCo()
        assert algo.name == "mock_moco"
        assert algo.order == 1

    def test_compensate_returns_data(self):
        algo = MockMoCo()
        result = algo.compensate("raw", "nav", "ref")
        assert result == "raw"


# ---------------------------------------------------------------------------
# AutofocusAlgorithm contract
# ---------------------------------------------------------------------------

class TestAutofocusABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            AutofocusAlgorithm()

    def test_concrete_implementation(self):
        algo = MockAutofocus()
        assert algo.name == "mock_pga"
        assert algo.max_iterations == 5
        assert algo.convergence_threshold == 0.02

    def test_focus_returns_image(self):
        algo = MockAutofocus()
        result = algo.focus(None, None)
        assert "data" in result

    def test_estimate_phase_error(self):
        algo = MockAutofocus()
        error = algo.estimate_phase_error(None)
        assert isinstance(error, np.ndarray)

    def test_default_estimate_phase_error_raises(self):
        """ABC default estimate_phase_error raises NotImplementedError."""

        class MinimalAutofocus(AutofocusAlgorithm):
            name = "minimal"

            def focus(self, phase_history, azimuth_compressor):
                return {}

        algo = MinimalAutofocus()
        with pytest.raises(NotImplementedError):
            algo.estimate_phase_error(None)


# ---------------------------------------------------------------------------
# ImageTransformationAlgorithm contract
# ---------------------------------------------------------------------------

class TestImageTransformationABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            ImageTransformationAlgorithm()

    def test_concrete_implementation(self):
        algo = MockGeoTransform()
        assert algo.name == "mock_slant_to_ground"
        assert algo.output_geometry == ImageGeometry.GROUND_RANGE

    def test_transform_returns_image(self):
        algo = MockGeoTransform()
        result = algo.transform(None, None, None)
        assert "data" in result


# ---------------------------------------------------------------------------
# PolarimetricDecomposition contract
# ---------------------------------------------------------------------------

class TestPolarimetricDecompositionABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            PolarimetricDecomposition()

    def test_concrete_implementation(self):
        algo = MockPolSAR()
        assert algo.name == "mock_pauli"
        assert algo.n_components == 3

    def test_decompose_returns_components(self):
        algo = MockPolSAR()
        result = algo.decompose("hh", "hv", "vh", "vv")
        assert isinstance(result, dict)
        assert len(result) == 3
        assert "surface" in result

    def test_validate_input_rejects_none(self):
        algo = MockPolSAR()
        with pytest.raises(ValueError, match="Missing HV"):
            algo.validate_input("hh", None, "vh", "vv")


# ---------------------------------------------------------------------------
# ClutterModel contract
# ---------------------------------------------------------------------------

class TestClutterModelABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            ClutterModel()

    def test_generate_shape(self):
        model = MockClutter()
        result = model.generate((50, 50), seed=42)
        assert result.shape == (50, 50)

    def test_generate_non_negative(self):
        model = MockClutter()
        result = model.generate((100, 100), seed=42)
        assert np.all(result >= 0)

    def test_generate_reproducible(self):
        model = MockClutter()
        r1 = model.generate((10, 10), seed=42)
        r2 = model.generate((10, 10), seed=42)
        np.testing.assert_array_equal(r1, r2)


# ---------------------------------------------------------------------------
# GPSErrorModel contract
# ---------------------------------------------------------------------------

class TestGPSErrorModelABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            GPSErrorModel()

    def test_apply_returns_noisy_positions(self):
        model = MockGPSError()
        true_pos = np.array([[0, 0, 100], [10, 0, 100], [20, 0, 100]], dtype=float)
        time = np.array([0, 1, 2], dtype=float)
        noisy = model.apply(true_pos, time, seed=42)
        assert noisy.shape == true_pos.shape
        assert not np.array_equal(noisy, true_pos)

    def test_apply_reproducible(self):
        model = MockGPSError()
        true_pos = np.zeros((5, 3))
        time = np.arange(5, dtype=float)
        r1 = model.apply(true_pos, time, seed=42)
        r2 = model.apply(true_pos, time, seed=42)
        np.testing.assert_array_equal(r1, r2)


# ---------------------------------------------------------------------------
# IMUErrorModel contract
# ---------------------------------------------------------------------------

class TestIMUErrorModelABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            IMUErrorModel()

    def test_apply_returns_tuple(self):
        model = MockIMUError()
        true_accel = np.zeros((5, 3))
        true_gyro = np.zeros((5, 3))
        time = np.arange(5, dtype=float)
        noisy_accel, noisy_gyro = model.apply(true_accel, true_gyro, time, seed=42)
        assert noisy_accel.shape == true_accel.shape
        assert noisy_gyro.shape == true_gyro.shape

    def test_apply_reproducible(self):
        model = MockIMUError()
        true_accel = np.zeros((5, 3))
        true_gyro = np.zeros((5, 3))
        time = np.arange(5, dtype=float)
        a1, g1 = model.apply(true_accel, true_gyro, time, seed=42)
        a2, g2 = model.apply(true_accel, true_gyro, time, seed=42)
        np.testing.assert_array_equal(a1, a2)
        np.testing.assert_array_equal(g1, g2)


# ---------------------------------------------------------------------------
# Plugin extensibility (SC-003): register mock, verify callable
# ---------------------------------------------------------------------------

class TestPluginExtensibility:
    """Verify that custom algorithms can be registered and used without
    modifying any existing code (SC-003 success criterion)."""

    def test_register_custom_image_formation(self):
        registry = AlgorithmRegistry(ImageFormationAlgorithm, "image_formation")
        registry.register(MockImageFormation)

        cls = registry.get("mock_rda")
        algo = cls()
        result = algo.process(None, None, None)
        assert "data" in result

    def test_register_custom_moco(self):
        registry = AlgorithmRegistry(MotionCompensationAlgorithm, "moco")
        registry.register(MockMoCo)

        cls = registry.get("mock_moco")
        algo = cls()
        assert algo.order == 1

    def test_register_custom_autofocus(self):
        registry = AlgorithmRegistry(AutofocusAlgorithm, "autofocus")
        registry.register(MockAutofocus)

        cls = registry.get("mock_pga")
        algo = cls()
        result = algo.focus(None, None)
        assert "data" in result

    def test_register_custom_geocoding(self):
        registry = AlgorithmRegistry(ImageTransformationAlgorithm, "geocoding")
        registry.register(MockGeoTransform)

        cls = registry.get("mock_slant_to_ground")
        algo = cls()
        assert algo.output_geometry == ImageGeometry.GROUND_RANGE

    def test_register_custom_polsar(self):
        registry = AlgorithmRegistry(PolarimetricDecomposition, "polarimetry")
        registry.register(MockPolSAR)

        cls = registry.get("mock_pauli")
        algo = cls()
        assert algo.n_components == 3

    def test_register_custom_clutter(self):
        registry = AlgorithmRegistry(ClutterModel, "clutter")
        registry.register(MockClutter)

        cls = registry.get("mock_uniform")
        model = cls()
        result = model.generate((5, 5), seed=0)
        assert result.shape == (5, 5)

    def test_register_custom_gps_error(self):
        registry = AlgorithmRegistry(GPSErrorModel, "gps_error")
        registry.register(MockGPSError)

        cls = registry.get("mock_gps_gaussian")
        model = cls()
        pos = np.zeros((3, 3))
        result = model.apply(pos, np.arange(3, dtype=float), seed=0)
        assert result.shape == (3, 3)

    def test_register_custom_imu_error(self):
        registry = AlgorithmRegistry(IMUErrorModel, "imu_error")
        registry.register(MockIMUError)

        cls = registry.get("mock_imu_white")
        model = cls()
        accel, gyro = model.apply(
            np.zeros((3, 3)), np.zeros((3, 3)), np.arange(3, dtype=float)
        )
        assert accel.shape == (3, 3)

    def test_registry_rejects_wrong_type(self):
        """Cannot register a clutter model in an image formation registry."""
        registry = AlgorithmRegistry(ImageFormationAlgorithm, "image_formation")
        with pytest.raises(TypeError, match="subclass"):
            registry.register(MockClutter)

    def test_multiple_algorithms_coexist(self):
        """Multiple algorithms can be registered and independently retrieved."""
        registry = AlgorithmRegistry(ImageFormationAlgorithm, "image_formation")
        registry.register(MockImageFormation)

        class AnotherAlgo(ImageFormationAlgorithm):
            name = "another_rda"

            def process(self, raw_data, radar, trajectory):
                return {}

            def range_compress(self, raw_data, radar):
                return {}

            def azimuth_compress(self, phase_history, radar, trajectory):
                return {}

            def supported_modes(self):
                return [SARMode.STRIPMAP]

        registry.register(AnotherAlgo)
        assert len(registry) == 2
        assert set(registry.list()) == {"mock_rda", "another_rda"}
