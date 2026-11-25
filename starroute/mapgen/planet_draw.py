"""Catalog stats for later weighted planet draws.

Gap-fill at reality ≥ 1 currently writes empty L2 stubs (`generate_l2_gapfill`)
for premise roles. It does **not** roll a full planet system.

TODO
- Use `summarize_catalog` (counts and means inside the current sphere) as the
  prior for a random generator.
- Offer a “thumb on the scale” from airless/dead moon → Earth-like → Venus-like
  hellworld → gas giant, as weights on top of those empirical means.
- Do not invent hosts below reality 4; stub bodies stay tagged `generated`.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def summarize_catalog(df: pd.DataFrame) -> dict[str, Any]:
    """Weighted-ish descriptive stats for hosts in `df` (already distance-cut)."""
    n = int(len(df))
    if not n:
        return {"hosts": 0}

    def col(name: str) -> pd.Series:
        return df[name] if name in df.columns else pd.Series(dtype="float64")

    pnum = pd.to_numeric(col("sy_pnum"), errors="coerce")
    rocky = pd.to_numeric(col("rocky_count"), errors="coerce")
    giant = pd.to_numeric(col("gas_giant_count"), errors="coerce")
    carbon = pd.to_numeric(col("carbon_ranking"), errors="coerce")
    sulfur = pd.to_numeric(col("sulfur_ranking"), errors="coerce")
    return {
        "hosts": n,
        "hosts_with_no_listed_planets": int((pnum.fillna(0) <= 0).sum()),
        "mean_planets_per_host": float(pnum.fillna(0).mean()),
        "hosts_with_rocky": int((rocky.fillna(0) > 0).sum()),
        "hosts_with_gas_giant": int((giant.fillna(0) > 0).sum()),
        "hosts_with_carbon_band": int((carbon.fillna(0) > 0).sum()),
        "hosts_with_sulfur_band": int((sulfur.fillna(0) > 0).sum()),
        "share_gas_giant": float((giant.fillna(0) > 0).mean()),
        "share_carbon_band": float((carbon.fillna(0) > 0).mean()),
    }
