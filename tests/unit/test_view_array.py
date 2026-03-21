"""Unit tests for view_array CLI tool (T096x)."""

from __future__ import annotations

import numpy as np
import pytest

from pySimSAR.tools.view_array import (
    describe_array,
    load_array,
    main,
    parse_slice,
    plot_array,
)


class TestLoadArray:
    """Tests for load_array."""

    def test_load_npy(self, tmp_path):
        arr = np.array([1.0, 2.0, 3.0])
        np.save(str(tmp_path / "test.npy"), arr)
        result = load_array(str(tmp_path / "test.npy"))
        np.testing.assert_array_equal(result, arr)

    def test_load_npz_single_key(self, tmp_path):
        arr = np.array([1, 2, 3])
        np.savez(str(tmp_path / "test.npz"), data=arr)
        result = load_array(str(tmp_path / "test.npz"))
        np.testing.assert_array_equal(result, arr)

    def test_load_npz_with_key(self, tmp_path):
        a = np.array([1, 2])
        b = np.array([3, 4])
        np.savez(str(tmp_path / "test.npz"), a=a, b=b)
        result = load_array(str(tmp_path / "test.npz"), key="b")
        np.testing.assert_array_equal(result, b)

    def test_load_npz_multi_key_no_selection_raises(self, tmp_path):
        np.savez(str(tmp_path / "test.npz"), a=np.array([1]), b=np.array([2]))
        with pytest.raises(ValueError, match="multiple arrays"):
            load_array(str(tmp_path / "test.npz"))

    def test_load_npz_invalid_key(self, tmp_path):
        np.savez(str(tmp_path / "test.npz"), data=np.array([1]))
        with pytest.raises(KeyError, match="not found"):
            load_array(str(tmp_path / "test.npz"), key="bad")

    def test_load_csv(self, tmp_path):
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        np.savetxt(str(tmp_path / "test.csv"), arr, delimiter=",")
        result = load_array(str(tmp_path / "test.csv"))
        np.testing.assert_array_almost_equal(result, arr)

    def test_unsupported_format(self, tmp_path):
        (tmp_path / "test.xyz").write_text("data")
        with pytest.raises(ValueError, match="Unsupported"):
            load_array(str(tmp_path / "test.xyz"))


class TestDescribeArray:
    """Tests for describe_array."""

    def test_real_array(self):
        arr = np.array([1.0, 2.0, 3.0])
        desc = describe_array(arr)
        assert "Shape: (3,)" in desc
        assert "Range:" in desc
        assert "Mean:" in desc

    def test_complex_array(self):
        arr = np.array([1 + 2j, 3 + 4j])
        desc = describe_array(arr)
        assert "Magnitude range:" in desc
        assert "Phase range:" in desc


class TestParseSlice:
    """Tests for parse_slice."""

    def test_basic_slice(self):
        result = parse_slice("0,:,:", 3)
        assert result == (0, slice(None), slice(None))

    def test_range_slice(self):
        result = parse_slice("0:5,:", 2)
        assert result == (slice(0, 5), slice(None))

    def test_dimension_mismatch(self):
        with pytest.raises(ValueError, match="dimensions"):
            parse_slice("0,:", 3)


class TestPlotArray:
    """Tests for plot_array (non-interactive)."""

    def test_1d_save(self, tmp_path):
        arr = np.array([1.0, 2.0, 3.0, 4.0])
        save_path = str(tmp_path / "1d.png")
        plot_array(arr, save=save_path, no_show=True)
        assert (tmp_path / "1d.png").exists()

    def test_2d_real_save(self, tmp_path):
        arr = np.random.rand(10, 10)
        save_path = str(tmp_path / "2d.png")
        plot_array(arr, save=save_path, no_show=True)
        assert (tmp_path / "2d.png").exists()

    def test_2d_complex_save(self, tmp_path):
        arr = np.random.rand(10, 10) + 1j * np.random.rand(10, 10)
        save_path = str(tmp_path / "2d_complex.png")
        plot_array(arr, save=save_path, no_show=True)
        assert (tmp_path / "2d_complex.png").exists()

    def test_positions_scatter(self, tmp_path):
        arr = np.random.rand(20, 3)
        save_path = str(tmp_path / "positions.png")
        plot_array(arr, save=save_path, no_show=True, is_positions=True)
        assert (tmp_path / "positions.png").exists()


class TestMainCLI:
    """Tests for main() CLI entry point."""

    def test_npy_file(self, tmp_path):
        arr = np.array([1.0, 2.0, 3.0])
        np.save(str(tmp_path / "test.npy"), arr)
        save_path = str(tmp_path / "output.png")
        result = main([str(tmp_path / "test.npy"), "--save", save_path, "--no-show"])
        assert result == 0
        assert (tmp_path / "output.png").exists()

    def test_invalid_file(self, tmp_path):
        result = main([str(tmp_path / "nonexistent.npy"), "--no-show"])
        assert result == 1
