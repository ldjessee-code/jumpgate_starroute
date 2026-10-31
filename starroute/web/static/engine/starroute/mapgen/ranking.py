"""Composite desirability used to pick jump/gate neighbors."""

from __future__ import annotations

import numpy as np
import pandas as pd

from starroute.mapgen.tiers import as_float, is_exoplanet_host

DEFAULT_WEIGHTS = {
    "habitable": 0.30,
    "stability": 0.15,
    "system": 0.45,
    "distance": 0.10,
}

# One stability step for a planet host with no measured st_mass.
# On a calm star (score 0 to 1) the stability term is multiplied by 2/3
# and the composite changes by -0.05 at the default stability weight 0.15.
MASS_UNKNOWN_STABILITY_STEP = 1


def mass_unknown_penalty(row) -> int | None:
    """Return 1 when a planet host has no measured ``st_mass``, else None."""
    if not is_exoplanet_host(row):
        return None
    if as_float(row.get("st_mass")) is None:
        return MASS_UNKNOWN_STABILITY_STEP
    return None


def rating_stability(row):
    """Stability score passed into ``composite_ranking``.

    A planet host with missing ``st_mass`` takes one extra step
    (``MASS_UNKNOWN_STABILITY_STEP``, which is 1), capped at 3. A blank
    stored score is passed as 1. On a calm star that step moves the score
    from 0 to 1, which multiplies the stability term ``(3 - score) / 3``
    by 2/3 and changes the composite by -0.05 at the default stability
    weight 0.15. Known mass does not take the step. The stored
    ``stability_score`` column is not modified, and ``estimate_stability``
    is not modified.
    """
    raw = row.get("stability_score")
    if mass_unknown_penalty(row) is None:
        return raw
    score = as_float(raw)
    if score is None:
        return float(MASS_UNKNOWN_STABILITY_STEP)
    return min(float(score) + MASS_UNKNOWN_STABILITY_STEP, 3.0)


def weight_distance(distance: float, preferred_ly: float) -> float:
    if preferred_ly <= 0:
        return 1.0 / (1.0 + max(distance, 0.0))
    if distance <= preferred_ly:
        return float(np.exp(-(distance / preferred_ly)))
    return float(1.0 / (1.0 + distance - preferred_ly))


def composite_ranking(
    carbon,
    sulfur,
    silicon,
    stability_score,
    sy_snum,
    sy_pnum,
    sy_mnum,
    cb_flag,
    st_met,
    distance,
    preferred_ly: float = 16.0,
    weights: dict | None = None,
) -> float:
    """Return a 0–1 score. Lower ``stability_score`` is better (0–3)."""
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    carbon_score = min(float(carbon) / 5.0, 1.0) if pd.notna(carbon) else 0.0
    sulfur_score = min(float(sulfur) / 5.0, 1.0) if pd.notna(sulfur) else 0.0
    silicon_score = min(float(silicon) / 5.0, 1.0) if pd.notna(silicon) else 0.0
    habitable = (1.0 * carbon_score + 0.66 * sulfur_score + 0.33 * silicon_score) / 1.99

    stability = (
        (3.0 - float(stability_score)) / 3.0 if pd.notna(stability_score) else 0.5
    )

    star_score = max((5.0 - float(sy_snum)) / 4.0, 0.0) if pd.notna(sy_snum) else 0.5
    planet_score = min(float(sy_pnum) / 8.0, 1.0) if pd.notna(sy_pnum) else 0.0
    moon_score = min((float(sy_mnum) / 20.0) * 0.25, 1.0) if pd.notna(sy_mnum) else 0.0
    cb_score = 1.0 - float(cb_flag) if pd.notna(cb_flag) else 1.0
    met_score = 0.0
    if pd.notna(st_met) and (pd.isna(sy_pnum) or float(sy_pnum) == 0):
        met_score = min(max(float(st_met) / 0.5, 0.0), 0.5)
    system = (
        0.6 * planet_score
        + 0.1 * moon_score
        + 0.2 * star_score
        + 0.1 * cb_score
        + 0.2 * met_score
    )
    denom = 1.0 if (pd.notna(sy_pnum) and float(sy_pnum) >= 1) else 1.2
    system = system / denom

    dist_w = weight_distance(float(distance) if pd.notna(distance) else 0.0, preferred_ly)
    return (
        w["habitable"] * habitable
        + w["stability"] * stability
        + w["system"] * system
        + w["distance"] * dist_w
    )
