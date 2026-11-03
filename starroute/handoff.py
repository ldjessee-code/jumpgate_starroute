"""System handoff records for orbit_match.

One record per star. When ``system_file`` is set, orbit_match loads that
detailed lore file. Otherwise it uses the fields on this record. ``belts``
may hold any number of belts (including none).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from starroute.luminosity import calculate_luminosity
from starroute.mapgen.ranking import mass_unknown_penalty
from starroute.mapgen.tiers import (
    DEFAULT_MIN_STELLAR_MASS,
    as_float,
    classify_tier,
    gate_status_for,
    is_exoplanet_host,
)
from starroute.names import aliases_for, display_name_for
from starroute.paths import ROOT
from starroute.turquenish import clean_id, load_turquenish_map, lookup_record

SCHEMA_PATH = ROOT / "docs" / "system-handoff.schema.json"
EXAMPLES_DIR = ROOT / "docs" / "examples"


def _text(value: Any) -> str | None:
    text = clean_id(value)
    return text or None


def _number(value: Any) -> float | None:
    return as_float(value)


def _whole(value: Any) -> int:
    number = as_float(value)
    if number is None or number < 0:
        return 0
    return int(number)


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in {"", "nan", "none", "<na>"}:
        return True
    try:
        if value != value:
            return True
    except Exception:
        return False
    return False


def _sy_pnum_value(row: Mapping[str, Any]) -> int | None:
    number = as_float(row.get("sy_pnum"))
    if number is None:
        return None
    return int(number)


def _exoplanet_count_value(row: Mapping[str, Any]) -> int:
    """Per-star count is ``exoplanet_count`` only.

    ``sy_pnum`` is the system total and is stored beside the count. A missing
    count is 0, including on a multi-star host whose ``sy_pnum`` is larger.
    """
    explicit = row.get("exoplanet_count")
    if not _missing(explicit):
        return _whole(explicit)
    return 0


def handoff_from_row(
    row: Mapping[str, Any],
    mapping: Mapping[str, Any] | None = None,
    *,
    min_stellar_mass: float = DEFAULT_MIN_STELLAR_MASS,
    max_stellar_mass: float | None = None,
    origin: str = "Sol",
) -> dict[str, Any]:
    """Build one handoff object. Does not read or write the catalog file."""
    table = mapping if mapping is not None else load_turquenish_map()
    overlay = lookup_record(row, table) or {}
    belts = overlay.get("belts")
    if not isinstance(belts, list):
        belts = row.get("belts") if isinstance(row.get("belts"), list) else []
    rings = overlay.get("rings")
    if not isinstance(rings, list):
        rings = row.get("rings") if isinstance(row.get("rings"), list) else []
    hostname = _text(overlay.get("hostname")) or _text(row.get("hostname")) or _text(row.get("exo_hostname"))
    name = _text(overlay.get("name")) or _text(row.get("name")) or display_name_for(row)
    if not hostname:
        hostname = name or _text(row.get("star_key")) or "unknown"
    if not name:
        name = hostname or _text(row.get("star_key")) or "unknown"
    system_file = _text(overlay.get("system_file")) or _text(row.get("system_file"))
    turquenish = _text(overlay.get("turquenish_system")) or _text(row.get("turquenish_system"))
    mag = _number(row.get("mag"))
    if mag is None:
        mag = _number(row.get("render_mag"))
    if mag is None:
        mag = _number(row.get("phot_g_mean_mag"))
    if mag is None:
        mag = _number(row.get("mag_v"))
    if mag is None:
        mag = _number(row.get("sy_vmag"))
    x = _number(row.get("x"))
    y = _number(row.get("y"))
    z = _number(row.get("z"))
    record = {
        "starroute_handoff": "1",
        "kind": "system_handoff",
        "star_key": _text(row.get("star_key")) or "",
        "gaia_source_id": _text(row.get("gaia_source_id")),
        "hyg_id": _text(row.get("hyg_id")),
        "hip": _text(row.get("hip")),
        "hd": _text(row.get("hd")),
        "hostname": hostname or "",
        "name": name,
        "ra_deg": _number(row.get("ra_deg") if row.get("ra_deg") not in (None, "") else row.get("ra")),
        "dec_deg": _number(row.get("dec_deg") if row.get("dec_deg") not in (None, "") else row.get("dec")),
        "dist_pc": _number(row.get("dist_pc") if row.get("dist_pc") not in (None, "") else row.get("sy_dist")),
        "x": x,
        "y": y,
        "z": z,
        "mag": mag,
        "bp_rp": _number(row.get("bp_rp")),
        "ci": _number(row.get("ci")),
        "spect": _text(row.get("spect")) or _text(row.get("st_spectype")) or _text(row.get("spectype")),
        "has_known_exoplanets": is_exoplanet_host(row),
        "exoplanet_count": _exoplanet_count_value(row),
        "sy_pnum": _sy_pnum_value(row),
        "aliases": list(overlay.get("aliases") or aliases_for(row)),
        "st_mass": _number(row.get("st_mass")),
        "mass_known": _number(row.get("st_mass")) is not None,
        "tier": classify_tier(row, min_stellar_mass, max_stellar_mass, origin),
        "turquenish_system": turquenish,
        "system_file": system_file,
        "belts": belts,
        "rings": rings,
    }
    lum, lum_method = calculate_luminosity(row)
    record["calculated_luminosity"] = lum
    record["calculated_luminosity_method"] = lum_method
    record["gate_status"] = gate_status_for(row)
    record["mass_unknown_penalty"] = mass_unknown_penalty(row)
    for key in ("lore_version", "rings_belts_version", "system_file_sha256"):
        text = _text(row.get(key))
        if text:
            record[key] = text
    sky = row.get("sky")
    if isinstance(sky, Mapping):
        record["sky"] = dict(sky)
    return record


def load_schema(path: str | Path | None = None) -> dict[str, Any]:
    schema_path = Path(path) if path else SCHEMA_PATH
    with schema_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def validate_handoff(instance: Any, schema: Mapping[str, Any] | None = None, path: str = "$") -> list[str]:
    """Check one record against the handoff schema. Empty list means valid."""
    spec = schema if schema is not None else load_schema()
    errors: list[str] = []
    if "allOf" in spec:
        for index, sub in enumerate(spec["allOf"]):
            errors.extend(validate_handoff(instance, sub, f"{path}/allOf{index}"))
    if "anyOf" in spec:
        matched = False
        for sub in spec["anyOf"]:
            if not validate_handoff(instance, sub, path):
                matched = True
                break
        if not matched:
            errors.append(f"{path} matched no anyOf branch")
    expected = spec.get("type")
    if expected is not None:
        options = expected if isinstance(expected, list) else [expected]
        if not any(_type_ok(instance, item) for item in options):
            errors.append(f"{path} type {type(instance).__name__} is not {expected}")
            return errors
    if "const" in spec and instance != spec["const"]:
        errors.append(f"{path} must be {spec['const']!r}")
    if "enum" in spec and instance not in spec["enum"]:
        errors.append(f"{path} must be one of {spec['enum']}")
    if isinstance(instance, str) and "minLength" in spec and len(instance) < int(spec["minLength"]):
        errors.append(f"{path} shorter than {spec['minLength']}")
    if isinstance(instance, list) and "minItems" in spec and len(instance) < int(spec["minItems"]):
        errors.append(f"{path} shorter than {spec['minItems']} items")
    if isinstance(instance, dict):
        for key in spec.get("required") or []:
            if key not in instance:
                errors.append(f"{path} missing {key}")
        properties = spec.get("properties") or {}
        for key, sub in properties.items():
            if key in instance:
                errors.extend(validate_handoff(instance[key], sub, f"{path}.{key}"))
    if isinstance(instance, list) and "items" in spec:
        for index, item in enumerate(instance):
            errors.extend(validate_handoff(item, spec["items"], f"{path}[{index}]"))
    return errors
