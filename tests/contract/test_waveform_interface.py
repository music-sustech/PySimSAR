"""Contract tests for the Waveform interface.

Verifies that:
1. Waveform ABC enforces the required interface
2. Concrete implementations satisfy generate() and range_compress()
3. Waveform properties work correctly
4. Duration derivation from duty_cycle / prf is correct
5. Phase noise and window are optional
6. Registry integration works
"""

import numpy as np
import pytest

from pySimSAR.algorithms.registry import AlgorithmRegistry
from pySimSAR.waveforms.base import Waveform
from pySimSAR.waveforms.phase_noise import PhaseNoiseModel

# ---------------------------------------------------------------------------
# Mock implementations for contract testing
# ---------------------------------------------------------------------------

class MockWaveform(Waveform):
    """Minimal concrete waveform for testing the ABC contract."""

    name = "mock_waveform"

    def generate(self, prf: float, sample_rate: float) -> np.ndarray:
        n_samples = int(self.duration(prf) * sample_rate)
        t = np.arange(n_samples) / sample_rate
        return np.exp(1j * np.pi * self.bandwidth / self.duration(prf) * t**2)

    def range_compress(
        self, echo: np.ndarray, prf: float, sample_rate: float
    ) -> np.ndarray:
        ref = self.generate(prf, sample_rate)
        if echo.ndim == 1:
            n = max(len(echo), len(ref))
            return np.fft.ifft(np.fft.fft(echo, n) * np.conj(np.fft.fft(ref, n)))
        # 2D: compress each pulse
        n = max(echo.shape[1], len(ref))
        ref_fft = np.conj(np.fft.fft(ref, n))
        return np.fft.ifft(np.fft.fft(echo, n, axis=1) * ref_fft, axis=1)


class MockPhaseNoise(PhaseNoiseModel):
    """Minimal phase noise model for testing."""

    name = "mock_phase_noise"

    def generate(
        self, n_samples: int, sample_rate: float, seed: int | None = None
    ) -> np.ndarray:
        rng = np.random.default_rng(seed)
        return rng.normal(0, 0.01, n_samples)


# ---------------------------------------------------------------------------
# Contract: Waveform ABC enforcement
# ---------------------------------------------------------------------------

class TestWaveformABC:
    """Test that the Waveform ABC enforces the required interface."""

    def test_cannot_instantiate_abc_directly(self):
        with pytest.raises(TypeError):
            Waveform(bandwidth=100e6, duty_cycle=0.1)

    def test_must_implement_generate(self):
        class IncompleteWaveform(Waveform):
            name = "incomplete"

            def range_compress(self, echo, prf, sample_rate):
                return echo

        with pytest.raises(TypeError):
            IncompleteWaveform(bandwidth=100e6, duty_cycle=0.1)

    def test_must_implement_range_compress(self):
        class IncompleteWaveform(Waveform):
            name = "incomplete"

            def generate(self, prf, sample_rate):
                return np.array([1.0])

        with pytest.raises(TypeError):
            IncompleteWaveform(bandwidth=100e6, duty_cycle=0.1)

    def test_concrete_implementation_instantiates(self):
        wf = MockWaveform(bandwidth=100e6, duty_cycle=0.1)
        assert isinstance(wf, Waveform)


# ---------------------------------------------------------------------------
# Contract: Waveform properties
# ---------------------------------------------------------------------------

class TestWaveformProperties:
    """Test waveform property access and validation."""

    def test_bandwidth_property(self):
        wf = MockWaveform(bandwidth=150e6, duty_cycle=0.1)
        assert wf.bandwidth == 150e6

    def test_duty_cycle_property(self):
        wf = MockWaveform(bandwidth=150e6, duty_cycle=0.25)
        assert wf.duty_cycle == 0.25

    def test_bandwidth_must_be_positive(self):
        with pytest.raises(ValueError, match="bandwidth"):
            MockWaveform(bandwidth=0, duty_cycle=0.1)

        with pytest.raises(ValueError, match="bandwidth"):
            MockWaveform(bandwidth=-100e6, duty_cycle=0.1)

    def test_duty_cycle_bounds(self):
        with pytest.raises(ValueError, match="duty_cycle"):
            MockWaveform(bandwidth=100e6, duty_cycle=0)

        with pytest.raises(ValueError, match="duty_cycle"):
            MockWaveform(bandwidth=100e6, duty_cycle=1.5)

        # Edge: duty_cycle=1.0 is valid (continuous wave)
        wf = MockWaveform(bandwidth=100e6, duty_cycle=1.0)
        assert wf.duty_cycle == 1.0

    def test_duration_derivation(self):
        """Duration = duty_cycle / prf (key design decision)."""
        wf = MockWaveform(bandwidth=100e6, duty_cycle=0.1)
        prf = 1000.0
        assert wf.duration(prf) == pytest.approx(0.1 / 1000.0)

    def test_duration_prf_must_be_positive(self):
        wf = MockWaveform(bandwidth=100e6, duty_cycle=0.1)
        with pytest.raises(ValueError, match="prf"):
            wf.duration(0)

    def test_phase_noise_optional(self):
        wf = MockWaveform(bandwidth=100e6, duty_cycle=0.1)
        assert wf.phase_noise is None

        pn = MockPhaseNoise()
        wf_with_pn = MockWaveform(bandwidth=100e6, duty_cycle=0.1, phase_noise=pn)
        assert wf_with_pn.phase_noise is pn

    def test_window_optional(self):
        wf = MockWaveform(bandwidth=100e6, duty_cycle=0.1)
        assert wf.window is None

        wf_with_win = MockWaveform(bandwidth=100e6, duty_cycle=0.1, window=np.hamming)
        assert wf_with_win.window is np.hamming


# ---------------------------------------------------------------------------
# Contract: generate() output
# ---------------------------------------------------------------------------

class TestWaveformGenerate:
    """Test the generate() method contract."""

    def test_generate_returns_complex_array(self):
        wf = MockWaveform(bandwidth=100e6, duty_cycle=0.1)
        signal = wf.generate(prf=1000.0, sample_rate=200e6)
        assert isinstance(signal, np.ndarray)
        assert np.iscomplexobj(signal)

    def test_generate_output_length(self):
        wf = MockWaveform(bandwidth=100e6, duty_cycle=0.1)
        prf = 1000.0
        sample_rate = 200e6
        signal = wf.generate(prf=prf, sample_rate=sample_rate)
        expected_samples = int(wf.duration(prf) * sample_rate)
        assert len(signal) == expected_samples

    def test_generate_is_1d(self):
        wf = MockWaveform(bandwidth=100e6, duty_cycle=0.1)
        signal = wf.generate(prf=1000.0, sample_rate=200e6)
        assert signal.ndim == 1


# ---------------------------------------------------------------------------
# Contract: range_compress() behavior
# ---------------------------------------------------------------------------

class TestWaveformRangeCompress:
    """Test the range_compress() method contract."""

    def test_range_compress_1d(self):
        wf = MockWaveform(bandwidth=100e6, duty_cycle=0.1)
        prf = 1000.0
        sample_rate = 200e6
        echo = wf.generate(prf=prf, sample_rate=sample_rate)
        result = wf.range_compress(echo, prf=prf, sample_rate=sample_rate)
        assert isinstance(result, np.ndarray)
        assert result.ndim == 1

    def test_range_compress_2d(self):
        wf = MockWaveform(bandwidth=100e6, duty_cycle=0.1)
        prf = 1000.0
        sample_rate = 200e6
        signal = wf.generate(prf=prf, sample_rate=sample_rate)
        # Simulate 4 pulses
        echo = np.tile(signal, (4, 1))
        result = wf.range_compress(echo, prf=prf, sample_rate=sample_rate)
        assert result.ndim == 2
        assert result.shape[0] == 4


# ---------------------------------------------------------------------------
# Contract: PhaseNoiseModel ABC
# ---------------------------------------------------------------------------

class TestPhaseNoiseModelABC:
    """Test the PhaseNoiseModel ABC contract."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            PhaseNoiseModel()

    def test_generate_returns_real_array(self):
        pn = MockPhaseNoise()
        samples = pn.generate(n_samples=1000, sample_rate=200e6, seed=42)
        assert isinstance(samples, np.ndarray)
        assert samples.shape == (1000,)
        assert not np.iscomplexobj(samples)

    def test_generate_reproducible_with_seed(self):
        pn = MockPhaseNoise()
        s1 = pn.generate(n_samples=100, sample_rate=200e6, seed=42)
        s2 = pn.generate(n_samples=100, sample_rate=200e6, seed=42)
        np.testing.assert_array_equal(s1, s2)


# ---------------------------------------------------------------------------
# Contract: Registry integration
# ---------------------------------------------------------------------------

class TestWaveformRegistryIntegration:
    """Test that waveforms can be registered and looked up."""

    def test_register_and_retrieve(self):
        registry = AlgorithmRegistry(Waveform, "test_waveform")
        registry.register(MockWaveform)
        assert "mock_waveform" in registry
        assert registry.get("mock_waveform") is MockWaveform

    def test_register_rejects_non_subclass(self):
        registry = AlgorithmRegistry(Waveform, "test_waveform")
        with pytest.raises(TypeError):
            registry.register(int)

    def test_register_rejects_duplicate(self):
        registry = AlgorithmRegistry(Waveform, "test_waveform")
        registry.register(MockWaveform)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(MockWaveform)

    def test_get_unknown_raises_keyerror(self):
        registry = AlgorithmRegistry(Waveform, "test_waveform")
        with pytest.raises(KeyError, match="Unknown"):
            registry.get("nonexistent")

    def test_list_returns_sorted_names(self):
        registry = AlgorithmRegistry(Waveform, "test_waveform")
        registry.register(MockWaveform)
        assert registry.list() == ["mock_waveform"]

    def test_registry_as_decorator(self):
        registry = AlgorithmRegistry(Waveform, "test_waveform")

        @registry.register
        class DecoratedWaveform(Waveform):
            name = "decorated"

            def generate(self, prf, sample_rate):
                return np.array([1.0 + 0j])

            def range_compress(self, echo, prf, sample_rate):
                return echo

        assert "decorated" in registry
        assert registry.get("decorated") is DecoratedWaveform

    def test_phase_noise_registry(self):
        registry = AlgorithmRegistry(PhaseNoiseModel, "test_phase_noise")
        registry.register(MockPhaseNoise)
        assert "mock_phase_noise" in registry
