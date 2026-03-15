"""Unit tests for WhiteNoiseIMUError and IMUSensor (T051)."""

from __future__ import annotations

import numpy as np
import pytest


class TestWhiteNoiseIMUError:
    """Tests for WhiteNoiseIMUError model."""

    def test_create_white_noise_imu(self):
        """WhiteNoiseIMUError stores noise density params."""
        from pySimSAR.sensors.imu_white_noise import WhiteNoiseIMUError

        model = WhiteNoiseIMUError(
            accel_noise_density=0.0002,
            gyro_noise_density=5e-6,
        )
        assert model.accel_noise_density == 0.0002
        assert model.gyro_noise_density == 5e-6
        assert model.name == "white_noise"

    def test_white_noise_imu_generates_noisy_output(self):
        """Apply adds noise to true acceleration and angular rate."""
        from pySimSAR.sensors.imu_white_noise import WhiteNoiseIMUError

        model = WhiteNoiseIMUError(
            accel_noise_density=0.01,
            gyro_noise_density=0.001,
        )
        n = 1000
        true_accel = np.zeros((n, 3))
        true_gyro = np.zeros((n, 3))
        time = np.linspace(0, 1, n)

        noisy_accel, noisy_gyro = model.apply(
            true_accel, true_gyro, time, seed=42
        )

        assert noisy_accel.shape == (n, 3)
        assert noisy_gyro.shape == (n, 3)
        assert np.any(noisy_accel != 0.0)
        assert np.any(noisy_gyro != 0.0)

    def test_white_noise_imu_noise_density_matching(self):
        """Noise RMS should match noise_density * sqrt(sample_rate) within 10%."""
        from pySimSAR.sensors.imu_white_noise import WhiteNoiseIMUError

        accel_nd = 0.01  # m/s^2/sqrt(Hz)
        gyro_nd = 0.001  # rad/s/sqrt(Hz)
        sample_rate = 200.0  # Hz

        model = WhiteNoiseIMUError(
            accel_noise_density=accel_nd,
            gyro_noise_density=gyro_nd,
        )

        n = 100000
        true_accel = np.zeros((n, 3))
        true_gyro = np.zeros((n, 3))
        time = np.arange(n) / sample_rate

        noisy_accel, noisy_gyro = model.apply(
            true_accel, true_gyro, time, seed=42
        )

        # Expected RMS = noise_density * sqrt(sample_rate)
        expected_accel_rms = accel_nd * np.sqrt(sample_rate)
        expected_gyro_rms = gyro_nd * np.sqrt(sample_rate)

        accel_errors = noisy_accel - true_accel
        gyro_errors = noisy_gyro - true_gyro

        for axis in range(3):
            accel_rms = np.sqrt(np.mean(accel_errors[:, axis] ** 2))
            gyro_rms = np.sqrt(np.mean(gyro_errors[:, axis] ** 2))

            assert abs(accel_rms - expected_accel_rms) / expected_accel_rms < 0.1, (
                f"Accel axis {axis}: RMS={accel_rms:.6f}, expected ~{expected_accel_rms:.6f}"
            )
            assert abs(gyro_rms - expected_gyro_rms) / expected_gyro_rms < 0.1, (
                f"Gyro axis {axis}: RMS={gyro_rms:.6f}, expected ~{expected_gyro_rms:.6f}"
            )

    def test_white_noise_imu_reproducible(self):
        """Same seed gives identical results."""
        from pySimSAR.sensors.imu_white_noise import WhiteNoiseIMUError

        model = WhiteNoiseIMUError(accel_noise_density=0.01, gyro_noise_density=0.001)
        true_accel = np.ones((50, 3))
        true_gyro = np.ones((50, 3)) * 0.1
        time = np.linspace(0, 0.5, 50)

        r1 = model.apply(true_accel, true_gyro, time, seed=42)
        r2 = model.apply(true_accel, true_gyro, time, seed=42)
        np.testing.assert_array_equal(r1[0], r2[0])
        np.testing.assert_array_equal(r1[1], r2[1])

    def test_white_noise_imu_validation(self):
        """Noise densities must be non-negative."""
        from pySimSAR.sensors.imu_white_noise import WhiteNoiseIMUError

        with pytest.raises(ValueError):
            WhiteNoiseIMUError(accel_noise_density=-0.01, gyro_noise_density=0.001)
        with pytest.raises(ValueError):
            WhiteNoiseIMUError(accel_noise_density=0.01, gyro_noise_density=-0.001)

    def test_white_noise_imu_registered(self):
        """WhiteNoiseIMUError is in the IMU error registry."""
        from pySimSAR.sensors.registry import imu_error_registry

        assert "white_noise" in imu_error_registry.list()


class TestIMUSensor:
    """Tests for IMUSensor configuration."""

    def test_create_imu_sensor(self):
        """IMUSensor stores config parameters."""
        from pySimSAR.sensors.imu_white_noise import WhiteNoiseIMUError
        from pySimSAR.sensors.imu import IMUSensor

        error_model = WhiteNoiseIMUError(
            accel_noise_density=0.0002,
            gyro_noise_density=5e-6,
        )
        sensor = IMUSensor(
            accel_noise_density=0.0002,
            gyro_noise_density=5e-6,
            sample_rate=200.0,
            error_model=error_model,
        )
        assert sensor.accel_noise_density == 0.0002
        assert sensor.gyro_noise_density == 5e-6
        assert sensor.sample_rate == 200.0
        assert sensor.error_model is error_model

    def test_imu_sensor_generate_measurements(self):
        """IMUSensor generates measurements at its sample rate."""
        from pySimSAR.sensors.imu_white_noise import WhiteNoiseIMUError
        from pySimSAR.sensors.imu import IMUSensor
        from pySimSAR.motion.trajectory import Trajectory

        n = 1000
        t = np.linspace(0, 1, n)
        pos = np.column_stack([t * 100, np.zeros(n), np.full(n, 2000.0)])
        vel = np.column_stack([np.full(n, 100.0), np.zeros(n), np.zeros(n)])
        att = np.zeros((n, 3))
        traj = Trajectory(time=t, position=pos, velocity=vel, attitude=att)

        sensor = IMUSensor(
            accel_noise_density=0.0002,
            gyro_noise_density=5e-6,
            sample_rate=200.0,
            error_model=WhiteNoiseIMUError(
                accel_noise_density=0.0002,
                gyro_noise_density=5e-6,
            ),
        )

        nav_data = sensor.generate_measurements(traj, seed=42)

        assert nav_data.source == "imu"
        assert nav_data.acceleration is not None
        assert nav_data.angular_rate is not None
        # ~200 measurements for 1 second at 200 Hz
        expected_n = int(1.0 * 200.0) + 1
        assert abs(len(nav_data.time) - expected_n) <= 1
