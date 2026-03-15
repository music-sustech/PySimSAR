"""Unit tests for Platform, Trajectory, and DrydenTurbulence (T047-T049)."""

from __future__ import annotations

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# T047: Platform unit tests
# ---------------------------------------------------------------------------

class TestPlatform:
    """Tests for Platform configuration and nominal path generation."""

    def test_create_basic_platform(self):
        """Platform stores velocity, altitude, heading, start position."""
        from pySimSAR.core.platform import Platform

        p = Platform(
            velocity=100.0,
            altitude=2000.0,
            heading=0.0,
            start_position=np.array([0.0, -5000.0, 2000.0]),
        )
        assert p.velocity == 100.0
        assert p.altitude == 2000.0
        assert p.heading == 0.0
        np.testing.assert_array_equal(
            p.start_position, [0.0, -5000.0, 2000.0]
        )

    def test_platform_defaults(self):
        """Platform has sensible defaults for optional fields."""
        from pySimSAR.core.platform import Platform

        p = Platform(velocity=50.0, altitude=1000.0)
        assert p.heading == 0.0
        np.testing.assert_array_equal(p.start_position, [0.0, 0.0, 1000.0])
        assert p.perturbation is None
        assert p.sensors == []

    def test_platform_validation_velocity(self):
        """Velocity must be positive."""
        from pySimSAR.core.platform import Platform

        with pytest.raises(ValueError, match="velocity"):
            Platform(velocity=-10.0, altitude=1000.0)
        with pytest.raises(ValueError, match="velocity"):
            Platform(velocity=0.0, altitude=1000.0)

    def test_platform_validation_altitude(self):
        """Altitude must be positive."""
        from pySimSAR.core.platform import Platform

        with pytest.raises(ValueError, match="altitude"):
            Platform(velocity=100.0, altitude=-500.0)

    def test_platform_heading_wrapping(self):
        """Heading should be stored in [0, 2pi)."""
        from pySimSAR.core.platform import Platform

        p = Platform(velocity=100.0, altitude=1000.0, heading=3 * np.pi)
        assert 0.0 <= p.heading < 2 * np.pi
        assert np.isclose(p.heading, np.pi)

    def test_platform_sensor_attachment(self):
        """Can attach GPS and IMU sensors to platform."""
        from pySimSAR.core.platform import Platform
        from pySimSAR.sensors.gps import GPSErrorModel
        from pySimSAR.sensors.imu import IMUErrorModel

        p = Platform(velocity=100.0, altitude=2000.0)
        # Just verify the sensors list works (actual sensor classes tested later)
        assert isinstance(p.sensors, list)
        assert len(p.sensors) == 0

    def test_platform_with_perturbation(self):
        """Platform can hold a MotionPerturbation."""
        from pySimSAR.core.platform import Platform
        from pySimSAR.motion.perturbation import DrydenTurbulence

        turb = DrydenTurbulence(sigma_u=1.0, sigma_v=1.0, sigma_w=0.5)
        p = Platform(
            velocity=100.0,
            altitude=2000.0,
            perturbation=turb,
        )
        assert p.perturbation is turb

    def test_platform_generate_ideal_trajectory(self):
        """Platform generates ideal (straight-line) trajectory."""
        from pySimSAR.core.platform import Platform
        from pySimSAR.motion.trajectory import Trajectory

        p = Platform(
            velocity=100.0,
            altitude=2000.0,
            heading=0.0,  # North
            start_position=np.array([0.0, 0.0, 2000.0]),
        )
        traj = p.generate_ideal_trajectory(n_pulses=100, prf=1000.0)

        assert isinstance(traj, Trajectory)
        assert traj.time.shape == (100,)
        assert traj.position.shape == (100, 3)
        assert traj.velocity.shape == (100, 3)
        assert traj.attitude.shape == (100, 3)

        # Check times are PRI-spaced
        dt = np.diff(traj.time)
        np.testing.assert_allclose(dt, 1.0 / 1000.0, rtol=1e-12)

        # Check heading=0 means movement in North (y) direction
        # Velocity should be [0, 100, 0] for north heading
        np.testing.assert_allclose(traj.velocity[0], [0.0, 100.0, 0.0], atol=1e-10)

        # Position should advance in y
        assert traj.position[-1, 1] > traj.position[0, 1]

    def test_platform_ideal_trajectory_heading_east(self):
        """Heading=pi/2 means East (positive x)."""
        from pySimSAR.core.platform import Platform

        p = Platform(
            velocity=100.0,
            altitude=2000.0,
            heading=np.pi / 2,  # East
            start_position=np.array([0.0, 0.0, 2000.0]),
        )
        traj = p.generate_ideal_trajectory(n_pulses=50, prf=500.0)

        # Velocity should be [100, 0, 0] for east heading
        np.testing.assert_allclose(traj.velocity[0], [100.0, 0.0, 0.0], atol=1e-10)

    def test_platform_ideal_trajectory_constant_altitude(self):
        """Ideal trajectory maintains constant altitude."""
        from pySimSAR.core.platform import Platform

        p = Platform(velocity=100.0, altitude=3000.0)
        traj = p.generate_ideal_trajectory(n_pulses=200, prf=1000.0)

        np.testing.assert_allclose(traj.position[:, 2], 3000.0, atol=1e-10)


# ---------------------------------------------------------------------------
# T048: DrydenTurbulence unit tests
# ---------------------------------------------------------------------------

class TestDrydenTurbulence:
    """Tests for Dryden wind turbulence model."""

    def test_create_dryden(self):
        """DrydenTurbulence stores sigma parameters."""
        from pySimSAR.motion.perturbation import DrydenTurbulence

        d = DrydenTurbulence(sigma_u=2.0, sigma_v=2.0, sigma_w=1.0)
        assert d.sigma_u == 2.0
        assert d.sigma_v == 2.0
        assert d.sigma_w == 1.0

    def test_dryden_generates_perturbation(self):
        """DrydenTurbulence generates 3D velocity perturbation arrays."""
        from pySimSAR.motion.perturbation import DrydenTurbulence

        d = DrydenTurbulence(sigma_u=2.0, sigma_v=2.0, sigma_w=1.0)
        n_samples = 1000
        dt = 0.001  # 1 ms
        velocity = 100.0
        altitude = 2000.0

        perturbation = d.generate(
            n_samples=n_samples,
            dt=dt,
            velocity=velocity,
            altitude=altitude,
            seed=42,
        )

        assert perturbation.shape == (n_samples, 3)
        assert perturbation.dtype == np.float64

    def test_dryden_rms_matches_sigma(self):
        """Generated turbulence RMS should approximately match sigma values.

        Note: Dryden turbulence has long correlation times (~L/V seconds),
        so many independent samples are needed for accurate RMS estimation.
        We use 500k samples (500s) which provides ~50 correlation times.
        """
        from pySimSAR.motion.perturbation import DrydenTurbulence

        sigma_u, sigma_v, sigma_w = 2.0, 2.0, 1.0
        d = DrydenTurbulence(sigma_u=sigma_u, sigma_v=sigma_v, sigma_w=sigma_w)

        perturbation = d.generate(
            n_samples=500000,
            dt=0.001,
            velocity=100.0,
            altitude=2000.0,
            seed=42,
        )

        # RMS should match within ~20% with sufficient samples
        rms_u = np.std(perturbation[:, 0])
        rms_v = np.std(perturbation[:, 1])
        rms_w = np.std(perturbation[:, 2])

        assert abs(rms_u - sigma_u) / sigma_u < 0.2
        assert abs(rms_v - sigma_v) / sigma_v < 0.2
        assert abs(rms_w - sigma_w) / sigma_w < 0.2

    def test_dryden_spectral_shape(self):
        """Dryden turbulence should have coloured (non-white) spectrum."""
        from pySimSAR.motion.perturbation import DrydenTurbulence

        d = DrydenTurbulence(sigma_u=2.0, sigma_v=2.0, sigma_w=1.0)
        perturbation = d.generate(
            n_samples=8192,
            dt=0.001,
            velocity=100.0,
            altitude=2000.0,
            seed=42,
        )

        # PSD should not be flat (i.e., it's coloured noise)
        from scipy import signal as sig
        f, psd = sig.welch(perturbation[:, 0], fs=1000.0, nperseg=1024)
        # Low frequencies should have more power than high frequencies
        low_power = np.mean(psd[1:10])
        high_power = np.mean(psd[-10:])
        assert low_power > high_power

    def test_dryden_zero_sigma_gives_zero(self):
        """Zero turbulence intensity gives zero perturbation."""
        from pySimSAR.motion.perturbation import DrydenTurbulence

        d = DrydenTurbulence(sigma_u=0.0, sigma_v=0.0, sigma_w=0.0)
        perturbation = d.generate(
            n_samples=100, dt=0.001, velocity=100.0, altitude=2000.0, seed=42
        )
        np.testing.assert_array_equal(perturbation, 0.0)

    def test_dryden_reproducible_with_seed(self):
        """Same seed produces identical output."""
        from pySimSAR.motion.perturbation import DrydenTurbulence

        d = DrydenTurbulence(sigma_u=2.0, sigma_v=2.0, sigma_w=1.0)
        kwargs = dict(n_samples=500, dt=0.001, velocity=100.0, altitude=2000.0)

        p1 = d.generate(**kwargs, seed=123)
        p2 = d.generate(**kwargs, seed=123)
        np.testing.assert_array_equal(p1, p2)

    def test_dryden_validation(self):
        """Sigma values must be non-negative."""
        from pySimSAR.motion.perturbation import DrydenTurbulence

        with pytest.raises(ValueError):
            DrydenTurbulence(sigma_u=-1.0, sigma_v=1.0, sigma_w=1.0)


# ---------------------------------------------------------------------------
# T049: Trajectory unit tests
# ---------------------------------------------------------------------------

class TestTrajectory:
    """Tests for Trajectory data class."""

    def test_create_trajectory(self):
        """Trajectory stores time, position, velocity, attitude arrays."""
        from pySimSAR.motion.trajectory import Trajectory

        n = 100
        t = np.linspace(0, 1, n)
        pos = np.zeros((n, 3))
        vel = np.ones((n, 3))
        att = np.zeros((n, 3))

        traj = Trajectory(time=t, position=pos, velocity=vel, attitude=att)

        assert traj.time.shape == (n,)
        assert traj.position.shape == (n, 3)
        assert traj.velocity.shape == (n, 3)
        assert traj.attitude.shape == (n, 3)

    def test_trajectory_validation_shapes(self):
        """All arrays must have consistent lengths."""
        from pySimSAR.motion.trajectory import Trajectory

        with pytest.raises(ValueError, match="consistent"):
            Trajectory(
                time=np.zeros(10),
                position=np.zeros((11, 3)),
                velocity=np.zeros((10, 3)),
                attitude=np.zeros((10, 3)),
            )

    def test_trajectory_time_monotonic(self):
        """Time array must be monotonically increasing."""
        from pySimSAR.motion.trajectory import Trajectory

        with pytest.raises(ValueError, match="monotonic"):
            Trajectory(
                time=np.array([0.0, 0.5, 0.3, 1.0]),
                position=np.zeros((4, 3)),
                velocity=np.zeros((4, 3)),
                attitude=np.zeros((4, 3)),
            )

    def test_trajectory_interpolate(self):
        """Trajectory can interpolate position at arbitrary times."""
        from pySimSAR.motion.trajectory import Trajectory

        n = 100
        t = np.linspace(0, 1, n)
        pos = np.column_stack([t * 100.0, t * 200.0, np.full(n, 2000.0)])
        vel = np.column_stack([
            np.full(n, 100.0), np.full(n, 200.0), np.zeros(n)
        ])
        att = np.zeros((n, 3))

        traj = Trajectory(time=t, position=pos, velocity=vel, attitude=att)

        # Interpolate at midpoint
        t_query = 0.5
        pos_interp = traj.interpolate_position(t_query)
        np.testing.assert_allclose(pos_interp, [50.0, 100.0, 2000.0], atol=0.5)

    def test_trajectory_perturbed_differs_from_ideal(self):
        """Perturbed trajectory positions differ from ideal."""
        from pySimSAR.core.platform import Platform
        from pySimSAR.motion.perturbation import DrydenTurbulence

        turb = DrydenTurbulence(sigma_u=2.0, sigma_v=2.0, sigma_w=1.0)
        p = Platform(
            velocity=100.0,
            altitude=2000.0,
            heading=0.0,
            start_position=np.array([0.0, 0.0, 2000.0]),
            perturbation=turb,
        )

        ideal = p.generate_ideal_trajectory(n_pulses=256, prf=1000.0)
        perturbed = p.generate_perturbed_trajectory(
            n_pulses=256, prf=1000.0, seed=42
        )

        # Positions should differ
        diff = np.linalg.norm(perturbed.position - ideal.position, axis=1)
        assert np.max(diff) > 0.0

    def test_trajectory_no_perturbation_matches_ideal(self):
        """Without perturbation model, perturbed equals ideal."""
        from pySimSAR.core.platform import Platform

        p = Platform(
            velocity=100.0,
            altitude=2000.0,
            heading=0.0,
            start_position=np.array([0.0, 0.0, 2000.0]),
        )

        ideal = p.generate_ideal_trajectory(n_pulses=100, prf=1000.0)
        perturbed = p.generate_perturbed_trajectory(
            n_pulses=100, prf=1000.0, seed=42
        )

        np.testing.assert_array_equal(perturbed.position, ideal.position)
        np.testing.assert_array_equal(perturbed.velocity, ideal.velocity)
