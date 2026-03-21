"""Unit tests for GaussianGPSError and GPSSensor (T050)."""

from __future__ import annotations

import numpy as np
import pytest


class TestGaussianGPSError:
    """Tests for GaussianGPSError model."""

    def test_create_gaussian_gps(self):
        """GaussianGPSError stores accuracy_rms."""
        from pySimSAR.sensors.gps_gaussian import GaussianGPSError

        model = GaussianGPSError(accuracy_rms=0.02)
        assert model.accuracy_rms == 0.02
        assert model.name == "gaussian"

    def test_gaussian_gps_generates_noisy_positions(self):
        """Apply adds noise to true positions."""
        from pySimSAR.sensors.gps_gaussian import GaussianGPSError

        model = GaussianGPSError(accuracy_rms=1.0)
        n = 1000
        true_pos = np.zeros((n, 3))
        time = np.linspace(0, 1, n)

        noisy = model.apply(true_pos, time, seed=42)

        assert noisy.shape == (n, 3)
        # Noise should be non-zero
        assert np.any(noisy != 0.0)

    def test_gaussian_gps_rms_matches_config(self):
        """Error RMS should match configured accuracy within 10%."""
        from pySimSAR.sensors.gps_gaussian import GaussianGPSError

        accuracy_rms = 0.5
        model = GaussianGPSError(accuracy_rms=accuracy_rms)
        n = 50000
        true_pos = np.zeros((n, 3))
        time = np.linspace(0, 10, n)

        noisy = model.apply(true_pos, time, seed=42)
        errors = noisy - true_pos

        # Per-axis RMS should match accuracy_rms within 10%
        for axis in range(3):
            rms = np.sqrt(np.mean(errors[:, axis] ** 2))
            assert abs(rms - accuracy_rms) / accuracy_rms < 0.1, (
                f"Axis {axis}: RMS={rms:.4f}, expected ~{accuracy_rms}"
            )

    def test_gaussian_gps_reproducible(self):
        """Same seed gives identical results."""
        from pySimSAR.sensors.gps_gaussian import GaussianGPSError

        model = GaussianGPSError(accuracy_rms=1.0)
        true_pos = np.random.default_rng(0).standard_normal((100, 3))
        time = np.linspace(0, 1, 100)

        r1 = model.apply(true_pos, time, seed=42)
        r2 = model.apply(true_pos, time, seed=42)
        np.testing.assert_array_equal(r1, r2)

    def test_gaussian_gps_validation(self):
        """accuracy_rms must be positive."""
        from pySimSAR.sensors.gps_gaussian import GaussianGPSError

        with pytest.raises(ValueError, match="accuracy_rms"):
            GaussianGPSError(accuracy_rms=-0.1)
        with pytest.raises(ValueError, match="accuracy_rms"):
            GaussianGPSError(accuracy_rms=0.0)

    def test_gaussian_gps_registered(self):
        """GaussianGPSError is in the GPS error registry."""
        from pySimSAR.sensors.registry import gps_error_registry

        assert "gaussian" in gps_error_registry.list()


class TestGPSSensor:
    """Tests for GPSSensor configuration."""

    def test_create_gps_sensor(self):
        """GPSSensor stores config parameters."""
        from pySimSAR.sensors.gps import GPSSensor
        from pySimSAR.sensors.gps_gaussian import GaussianGPSError

        error_model = GaussianGPSError(accuracy_rms=0.02)
        sensor = GPSSensor(
            accuracy_rms=0.02,
            update_rate=10.0,
            error_model=error_model,
        )
        assert sensor.accuracy_rms == 0.02
        assert sensor.update_rate == 10.0
        assert sensor.error_model is error_model
        assert sensor.outage_intervals == []

    def test_gps_sensor_with_outages(self):
        """GPSSensor can have outage intervals."""
        from pySimSAR.sensors.gps import GPSSensor
        from pySimSAR.sensors.gps_gaussian import GaussianGPSError

        sensor = GPSSensor(
            accuracy_rms=0.5,
            update_rate=10.0,
            error_model=GaussianGPSError(accuracy_rms=0.5),
            outage_intervals=[(1.0, 2.0), (5.0, 5.5)],
        )
        assert len(sensor.outage_intervals) == 2

    def test_gps_sensor_generate_measurements(self):
        """GPSSensor generates measurements at its update rate."""
        from pySimSAR.motion.trajectory import Trajectory
        from pySimSAR.sensors.gps import GPSSensor
        from pySimSAR.sensors.gps_gaussian import GaussianGPSError

        n = 1000
        t = np.linspace(0, 1, n)
        pos = np.column_stack([t * 100, np.zeros(n), np.full(n, 2000.0)])
        vel = np.column_stack([np.full(n, 100.0), np.zeros(n), np.zeros(n)])
        att = np.zeros((n, 3))
        traj = Trajectory(time=t, position=pos, velocity=vel, attitude=att)

        sensor = GPSSensor(
            accuracy_rms=0.5,
            update_rate=10.0,
            error_model=GaussianGPSError(accuracy_rms=0.5),
        )

        nav_data = sensor.generate_measurements(traj, seed=42)

        # Should have ~10 measurements (10 Hz for 1 second)
        assert nav_data.source == "gps"
        assert nav_data.position is not None
        expected_n = int(1.0 * 10.0) + 1  # approximately
        assert abs(len(nav_data.time) - expected_n) <= 1

    def test_gps_sensor_outage_masks_data(self):
        """During outage intervals, GPS produces no measurements."""
        from pySimSAR.motion.trajectory import Trajectory
        from pySimSAR.sensors.gps import GPSSensor
        from pySimSAR.sensors.gps_gaussian import GaussianGPSError

        n = 10000
        t = np.linspace(0, 10, n)
        pos = np.zeros((n, 3))
        vel = np.zeros((n, 3))
        att = np.zeros((n, 3))
        traj = Trajectory(time=t, position=pos, velocity=vel, attitude=att)

        sensor = GPSSensor(
            accuracy_rms=0.5,
            update_rate=10.0,
            error_model=GaussianGPSError(accuracy_rms=0.5),
            outage_intervals=[(2.0, 4.0)],
        )

        nav_data = sensor.generate_measurements(traj, seed=42)

        # No measurements in [2.0, 4.0]
        in_outage = (nav_data.time >= 2.0) & (nav_data.time <= 4.0)
        assert not np.any(in_outage), "Should have no measurements during outage"
