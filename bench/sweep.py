"""One-factor sweep at extreme, midpoint, and minimal levels."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Operating point held constant while one parameter moves.
# Routes 8 is Doug's reference. Spacing 16 ly matches the crowded preset.
# Radius 100 ly is a real map inside the 500 ly cap. Criteria are the
# standard exclusions (variable, flare, pulsar/neutron including companions,
# standard unstable-multiple rule).
BASELINE: dict[str, Any] = {
    "min_stellar_mass": 0.40,
    "max_neighbors": 8,
    "max_jump_ly": 16.0,
    "max_distance_ly": 100.0,
    "criteria": "standard",
}

# Extreme is the heavy end (most stars, widest links). Minimal is the small end.
LEVELS: dict[str, dict[str, Any]] = {
    "min_stellar_mass": {"extreme": 0.25, "midpoint": 0.50, "minimal": 0.80},
    "max_neighbors": {"extreme": 16, "midpoint": 8, "minimal": 4},
    "max_jump_ly": {"extreme": 32.0, "midpoint": 20.0, "minimal": 8.0},
    "max_distance_ly": {"extreme": 500.0, "midpoint": 250.0, "minimal": 60.0},
    "criteria": {"extreme": "permissive", "midpoint": "standard", "minimal": "strict"},
}

CRITERIA: dict[str, dict[str, Any]] = {
    "permissive": {
        "exclude_variable": False,
        "exclude_flare": False,
        "exclude_pulsar_neutron": False,
        "exclude_unstable_multiple": False,
        "unstable_rule": "standard",
    },
    "standard": {
        "exclude_variable": True,
        "exclude_flare": True,
        "exclude_pulsar_neutron": True,
        "exclude_unstable_multiple": True,
        "unstable_rule": "standard",
    },
    "strict": {
        "exclude_variable": True,
        "exclude_flare": True,
        "exclude_pulsar_neutron": True,
        "exclude_unstable_multiple": True,
        "unstable_rule": "strict",
    },
}

# Not swept. The link cap stays high so radius and spacing can show up.
# Generator defaults are unchanged when these are not passed.
FIXED: dict[str, Any] = {
    "max_linked_nodes": 100000,
    "medium_start_pct": 50.0,
    "long_start_pct": 75.0,
    "hard_rank": 0.20,
    "soft_rank": 0.30,
    "root_hostname": "Sol",
    "max_stellar_mass": None,
}

CAPS = {
    "min_stellar_mass": 0.25,
    "max_neighbors": 16,
    "max_distance_ly": 500.0,
}

PARAM_KEYS = (
    "min_stellar_mass",
    "max_neighbors",
    "max_jump_ly",
    "max_distance_ly",
    "criteria",
)


def _with(level_key: str, level: str) -> dict[str, Any]:
    params = dict(BASELINE)
    params[level_key] = LEVELS[level_key][level]
    return params


def _variant(name: str, phase: str, parameter: str, level: str, params: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "phase": phase,
        "parameter": parameter,
        "level": level,
        "params": params,
    }


def build_matrix() -> dict[str, Any]:
    """Extreme, midpoint, and minimal one-factor variants plus two combined extremes."""
    extreme = [
        _variant("mass_extreme", "extreme", "min_stellar_mass", "extreme", _with("min_stellar_mass", "extreme")),
        _variant("routes_extreme", "extreme", "max_neighbors", "extreme", _with("max_neighbors", "extreme")),
        _variant("spacing_extreme", "extreme", "max_jump_ly", "extreme", _with("max_jump_ly", "extreme")),
        _variant("radius_extreme", "extreme", "max_distance_ly", "extreme", _with("max_distance_ly", "extreme")),
        _variant("criteria_extreme", "extreme", "criteria", "extreme", _with("criteria", "extreme")),
    ]
    combined_025 = dict(BASELINE)
    combined_025.update(
        {
            "min_stellar_mass": 0.25,
            "max_neighbors": 16,
            "max_jump_ly": 32.0,
            "max_distance_ly": 500.0,
            "criteria": "standard",
        }
    )
    combined_030 = dict(combined_025)
    combined_030["min_stellar_mass"] = 0.30
    extreme.append(_variant("combined_m025", "extreme", "combined", "extreme", combined_025))
    extreme.append(_variant("combined_m030", "extreme", "combined", "extreme", combined_030))

    midpoint = [
        _variant("mass_midpoint", "midpoint", "min_stellar_mass", "midpoint", _with("min_stellar_mass", "midpoint")),
        _variant("routes_midpoint", "midpoint", "max_neighbors", "midpoint", _with("max_neighbors", "midpoint")),
        _variant("spacing_midpoint", "midpoint", "max_jump_ly", "midpoint", _with("max_jump_ly", "midpoint")),
        _variant("radius_midpoint", "midpoint", "max_distance_ly", "midpoint", _with("max_distance_ly", "midpoint")),
        _variant("criteria_midpoint", "midpoint", "criteria", "midpoint", _with("criteria", "midpoint")),
    ]
    minimal = [
        _variant("mass_minimal", "minimal", "min_stellar_mass", "minimal", _with("min_stellar_mass", "minimal")),
        _variant("routes_minimal", "minimal", "max_neighbors", "minimal", _with("max_neighbors", "minimal")),
        _variant("spacing_minimal", "minimal", "max_jump_ly", "minimal", _with("max_jump_ly", "minimal")),
        _variant("radius_minimal", "minimal", "max_distance_ly", "minimal", _with("max_distance_ly", "minimal")),
        _variant("criteria_minimal", "minimal", "criteria", "minimal", _with("criteria", "minimal")),
    ]
    return {
        "baseline": dict(BASELINE),
        "levels": LEVELS,
        "criteria_levels": CRITERIA,
        "fixed": dict(FIXED),
        "caps": dict(CAPS),
        "notes": [
            "One parameter changes from the baseline at a time, except combined_m025 and combined_m030.",
            "Extreme is the heavy end. Minimal is the small end. Midpoint is the middle level.",
            "routes_midpoint and criteria_midpoint match the baseline because 8 routes and standard criteria are both the midpoint and the baseline.",
            "max_neighbors is the generator's max routes per gate. The sweep never sets it above 16.",
            "min_stellar_mass is never below 0.25. max_distance_ly is never above 500.",
            "max_linked_nodes is fixed at 100000 so the historical default of 101 does not hide radius or spacing.",
            "Generator defaults are unchanged when a caller does not pass these parameters.",
        ],
        "variants": extreme + midpoint + minimal,
    }


def changed_parameters(params: dict[str, Any], baseline: dict[str, Any] | None = None) -> list[str]:
    base = baseline or BASELINE
    return [key for key in PARAM_KEYS if params.get(key) != base.get(key)]


def validate_matrix(matrix: dict[str, Any] | None = None) -> None:
    """Raise ValueError when a variant breaks a cap or the one-factor rule."""
    matrix = matrix or build_matrix()
    names = [item["name"] for item in matrix["variants"]]
    if len(names) != len(set(names)):
        raise ValueError("duplicate variant name")
    phases = {"extreme", "midpoint", "minimal"}
    for item in matrix["variants"]:
        if item["phase"] not in phases:
            raise ValueError(f"{item['name']} has a bad phase")
        params = item["params"]
        mass = float(params["min_stellar_mass"])
        routes = int(params["max_neighbors"])
        radius = float(params["max_distance_ly"])
        spacing = float(params["max_jump_ly"])
        if mass < CAPS["min_stellar_mass"]:
            raise ValueError(f"{item['name']} mass {mass} is below 0.25")
        if routes > CAPS["max_neighbors"] or routes < 1:
            raise ValueError(f"{item['name']} routes {routes} break the 1..16 cap")
        if radius > CAPS["max_distance_ly"] or radius <= 0:
            raise ValueError(f"{item['name']} radius {radius} breaks the 500 ly cap")
        if spacing <= 0:
            raise ValueError(f"{item['name']} spacing must be positive")
        if params["criteria"] not in CRITERIA:
            raise ValueError(f"{item['name']} has an unknown criteria level")
        changed = changed_parameters(params, matrix["baseline"])
        if item["parameter"] == "combined":
            expected = {"min_stellar_mass", "max_neighbors", "max_jump_ly", "max_distance_ly"}
            if set(changed) != expected:
                raise ValueError(f"{item['name']} combined keys {changed}")
            continue
        if item["level"] == "midpoint" and LEVELS[item["parameter"]]["midpoint"] == matrix["baseline"][item["parameter"]]:
            if changed:
                raise ValueError(f"{item['name']} should match the baseline")
            continue
        if changed != [item["parameter"]]:
            raise ValueError(f"{item['name']} changed {changed}, expected only {item['parameter']}")


def network_params(variant: dict[str, Any], fixed: dict[str, Any] | None = None) -> dict[str, Any]:
    """Flatten a variant into generate_network params."""
    params = dict(fixed or FIXED)
    body = variant["params"]
    params.update(
        {
            "min_stellar_mass": float(body["min_stellar_mass"]),
            "max_neighbors": int(body["max_neighbors"]),
            "max_jump_ly": float(body["max_jump_ly"]),
            "max_distance_ly": float(body["max_distance_ly"]),
        }
    )
    params.update(CRITERIA[body["criteria"]])
    return params


def variants_for(matrix: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    return [item for item in matrix["variants"] if item["phase"] == phase]


def write_sweep(path: str | Path, matrix: dict[str, Any] | None = None) -> Path:
    matrix = matrix or build_matrix()
    validate_matrix(matrix)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
    return target
