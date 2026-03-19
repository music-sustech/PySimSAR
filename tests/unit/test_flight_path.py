"""Tests for flight path computation helper."""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from pySimSAR.core.flight_path import FlightPathResult, compute_flight_path


class TestModeAStartStop:
    """Mode A: start + stop positions."""

    def test_basic(self):
        result = compute_flight_path(
            start_position=[0, 0, 1000],
            stop_position=[0, 500, 1000],
            velocity=100,
        )
        assert isinstance(result, FlightPathResult)
        assert_allclose(result.heading, [0, 1, 0])
        assert result.distance == pytest.approx(500.0)
        assert result.flight_time == pytest.approx(5.0)

    def test_with_prf(self):
        result = compute_flight_path(
            start_position=[0, 0, 1000],
            stop_position=[0, 500, 1000],
            velocity=100,
            prf=1000,
        )
        assert_allclose(result.heading, [0, 1, 0])
        assert result.distance == pytest.approx(500.0)
        assert result.flight_time == pytest.approx(5.0)
        assert result.n_pulses == 5000


class TestModeBStartHeadingTime:
    """Mode B: start + heading + flight_time."""

    def test_basic(self):
        result = compute_flight_path(
            start_position=[0, 0, 1000],
            heading=[1, 0, 0],
            velocity=100,
            flight_time=10,
        )
        assert_allclose(result.stop_position, [1000, 0, 1000])
        assert result.distance == pytest.approx(1000.0)

    def test_with_prf(self):
        result = compute_flight_path(
            start_position=[0, 0, 1000],
            heading=[1, 0, 0],
            velocity=100,
            flight_time=10,
            prf=500,
        )
        assert_allclose(result.stop_position, [1000, 0, 1000])
        assert result.distance == pytest.approx(1000.0)
        assert result.n_pulses == 5000


class TestErrors:
    """Invalid inputs raise ValueError."""

    def test_zero_velocity(self):
        with pytest.raises(ValueError):
            compute_flight_path(
                start_position=[0, 0, 1000],
                stop_position=[0, 500, 1000],
                velocity=0,
            )

    def test_zero_distance(self):
        with pytest.raises(ValueError):
            compute_flight_path(
                start_position=[0, 0, 1000],
                stop_position=[0, 0, 1000],
                velocity=100,
            )

    def test_zero_heading(self):
        with pytest.raises(ValueError):
            compute_flight_path(
                start_position=[0, 0, 1000],
                heading=[0, 0, 0],
                velocity=100,
                flight_time=10,
            )

    def test_negative_flight_time(self):
        with pytest.raises(ValueError):
            compute_flight_path(
                start_position=[0, 0, 1000],
                heading=[1, 0, 0],
                velocity=100,
                flight_time=-5,
            )

    def test_ambiguous_inputs(self):
        with pytest.raises(ValueError):
            compute_flight_path(
                start_position=[0, 0, 1000],
                stop_position=[0, 500, 1000],
                heading=[1, 0, 0],
                velocity=100,
                flight_time=10,
            )

    def test_insufficient_inputs(self):
        with pytest.raises(ValueError):
            compute_flight_path(
                start_position=[0, 0, 1000],
                velocity=100,
            )
