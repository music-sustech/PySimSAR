"""Parameter set I/O: load, build, and save simulation configurations.

A parameter set is a project directory containing JSON files and binary data
that together define a complete SAR simulation and processing setup.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# Unit suffixes that get stripped on load (key renamed, value unchanged)
_UNIT_SUFFIXES = ("_hz", "_m", "_mps", "_dB", "_dBc", "_K", "_w", "_m2")

# Geographic coordinate keys that are NOT converted from degrees
_GEO_KEYS = {"origin_lat_deg", "origin_lon_deg"}


def _preset_dir() -> Path:
    """Return the path to the shipped presets directory."""
    return Path(__file__).resolve().parent.parent / "presets"


def _load_preset(relative_path: str) -> dict:
    """Load a JSON preset file from the presets directory."""
    path = _preset_dir() / relative_path
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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

        with open(ref_path, encoding="utf-8") as f:
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

    with open(project_file, encoding="utf-8") as f:
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


def make_window(window_name: str | None, window_params: dict | None = None):
    """Create a window function callable from a name string.

    Parameters
    ----------
    window_name : str | None
        Window name (hamming, hanning, blackman, kaiser, tukey) or None.
    window_params : dict | None
        Extra parameters, e.g. ``{"beta": 6.0}`` for Kaiser.

    Returns
    -------
    callable | None
        ``f(n) -> np.ndarray`` or None if no window is requested.
    """
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
        beta = params.get("beta", 6.0)
        return lambda n, _b=beta: np.kaiser(n, _b)
    elif name == "tukey":
        from scipy.signal.windows import tukey
        alpha = params.get("alpha", 0.5)
        return lambda n, _a=alpha: tukey(n, _a)
    else:
        raise ValueError(f"Unknown window function: {window_name!r}")


# Keep backward-compatible alias
_make_window = make_window


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
    from pySimSAR.core.radar import Radar
    from pySimSAR.core.scene import DistributedTarget, PointTarget, Scene
    from pySimSAR.core.types import SARModeConfig

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
    waveform = _build_waveform(wf_data, prf=radar_params.get("prf", 1000.0))

    # --- Antenna ---
    ant_data = radar_params.get("antenna", {})
    antenna = _build_antenna(ant_data)

    # --- SARModeConfig ---
    sarmode_data = params.get("sarmode", {})
    mode_str = sarmode_data.get("mode", "stripmap")
    if isinstance(mode_str, str) and mode_str.lower() == "scansar":
        mode_str = "scanmar"

    sim_data = params.get("simulation", {})
    scene_center_raw = sarmode_data.get("scene_center")
    # squint_angle: prefer sarmode block, fall back to radar block for compat
    squint_angle = sarmode_data.get(
        "squint_angle",
        radar_params.get("squint_angle", 0.0),
    )
    sar_mode_config = SARModeConfig(
        mode=mode_str,
        look_side=sarmode_data.get("look_side", "right"),
        depression_angle=sarmode_data.get("depression_angle", np.radians(45.0)),
        squint_angle=squint_angle,
        scene_center=(
            np.asarray(scene_center_raw, dtype=float) if scene_center_raw is not None else None
        ),
        n_subswaths=int(sarmode_data.get("n_subswaths", 3)),
        burst_length=int(sarmode_data.get("burst_length", 20)),
    )

    # --- Radar ---
    radar = Radar(
        carrier_freq=radar_params.get("carrier_freq", 9.65e9),
        transmit_power=radar_params.get("transmit_power", 1.0),
        waveform=waveform,
        antenna=antenna,
        polarization=radar_params.get("polarization", "single"),
        noise_figure=radar_params.get("noise_figure", 3.0),
        system_losses=radar_params.get("system_losses", 2.0),
        reference_temp=radar_params.get("reference_temp", 290.0),
        receiver_gain_dB=radar_params.get("receiver_gain", 30.0),
        sar_mode_config=sar_mode_config,
    )

    # --- Platform ---
    plat_data = params.get("platform", {})
    platform = _build_platform(plat_data)

    # --- Simulation engine kwargs ---
    swath_range_raw = sim_data.get("swath_range")
    swath_range = tuple(swath_range_raw) if swath_range_raw is not None else None

    # n_pulses is derived from flight_time × PRF (not stored in project.json)
    prf = radar.waveform.prf
    flight_time = plat_data.get("flight_time", 0.5)
    n_pulses_from_sim = sim_data.get("n_pulses")
    n_pulses = int(n_pulses_from_sim) if n_pulses_from_sim is not None else max(1, int(prf * flight_time))

    engine_kwargs = {
        "n_pulses": n_pulses,
        "seed": int(sim_data.get("seed", 42)),
        "sample_rate": sim_data.get("sample_rate"),
        "sar_mode_config": sar_mode_config,
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
    seed: int,
    sample_rate: float | None = None,
    swath_range: tuple[float, float] | None = None,
    processing_config: object | None = None,
    name: str = "",
    description: str = "",
    flight_time: float = 0.5,
) -> Path:
    """Serialize a complete simulation setup to a project directory.

    Creates the directory and writes project.json with $ref links to
    component files, plus .npy files for large array data.

    n_pulses is derived from flight_time × PRF and is NOT stored in
    project.json.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Scene
    scene_data = _serialize_scene(scene, output_dir)
    _write_json(output_dir / "scene.json", scene_data)

    # Radar (includes waveform and antenna)
    radar_data = _serialize_radar(radar, output_dir)
    _write_json(output_dir / "radar.json", radar_data)

    # SAR mode
    sarmode_data = _serialize_sarmode(radar)
    _write_json(output_dir / "sarmode.json", sarmode_data)

    # Platform (includes flight_time)
    platform_data = _serialize_platform(platform, output_dir, flight_time=flight_time)
    _write_json(output_dir / "platform.json", platform_data)

    # Processing
    if processing_config is not None:
        proc_data = _serialize_processing_config(processing_config)
        _write_json(output_dir / "processing.json", proc_data)

    # Project.json — n_pulses derived from flight_time × PRF, not stored
    project = {
        "format_version": "1.0",
        "name": name,
        "description": description,
        "scene": {"$ref": "scene.json"},
        "radar": {"$ref": "radar.json"},
        "sarmode": {"$ref": "sarmode.json"},
        "platform": {"$ref": "platform.json"},
        "simulation": {
            "seed": seed,
            "sample_rate_hz": sample_rate,
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


def _build_waveform(wf_data: dict, prf: float | None = None):
    """Build a Waveform from parameter dict."""
    from pySimSAR.waveforms.fmcw import FMCWWaveform
    from pySimSAR.waveforms.lfm import LFMWaveform

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
                           window=window, phase_noise=phase_noise, prf=prf)
    elif wf_type == "fmcw":
        ramp = wf_data.get("ramp_type", "up")
        return FMCWWaveform(bandwidth=bandwidth, duty_cycle=duty_cycle,
                            ramp_type=ramp, window=window, phase_noise=phase_noise,
                            prf=prf)
    else:
        raise ValueError(f"Unknown waveform type: {wf_type!r}")


def _build_antenna(ant_data: dict):
    """Build an AntennaPattern from parameter dict."""
    from pySimSAR.core.radar import AntennaPattern, create_antenna_from_preset

    ant_type = ant_data.get("type", "preset")

    if ant_type == "preset":
        preset = ant_data.get("preset", "flat")
        az_bw = ant_data.get("az_beamwidth", ant_data.get("az_beamwidth_deg", np.radians(3.0)))
        el_bw = ant_data.get("el_beamwidth", ant_data.get("el_beamwidth_deg", np.radians(10.0)))
        return create_antenna_from_preset(preset, az_bw, el_bw)
    elif ant_type == "measured":
        pattern_data = ant_data.get("pattern", {})
        if isinstance(pattern_data, dict):
            pattern_2d = pattern_data.get("pattern_2d")
            az_angles = pattern_data.get("az_angles")
            el_angles = pattern_data.get("el_angles")
        else:
            raise ValueError("Measured antenna requires pattern data")
        az_bw = az_angles[-1] - az_angles[0]
        el_bw = el_angles[-1] - el_angles[0]
        return AntennaPattern(
            pattern_2d=pattern_2d, az_beamwidth=az_bw,
            el_beamwidth=el_bw,
            az_angles=az_angles, el_angles=el_angles,
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
    heading_raw = plat_data.get("heading", plat_data.get("heading_deg", 0.0))
    if isinstance(heading_raw, (list, tuple)):
        heading = np.array(heading_raw, dtype=float)
    else:
        # Legacy scalar — treat as degrees, convert to radians for Platform
        heading = float(np.radians(float(heading_raw)))
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
            mean_val = getattr(dt.clutter_model, 'mean_intensity', 1.0)
            dt_data["clutter_model"] = {"type": "uniform", "mean_intensity": mean_val}
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
    }
    _write_json(output_dir / "antenna.json", ant_data)

    return {
        "carrier_freq_hz": radar.carrier_freq,
        "prf_hz": radar.waveform.prf,
        "transmit_power_w": radar.transmit_power,
        "receiver_gain_dB": radar.receiver_gain,
        "noise_figure_dB": radar.noise_figure,
        "system_losses_dB": radar.system_losses,
        "reference_temp_K": radar.reference_temp,
        "polarization": radar.polarization.value,
        "waveform": {"$ref": "waveform.json"},
        "antenna": {"$ref": "antenna.json"},
    }


def _serialize_sarmode(radar) -> dict:
    """Serialize SAR imaging mode config to JSON dict."""
    cfg = radar.sar_mode_config
    return {
        "mode": cfg.mode.value,
        "look_side": cfg.look_side.value,
        "depression_angle_deg": np.degrees(cfg.depression_angle),
        "squint_angle_deg": np.degrees(cfg.squint_angle),
        "scene_center_m": cfg.scene_center.tolist() if cfg.scene_center is not None else None,
        "n_subswaths": cfg.n_subswaths,
        "burst_length": cfg.burst_length,
    }


def _serialize_platform(platform, output_dir: Path, flight_time: float = 0.5) -> dict:
    """Serialize Platform to JSON dict."""
    if platform is None:
        return {}

    data = {
        "velocity_mps": platform.velocity,
        "altitude_m": platform.altitude,
        "heading": platform.heading_vector.tolist(),
        "flight_path_mode": "heading_time",
        "flight_time": flight_time,
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


def _default_project_dir() -> Path:
    """Return the path to the shipped default project."""
    return Path(__file__).resolve().parent.parent / "presets" / "projects" / "default_stripmap"


def project_to_gui_params(params: dict) -> dict:
    """Convert a resolved project parameter dict to GUI tree format.

    The GUI tree's ``set_all_parameters`` expects a dict with keys:
    simulation, sarmode, radar, antenna, waveform, platform, scene,
    processing_config.

    Parameters
    ----------
    params : dict
        Resolved parameter dictionary from ``load_parameter_set()``.

    Returns
    -------
    dict
        Parameter dict suitable for ``ParameterTreeWidget.set_all_parameters()``.
    """
    radar_data = params.get("radar", {})
    sarmode_data = params.get("sarmode", {})
    sim_data = params.get("simulation", {})
    plat_data = params.get("platform", {})
    scene_data = params.get("scene", {})
    proc_data = params.get("processing", {})

    # --- sarmode (imaging geometry) ---
    # squint_angle: prefer sarmode, fall back to radar for compat
    squint_val = sarmode_data.get(
        "squint_angle",
        radar_data.get("squint_angle", 0.0),
    )
    sarmode = {
        "mode": sarmode_data.get("mode", "stripmap"),
        "look_side": sarmode_data.get("look_side", "right"),
        "depression_angle": sarmode_data.get("depression_angle", np.radians(45.0)),
        "squint_angle": squint_val,
        "scene_center": sarmode_data.get("scene_center", [0, 0, 0]),
        "n_subswaths": sarmode_data.get("n_subswaths", 3),
        "burst_length": sarmode_data.get("burst_length", 20),
    }

    # --- simulation ---
    swath_raw = sim_data.get("swath_range")
    simulation = {
        "seed": sim_data.get("seed", 42),
        "swath_range": tuple(swath_raw) if swath_raw is not None else (1350.0, 1500.0),
        "sample_rate": sim_data.get("sample_rate"),
    }

    # --- radar (hardware only, no mode/look/depression) ---
    wf_data = radar_data.get("waveform", {})
    ant_data = radar_data.get("antenna", {})

    radar = {
        "carrier_freq": radar_data.get("carrier_freq", 9.65e9),
        "transmit_power": radar_data.get("transmit_power", 1.0),
        "receiver_gain_dB": radar_data.get("receiver_gain", 30.0),
        "system_losses": radar_data.get("system_losses", 2.0),
        "noise_figure": radar_data.get("noise_figure", 3.0),
        "reference_temp": radar_data.get("reference_temp", 290.0),
        "polarization": radar_data.get("polarization", "single"),
    }

    antenna = {
        "preset": ant_data.get("preset", "flat"),
        "az_beamwidth": ant_data.get("az_beamwidth", np.radians(10.0)),
        "el_beamwidth": ant_data.get("el_beamwidth", np.radians(10.0)),
    }

    phase_noise_data = wf_data.get("phase_noise")
    phase_noise_enabled = phase_noise_data is not None
    if phase_noise_data is None:
        try:
            phase_noise_data = _load_preset("waveforms/phase_noise_default.json")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    waveform = {
        "waveform_type": (wf_data.get("type", "lfm")).upper(),
        "prf": wf_data.get("prf", radar_data.get("prf", 1000.0)),
        "bandwidth": wf_data.get("bandwidth", 100e6),
        "duty_cycle": wf_data.get("duty_cycle", 0.01),
        "window": wf_data.get("window"),
        "phase_noise": phase_noise_data,
        "phase_noise_enabled": phase_noise_enabled,
    }

    # --- platform ---
    heading_raw = plat_data.get("heading", [0, 1, 0])

    # Extract GPS/IMU from sensors list (project JSON uses "sensors", not
    # top-level "gps"/"imu" keys).
    gps_data = None
    imu_data = None
    gps_enabled = False
    imu_enabled = False
    sensors_list = plat_data.get("sensors") or []
    if isinstance(sensors_list, list):
        for s in sensors_list:
            if not isinstance(s, dict):
                continue
            stype = s.get("type", "").lower()
            if stype == "gps":
                gps_data = {
                    "accuracy": s.get("accuracy_rms", s.get("accuracy_rms_m", 0.002)),
                    "rate": s.get("update_rate", s.get("update_rate_hz", 10.0)),
                }
                gps_enabled = True
            elif stype == "imu":
                imu_data = {
                    "accel_noise": s.get(
                        "accel_noise_density", 0.0001
                    ),
                    "gyro_noise": s.get(
                        "gyro_noise_density", 0.00001
                    ),
                    "rate": s.get("sample_rate", s.get("sample_rate_hz", 200.0)),
                }
                imu_enabled = True

    # Load preset defaults for disabled optional features so GUI spinners
    # are pre-populated with sensible values even when the feature is off.
    perturbation_data = plat_data.get("perturbation")
    perturbation_enabled = perturbation_data is not None
    if perturbation_data is None:
        try:
            perturbation_data = _load_preset("perturbation/dryden_default.json")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    if gps_data is None:
        try:
            gp = _load_preset("sensors/rtk_gps.json")
            gps_data = {
                "accuracy": gp.get("accuracy_rms_m", 0.002),
                "rate": gp.get("update_rate_hz", 10.0),
            }
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    if imu_data is None:
        try:
            ip = _load_preset("sensors/navigation_imu.json")
            imu_data = {
                "accel_noise": ip.get("accel_noise_density", 0.0001),
                "gyro_noise": ip.get("gyro_noise_density", 0.00001),
                "rate": ip.get("sample_rate_hz", 200.0),
            }
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    platform = {
        "velocity": plat_data.get("velocity", 100.0),
        "altitude": plat_data.get("altitude", 1000.0),
        "heading": heading_raw if isinstance(heading_raw, list) else [0, 1, 0],
        "start_position": plat_data.get("start_position", [0, -25, 1000]),
        "flight_path_mode": plat_data.get("flight_path_mode", "heading_time"),
        "flight_time": plat_data.get("flight_time", 0.5),
        "perturbation": perturbation_data,
        "perturbation_enabled": perturbation_enabled,
        "gps": gps_data,
        "gps_enabled": gps_enabled,
        "imu": imu_data,
        "imu_enabled": imu_enabled,
    }

    # --- scene ---
    targets = []
    for pt in scene_data.get("point_targets", []):
        pos = pt.get("position", pt.get("position_m", [0, 0, 0]))
        rcs = pt.get("rcs", pt.get("rcs_m2", 1.0))
        vel = pt.get("velocity", pt.get("velocity_mps"))
        entry = {"position": list(pos), "rcs": float(rcs)}
        if vel is not None:
            entry["velocity"] = list(vel)
        targets.append(entry)

    scene = {
        "origin_lat": scene_data.get("origin_lat", scene_data.get("origin_lat_deg", 0.0)),
        "origin_lon": scene_data.get("origin_lon", scene_data.get("origin_lon_deg", 0.0)),
        "origin_alt": scene_data.get("origin_alt", 0.0),
        "targets": targets,
        "distributed_targets": scene_data.get("distributed_targets", []),
    }

    # --- processing_config ---
    processing_config = {}
    for step in ("image_formation", "moco", "autofocus", "geocoding", "polarimetric_decomposition"):
        step_data = proc_data.get(step)
        if step_data is None:
            processing_config[step] = None
        elif isinstance(step_data, str):
            processing_config[step] = step_data
        elif isinstance(step_data, dict):
            processing_config[step] = step_data.get("algorithm")
            step_params = step_data.get("params", {})
            if step_params:
                processing_config[f"{step}_params"] = step_params

    return {
        "simulation": simulation,
        "sarmode": sarmode,
        "radar": radar,
        "antenna": antenna,
        "waveform": waveform,
        "platform": platform,
        "scene": scene,
        "processing_config": processing_config,
    }


def load_default_gui_params() -> dict:
    """Load the shipped default project and return GUI-ready parameter dict.

    Returns
    -------
    dict
        Parameter dict for ``ParameterTreeWidget.set_all_parameters()``.
    """
    project_dir = _default_project_dir()
    params = load_parameter_set(project_dir)
    return project_to_gui_params(params)


__all__ = [
    "resolve_refs",
    "load_parameter_set",
    "build_simulation",
    "save_parameter_set",
    "make_window",
    "project_to_gui_params",
    "load_default_gui_params",
]
