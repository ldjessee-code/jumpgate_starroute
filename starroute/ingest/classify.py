"""Planet-class and stellar-stability flags used by ranking and faction rules.

Equilibrium-temperature bands are setting conventions (carbon / sulfur /
silicon life), not IAU habitable-zone definitions. Planet classes are rough
density cuts on NASA best-mass and radius when both exist.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

STABILITY_SYMBOLS = {0: "circle", 1: "diamond", 2: "square", 3: "cross"}

# Columns written onto each host after grouping planets.
PLANET_FLAG_COLUMNS = [
    "rocky_count",
    "gas_giant_count",
    "ice_giant_count",
    "has_rocky_planet",
    "has_gas_giant",
    "has_ice_giant",
    "has_rocky_planet_in_carbon_zone",
    "has_rocky_planet_in_sulfur_zone",
    "has_rocky_planet_in_silicon_zone",
    "has_gas_planet_in_carbon_zone",
    "has_gas_planet_in_sulfur_zone",
    "has_gas_planet_in_silicon_zone",
]


def extract_year(ref_string) -> int:
    match = re.search(r"(\d{4})", str(ref_string))
    return int(match.group(1)) if match else 0


def classify_planets(planets: pd.DataFrame) -> pd.DataFrame:
    """Vectorized per-planet flags, then summed per ``hostname``."""
    if planets.empty:
        return pd.DataFrame(columns=["hostname", *PLANET_FLAG_COLUMNS])

    mass = pd.to_numeric(planets.get("pl_bmasse"), errors="coerce")
    radius = pd.to_numeric(planets.get("pl_rade"), errors="coerce")
    eqt = pd.to_numeric(planets.get("pl_eqt"), errors="coerce")
    density = mass / (radius ** 3)

    is_rocky = (mass < 5) & (radius < 1.6) & (density > 4)
    is_gas = (mass > 10) & (radius > 4) & (density < 2)
    is_ice = (mass >= 6) & (mass <= 15) & (eqt < 150)

    in_c = eqt.between(240, 320)
    in_s = eqt.between(180, 500)
    in_si = eqt.between(150, 800)

    work = pd.DataFrame(
        {
            "hostname": planets["hostname"].astype(str),
            "rocky_count": is_rocky.fillna(False).astype(int),
            "gas_giant_count": is_gas.fillna(False).astype(int),
            "ice_giant_count": is_ice.fillna(False).astype(int),
            "has_rocky_planet_in_carbon_zone": (is_rocky & in_c).fillna(False).astype(int),
            "has_rocky_planet_in_sulfur_zone": (is_rocky & in_s).fillna(False).astype(int),
            "has_rocky_planet_in_silicon_zone": (is_rocky & in_si).fillna(False).astype(int),
            "has_gas_planet_in_carbon_zone": (is_gas & in_c).fillna(False).astype(int),
            "has_gas_planet_in_sulfur_zone": (is_gas & in_s).fillna(False).astype(int),
            "has_gas_planet_in_silicon_zone": (is_gas & in_si).fillna(False).astype(int),
        }
    )
    grouped = work.groupby("hostname", as_index=False).sum()
    grouped["has_rocky_planet"] = (grouped["rocky_count"] > 0).astype(int)
    grouped["has_gas_giant"] = (grouped["gas_giant_count"] > 0).astype(int)
    grouped["has_ice_giant"] = (grouped["ice_giant_count"] > 0).astype(int)
    return grouped[["hostname", *PLANET_FLAG_COLUMNS]]


def ranking_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["carbon_ranking"] = (
        out["has_rocky_planet_in_carbon_zone"].astype(int) * 2
        + out["has_gas_planet_in_carbon_zone"].astype(int)
    )
    out["sulfur_ranking"] = (
        out["has_rocky_planet_in_sulfur_zone"].astype(int) * 2
        + out["has_gas_planet_in_sulfur_zone"].astype(int)
    )
    out["silicon_ranking"] = (
        out["has_rocky_planet_in_silicon_zone"].astype(int) * 2
        + out["has_gas_planet_in_silicon_zone"].astype(int)
    )
    out["combined_score"] = (
        out["carbon_ranking"] + out["sulfur_ranking"] + out["silicon_ranking"]
    ) / 3.0
    return out


def estimate_stability(row: pd.Series) -> int:
    """0 = most stable, 3 = least. Missing values do not add risk."""
    score = 0
    age = row.get("st_age")
    rotp = row.get("st_rotp")
    mass = row.get("st_mass")
    if pd.notna(age) and (age < 0.5 or age > 10):
        score += 1
    if pd.notna(rotp) and rotp < 5:
        score += 1
    if pd.notna(mass) and mass > 1.5:
        score += 1
    return min(score, 3)


def add_stability(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["stability_score"] = out.apply(estimate_stability, axis=1)
    out["stability_symbol"] = out["stability_score"].map(STABILITY_SYMBOLS).fillna("cross")
    return out


def completeness_score(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    """How many key stellar fields are present — used to pick one host row."""
    score = np.zeros(len(df), dtype=int)
    for col in columns:
        if col in df.columns:
            score += df[col].notna().to_numpy().astype(int)
    return pd.Series(score, index=df.index)
