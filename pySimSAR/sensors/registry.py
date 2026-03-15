"""Sensor error model registries."""

from pySimSAR.algorithms.registry import AlgorithmRegistry
from pySimSAR.sensors.gps import GPSErrorModel
from pySimSAR.sensors.imu import IMUErrorModel

gps_error_registry = AlgorithmRegistry(GPSErrorModel, "gps_error")
imu_error_registry = AlgorithmRegistry(IMUErrorModel, "imu_error")

__all__ = ["gps_error_registry", "imu_error_registry"]
