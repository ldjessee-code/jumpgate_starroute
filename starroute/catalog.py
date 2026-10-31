"""Stream the merged star catalog and trim it for one map.

The full catalog stays where it is. A map build keeps only the stars inside
that map's max distance from its origin. NASA ingest, then
``sample-systems.csv``, is the fallback when the catalog file is missing.
"""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

import pandas as pd

from starroute.coords import PC_TO_LY, ra_dec_dist_to_xyz
from starroute.ingest.sol import SOL_ROW
from starroute.luminosity import calculate_luminosity
from starroute.names import catalog_id_token, gliese_token, primary_letter, split_host_component
from starroute.paths import CATALOG_JSON, SAMPLE_SYSTEMS_CSV, SYSTEMS_CSV
from starroute.turquenish import clean_id

CATALOG_ENV = "STARROUTE_CATALOG"

MERGED_COLUMNS = [
    "star_key",
    "gaia_source_id",
    "hyg_id",
    "hip",
    "hd",
    "hr",
    "gl",
    "proper",
    "exo_hostname",
    "ra_deg",
    "dec_deg",
    "epoch",
    "dist_pc",
    "dist_ly",
    "x",
    "y",
    "z",
    "parallax",
    "pmra",
    "pmdec",
    "radial_velocity",
    "mag_v",
    "phot_g_mean_mag",
    "render_mag",
    "bp_rp",
    "ci",
    "spect",
    "has_known_exoplanets",
    "exoplanet_count",
    "exo_match_method",
    "sources",
    "match_method",
    "turquenish_system",
]

ENRICH_FIELDS = (
    "st_mass",
    "st_spectype",
    "sy_pnum",
    "sy_snum",
    "sy_mnum",
    "cb_flag",
    "st_met",
    "carbon_ranking",
    "sulfur_ranking",
    "silicon_ranking",
    "combined_score",
    "stability_score",
    "stability_symbol",
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
    "gate_status",
    "disc_year",
    "pl_controv_flag",
    "bf",
    "bayer",
    "con",
    "flam",
)


def _float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in {"", "nan", "none"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number


def load_catalog_config(path: str | Path | None = None) -> dict[str, Any]:
    file_path = Path(path) if path else CATALOG_JSON
    if not file_path.is_file():
        return {}
    with file_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def resolve_catalog_path(
    cli: str | Path | None = None,
    *,
    config_file: str | Path | None = None,
) -> Path | None:
    """CLI, then ``STARROUTE_CATALOG``, then ``config/catalog.json``.

    A path that is not a file is skipped so the caller can fall back.
    An explicit CLI path that is missing raises, so a typo is not silent.
    """
    if cli:
        chosen = Path(cli)
        if not chosen.is_file():
            raise FileNotFoundError(f"Catalog not found: {chosen}")
        return chosen
    env = os.environ.get(CATALOG_ENV, "").strip()
    if env:
        env_path = Path(env)
        if env_path.is_file():
            return env_path
    config = load_catalog_config(config_file)
    raw = str(config.get("merged_catalog") or "").strip()
    if raw and Path(raw).is_file():
        return Path(raw)
    return None


def iter_catalog_rows(path: str | Path) -> Iterator[dict[str, str]]:
    """Stream one merged-catalog CSV. The file is opened read-only."""
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def distance_ly(row: Mapping[str, Any], origin_xyz: tuple[float, float, float]) -> float | None:
    """Light-years from ``origin_xyz``. Adapted rows use calculated_* (ly)."""
    try:
        x = float(row["calculated_x"])
        y = float(row["calculated_y"])
        z = float(row["calculated_z"])
    except (KeyError, TypeError, ValueError):
        return None
    ox, oy, oz = origin_xyz
    return ((x - ox) ** 2 + (y - oy) ** 2 + (z - oz) ** 2) ** 0.5


def trim_records(
    records: Iterable[Mapping[str, Any]],
    origin_xyz: tuple[float, float, float],
    max_distance_ly: float,
) -> list[Mapping[str, Any]]:
    """Stars at or inside the radius. Does not modify ``records`` or its rows."""
    limit = float(max_distance_ly)
    kept: list[Mapping[str, Any]] = []
    for row in records:
        dist = distance_ly(row, origin_xyz)
        if dist is not None and dist <= limit:
            kept.append(row)
    return kept


def _is_sol(row: Mapping[str, Any]) -> bool:
    key = clean_id(row.get("star_key")).lower()
    hyg = clean_id(row.get("hyg_id"))
    proper = clean_id(row.get("proper")).lower()
    host = clean_id(row.get("hostname")).lower()
    return key == "hyg:0" or hyg == "0" or proper in {"sol", "sun"} or host in {"sol", "sun"}


def _hostname(row: Mapping[str, Any]) -> str:
    if _is_sol(row):
        return "Sol"
    for key in ("hostname", "proper", "exo_hostname", "sy_name", "star_key"):
        text = clean_id(row.get(key))
        if text:
            return text
    return "unknown"


def _component_letter(row: Mapping[str, Any]) -> str:
    """Trailing A/B from hostname, Gliese, or HIP/HD. Bare is the primary."""
    for key in ("hostname", "exo_hostname", "sy_name", "gl", "hip", "hip_name", "hd", "hd_name"):
        _, letter = split_host_component(row.get(key))
        if letter:
            return letter
    glued = gliese_token(row.get("gl"))
    if glued and glued[-1].isalpha():
        return glued[-1].upper()
    for raw, prefix in (
        (row.get("hip") or row.get("hip_name"), "HIP"),
        (row.get("hd") or row.get("hd_name"), "HD"),
    ):
        token = catalog_id_token(raw, prefix) or catalog_id_token(raw)
        if token and token[-1].isalpha():
            return token[-1].upper()
    return ""


def _catalog_tokens(raw: Any, prefix: str, letter: str) -> list[str]:
    token = catalog_id_token(raw, prefix) or catalog_id_token(raw)
    if not token:
        return []
    has_letter = token[-1].isalpha()
    if has_letter:
        return [token]
    if letter and letter != "A":
        return [token + letter]
    return [token, token + "A"]


def _index_keys(row: Mapping[str, Any]) -> list[str]:
    keys = []
    host = clean_id(row.get("hostname") or row.get("sy_name") or row.get("proper") or row.get("exo_hostname"))
    letter = _component_letter(row)
    if host:
        keys.append("host:" + host.lower())
        base, host_letter = split_host_component(host)
        if host_letter:
            keys.append("host:" + f"{base} {host_letter}".lower())
        elif base:
            keys.append("host:" + f"{base} a".lower())
    for label, raw, prefix in (
        ("hip", row.get("hip") or row.get("hip_name"), "HIP"),
        ("hd", row.get("hd") or row.get("hd_name"), "HD"),
    ):
        for token in _catalog_tokens(raw, prefix, letter):
            keys.append(f"{label}:{token}")
    gl = gliese_token(row.get("gl"))
    if gl:
        keys.append("gl:" + gl.lower())
    star_key = clean_id(row.get("star_key"))
    if star_key:
        keys.append("key:" + star_key)
    return keys


def load_enrichment(paths: Iterable[str | Path] | None = None) -> dict[str, dict[str, str]]:
    """First matching NASA/sample row wins. Used only to fill mass and ranks."""
    sources = list(paths) if paths is not None else [SAMPLE_SYSTEMS_CSV, SYSTEMS_CSV]
    index: dict[str, dict[str, str]] = {}
    for raw_path in sources:
        path = Path(raw_path)
        if not path.is_file():
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                payload = {
                    key: row[key]
                    for key in ENRICH_FIELDS
                    if key in row and str(row[key]).strip() not in {"", "nan", "None"}
                }
                if not payload:
                    continue
                payload["_component"] = _component_letter(row)
                for key in _index_keys(row):
                    index.setdefault(key, payload)
    return index


def _xyz_ly_from_merged(row: Mapping[str, Any]) -> tuple[float, float, float] | None:
    if _is_sol(row):
        return 0.0, 0.0, 0.0
    x = _float(row.get("x"))
    y = _float(row.get("y"))
    z = _float(row.get("z"))
    if x is not None and y is not None and z is not None:
        return x * PC_TO_LY, y * PC_TO_LY, z * PC_TO_LY
    dist = _float(row.get("dist_ly"))
    ra = _float(row.get("ra_deg"))
    dec = _float(row.get("dec_deg"))
    if dist is None or ra is None or dec is None:
        return None
    cx, cy, cz = ra_dec_dist_to_xyz(ra, dec, dist)
    return float(cx), float(cy), float(cz)


def _heliocentric_ly(row: Mapping[str, Any]) -> float | None:
    if _is_sol(row):
        return 0.0
    dist = _float(row.get("dist_ly"))
    if dist is not None:
        return dist
    xyz = _xyz_ly_from_merged(row)
    if xyz is None:
        return None
    return (xyz[0] ** 2 + xyz[1] ** 2 + xyz[2] ** 2) ** 0.5


def _row_matches_origin(row: Mapping[str, Any], origin: str) -> bool:
    needle = origin.strip().lower()
    if needle in {"sol", "sun"} and _is_sol(row):
        return True
    for key in ("hostname", "proper", "exo_hostname", "sy_name", "star_key"):
        if clean_id(row.get(key)).lower() == needle:
            return True
    return False


def _payload_without_meta(payload: Mapping[str, str]) -> dict[str, str]:
    return {key: value for key, value in payload.items() if not str(key).startswith("_")}


def _letter_from_key(key: str) -> str:
    body = key.split(":", 1)[1] if ":" in key else key
    _, letter = split_host_component(body)
    if letter:
        return letter
    glued = re.search(r"(\d)([A-D])$", body, flags=re.IGNORECASE)
    if glued:
        return glued.group(2).upper()
    return ""


def _enrich(row: Mapping[str, Any], index: Mapping[str, Mapping[str, str]]) -> dict[str, str]:
    """Fill mass and ranks from a matching component. Never cross A/B."""
    want = primary_letter(_component_letter(row))
    for key in _index_keys(row):
        payload = index.get(key)
        if not payload:
            continue
        got = payload.get("_component") or _letter_from_key(key)
        if primary_letter(got) != want:
            continue
        return _payload_without_meta(payload)
    host = _hostname(row).lower()
    fallback = "host:" + host
    payload = index.get(fallback)
    if payload:
        got = payload.get("_component") or _letter_from_key(fallback)
        if primary_letter(got) == want:
            return _payload_without_meta(payload)
    return {}


def _lum_inputs(row: Mapping[str, Any], adapted: Mapping[str, Any]) -> dict[str, Any]:
    """Catalog luminosity cells plus Johnson V and distance. Does not copy them onto ``adapted``."""

    def first(*values: Any) -> Any:
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and value.strip().lower() in {"", "nan", "none", "<na>"}:
                continue
            return value
        return None

    return {
        "st_lum": row.get("st_lum"),
        "luminosity": row.get("luminosity"),
        "lum": row.get("lum"),
        "lum_solar": row.get("lum_solar"),
        "mag_v": first(row.get("mag_v"), adapted.get("mag_v")),
        "sy_vmag": first(row.get("sy_vmag"), adapted.get("sy_vmag")),
        "dist_pc": first(row.get("dist_pc"), adapted.get("dist_pc")),
    }


def adapt_merged_row(row: Mapping[str, Any], enrichment: Mapping[str, Mapping[str, str]] | None = None) -> dict[str, Any]:
    """One merged-catalog row → the systems-table shape the network already reads."""
    extra = _enrich(row, enrichment or {})
    xyz = _xyz_ly_from_merged(row)
    if xyz is None:
        xyz = (float("nan"), float("nan"), float("nan"))
    sol = _is_sol(row)
    hostname = _hostname(row)
    dist_pc = 0.0 if sol else _float(row.get("dist_pc"))
    dist_ly = 0.0 if sol else _heliocentric_ly(row)
    mass = _float(extra.get("st_mass"))
    if sol:
        mass = 1.0
    elif mass is None:
        mass = _float(row.get("st_mass"))
    sy_pnum = _float(extra.get("sy_pnum"))
    if sol:
        sy_pnum = 8.0
    elif sy_pnum is None:
        sy_pnum = _float(row.get("sy_pnum"))
    catalog_count = _float(row.get("exoplanet_count"))
    if sol:
        catalog_count = 8.0
    spect = clean_id(row.get("spect")) or clean_id(extra.get("st_spectype")) or ("G2 V" if sol else "")
    if sol:
        has_text = "true"
    else:
        flag = str(row.get("has_known_exoplanets")).strip().lower() == "true"
        has_text = "true" if flag or (catalog_count or 0) > 0 else "false"
    adapted: dict[str, Any] = {
        "hostname": hostname,
        "sy_name": hostname,
        "ra": 0.0 if sol else _float(row.get("ra_deg")),
        "dec": 0.0 if sol else _float(row.get("dec_deg")),
        "sy_dist": dist_pc if dist_pc is not None else "",
        "sy_pnum": sy_pnum if sy_pnum is not None else 0,
        "st_mass": mass if mass is not None else "",
        "st_spectype": spect,
        "sy_vmag": _float(row.get("mag_v")),
        "sy_gaiamag": _float(row.get("phot_g_mean_mag")),
        "calculated_x": xyz[0],
        "calculated_y": xyz[1],
        "calculated_z": xyz[2],
        "distance_from_sol_ly": dist_ly if dist_ly is not None else "",
        "has_known_exoplanets": has_text,
        "exoplanet_count": catalog_count if catalog_count is not None else 0,
        "star_key": "hyg:0" if sol else clean_id(row.get("star_key")),
        "gaia_source_id": "" if sol else clean_id(row.get("gaia_source_id")),
        "hyg_id": "0" if sol else clean_id(row.get("hyg_id")),
        "hip": clean_id(row.get("hip") or row.get("hip_name")),
        "hd": clean_id(row.get("hd") or row.get("hd_name")),
        "bf": clean_id(row.get("bf") or extra.get("bf")),
        "bayer": clean_id(row.get("bayer") or extra.get("bayer")),
        "con": clean_id(row.get("con") or extra.get("con")),
        "flam": clean_id(row.get("flam") or extra.get("flam")),
        "proper": "Sol" if sol else clean_id(row.get("proper")),
        "bp_rp": _float(row.get("bp_rp")),
        "ci": _float(row.get("ci")),
        "spect": spect,
        "mag": _float(row.get("render_mag") or row.get("mag_v")),
        "x": 0.0 if sol else _float(row.get("x")),
        "y": 0.0 if sol else _float(row.get("y")),
        "z": 0.0 if sol else _float(row.get("z")),
        "ra_deg": 0.0 if sol else _float(row.get("ra_deg")),
        "dec_deg": 0.0 if sol else _float(row.get("dec_deg")),
        "dist_pc": dist_pc if dist_pc is not None else "",
        "render_mag": _float(row.get("render_mag")),
        "mag_v": _float(row.get("mag_v")),
        "stability_symbol": extra.get("stability_symbol") or "circle",
    }
    for key in ENRICH_FIELDS:
        # A merged exoplanet_count stays the catalog value. Enrichment must not replace it.
        if key == "exoplanet_count":
            continue
        if key in adapted and adapted[key] not in ("", None):
            continue
        if key in extra and key != "exoplanet_count":
            adapted[key] = extra[key]
    if sol:
        for key, value in SOL_ROW.items():
            if key not in adapted or adapted[key] in ("", None):
                adapted[key] = value
        adapted["has_known_exoplanets"] = "true"
        adapted["st_mass"] = 1.0
        adapted["sy_pnum"] = 8
    lum, method = calculate_luminosity(_lum_inputs(row, adapted))
    adapted["calculated_luminosity"] = lum
    adapted["calculated_luminosity_method"] = method
    return adapted


def _unique_hostnames(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, int] = {}
    out = []
    for row in rows:
        name = str(row.get("hostname") or "unknown")
        count = seen.get(name, 0)
        seen[name] = count + 1
        if count:
            row = dict(row)
            row["hostname"] = f"{name} [{row.get('star_key') or count}]"
            row["sy_name"] = row["hostname"]
        out.append(row)
    return out


def _origin_xyz(path: Path, origin: str) -> tuple[float, float, float]:
    if origin.strip().lower() in {"sol", "sun"}:
        return 0.0, 0.0, 0.0
    for row in iter_catalog_rows(path):
        if _row_matches_origin(row, origin):
            xyz = _xyz_ly_from_merged(row)
            if xyz is None:
                break
            return xyz
    raise ValueError(f"Origin '{origin}' is not in the catalog {path}")


def stream_trimmed_rows(
    path: str | Path,
    *,
    origin: str = "Sol",
    max_distance_ly: float = 60.0,
    enrichment: Mapping[str, Mapping[str, str]] | None = None,
    enrichment_paths: Iterable[str | Path] | None = None,
) -> list[dict[str, Any]]:
    """Stream ``path`` and return adapted rows inside the radius.

    The catalog file is not written. Pass ``enrichment`` (or
    ``enrichment_paths``) to fill stellar mass from the NASA/sample tables.
    An explicit empty ``enrichment`` skips those tables.
    """
    catalog = Path(path)
    if enrichment is not None:
        index = enrichment
    else:
        index = load_enrichment(enrichment_paths)
    origin_xyz = _origin_xyz(catalog, origin)
    limit = float(max_distance_ly)
    kept: list[dict[str, Any]] = []
    sol_seen = False
    for row in iter_catalog_rows(catalog):
        xyz = _xyz_ly_from_merged(row)
        if xyz is None:
            continue
        dist = ((xyz[0] - origin_xyz[0]) ** 2 + (xyz[1] - origin_xyz[1]) ** 2 + (xyz[2] - origin_xyz[2]) ** 2) ** 0.5
        # Sol-origin rows may carry dist_ly that is the published figure.
        # Prefer that when the origin is Sol so a blank xyz still cannot sneak in,
        # and so the published distance is the trim measure.
        if origin.strip().lower() in {"sol", "sun"}:
            published = _heliocentric_ly(row)
            if published is not None:
                dist = published
        if dist > limit:
            continue
        adapted = adapt_merged_row(row, index)
        adapted["origin_hostname"] = origin
        ox, oy, oz = origin_xyz
        adapted["calculated_x"] = float(adapted["calculated_x"]) - ox
        adapted["calculated_y"] = float(adapted["calculated_y"]) - oy
        adapted["calculated_z"] = float(adapted["calculated_z"]) - oz
        dx = float(adapted["calculated_x"])
        dy = float(adapted["calculated_y"])
        dz = float(adapted["calculated_z"])
        adapted["distance_from_origin_ly"] = (dx * dx + dy * dy + dz * dz) ** 0.5
        if adapted["hostname"] == "Sol":
            sol_seen = True
        kept.append(adapted)
    if origin.strip().lower() in {"sol", "sun"} and not sol_seen and limit >= 0:
        sol = adapt_merged_row({"star_key": "hyg:0", "hyg_id": "0", "proper": "Sol", "x": 0, "y": 0, "z": 0, "dist_ly": 0, "dist_pc": 0}, index)
        sol["origin_hostname"] = origin
        sol["distance_from_origin_ly"] = 0.0
        kept.insert(0, sol)
    return _unique_hostnames(kept)


def load_trimmed_frame(
    path: str | Path,
    origin: str = "Sol",
    max_distance_ly: float = 60.0,
    enrichment: Mapping[str, Mapping[str, str]] | None = None,
    enrichment_paths: Iterable[str | Path] | None = None,
) -> pd.DataFrame:
    rows = stream_trimmed_rows(
        path,
        origin=origin,
        max_distance_ly=max_distance_ly,
        enrichment=enrichment,
        enrichment_paths=enrichment_paths,
    )
    return pd.DataFrame(rows)
