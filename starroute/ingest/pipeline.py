"""Load NASA CSVs, classify planets, insert Sol, write ``systems.csv``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from starroute.coords import add_cartesian_columns
from starroute.ingest.classify import (
    PLANET_FLAG_COLUMNS,
    add_stability,
    classify_planets,
    completeness_score,
    extract_year,
    ranking_columns,
)
from starroute.ingest.sol import SOL_ROW
from starroute.paths import DATA_RAW, ORIGIN_JSON, SYSTEMS_CSV, ensure_data_dirs

HOST_KEEP = [
    "sy_name",
    "hostname",
    "hd_name",
    "hip_name",
    "ra",
    "dec",
    "glon",
    "glat",
    "sy_dist",
    "sy_snum",
    "sy_pnum",
    "sy_mnum",
    "cb_flag",
    "st_spectype",
    "st_teff",
    "st_mass",
    "st_rad",
    "st_met",
    "st_metratio",
    "st_lum",
    "st_logg",
    "st_age",
    "st_dens",
    "st_vsin",
    "st_rotp",
    "sy_vmag",
    "sy_gaiamag",
    "st_refname",
    "sy_refname",
]

PLANET_KEEP = [
    "hostname",
    "pl_name",
    "pl_letter",
    "pl_bmasse",
    "pl_rade",
    "pl_eqt",
    "pl_orbsmax",
]

COMPLETENESS_COLS = [
    "st_mass",
    "st_teff",
    "st_age",
    "st_met",
    "st_spectype",
    "ra",
    "dec",
    "sy_dist",
    "st_rotp",
    "st_logg",
]


def _read_nasa_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    header = pd.read_csv(path, comment="#", nrows=0)
    use = [c for c in columns if c in header.columns]
    text_cols = {c: "string" for c in ("hd_name", "hip_name", "st_spectype", "st_metratio") if c in use}
    return pd.read_csv(path, comment="#", usecols=use, dtype=text_cols, low_memory=False)


def detect_default_sources(raw_dir: Path | None = None) -> dict[str, Any]:
    """Pick the newest PSCompPars / STELLARHOSTS snapshots in ``data/raw``."""
    folder = raw_dir or DATA_RAW
    planets = sorted(folder.glob("PSCompPars*.csv"), key=lambda p: p.stat().st_mtime)
    hosts = sorted(folder.glob("STELLARHOSTS*.csv"), key=lambda p: p.stat().st_mtime)
    return {
        "raw_dir": str(folder),
        "planet_candidates": [str(p) for p in planets],
        "host_candidates": [str(p) for p in hosts],
        "planet_path": str(planets[-1]) if planets else None,
        "host_path": str(hosts[-1]) if hosts else None,
    }


def preview_sources(planet_path: str | Path, host_path: str | Path) -> dict[str, Any]:
    """Cheap confirmation payload: row counts, columns, missing coords."""
    planet_path = Path(planet_path)
    host_path = Path(host_path)
    if not planet_path.is_file():
        raise FileNotFoundError(f"Planet table not found: {planet_path}")
    if not host_path.is_file():
        raise FileNotFoundError(f"Stellar-host table not found: {host_path}")

    planets = _read_nasa_csv(planet_path, PLANET_KEEP)
    hosts = _read_nasa_csv(host_path, HOST_KEEP)
    missing = hosts[["ra", "dec", "sy_dist"]].isna().any(axis=1).sum() if len(hosts) else 0
    sample = (
        hosts.dropna(subset=["hostname"])["hostname"]
        .astype(str)
        .drop_duplicates()
        .head(8)
        .tolist()
    )
    return {
        "planet_path": str(planet_path),
        "host_path": str(host_path),
        "planet_rows": int(len(planets)),
        "planet_hosts": int(planets["hostname"].nunique()) if "hostname" in planets else 0,
        "host_rows": int(len(hosts)),
        "unique_hosts": int(hosts["hostname"].nunique()) if "hostname" in hosts else 0,
        "hosts_missing_coords": int(missing),
        "host_columns": list(hosts.columns),
        "planet_columns": list(planets.columns),
        "sample_hosts": sample,
    }


def search_hostnames(
    query: str,
    host_path: str | Path | None = None,
    limit: int = 20,
) -> list[str]:
    """Typeahead list: Sol plus NASA hostnames matching ``query``."""
    needle = (query or "").strip().lower()
    names = ["Sol"]
    if host_path and Path(host_path).is_file():
        hosts = pd.read_csv(host_path, comment="#", usecols=["hostname"], dtype="string")
        names.extend(hosts["hostname"].dropna().astype(str).unique().tolist())
    elif SYSTEMS_CSV.exists():
        hosts = pd.read_csv(SYSTEMS_CSV, usecols=["hostname"])
        names.extend(hosts["hostname"].dropna().astype(str).tolist())
    seen = set()
    unique = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        unique.append(name)
    if needle:
        unique = [name for name in unique if needle in name.lower()]
        unique.sort(key=lambda name: (
            0 if name.lower() == needle else
            1 if name.lower().startswith(needle) else
            2,
            len(name),
            name.lower(),
        ))
    return unique[:limit]


def _recenter(systems: pd.DataFrame, origin_hostname: str) -> pd.DataFrame:
    """Translate XYZ so ``origin_hostname`` sits at (0, 0, 0)."""
    out = systems.copy()
    origin_hostname = origin_hostname or "Sol"
    match = out[out["hostname"] == origin_hostname]
    if match.empty:
        raise ValueError(
            f"Origin '{origin_hostname}' is not in the catalog. "
            "Pick Sol or a host that has RA, Dec, and distance."
        )
    ox = float(match.iloc[0]["calculated_x"])
    oy = float(match.iloc[0]["calculated_y"])
    oz = float(match.iloc[0]["calculated_z"])
    out["calculated_x"] = out["calculated_x"] - ox
    out["calculated_y"] = out["calculated_y"] - oy
    out["calculated_z"] = out["calculated_z"] - oz
    out["distance_from_origin_ly"] = (
        out["calculated_x"] ** 2 + out["calculated_y"] ** 2 + out["calculated_z"] ** 2
    ) ** 0.5
    out["origin_hostname"] = origin_hostname
    return out


def _dedupe_hosts(hosts: pd.DataFrame) -> pd.DataFrame:
    """STELLARHOSTS has one row per literature reference; keep the richest row."""
    work = hosts.copy()
    work["hostname"] = work["hostname"].astype(str)
    work["_year"] = work.get("sy_refname", pd.Series("", index=work.index)).map(extract_year)
    if "st_refname" in work.columns:
        work["_year"] = work["_year"].where(work["_year"] > 0, work["st_refname"].map(extract_year))
    work["_complete"] = completeness_score(work, COMPLETENESS_COLS)
    work = work.sort_values(["_complete", "_year"], ascending=[False, False])
    work = work.drop_duplicates(subset="hostname", keep="first")
    return work.drop(columns=["_year", "_complete"], errors="ignore")


def build_systems_dataset(
    planet_path: str | Path,
    host_path: str | Path,
    output_path: str | Path | None = None,
    max_distance_ly: float = 1000.0,
    min_stellar_mass: float = 0.25,
    origin_hostname: str = "Sol",
) -> dict[str, Any]:
    """Ingest NASA tables → one row per host, plus Sol, written to CSV."""
    ensure_data_dirs()
    planet_path = Path(planet_path)
    host_path = Path(host_path)
    output_path = Path(output_path) if output_path else SYSTEMS_CSV

    planets = _read_nasa_csv(planet_path, PLANET_KEEP)
    hosts = _read_nasa_csv(host_path, HOST_KEEP)
    host_rows_raw = int(len(hosts))
    planets = planets.dropna(subset=["hostname"])
    planets["hostname"] = planets["hostname"].astype(str)
    hosts = hosts.dropna(subset=["hostname"])
    hosts = _dedupe_hosts(hosts)

    flags = classify_planets(planets)
    systems = hosts.merge(flags, on="hostname", how="left")
    for col in PLANET_FLAG_COLUMNS:
        systems[col] = systems[col].fillna(0).astype(int)

    systems = systems.dropna(subset=["ra", "dec", "sy_dist"])
    systems = add_cartesian_columns(systems)
    systems = ranking_columns(systems)
    systems = add_stability(systems)
    systems["manual_entry"] = 0

    sol = pd.DataFrame([SOL_ROW])
    for col in systems.columns:
        if col not in sol.columns:
            sol[col] = pd.NA
    sol = sol[[c for c in systems.columns if c in sol.columns]]
    extra = [c for c in SOL_ROW if c not in systems.columns]
    for col in extra:
        systems[col] = pd.NA
        sol[col] = SOL_ROW[col]
    systems = systems[systems["hostname"] != "Sol"]
    systems = pd.concat([sol, systems], ignore_index=True)

    origin_hostname = (origin_hostname or "Sol").strip() or "Sol"
    systems = _recenter(systems, origin_hostname)

    before_filter = len(systems)
    mass_ok = pd.to_numeric(systems["st_mass"], errors="coerce") >= min_stellar_mass
    keep = (systems["distance_from_origin_ly"] <= max_distance_ly) & mass_ok
    keep = keep | systems["hostname"].eq(origin_hostname)
    systems = systems[keep].copy()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    systems.to_csv(output_path, index=False)
    ORIGIN_JSON.write_text(
        json.dumps({"origin_hostname": origin_hostname, "max_distance_ly": max_distance_ly}, indent=2),
        encoding="utf-8",
    )

    nearest_cols = [c for c in ("hostname", "distance_from_origin_ly", "distance_from_sol_ly", "st_spectype", "sy_pnum") if c in systems.columns]
    return {
        "output_path": str(output_path),
        "planet_rows": int(len(planets)),
        "host_rows_raw": host_rows_raw,
        "unique_hosts_after_dedupe": int(len(hosts)),
        "systems_before_distance_filter": int(before_filter),
        "systems_written": int(len(systems)),
        "includes_sol": bool((systems["hostname"] == "Sol").any()),
        "origin_hostname": origin_hostname,
        "max_distance_ly": max_distance_ly,
        "min_stellar_mass": min_stellar_mass,
        "nearest": systems.nsmallest(6, "distance_from_origin_ly")[nearest_cols].to_dict(orient="records"),
    }
