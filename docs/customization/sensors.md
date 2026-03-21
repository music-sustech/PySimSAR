# Custom Sensors

PySimSAR models navigation sensors (GPS, IMU) through abstract error model
classes. Custom error models can be created and attached to a Platform to
control how navigation measurement errors flow into motion compensation.

## Sensor architecture

The sensor system has three layers:

1. **Error model** (abstract): defines how noise is applied to true data.
2. **Sensor configuration**: wraps an error model with hardware parameters
   (accuracy, update rate) and generates `NavigationData`.
3. **Platform attachment**: sensors are listed in `Platform.sensors` and
   produce navigation data during simulation.

Navigation errors affect the MoCo pipeline:

```
True trajectory --> Sensor.generate_measurements() --> NavigationData
                                                          |
                                                          v
                                    MoCo algorithm uses noisy nav data
                                    to estimate and correct phase errors
```

## GPSErrorModel interface

Located in `pySimSAR.sensors.gps`.

```python
class GPSErrorModel(ABC):
    name: str = ""

    @abstractmethod
    def apply(
        self,
        true_positions: np.ndarray,   # shape (n_samples, 3), ENU meters
        time: np.ndarray,             # shape (n_samples,), seconds
        seed: int | None = None,
    ) -> np.ndarray:
        """Return noisy GPS positions, shape (n_samples, 3)."""
```

The `apply()` method receives the true platform positions in ENU coordinates
and must return position measurements with realistic errors added.

## IMUErrorModel interface

Located in `pySimSAR.sensors.imu`.

```python
class IMUErrorModel(ABC):
    name: str = ""

    @abstractmethod
    def apply(
        self,
        true_acceleration: np.ndarray,   # shape (n_samples, 3), m/s^2
        true_angular_rate: np.ndarray,   # shape (n_samples, 3), rad/s
        time: np.ndarray,                # shape (n_samples,), seconds
        seed: int | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return (noisy_acceleration, noisy_angular_rate)."""
```

## Step-by-step: create a custom GPS error model

This example creates a GPS model with time-correlated (random walk) errors.

### 1. Subclass GPSErrorModel

```python
import numpy as np
from pySimSAR.sensors.gps import GPSErrorModel


class RandomWalkGPSError(GPSErrorModel):
    """GPS error model with random walk position drift.

    Parameters
    ----------
    drift_rate : float
        Position drift rate in m/sqrt(s).
    white_noise_std : float
        White noise standard deviation in meters per axis.
    """

    name = "random_walk"

    def __init__(self, drift_rate: float = 0.1, white_noise_std: float = 1.0):
        self.drift_rate = drift_rate
        self.white_noise_std = white_noise_std

    def apply(
        self,
        true_positions: np.ndarray,
        time: np.ndarray,
        seed: int | None = None,
    ) -> np.ndarray:
        rng = np.random.default_rng(seed)
        n = len(time)

        # White noise component
        white = rng.normal(0, self.white_noise_std, size=(n, 3))

        # Random walk component (integrated white noise)
        dt = np.diff(time, prepend=time[0])
        walk_increments = rng.normal(0, self.drift_rate, size=(n, 3)) * np.sqrt(dt[:, None])
        walk = np.cumsum(walk_increments, axis=0)

        return true_positions + white + walk
```

### 2. Wrap in a GPSSensor

```python
from pySimSAR.sensors.gps import GPSSensor

gps = GPSSensor(
    accuracy_rms=2.0,          # meters
    update_rate=10.0,          # Hz
    error_model=RandomWalkGPSError(drift_rate=0.05, white_noise_std=1.5),
    outage_intervals=[(5.0, 6.0)],  # GPS blackout from t=5s to t=6s
)
```

### 3. Attach to Platform

```python
from pySimSAR.core.platform import Platform

platform = Platform(
    velocity=100.0,
    altitude=2000.0,
    heading=0.0,
    sensors=[gps],
)
```

### 4. Use in simulation

```python
from pySimSAR import SimulationEngine, Scene, PointTarget, Radar
import numpy as np

scene = Scene(origin_lat=0.0, origin_lon=0.0, origin_alt=0.0)
scene.add_target(PointTarget(position=np.array([5000.0, 0.0, 0.0]), rcs=1.0))

engine = SimulationEngine(
    scene=scene,
    radar=radar,        # previously configured
    n_pulses=256,
    platform=platform,
)
result = engine.run()

# Navigation data is available in the result
print(result.navigation_data)  # list of NavigationData objects
```

## GPSSensor configuration

| Parameter | Type | Default | Description |
|---|---|---|---|
| `accuracy_rms` | `float` | (required) | Position accuracy RMS in meters. Must be > 0. |
| `update_rate` | `float` | (required) | Output rate in Hz. Must be > 0. |
| `error_model` | `GPSErrorModel` | (required) | Error generation model. |
| `outage_intervals` | `list[tuple[float, float]] \| None` | `None` | Time intervals with no GPS output. Each tuple is (start_s, end_s). |

Key method: `generate_measurements(trajectory, seed=None) -> NavigationData`

## IMUSensor configuration

| Parameter | Type | Default | Description |
|---|---|---|---|
| `accel_noise_density` | `float` | (required) | Accelerometer noise density (VRW) in m/s^2/sqrt(Hz). Must be >= 0. |
| `gyro_noise_density` | `float` | (required) | Gyroscope noise density (ARW) in rad/s/sqrt(Hz). Must be >= 0. |
| `sample_rate` | `float` | (required) | IMU output rate in Hz. Must be > 0. |
| `error_model` | `IMUErrorModel` | (required) | Error generation model. |

Key method: `generate_measurements(trajectory, seed=None) -> NavigationData`

## How navigation errors flow into MoCo

When a `Platform` with sensors is used:

1. **SimulationEngine** calls `platform.generate_perturbed_trajectory()` to
   create the true (noisy) platform trajectory.
2. For each attached sensor, `sensor.generate_measurements(true_trajectory)`
   produces a `NavigationData` object with noisy measurements.
3. The `NavigationData` list is stored in `SimulationResult.navigation_data`.
4. During processing, `PipelineRunner` passes the navigation data to the
   motion compensation algorithm.
5. The MoCo algorithm (e.g., `FirstOrderMoCo`) uses the GPS positions to
   fit a reference track and compute per-pulse phase corrections.
6. Residual errors after MoCo can be corrected by autofocus algorithms
   (PGA, MDA, MEA, PPP).

GPS sensors provide position data (used by MoCo for phase correction).
IMU sensors provide acceleration and angular rate data (reserved for future
GPS/INS fusion). Currently, only GPS-based MoCo is implemented; IMU data
is recorded but not consumed by the MoCo pipeline.
