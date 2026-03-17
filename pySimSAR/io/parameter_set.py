"""Parameter set I/O: load, build, and save simulation configurations.

A parameter set is a project directory containing JSON files and binary data
that together define a complete SAR simulation and processing setup.
"""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

import numpy as np

# Unit suffixes that get stripped on load (key renamed, value unchanged)
_UNIT_SUFFIXES = ("_hz", "_m", "_mps", "_dB", "_dBc", "_K", "_w", "_m2")

# Geographic coordinate keys that are NOT converted from degrees
_GEO_KEYS = {"origin_lat_deg", "origin_lon_deg"}


def _preset_dir() -> Path:
    """Return the path to the shipped presets directory."""
    return Path(__file__).resolve().parent.parent / "presets"


def resolve_refs(
    data: dict | list,
    base_dir: Path,
    _visited: set[str] | None = None,
) -> dict | list:
    """Recursively resolve all $ref and $data entries in a nested structure.

    Parameters
    ----------
    data : dict | list
        Parsed JSON structure.
    base_dir : Path
        Directory for resolving relative paths.

    Returns
    -------
    dict | list
        Resolved structure with $ref/$data replaced by their contents.
    """
    if _visited is None:
        _visited = set()

    if isinstance(data, list):
        return [
            resolve_refs(item, base_dir, _visited) if isinstance(item, (dict, list)) else item
            for item in data
        ]

    if not isinstance(data, dict):
        return data

    # Handle $ref
    if "$ref" in data:
        if len(data) > 1:
            raise ValueError(
                f"$ref must be the only key in an object, but found sibling keys: "
                f"{sorted(k for k in data if k != '$ref')}"
            )
        ref_path_str = data["$ref"]

        # Resolve $preset prefix
        if ref_path_str.startswith("$preset/"):
            ref_path = _preset_dir() / ref_path_str[len("$preset/"):]
        else:
            ref_path = (base_dir / ref_path_str).resolve()

        canonical = str(ref_path)
        if canonical in _visited:
            raise ValueError(f"Circular $ref detected: {canonical}")
        _visited.add(canonical)

        with open(ref_path, "r", encoding="utf-8") as f:
            ref_data = json.load(f)

        resolved = resolve_refs(ref_data, ref_path.parent, _visited)
        _visited.discard(canonical)
        return resolved

    # Handle $data
    if "$data" in data:
        if len(data) > 1:
            raise ValueError(
                f"$data must be the only key in an object, but found sibling keys: "
                f"{sorted(k for k in data if k != '$data')}"
            )
        data_path_str = data["$data"]
        data_path = (base_dir / data_path_str).resolve()
        suffix = data_path.suffix.lower()

        if suffix == ".npy":
            return np.load(str(data_path), allow_pickle=False)
        elif suffix == ".npz":
            npz = np.load(str(data_path), allow_pickle=False)
            return dict(npz)
        elif suffix == ".csv":
            return np.loadtxt(str(data_path), delimiter=",")
        else:
            raise ValueError(f"Unsupported $data format: {suffix}")

    # Recurse into dict values
    result = {}
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            result[key] = resolve_refs(value, base_dir, _visited)
        else:
            result[key] = value

    return result


def _strip_unit_suffix(key: str) -> tuple[str, bool]:
    """Strip unit suffix from a key, returning (stripped_key, is_degree).

    Returns
    -------
    tuple[str, bool]
        (stripped key name, True if _deg suffix was stripped)
    """
    if key.endswith("_deg"):
        return key[:-4], True
    for suffix in _UNIT_SUFFIXES:
        if key.endswith(suffix):
            return key[: -len(suffix)], False
    return key, False


def _convert_units(data: dict, parent_key: str = "") -> dict:
    """Strip unit suffixes from keys and convert degrees to radians.

    Geographic coordinates (origin_lat_deg, origin_lon_deg) are stripped
    but NOT converted to radians.
    """
    result = {}
    for key, value in data.items():
        full_key = f"{parent_key}.{key}" if parent_key else key

        if isinstance(value, dict) and "$ref" not in value and "$data" not in value:
            result[key] = _convert_units(value, full_key)
            continue

        stripped, is_deg = _strip_unit_suffix(key)

        if is_deg and key not in _GEO_KEYS:
            # Convert degrees to radians
            if isinstance(value, (int, float)):
                result[stripped] = np.radians(value)
            else:
                result[stripped] = value
        elif stripped != key:
            result[stripped] = value
        else:
            result[key] = value

    return result


def load_parameter_set(project_path: str | Path) -> dict:
    """Load a parameter set from a project directory.

    Reads project.json, resolves all $ref and $data entries, converts units,
    and returns the fully resolved parameter dictionary.

    Parameters
    ----------
    project_path : str | Path
        Path to project directory (containing project.json) or to a
        project.json file directly.

    Returns
    -------
    dict
        Fully resolved parameter dictionary.
    """
    project_path = Path(project_path)

    if project_path.is_file():
        project_file = project_path
        base_dir = project_path.parent
    else:
        project_file = project_path / "project.json"
        base_dir = project_path

    with open(project_file, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Validate format version
    version = raw.get("format_version")
    if version is None:
        raise ValueError("project.json must include 'format_version'")

    # Resolve all references
    resolved = resolve_refs(raw, base_dir)

    # Convert units (strip suffixes, deg->rad)
    converted = _convert_units(resolved)

    return converted


def _make_window(window_name: str | None, window_params: dict | None = None):
    """Create a window function callable from a name string."""
    if window_name is None or window_name.lower() == "none":
        return None

    name = window_name.lower()
    params = window_params or {}

    if name == "hamming":
        return lambda n: np.hamming(n)
    elif name == "hanning":
        return lambda n: np.hanning(n)
    elif name == "blackman":
        return lambda n: np.blackman(n)
    elif name == "kaiser":
        beta = params.get("beta")
        if beta is None:
            raise ValueError("Kaiser window requires 'beta' parameter")
        return lambda n, _b=beta: np.kaiser(n, _b)
    elif name == "tukey":
        from scipy.signal.windows import tukey
        alpha = params.get("alpha", 0.5)
        return lambda n, _a=alpha: tukey(n, _a)
    else:
        raise ValueError(f"Unknown window function: {window_name!r}")


def build_simulation(params: dict) -> dict:
    """Construct simulation objects from a resolved parameter dictionary.

    Parameters
    ----------
    params : dict
        Resolved parameter dictionary from load_parameter_set().

    Returns
    -------
    dict
        Keys: 'scene', 'radar', 'platform', 'engine_kwargs', 'processing_config'.
    """
    from pySimSAR.core.platform import Platform
    from pySimSAR.core.radar import Radar, create_antenna_from_preset, AntennaPattern
    from pySimSAR.core.rcs_model import StaticRCS
    from pySimSAR.core.scene import DistributedTarget, PointTarget, Scene
    from pySimSAR.core.types import SARMode
    from pySimSAR.io.config import ProcessingConfig
    from pySimSAR.waveforms.lfm import LFMWaveform
    from pySimSAR.waveforms.fmcw import FMCWWaveform

    # --- Scene ---
    scene_params = params.get("scene", {})
    origin_lat = scene_params.get("origin_lat", scene_params.get("origin_lat_deg", 0.0))
    origin_lon = scene_params.get("origin_lon", scene_params.get("origin_lon_deg", 0.0))
    origin_alt = scene_params.get("origin_alt", 0.0)
    scene = Scene(origin_lat=origin_lat, origin_lon=origin_lon, origin_alt=origin_alt)

    # Inline point targets
    for pt_data in scene_params.get("point_targets", []):
        pos = np.asarray(pt_data.get("position", pt_data.get("position_m", [0, 0, 0])), dtype=float)
        rcs_raw = pt_data.get("rcs", pt_data.get("rcs_m2", 1.0))
        rcs = _parse_rcs(rcs_raw)
        vel_raw = pt_data.get("velocity", pt_data.get("velocity_mps"))
        velocity = np.asarray(vel_raw, dtype=float) if vel_raw is not None else None
        rcs_model = _parse_rcs_model(pt_data.get("rcs_model"))
        scene.add_target(PointTarget(position=pos, rcs=rcs, velocity=velocity, rcs_model=rcs_model))

    # File-based point targets
    pt_file = scene_params.get("point_targets_file")
    if pt_file:
        positions = pt_file.get("positions")
        rcs_arr = pt_file.get("rcs")
        velocities = pt_file.get("velocities")
        rcs_models_data = pt_file.get("rcs_models")

        if positions is not None:
            n = len(positions)
            for i in range(n):
                pos = np.asarray(positions[i], dtype=float)
                rcs = _parse_rcs(rcs_arr[i] if rcs_arr is not None else 1.0)
                vel = np.asarray(velocities[i], dtype=float) if velocities is not None else None
                rm = _parse_rcs_model(rcs_models_data[i] if rcs_models_data is not None else None)
                scene.add_target(PointTarget(position=pos, rcs=rcs, velocity=vel, rcs_model=rm))

    # Distributed targets
    for dt_data in scene_params.get("distributed_targets", []):
        origin = np.asarray(dt_data.get("origin", dt_data.get("origin_m", [0, 0, 0])), dtype=float)
        extent = np.asarray(dt_data.get("extent", dt_data.get("extent_m", [100, 100])), dtype=float)
        cell_size = float(dt_data.get("cell_size", dt_data.get("cell_size_m", 1.0)))
        reflectivity = dt_data.get("reflectivity")
        if isinstance(reflectivity, np.ndarray):
            pass
        elif reflectivity is not None:
            reflectivity = np.asarray(reflectivity, dtype=float)
        scattering_matrix = dt_data.get("scattering_matrix")
        elevation = dt_data.get("elevation")
        if isinstance(elevation, np.ndarray):
            pass
        elif elevation is not None:
            elevation = np.asarray(elevation, dtype=float)

        clutter_model = None
        cm_data = dt_data.get("clutter_model")
        if cm_data is not None:
            clutter_model = _build_clutter_model(cm_data)

        scene.add_target(DistributedTarget(
            origin=origin, extent=extent, cell_size=cell_size,
            reflectivity=reflectivity, scattering_matrix=scattering_matrix,
            elevation=elevation, clutter_model=clutter_model,
        ))

    # --- Waveform ---
    radar_params = params.get("radar", {})
    wf_data = radar_params.get("waveform", {})
    waveform = _build_waveform(wf_data)

    # --- Antenna ---
    ant_data = radar_params.get("antenna", {})
    antenna = _build_antenna(ant_data)

    # --- Radar ---
    mode_str = radar_params.get("mode", "stripmap")
    # Accept "scansar" as alias for "scanmar"
    if mode_str.lower() == "scansar":
        mode_str = "scanmar"

    radar = Radar(
        carrier_freq=radar_params.get("carrier_freq", 9.65e9),
        prf=radar_params.get("prf", 1000.0),
        transmit_power=radar_params.get("transmit_power", 1000.0),
        waveform=waveform,
        antenna=antenna,
        polarization=radar_params.get("polarization", "single"),
        mode=mode_str,
        look_side=radar_params.get("look_side", "right"),
        depression_angle=radar_params.get("depression_angle", np.radians(45.0)),
        noise_figure=radar_params.get("noise_figure", 3.0),
        system_losses=radar_params.get("system_losses", 2.0),
        reference_temp=radar_params.get("reference_temp", 290.0),
        squint_angle=radar_params.get("squint_angle", 0.0),
        receiver_gain_dB=radar_params.get("receiver_gain", 0.0),
    )

    # --- Platform ---
    plat_data = params.get("platform", {})
    platform = _build_platform(plat_data)

    # --- Simulation engine kwargs ---
    sim_data = params.get("simulation", {})
    scene_center_raw = sim_data.get("scene_center")
    swath_range_raw = sim_data.get("swath_range")
    swath_range = tuple(swath_range_raw) if swath_range_raw is not None else None

    engine_kwargs = {
        "n_pulses": int(sim_data.get("n_pulses", 256)),
        "seed": int(sim_data.get("seed", 42)),
        "sample_rate": sim_data.get("sample_rate"),
        "scene_center": np.asarray(scene_center_raw, dtype=float) if scene_center_raw is not None else None,
        "n_subswaths": int(sim_data.get("n_subswaths", 3)),
        "burst_length": int(sim_data.get("burst_length", 20)),
        "swath_range": swath_range,
    }

    # --- Processing config ---
    proc_data = params.get("processing")
    processing_config = None
    if proc_data is not None:
        processing_config = _build_processing_config(proc_data)

    return {
        "scene": scene,
        "radar": radar,
        "platform": platform,
        "engine_kwargs": engine_kwargs,
        "processing_config": processing_config,
    }


def save_parameter_set(
    output_dir: str | Path,
    *,
    scene: object,
    radar: object,
    platform: object,
    n_pulses: int,
    seed: int,
    sample_rate: float | None = None,
    scene_center: np.ndarray | None = None,
    n_subswaths: int = 3,
    burst_length: int = 20,
    swath_range: tuple[float, float] | None = None,
    processing_config: object | None = None,
    name: str = "",
    description: str = "",
) -> Path:
    """Serialize a complete simulation setup to a project directory.

    Creates the directory and writes project.json with $ref links to
    component files, plus .npy files for large array data.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Scene
    scene_data = _serialize_scene(scene, output_dir)
    _write_json(output_dir / "scene.json", scene_data)

    # Radar (includes waveform and antenna)
    radar_data = _serialize_radar(radar, output_dir)
    _write_json(output_dir / "radar.json", radar_data)

    # Platform
    platform_data = _serialize_platform(platform, output_dir)
    _write_json(output_dir / "platform.json", platform_data)

    # Processing
    if processing_config is not None:
        proc_data = _serialize_processing_config(processing_config)
        _write_json(output_dir / "processing.json", proc_data)

    # Project.json
    project = {
        "format_version": "1.0",
        "name": name,
        "description": description,
        "scene": {"$ref": "scene.json"},
        "radar": {"$ref": "radar.json"},
        "platform": {"$ref": "platform.json"},
        "simulation": {
            "n_pulses": n_pulses,
            "seed": seed,
            "sample_rate_hz": sample_rate,
            "scene_center_m": scene_center.tolist() if scene_center is not None else None,
            "n_subswaths": n_subswaths,
            "burst_length": burst_length,
            "swath_range_m": list(swath_range) if swath_range is not None else None,
        },
    }
    if processing_config is not None:
        project["processing"] = {"$ref": "processing.json"}

    _write_json(output_dir / "project.json", project)

    return output_dir


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=_json_default)


def _json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _parse_rcs(rcs_raw) -> float | np.ndarray:
    """Parse RCS from JSON (scalar, dict with hh/hv/vh/vv, or array)."""
    if isinstance(rcs_raw, (int, float)):
        return float(rcs_raw)
    if isinstance(rcs_raw, np.ndarray):
        return rcs_raw
    if isinstance(rcs_raw, dict):
        # Quad-pol: {"hh": [re, im], "hv": [re, im], ...}
        matrix = np.zeros((2, 2), dtype=complex)
        for ch, idx in [("hh", (0, 0)), ("hv", (0, 1)), ("vh", (1, 0)), ("vv", (1, 1))]:
            val = rcs_raw.get(ch, [0.0, 0.0])
            if isinstance(val, list):
                matrix[idx] = complex(val[0], val[1])
            else:
                matrix[idx] = complex(val)
        return matrix
    if isinstance(rcs_raw, list):
        return float(rcs_raw[0]) if len(rcs_raw) == 1 else np.asarray(rcs_raw)
    return float(rcs_raw)


def _parse_rcs_model(model_data):
    """Parse RCS model from JSON config."""
    from pySimSAR.core.rcs_model import StaticRCS
    if model_data is None:
        return StaticRCS()
    model_type = model_data.get("type", "static")
    if model_type == "static":
        return StaticRCS()
    raise ValueError(f"Unknown RCS model type: {model_type!r}")


def _build_waveform(wf_data: dict):
    """Build a Waveform from parameter dict."""
    from pySimSAR.waveforms.lfm import LFMWaveform
    from pySimSAR.waveforms.fmcw import FMCWWaveform

    wf_type = wf_data.get("type", "lfm").lower()
    bandwidth = wf_data.get("bandwidth", wf_data.get("bandwidth_hz", 150e6))
    duty_cycle = wf_data.get("duty_cycle", 0.1 if wf_type == "lfm" else 1.0)
    window = _make_window(wf_data.get("window"), wf_data.get("window_params"))

    # Phase noise
    phase_noise = None
    pn_data = wf_data.get("phase_noise")
    if pn_data is not None:
        from pySimSAR.waveforms.phase_noise import CompositePSDPhaseNoise
        phase_noise = CompositePSDPhaseNoise(
            flicker_fm_level=pn_data.get("flicker_fm_level", pn_data.get("flicker_fm_level_dBc", -80.0)),
            white_fm_level=pn_data.get("white_fm_level", pn_data.get("white_fm_level_dBc", -100.0)),
            flicker_pm_level=pn_data.get("flicker_pm_level", pn_data.get("flicker_pm_level_dBc", -120.0)),
            white_floor=pn_data.get("white_floor", pn_data.get("white_floor_dBc", -150.0)),
        )

    if wf_type == "lfm":
        return LFMWaveform(bandwidth=bandwidth, duty_cycle=duty_cycle,
                           window=window, phase_noise=phase_noise)
    elif wf_type == "fmcw":
        from pySimSAR.core.types import RampType
        ramp = wf_data.get("ramp_type", "up")
        return FMCWWaveform(bandwidth=bandwidth, duty_cycle=duty_cycle,
                            ramp_type=ramp, window=window, phase_noise=phase_noise)
    else:
        raise ValueError(f"Unknown waveform type: {wf_type!r}")


def _build_antenna(ant_data: dict):
    """Build an AntennaPattern from parameter dict."""
    from pySimSAR.core.radar import AntennaPattern, create_antenna_from_preset

    ant_type = ant_data.get("type", "preset")
    peak_gain = ant_data.get("peak_gain", ant_data.get("peak_gain_dB", 30.0))

    if ant_type == "preset":
        preset = ant_data.get("preset", "flat")
        az_bw = ant_data.get("az_beamwidth", ant_data.get("az_beamwidth_deg", np.radians(3.0)))
        el_bw = ant_data.get("el_beamwidth", ant_data.get("el_beamwidth_deg", np.radians(10.0)))
        return create_antenna_from_preset(preset, az_bw, el_bw, peak_gain)
    elif ant_type == "measured":
        pattern_data = ant_data.get("pattern", {})
        if isinstance(pattern_data, dict):
            pattern_2d = pattern_data.get("pattern_2d")
            az_angles = pattern_data.get("az_angles")
            el_angles = pattern_data.get("el_angles")
        else:
            raise ValueError("Measured antenna requires pattern data")
        return AntennaPattern(
            pattern_2d=pattern_2d, az_beamwidth=az_angles[-1] - az_angles[0],
            el_beamwidth=el_angles[-1] - el_angles[0],
            peak_gain_dB=peak_gain, az_angles=az_angles, el_angles=el_angles,
        )
    else:
        raise ValueError(f"Unknown antenna type: {ant_type!r}")


def _build_platform(plat_data: dict):
    """Build a Platform from parameter dict."""
    from pySimSAR.core.platform import Platform

    if not plat_data:
        return None

    velocity = plat_data.get("velocity", plat_data.get("velocity_mps", 100.0))
    altitude = plat_data.get("altitude", plat_data.get("altitude_m", 2000.0))
    heading = plat_data.get("heading", plat_data.get("heading_deg", 0.0))
    start_pos_raw = plat_data.get("start_position", plat_data.get("start_position_m"))
    start_position = np.asarray(start_pos_raw, dtype=float) if start_pos_raw is not None else None

    # Perturbation
    perturbation = None
    pert_data = plat_data.get("perturbation")
    if pert_data is not None:
        pert_type = pert_data.get("type", "dryden")
        if pert_type == "dryden":
            from pySimSAR.motion.perturbation import DrydenTurbulence
            perturbation = DrydenTurbulence(
                sigma_u=pert_data.get("sigma_u", 1.0),
                sigma_v=pert_data.get("sigma_v", 1.0),
                sigma_w=pert_data.get("sigma_w", 0.5),
            )

    # Sensors
    sensors = []
    for sensor_data in plat_data.get("sensors", []) or []:
        sensor = _build_sensor(sensor_data)
        if sensor is not None:
            sensors.append(sensor)

    return Platform(
        velocity=velocity, altitude=altitude, heading=heading,
        start_position=start_position, perturbation=perturbation,
        sensors=sensors if sensors else None,
    )


def _build_sensor(sensor_data: dict):
    """Build a navigation sensor from parameter dict."""
    sensor_type = sensor_data.get("type", "").lower()

    if sensor_type == "gps":
        from pySimSAR.sensors.gps import GPSSensor
        from pySimSAR.sensors.gps_gaussian import GaussianGPSError
        accuracy = sensor_data.get("accuracy_rms", sensor_data.get("accuracy_rms_m", 1.0))
        error_model = GaussianGPSError(accuracy_rms=accuracy)
        outage_raw = sensor_data.get("outage_intervals", [])
        outage_intervals = [tuple(iv) for iv in outage_raw] if outage_raw else None
        return GPSSensor(
            accuracy_rms=accuracy,
            update_rate=sensor_data.get("update_rate", sensor_data.get("update_rate_hz", 10.0)),
            error_model=error_model,
            outage_intervals=outage_intervals,
        )
    elif sensor_type == "imu":
        from pySimSAR.sensors.imu import IMUSensor
        from pySimSAR.sensors.imu_white_noise import WhiteNoiseIMUError
        accel_nd = sensor_data.get("accel_noise_density", 0.003)
        gyro_nd = sensor_data.get("gyro_noise_density", 0.0005)
        error_model = WhiteNoiseIMUError(accel_noise_density=accel_nd, gyro_noise_density=gyro_nd)
        return IMUSensor(
            accel_noise_density=accel_nd,
            gyro_noise_density=gyro_nd,
            sample_rate=sensor_data.get("sample_rate", sensor_data.get("sample_rate_hz", 100.0)),
            error_model=error_model,
        )
    return None


def _build_clutter_model(cm_data: dict):
    """Build a ClutterModel from parameter dict."""
    cm_type = cm_data.get("type", "uniform")
    if cm_type == "uniform":
        from pySimSAR.clutter.uniform import UniformClutter
        return UniformClutter(mean_intensity=cm_data.get("mean_intensity", 1.0))
    raise ValueError(f"Unknown clutter model type: {cm_type!r}")


def _build_processing_config(proc_data: dict):
    """Build ProcessingConfig from parameter dict."""
    from pySimSAR.io.config import ProcessingConfig

    if_data = proc_data.get("image_formation", {})
    moco_data = proc_data.get("moco")
    af_data = proc_data.get("autofocus")
    gc_data = proc_data.get("geocoding")
    pd_data = proc_data.get("polarimetric_decomposition")

    def _algo_name(d):
        if d is None:
            return None
        if isinstance(d, str):
            return d
        return d.get("algorithm")

    def _algo_params(d):
        if d is None or isinstance(d, str):
            return {}
        return d.get("params", {})

    return ProcessingConfig(
        image_formation=_algo_name(if_data) or "range_doppler",
        image_formation_params=_algo_params(if_data),
        moco=_algo_name(moco_data),
        moco_params=_algo_params(moco_data),
        autofocus=_algo_name(af_data),
        autofocus_params=_algo_params(af_data),
    )


# ---------------------------------------------------------------------------
# Serialization helpers for save_parameter_set
# ---------------------------------------------------------------------------

def _serialize_scene(scene, output_dir: Path) -> dict:
    """Serialize a Scene to a JSON-compatible dict."""
    data = {
        "origin_lat_deg": scene.origin_lat,
        "origin_lon_deg": scene.origin_lon,
        "origin_alt_m": scene.origin_alt,
    }

    pts = scene.point_targets
    if len(pts) <= 20:
        # Inline
        targets = []
        for pt in pts:
            t = {
                "position_m": pt.position.tolist(),
                "rcs_m2": _serialize_rcs(pt.rcs),
            }
            if hasattr(pt, 'rcs_model') and pt.rcs_model.name != "static":
                t["rcs_model"] = {"type": pt.rcs_model.name}
            else:
                t["rcs_model"] = {"type": "static"}
            if pt.velocity is not None:
                t["velocity_mps"] = pt.velocity.tolist()
            else:
                t["velocity_mps"] = None
            targets.append(t)
        data["point_targets"] = targets
    else:
        # External files
        positions = np.array([pt.position for pt in pts])
        np.save(str(output_dir / "scene_point_targets_positions.npy"), positions)

        rcs_values = [pt.rcs for pt in pts]
        if all(isinstance(r, (int, float)) for r in rcs_values):
            rcs_arr = np.array(rcs_values)
        else:
            rcs_arr = np.array(rcs_values, dtype=complex)
        np.save(str(output_dir / "scene_point_targets_rcs.npy"), rcs_arr)

        if any(pt.velocity is not None for pt in pts):
            velocities = np.array([pt.velocity if pt.velocity is not None else [0, 0, 0] for pt in pts])
            np.save(str(output_dir / "scene_point_targets_velocities.npy"), velocities)
            data["point_targets_file"] = {
                "positions": {"$data": "scene_point_targets_positions.npy"},
                "rcs": {"$data": "scene_point_targets_rcs.npy"},
                "velocities": {"$data": "scene_point_targets_velocities.npy"},
            }
        else:
            data["point_targets_file"] = {
                "positions": {"$data": "scene_point_targets_positions.npy"},
                "rcs": {"$data": "scene_point_targets_rcs.npy"},
            }

    # Distributed targets
    dt_list = []
    for i, dt in enumerate(scene.distributed_targets):
        dt_data = {
            "origin_m": dt.origin.tolist(),
            "extent_m": dt.extent.tolist(),
            "cell_size_m": dt.cell_size,
        }
        if dt.reflectivity is not None:
            fname = f"dist_target_{i}_reflectivity.npy"
            np.save(str(output_dir / fname), dt.reflectivity)
            dt_data["reflectivity"] = {"$data": fname}
        if dt.scattering_matrix is not None:
            fname = f"dist_target_{i}_scattering_matrix.npy"
            np.save(str(output_dir / fname), dt.scattering_matrix)
            dt_data["scattering_matrix"] = {"$data": fname}
        if dt.elevation is not None:
            fname = f"dist_target_{i}_elevation.npy"
            np.save(str(output_dir / fname), dt.elevation)
            dt_data["elevation"] = {"$data": fname}
        if dt.clutter_model is not None:
            dt_data["clutter_model"] = {"type": "uniform", "mean_intensity": getattr(dt.clutter_model, 'mean_intensity', 1.0)}
        dt_list.append(dt_data)

    if dt_list:
        data["distributed_targets"] = dt_list

    return data


def _serialize_rcs(rcs) -> float | dict:
    """Serialize RCS to JSON."""
    if isinstance(rcs, (int, float)):
        return float(rcs)
    if isinstance(rcs, np.ndarray) and rcs.shape == (2, 2):
        return {
            "hh": [float(rcs[0, 0].real), float(rcs[0, 0].imag)],
            "hv": [float(rcs[0, 1].real), float(rcs[0, 1].imag)],
            "vh": [float(rcs[1, 0].real), float(rcs[1, 0].imag)],
            "vv": [float(rcs[1, 1].real), float(rcs[1, 1].imag)],
        }
    return float(rcs)


def _serialize_radar(radar, output_dir: Path) -> dict:
    """Serialize Radar to JSON dict with waveform and antenna sub-refs."""
    # Waveform
    wf = radar.waveform
    wf_data = {
        "type": wf.name,
        "bandwidth_hz": wf.bandwidth,
        "duty_cycle": wf.duty_cycle,
        "window": None,
        "window_params": None,
        "phase_noise": None,
    }
    if hasattr(wf, "ramp_type"):
        wf_data["ramp_type"] = wf.ramp_type.value if hasattr(wf.ramp_type, "value") else str(wf.ramp_type)
    _write_json(output_dir / "waveform.json", wf_data)

    # Antenna - save as preset reference if possible
    ant = radar.antenna
    ant_data = {
        "type": "preset",
        "preset": "flat",  # default
        "az_beamwidth_deg": np.degrees(ant.az_beamwidth),
        "el_beamwidth_deg": np.degrees(ant.el_beamwidth),
        "peak_gain_dB": ant.peak_gain_dB,
    }
    _write_json(output_dir / "antenna.json", ant_data)

    return {
        "carrier_freq_hz": radar.carrier_freq,
        "prf_hz": radar.prf,
        "transmit_power_w": radar.transmit_power,
        "receiver_gain_dB": radar.receiver_gain,
        "noise_figure_dB": radar.noise_figure,
        "system_losses_dB": radar.system_losses,
        "reference_temp_K": radar.reference_temp,
        "polarization": radar.polarization.value,
        "mode": radar.mode.value,
        "look_side": radar.look_side.value,
        "depression_angle_deg": np.degrees(radar.depression_angle),
        "squint_angle_deg": np.degrees(radar.squint_angle),
        "waveform": {"$ref": "waveform.json"},
        "antenna": {"$ref": "antenna.json"},
    }


def _serialize_platform(platform, output_dir: Path) -> dict:
    """Serialize Platform to JSON dict."""
    if platform is None:
        return {}

    data = {
        "velocity_mps": platform.velocity,
        "altitude_m": platform.altitude,
        "heading_deg": np.degrees(platform.heading) if platform.heading != 0 else 0.0,
    }

    if platform.start_position is not None:
        data["start_position_m"] = platform.start_position.tolist()

    if platform.perturbation is not None:
        pert = platform.perturbation
        data["perturbation"] = {
            "type": "dryden",
            "sigma_u": getattr(pert, "sigma_u", 1.0),
            "sigma_v": getattr(pert, "sigma_v", 1.0),
            "sigma_w": getattr(pert, "sigma_w", 0.5),
        }

    if platform.sensors:
        sensors = []
        for sensor in platform.sensors:
            s_type = type(sensor).__name__
            if "GPS" in s_type:
                sensors.append({
                    "type": "gps",
                    "accuracy_rms_m": sensor.accuracy_rms,
                    "update_rate_hz": sensor.update_rate,
                    "outage_intervals": getattr(sensor, "outage_intervals", []),
                    "error_model": {"type": "gaussian"},
                })
            elif "IMU" in s_type:
                sensors.append({
                    "type": "imu",
                    "accel_noise_density": sensor.accel_noise_density,
                    "gyro_noise_density": sensor.gyro_noise_density,
                    "sample_rate_hz": sensor.sample_rate,
                    "error_model": {"type": "white_noise"},
                })
        if sensors:
            data["sensors"] = sensors

    return data


def _serialize_processing_config(pc) -> dict:
    """Serialize ProcessingConfig to JSON dict."""
    data = {}

    if_name = pc.image_formation
    if_params = pc.image_formation_params if hasattr(pc, 'image_formation_params') else {}
    data["image_formation"] = {"algorithm": if_name, "params": if_params}

    if pc.moco:
        moco_params = pc.moco_params if hasattr(pc, 'moco_params') else {}
        data["moco"] = {"algorithm": pc.moco, "params": moco_params}

    if pc.autofocus:
        af_params = pc.autofocus_params if hasattr(pc, 'autofocus_params') else {}
        data["autofocus"] = {"algorithm": pc.autofocus, "params": af_params}

    return data


__all__ = [
    "resolve_refs",
    "load_parameter_set",
    "build_simulation",
    "save_parameter_set",
]
