"""Trim the placed catalog to 500 ly and adapt rows for the generator."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from starroute.catalog import ENRICH_FIELDS, _component_letter, _index_keys, adapt_merged_row, load_enrichment
from starroute.catalog import _unique_hostnames

DIGEST_COLUMNS = (
    "star_key",
    "dist_ly",
    "x",
    "y",
    "z",
    "spect",
    "exoplanet_count",
    "has_known_exoplanets",
    "proper",
    "gl",
    "hyg_id",
    "hip",
    "gaia_source_id",
)
DISTANCE_CAP_LY = 500.0


def _sol_mask(df: pd.DataFrame) -> pd.Series:
    """True for Sol by star_key or proper name. Missing columns stay false."""
    mask = pd.Series(False, index=df.index)
    if "star_key" in df.columns:
        mask = mask | df["star_key"].fillna("").eq("hyg:0")
    if "proper" in df.columns:
        proper = df["proper"].fillna("").astype(str).str.strip().str.lower()
        mask = mask | proper.isin(("sol", "sun"))
    return mask


def read_catalog(path: str | Path, cap_ly: float = DISTANCE_CAP_LY) -> pd.DataFrame:
    """Stream the placed catalog and keep stars at or inside ``cap_ly``.

    Blank ``dist_ly`` rows stay out, except Sol. The file is not written.
    """
    cap = min(float(cap_ly), DISTANCE_CAP_LY)
    parts: list[pd.DataFrame] = []
    for chunk in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=250_000):
        dist = pd.to_numeric(chunk["dist_ly"], errors="coerce")
        keep = _sol_mask(chunk) | (dist.notna() & (dist <= cap))
        parts.append(chunk.loc[keep])
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def frame_digest(df: pd.DataFrame) -> str:
    """Order-independent digest of the columns the generator cares about."""
    digest = hashlib.sha256()
    columns = [column for column in DIGEST_COLUMNS if column in df.columns]
    ordered = df.sort_values("star_key", kind="mergesort") if "star_key" in df.columns else df
    for values in ordered[columns].itertuples(index=False, name=None):
        for value in values:
            digest.update(str(value).encode("utf-8"))
            digest.update(b"\x1f")
        digest.update(b"\n")
    digest.update(str(len(df)).encode("utf-8"))
    return digest.hexdigest()


def filter_radius(df: pd.DataFrame, radius_ly: float) -> pd.DataFrame:
    """Subset an already-capped frame. Radius cannot exceed 500 ly."""
    radius = min(float(radius_ly), DISTANCE_CAP_LY)
    dist = pd.to_numeric(df["dist_ly"], errors="coerce")
    keep = _sol_mask(df) | (dist.notna() & (dist <= radius))
    return df.loc[keep].reset_index(drop=True)


def load_bench_enrichment(raw_dir: str | Path | None = None) -> dict[str, dict[str, str]]:
    """Default sample enrichment, then NASA rows for hosts the sample does not have.

    First match wins, which is the catalog loader's rule. NASA files with a
    leading ``#`` comment block are skipped by the stock loader, so this
    helper strips those comments and only fills missing keys.
    """
    index = load_enrichment()
    folder = Path(raw_dir) if raw_dir else Path(__file__).resolve().parents[1] / "data" / "raw"
    if not folder.is_dir():
        return index
    for path in sorted(folder.glob("*.csv")):
        _merge_nasa(index, path)
    return index


def _merge_nasa(index: dict[str, dict[str, str]], path: Path) -> int:
    added = 0
    with path.open(encoding="utf-8", newline="") as handle:
        filtered = (line for line in handle if not line.startswith("#"))
        reader = csv.DictReader(filtered)
        if not reader.fieldnames or "hostname" not in reader.fieldnames:
            return 0
        if "st_mass" not in reader.fieldnames and "sy_snum" not in reader.fieldnames:
            return 0
        for row in reader:
            payload = {
                key: row[key]
                for key in ENRICH_FIELDS
                if key in row and str(row[key]).strip() not in {"", "nan", "None"}
            }
            if not payload:
                continue
            payload["_component"] = _component_letter(row)
            for key in _index_keys(row):
                if key in index:
                    continue
                index[key] = payload
                added += 1
    return added


def _dedupe_hostnames_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Same suffix rule as ``_unique_hostnames``, without holding every row dict."""
    if df.empty or "hostname" not in df.columns:
        return df
    seen: dict[str, int] = {}
    host = df["hostname"].tolist()
    keys = df["star_key"].tolist() if "star_key" in df.columns else [""] * len(df)
    sy = df["sy_name"].tolist() if "sy_name" in df.columns else None
    changed = False
    for index, name in enumerate(host):
        label = str(name or "unknown")
        count = seen.get(label, 0)
        seen[label] = count + 1
        if not count:
            continue
        renamed = f"{label} [{keys[index] or count}]"
        host[index] = renamed
        if sy is not None:
            sy[index] = renamed
        changed = True
    if not changed:
        return df
    out = df.copy()
    out["hostname"] = host
    if sy is not None:
        out["sy_name"] = sy
    return out


def adapt_frame(
    df: pd.DataFrame,
    enrichment: Mapping[str, Mapping[str, str]] | None,
    origin: str = "Sol",
) -> pd.DataFrame:
    """Adapt catalog rows with the same function the map builder uses.

    Rows are adapted in batches so a 500 ly catalog does not keep two full
    dict lists alive at once. Hostname suffixes match ``_unique_hostnames``.
    """
    index = enrichment or {}
    parts: list[pd.DataFrame] = []
    batch: list[dict[str, Any]] = []
    step = 20000

    def flush() -> None:
        if batch:
            parts.append(pd.DataFrame(batch))
            batch.clear()

    total = len(df)
    for start in range(0, total, step):
        for record in df.iloc[start:start + step].to_dict("records"):
            adapted = adapt_merged_row(record, index)
            adapted["origin_hostname"] = origin
            dist = adapted.get("distance_from_sol_ly")
            adapted["distance_from_origin_ly"] = 0.0 if adapted.get("hostname") == origin else dist
            for key in ("gl", "comp_primary", "variable", "var", "flare", "pulsar", "neutron"):
                if key in record and record.get(key) not in ("", None) and not adapted.get(key):
                    adapted[key] = record.get(key)
            batch.append(adapted)
        flush()
    if not parts:
        return pd.DataFrame(_unique_hostnames([]))
    out = parts[0] if len(parts) == 1 else pd.concat(parts, ignore_index=True)
    return _dedupe_hostnames_frame(out)
