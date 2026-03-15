"""HDF5 read/write for PySimSAR data types.

Implements the data format contract defined in
specs/001-sar-signal-simulator/contracts/data-format.md.

All round-trip operations preserve bit-exact fidelity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import h5py
import numpy as np

from pySimSAR.core.types import RawData, PhaseHistoryData, SARImage

if TYPE_CHECKING:
    from pySimSAR.motion.trajectory import Trajectory
    from pySimSAR.sensors.nav_data import NavigationData

# Compression threshold in bytes (1 MB)
_COMPRESS_THRESHOLD = 1_000_000

_VERSION = "pySimSAR 0.1.0"


def _create_dataset(group: h5py.Group, name: str, data: np.ndarray) -> h5py.Dataset:
    """Create a dataset with optional gzip compression for large arrays."""
    nbytes = data.nbytes
    if nbytes > _COMPRESS_THRESHOLD:
        return group.create_dataset(name, data=data, compression="gzip",
                                    compression_opts=4)
    return group.create_dataset(name, data=data)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def write_hdf5(
    filepath: str | Path,
    *,
    raw_data: dict[str, RawData] | None = None,
    trajectory: object | None = None,
    navigation_data: list | None = None,
    images: dict[str, SARImage] | None = None,
    simulation_config_json: str | None = None,
    processing_config_json: str | None = None,
    origin_lat: float = 0.0,
    origin_lon: float = 0.0,
    origin_alt: float = 0.0,
) -> None:
    """Write PySimSAR data to HDF5 file.

    Parameters
    ----------
    filepath : str | Path
        Output HDF5 file path.
    raw_data : dict[str, RawData] | None
        Raw echo data keyed by channel name.
    trajectory : Trajectory | None
        Platform trajectory (ideal or true).
    navigation_data : list[NavigationData] | None
        Sensor measurements.
    images : dict[str, SARImage] | None
        Formed images keyed by name.
    simulation_config_json : str | None
        JSON-serialized SimulationConfig.
    processing_config_json : str | None
        JSON-serialized ProcessingConfig.
    origin_lat, origin_lon, origin_alt : float
        WGS84 origin coordinates for ENU reference.
    """
    filepath = Path(filepath)
    with h5py.File(filepath, "w") as f:
        # /metadata
        meta = f.create_group("metadata")
        meta.attrs["software_version"] = _VERSION
        meta.attrs["creation_date"] = datetime.now(timezone.utc).isoformat()
        meta.attrs["coordinate_system"] = "ENU"
        meta.attrs["origin_lat"] = origin_lat
        meta.attrs["origin_lon"] = origin_lon
        meta.attrs["origin_alt"] = origin_alt

        # /config
        cfg = f.create_group("config")
        if simulation_config_json is not None:
            cfg.attrs["simulation_config"] = simulation_config_json
        if processing_config_json is not None:
            cfg.attrs["processing_config"] = processing_config_json

        # /raw_data
        if raw_data:
            rd_grp = f.create_group("raw_data")
            for channel_name, rd in raw_data.items():
                ch_grp = rd_grp.create_group(channel_name)
                _create_dataset(ch_grp, "echo", rd.echo)
                ch_grp.attrs["carrier_freq"] = rd.carrier_freq
                ch_grp.attrs["bandwidth"] = rd.bandwidth
                ch_grp.attrs["prf"] = rd.prf
                ch_grp.attrs["sample_rate"] = rd.sample_rate
                ch_grp.attrs["waveform"] = rd.waveform_name
                ch_grp.attrs["sar_mode"] = rd.sar_mode
                ch_grp.attrs["polarization"] = rd.channel

        # /navigation
        if trajectory is not None or navigation_data:
            nav_grp = f.create_group("navigation")

            if trajectory is not None:
                _write_trajectory(nav_grp, trajectory)

            if navigation_data:
                for nav in navigation_data:
                    _write_navigation_sensor(nav_grp, nav)

        # /images
        if images:
            img_grp = f.create_group("images")
            for name, img in images.items():
                _write_image(img_grp, name, img)


def _write_trajectory(nav_grp: h5py.Group, traj: object) -> None:
    """Write trajectory data to the /navigation/trajectory group."""
    from pySimSAR.motion.trajectory import Trajectory

    if not isinstance(traj, Trajectory):
        return

    traj_grp = nav_grp.create_group("trajectory")
    _create_dataset(traj_grp, "time", traj.time)
    _create_dataset(traj_grp, "position", traj.position)
    _create_dataset(traj_grp, "velocity", traj.velocity)
    _create_dataset(traj_grp, "attitude", traj.attitude)


def _write_navigation_sensor(nav_grp: h5py.Group, nav: object) -> None:
    """Write a NavigationData sensor measurement to the appropriate group."""
    from pySimSAR.sensors.nav_data import NavigationData

    if not isinstance(nav, NavigationData):
        return

    source = nav.source
    if source in nav_grp:
        return  # already written (e.g., duplicate source)

    s_grp = nav_grp.create_group(source)
    _create_dataset(s_grp, "time", nav.time)

    if nav.position is not None:
        _create_dataset(s_grp, "position", nav.position)
    if nav.velocity is not None:
        _create_dataset(s_grp, "velocity", nav.velocity)
    if nav.acceleration is not None:
        _create_dataset(s_grp, "acceleration", nav.acceleration)
    if nav.angular_rate is not None:
        _create_dataset(s_grp, "angular_rate", nav.angular_rate)


def _write_image(img_grp: h5py.Group, name: str, img: SARImage) -> None:
    """Write a SARImage to the /images/{name} group."""
    grp = img_grp.create_group(name)
    _create_dataset(grp, "data", img.data)
    grp.attrs["algorithm"] = img.algorithm
    grp.attrs["pixel_spacing_range"] = img.pixel_spacing_range
    grp.attrs["pixel_spacing_azimuth"] = img.pixel_spacing_azimuth
    grp.attrs["geometry"] = img.geometry
    grp.attrs["polarization"] = img.channel
    if img.geo_transform is not None:
        grp.attrs["geo_transform"] = img.geo_transform
    if img.projection_wkt is not None:
        grp.attrs["projection_wkt"] = img.projection_wkt


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


def read_hdf5(filepath: str | Path) -> dict:
    """Read PySimSAR data from HDF5 file.

    Returns a dictionary with keys matching the file structure:
    - "metadata": dict of metadata attributes
    - "config": dict with "simulation_config" and/or "processing_config" JSON strings
    - "raw_data": dict[str, RawData] keyed by channel
    - "trajectory": Trajectory or None
    - "navigation_data": list[NavigationData]
    - "images": dict[str, SARImage] keyed by image name
    """
    filepath = Path(filepath)
    result: dict = {
        "metadata": {},
        "config": {},
        "raw_data": {},
        "trajectory": None,
        "navigation_data": [],
        "images": {},
    }

    with h5py.File(filepath, "r") as f:
        # /metadata
        if "metadata" in f:
            result["metadata"] = dict(f["metadata"].attrs)

        # /config
        if "config" in f:
            cfg = f["config"]
            if "simulation_config" in cfg.attrs:
                result["config"]["simulation_config"] = cfg.attrs[
                    "simulation_config"
                ]
            if "processing_config" in cfg.attrs:
                result["config"]["processing_config"] = cfg.attrs[
                    "processing_config"
                ]

        # /raw_data
        if "raw_data" in f:
            for ch_name in f["raw_data"]:
                ch_grp = f["raw_data"][ch_name]
                echo = ch_grp["echo"][:]
                result["raw_data"][ch_name] = RawData(
                    echo=echo,
                    channel=str(ch_grp.attrs["polarization"]),
                    sample_rate=float(ch_grp.attrs["sample_rate"]),
                    carrier_freq=float(ch_grp.attrs["carrier_freq"]),
                    bandwidth=float(ch_grp.attrs["bandwidth"]),
                    prf=float(ch_grp.attrs["prf"]),
                    waveform_name=str(ch_grp.attrs["waveform"]),
                    sar_mode=str(ch_grp.attrs["sar_mode"]),
                )

        # /navigation
        if "navigation" in f:
            nav = f["navigation"]
            if "trajectory" in nav:
                result["trajectory"] = _read_trajectory(nav["trajectory"])
            # Read sensor groups (gps, imu, fused)
            for key in nav:
                if key == "trajectory":
                    continue
                result["navigation_data"].append(
                    _read_navigation_sensor(nav[key], source=key)
                )

        # /images
        if "images" in f:
            for name in f["images"]:
                result["images"][name] = _read_image(f["images"][name])

    return result


def _read_trajectory(grp: h5py.Group):
    """Read a Trajectory from an HDF5 group."""
    from pySimSAR.motion.trajectory import Trajectory

    return Trajectory(
        time=grp["time"][:],
        position=grp["position"][:],
        velocity=grp["velocity"][:],
        attitude=grp["attitude"][:],
    )


def _read_navigation_sensor(grp: h5py.Group, source: str):
    """Read a NavigationData from an HDF5 group."""
    from pySimSAR.sensors.nav_data import NavigationData

    kwargs: dict = {
        "time": grp["time"][:],
        "source": source,
    }
    if "position" in grp:
        kwargs["position"] = grp["position"][:]
    if "velocity" in grp:
        kwargs["velocity"] = grp["velocity"][:]
    if "acceleration" in grp:
        kwargs["acceleration"] = grp["acceleration"][:]
    if "angular_rate" in grp:
        kwargs["angular_rate"] = grp["angular_rate"][:]

    return NavigationData(**kwargs)


def _read_image(grp: h5py.Group) -> SARImage:
    """Read a SARImage from an HDF5 group."""
    geo_transform = None
    if "geo_transform" in grp.attrs:
        geo_transform = np.array(grp.attrs["geo_transform"])

    projection_wkt = None
    if "projection_wkt" in grp.attrs:
        projection_wkt = str(grp.attrs["projection_wkt"])

    return SARImage(
        data=grp["data"][:],
        pixel_spacing_range=float(grp.attrs["pixel_spacing_range"]),
        pixel_spacing_azimuth=float(grp.attrs["pixel_spacing_azimuth"]),
        geometry=str(grp.attrs["geometry"]),
        algorithm=str(grp.attrs["algorithm"]),
        channel=str(grp.attrs["polarization"]),
        geo_transform=geo_transform,
        projection_wkt=projection_wkt,
    )


__all__ = ["write_hdf5", "read_hdf5"]
