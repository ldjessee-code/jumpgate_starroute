"""Hazard classes from spectral type and activity proxies. No dated events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from starroute.paths import CONFIG_DIR

TEMPLATES_JSON = CONFIG_DIR / "phenomena_templates.json"


def _spectype(value: Any) -> str:
    return str(value or "").strip().upper()


def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if value != value:  # NaN
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_star(row: dict[str, Any]) -> list[str]:
    """Return class ids. Sol is mild; AU Mic is an active M dwarf."""
    spec = _spectype(row.get("st_spectype") or (row.get("star") or {}).get("st_spectype"))
    star = row.get("star") if isinstance(row.get("star"), dict) else {}
    rotp = _num(row.get("st_rotp") if row.get("st_rotp") is not None else star.get("st_rotp"))
    age = _num(row.get("st_age") if row.get("st_age") is not None else star.get("st_age"))
    vsin = _num(row.get("st_vsin") if row.get("st_vsin") is not None else star.get("st_vsin"))
    flags = row.get("flags") if isinstance(row.get("flags"), dict) else {}
    stability = _num(row.get("stability_score") if row.get("stability_score") is not None else flags.get("stability_score"))
    snum = _num(row.get("sy_snum") if row.get("sy_snum") is not None else star.get("sy_snum"))
    cb = _num(row.get("cb_flag") if row.get("cb_flag") is not None else star.get("cb_flag"))

    classes: list[str] = []
    letter = spec[:1]
    is_m = spec.startswith("M")
    is_gk = letter in {"G", "K"}

    if spec.startswith("G2") and (rotp is None or rotp >= 20) and (age is None or 4.0 <= age <= 6.0):
        classes.append("flare:sol_mild")
    elif is_gk and (rotp is None or rotp >= 15):
        classes.append("flare:G_quiet")

    m_active = is_m and (
        (rotp is not None and rotp < 10)
        or (age is not None and age < 0.5)
        or (stability is not None and stability >= 2)
    )
    if m_active:
        classes.append("flare:M_active")
        if vsin is not None and vsin >= 5:
            classes.append("cme:M_severe")

    if (snum is not None and snum >= 2) or (cb is not None and cb >= 1):
        classes.append("radiation:binary")

    return classes


def load_templates() -> list[dict[str, Any]]:
    if not TEMPLATES_JSON.exists():
        return DEFAULT_TEMPLATES
    return json.loads(TEMPLATES_JSON.read_text(encoding="utf-8"))


DEFAULT_TEMPLATES = [
    {
        "id": "tmpl-sol-flare",
        "kind": "stellar_flare",
        "class_id": "flare:sol_mild",
        "natural": True,
        "needs_delta": False,
        "proposed_effect": "Occasional radio noise; Earth-like magnetospheres cope.",
        "default_lag_mode": "light",
    },
    {
        "id": "tmpl-m-flare",
        "kind": "stellar_flare",
        "class_id": "flare:M_active",
        "natural": True,
        "needs_delta": False,
        "proposed_effect": "Radio blackout inner system; H-class at surface may drop one step (Worldstack).",
        "default_lag_mode": "light",
    },
    {
        "id": "tmpl-m-cme",
        "kind": "cme",
        "class_id": "cme:M_severe",
        "natural": True,
        "needs_delta": False,
        "proposed_effect": "Atmospheric stripping risk on close-in worlds.",
        "default_lag_mode": "light",
    },
    {
        "id": "tmpl-binary-xuv",
        "kind": "radiation",
        "class_id": "radiation:binary",
        "natural": True,
        "needs_delta": False,
        "proposed_effect": "Elevated XUV near the barycenter.",
        "default_lag_mode": "light",
    },
    {
        "id": "tmpl-rogue-transit",
        "kind": "rogue_star_transit",
        "class_id": "transit:rogue",
        "natural": True,
        "needs_delta": True,
        "proposed_effect": "Oort-cloud stirring; rare close approach (slider ≥ 3 unless a named catalog object).",
        "default_lag_mode": "light",
    },
]


def suggest_events(classes: list[str]) -> list[dict[str, Any]]:
    """Templates matching the classes. Dated instances belong to Chronos."""
    templates = load_templates()
    wanted = set(classes)
    return [t for t in templates if t.get("class_id") in wanted]
