"""Hardcoded algorithm parameter schemas for the GUI parameter editor.

Each registry maps algorithm names to lists of parameter definitions.
Parameter dicts use keys: name, type, default, and optionally
min, max, description, unit, choices (for enum type).
"""

from __future__ import annotations

ALGORITHM_SCHEMAS: dict[str, dict[str, list[dict]]] = {
    "image_formation": {
        "range_doppler": [
            {
                "name": "apply_rcmc",
                "label": "Apply RCMC",
                "type": "bool",
                "default": True,
                "description": "Apply range cell migration correction",
            },
            {
                "name": "rcmc_interp_order",
                "label": "RCMC Interp. Order",
                "type": "int",
                "default": 8,
                "min": 2,
                "max": 16,
                "description": "Interpolation order for RCMC",
            },
        ],
        "chirp_scaling": [
            {
                "name": "n_iterations",
                "type": "int",
                "default": 1,
                "min": 1,
                "max": 10,
                "description": "Number of chirp-scaling iterations",
            },
        ],
        "omega_k": [
            {
                "name": "reference_range",
                "type": "float",
                "default": 0.0,
                "unit": "m",
                "description": "Reference range for focusing, 0=auto",
            },
        ],
    },
    "moco": {
        "first_order": [],
        "second_order": [],
    },
    "autofocus": {
        "pga": [
            {
                "name": "max_iterations",
                "type": "int",
                "default": 10,
                "min": 1,
                "max": 100,
                "description": "Maximum number of PGA iterations",
            },
            {
                "name": "window_fraction",
                "type": "float",
                "default": 0.5,
                "min": 0.1,
                "max": 1.0,
                "description": "Fraction of data used for windowing",
            },
            {
                "name": "n_dominant",
                "type": "int",
                "default": 0,
                "min": 0,
                "max": 100,
                "description": "Number of dominant scatterers, 0=auto",
            },
        ],
        "min_entropy": [
            {
                "name": "max_iterations",
                "type": "int",
                "default": 20,
                "min": 1,
                "max": 100,
                "description": "Maximum number of iterations",
            },
            {
                "name": "poly_order",
                "type": "int",
                "default": 4,
                "min": 1,
                "max": 10,
                "description": "Polynomial order for phase correction",
            },
            {
                "name": "convergence_threshold",
                "type": "float",
                "default": 1e-4,
                "min": 1e-8,
                "max": 1.0,
                "description": "Convergence threshold for stopping",
            },
        ],
        "mda": [
            {
                "name": "max_iterations",
                "type": "int",
                "default": 10,
                "min": 1,
                "max": 100,
                "description": "Maximum number of iterations",
            },
            {
                "name": "n_subapertures",
                "type": "int",
                "default": 4,
                "min": 2,
                "max": 32,
                "description": "Number of subapertures for map drift",
            },
        ],
        "ppp": [
            {
                "name": "n_points",
                "type": "int",
                "default": 5,
                "min": 1,
                "max": 50,
                "description": "Number of prominent points to use",
            },
            {
                "name": "search_radius",
                "type": "int",
                "default": 16,
                "min": 4,
                "max": 128,
                "unit": "pixels",
                "description": "Search radius around each prominent point",
            },
        ],
    },
    "geocoding": {
        "slant_to_ground": [
            {
                "name": "interp_method",
                "type": "enum",
                "default": "bilinear",
                "choices": ["nearest", "bilinear", "bicubic"],
                "description": "Interpolation method for resampling",
            },
        ],
        "georeferencing": [
            {
                "name": "output_spacing",
                "type": "float",
                "default": 1.0,
                "min": 0.1,
                "max": 100.0,
                "unit": "m",
                "description": "Output pixel spacing",
            },
            {
                "name": "projection",
                "type": "enum",
                "default": "UTM",
                "choices": ["UTM", "WGS84"],
                "description": "Output map projection",
            },
        ],
    },
    "polarimetry": {
        "pauli": [],
        "freeman_durden": [
            {
                "name": "max_iterations",
                "type": "int",
                "default": 10,
                "min": 1,
                "max": 50,
                "description": "Maximum decomposition iterations",
            },
        ],
        "cloude_pottier": [
            {
                "name": "window_size",
                "type": "int",
                "default": 5,
                "min": 3,
                "max": 21,
                "description": "Spatial averaging window",
            },
        ],
        "yamaguchi": [
            {
                "name": "max_iterations",
                "type": "int",
                "default": 10,
                "min": 1,
                "max": 50,
                "description": "Maximum decomposition iterations",
            },
            {
                "name": "orientation_compensation",
                "type": "bool",
                "default": True,
                "description": "Apply orientation angle compensation",
            },
        ],
    },
}
