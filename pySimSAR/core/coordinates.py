"""ENU coordinate system and WGS84 geodetic transforms."""

from __future__ import annotations

import numpy as np

# WGS84 ellipsoid parameters
WGS84_A = 6378137.0  # Semi-major axis (m)
WGS84_F = 1.0 / 298.257223563  # Flattening
WGS84_B = WGS84_A * (1.0 - WGS84_F)  # Semi-minor axis (m)
WGS84_E2 = 2.0 * WGS84_F - WGS84_F**2  # First eccentricity squared


def geodetic_to_ecef(
    lat: float, lon: float, alt: float
) -> tuple[float, float, float]:
    """Convert geodetic (WGS84) to ECEF coordinates.

    Args:
        lat: Latitude in degrees.
        lon: Longitude in degrees.
        alt: Altitude above ellipsoid in meters.

    Returns:
        (x, y, z) in ECEF meters.
    """
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)

    sin_lat = np.sin(lat_rad)
    cos_lat = np.cos(lat_rad)
    sin_lon = np.sin(lon_rad)
    cos_lon = np.cos(lon_rad)

    n = WGS84_A / np.sqrt(1.0 - WGS84_E2 * sin_lat**2)

    x = (n + alt) * cos_lat * cos_lon
    y = (n + alt) * cos_lat * sin_lon
    z = (n * (1.0 - WGS84_E2) + alt) * sin_lat

    return x, y, z


def ecef_to_geodetic(
    x: float, y: float, z: float
) -> tuple[float, float, float]:
    """Convert ECEF to geodetic (WGS84) coordinates.

    Uses Bowring's iterative method.

    Args:
        x, y, z: ECEF coordinates in meters.

    Returns:
        (lat, lon, alt) with lat/lon in degrees, alt in meters.
    """
    lon = np.degrees(np.arctan2(y, x))

    p = np.sqrt(x**2 + y**2)
    theta = np.arctan2(z * WGS84_A, p * WGS84_B)

    lat_rad = np.arctan2(
        z + WGS84_E2 / (1.0 - WGS84_E2) * WGS84_B * np.sin(theta) ** 3,
        p - WGS84_E2 * WGS84_A * np.cos(theta) ** 3,
    )

    sin_lat = np.sin(lat_rad)
    n = WGS84_A / np.sqrt(1.0 - WGS84_E2 * sin_lat**2)
    alt = p / np.cos(lat_rad) - n

    lat = np.degrees(lat_rad)

    return lat, lon, alt


def ecef_to_enu_rotation(lat: float, lon: float) -> np.ndarray:
    """Compute the ECEF-to-ENU rotation matrix for a reference point.

    Args:
        lat: Reference latitude in degrees.
        lon: Reference longitude in degrees.

    Returns:
        3x3 rotation matrix (ENU = R @ ECEF_delta).
    """
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)

    sin_lat = np.sin(lat_rad)
    cos_lat = np.cos(lat_rad)
    sin_lon = np.sin(lon_rad)
    cos_lon = np.cos(lon_rad)

    r = np.array(
        [
            [-sin_lon, cos_lon, 0.0],
            [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
            [cos_lat * cos_lon, cos_lat * sin_lon, sin_lat],
        ]
    )
    return r


def geodetic_to_enu(
    lat: float,
    lon: float,
    alt: float,
    ref_lat: float,
    ref_lon: float,
    ref_alt: float,
) -> np.ndarray:
    """Convert geodetic (WGS84) to local ENU coordinates.

    Args:
        lat, lon, alt: Point coordinates (degrees, degrees, meters).
        ref_lat, ref_lon, ref_alt: ENU origin (degrees, degrees, meters).

    Returns:
        ENU coordinates as ndarray (3,) in meters [east, north, up].
    """
    x, y, z = geodetic_to_ecef(lat, lon, alt)
    x0, y0, z0 = geodetic_to_ecef(ref_lat, ref_lon, ref_alt)

    dx = np.array([x - x0, y - y0, z - z0])
    r = ecef_to_enu_rotation(ref_lat, ref_lon)

    return r @ dx


def enu_to_geodetic(
    enu: np.ndarray,
    ref_lat: float,
    ref_lon: float,
    ref_alt: float,
) -> tuple[float, float, float]:
    """Convert local ENU coordinates to geodetic (WGS84).

    Args:
        enu: ENU coordinates as ndarray (3,) in meters [east, north, up].
        ref_lat, ref_lon, ref_alt: ENU origin (degrees, degrees, meters).

    Returns:
        (lat, lon, alt) with lat/lon in degrees, alt in meters.
    """
    r = ecef_to_enu_rotation(ref_lat, ref_lon)
    dx = r.T @ enu

    x0, y0, z0 = geodetic_to_ecef(ref_lat, ref_lon, ref_alt)
    x = dx[0] + x0
    y = dx[1] + y0
    z = dx[2] + z0

    return ecef_to_geodetic(x, y, z)
