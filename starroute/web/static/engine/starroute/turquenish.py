"""Catalog id → Turquenish system name, applied at map build.

The merged catalog leaves ``turquenish_system`` blank. This map does not edit
``setting/``. Names come from ``config/turquenish_systems.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from starroute.paths import TURQUENISH_SYSTEMS_JSON


def clean_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "<na>"}:
        return ""
    if text.endswith(".0"):
        head = text[:-2]
        if head.isdigit() or (head.startswith("-") and head[1:].isdigit()):
            text = head
    return text


def _digits(value: Any) -> str:
    text = clean_id(value)
    if not text:
        return ""
    digits = []
    for char in text:
        if char.isdigit():
            digits.append(char)
    return "".join(digits)


def _first_text(*values: Any) -> str:
    """First non-blank id. Avoids ``a or b`` because pandas NA has no truth value."""
    for value in values:
        text = clean_id(value)
        if text:
            return text
    return ""


def load_turquenish_map(path: str | Path | None = None) -> dict[str, Any]:
    file_path = Path(path) if path else TURQUENISH_SYSTEMS_JSON
    if not file_path.is_file():
        return {"systems": []}
    with file_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    payload.setdefault("systems", [])
    return payload


def _record_keys(record: Mapping[str, Any]) -> dict[str, str]:
    keys = {}
    star_key = clean_id(record.get("star_key"))
    gaia = clean_id(record.get("gaia_source_id"))
    hip = _digits(_first_text(record.get("hip"), record.get("hip_name")))
    hd = _digits(_first_text(record.get("hd"), record.get("hd_name")))
    hyg = clean_id(record.get("hyg_id"))
    if star_key:
        keys["star_key:" + star_key] = star_key
    if gaia:
        keys["gaia:" + gaia] = gaia
    if hip:
        keys["hip:" + hip] = hip
    if hd:
        keys["hd:" + hd] = hd
    if hyg:
        keys["hyg:" + hyg] = hyg
    return keys


def _indexes(mapping: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for record in mapping.get("systems") or []:
        for key in _record_keys(record):
            found.setdefault(key, record)
    return found


def lookup_record(row: Mapping[str, Any], mapping: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    """First hit wins: star_key, Gaia id, HIP, HD, HYG id."""
    index = _indexes(mapping if mapping is not None else load_turquenish_map())
    for key in _record_keys(row):
        if key in index:
            return index[key]
    return None


def lookup_turquenish(row: Mapping[str, Any], mapping: Mapping[str, Any] | None = None) -> str:
    record = lookup_record(row, mapping)
    if not record:
        return ""
    return clean_id(record.get("turquenish_system"))


def lookup_system_file(row: Mapping[str, Any], mapping: Mapping[str, Any] | None = None) -> str:
    record = lookup_record(row, mapping)
    if not record:
        return ""
    return clean_id(record.get("system_file"))


def apply_turquenish(df, mapping: Mapping[str, Any] | None = None):
    """Copy Turquenish name and lore-file pointer onto a systems frame."""
    table = mapping if mapping is not None else load_turquenish_map()
    out = df.copy()
    names = []
    files = []
    display = []
    for _, row in out.iterrows():
        record = lookup_record(row, table) or {}
        names.append(clean_id(record.get("turquenish_system")))
        files.append(clean_id(record.get("system_file")))
        display.append(clean_id(record.get("name")))
    out["turquenish_system"] = names
    out["system_file"] = files
    out["setting_name"] = names
    out["handoff_name"] = display
    return out
