"""Lift ``systems.csv`` / PLANET_KEEP rows into v3 JSON documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd

from starroute.ids import body_id, host_id
from starroute.schemas.body import BodyDocument
from starroute.schemas.system import CoordCard, FlagCard, SourceRef, StarCard, SystemDocument

_STAR_COLS = (
    "st_spectype",
    "st_teff",
    "st_mass",
    "st_rad",
    "st_lum",
    "st_age",
    "st_rotp",
    "st_met",
    "sy_snum",
    "cb_flag",
)


def _num(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> Optional[int]:
    n = _num(value)
    return None if n is None else int(n)


def _str(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def lift_system_row(
    row: pd.Series,
    *,
    setting_id: Optional[str] = None,
    snapshot: Optional[str] = None,
    body_ids: Optional[list[str]] = None,
) -> SystemDocument:
    hostname = str(row["hostname"])
    manual = bool(_int(row.get("manual_entry")) or 0)
    return SystemDocument(
        id=host_id(hostname),
        hostname=hostname,
        setting_id=setting_id,
        source=SourceRef(
            kind="hand" if manual else "nasa",
            snapshot=None if manual else snapshot,
            manual_entry=manual,
        ),
        star=StarCard(
            st_spectype=_str(row.get("st_spectype")),
            st_teff=_num(row.get("st_teff")),
            st_mass=_num(row.get("st_mass")),
            st_rad=_num(row.get("st_rad")),
            st_lum=_num(row.get("st_lum")),
            st_age=_num(row.get("st_age")),
            st_rotp=_num(row.get("st_rotp")),
            st_met=_num(row.get("st_met")),
            sy_snum=_num(row.get("sy_snum")),
            cb_flag=_int(row.get("cb_flag")),
        ),
        coords=CoordCard(
            ra=_num(row.get("ra")),
            dec=_num(row.get("dec")),
            sy_dist_pc=_num(row.get("sy_dist")),
            distance_from_sol_ly=_num(row.get("distance_from_sol_ly")),
            xyz_ly=[
                _num(row.get("calculated_x")),
                _num(row.get("calculated_y")),
                _num(row.get("calculated_z")),
            ],
            origin_hostname=_str(row.get("origin_hostname")) or "Sol",
        ),
        flags=FlagCard(
            rocky_count=_int(row.get("rocky_count")),
            gas_giant_count=_int(row.get("gas_giant_count")),
            ice_giant_count=_int(row.get("ice_giant_count")),
            stability_score=_int(row.get("stability_score")),
        ),
        bodies=list(body_ids or []),
    )


def lift_systems_csv(
    path: Path | str,
    *,
    setting_id: Optional[str] = None,
    snapshot: Optional[str] = None,
    body_ids_by_host: Optional[dict[str, list[str]]] = None,
) -> list[SystemDocument]:
    df = pd.read_csv(path)
    if "hostname" not in df.columns:
        raise ValueError("systems.csv must include hostname")
    seen: dict[str, str] = {}
    out: list[SystemDocument] = []
    for _, row in df.iterrows():
        hostname = str(row["hostname"])
        sid = host_id(hostname)
        if sid in seen and seen[sid] != hostname:
            raise ValueError(f"id_collision: {sid!r} from {seen[sid]!r} and {hostname!r}")
        seen[sid] = hostname
        bodies = (body_ids_by_host or {}).get(hostname, [])
        out.append(
            lift_system_row(
                row,
                setting_id=setting_id,
                snapshot=snapshot,
                body_ids=bodies,
            )
        )
    return out


def lift_bodies_from_planets(
    rows: pd.DataFrame | Iterable[dict[str, Any]] | Path | str,
    *,
    snapshot: Optional[str] = None,
) -> list[BodyDocument]:
    if isinstance(rows, (str, Path)):
        df = pd.read_csv(rows)
    elif isinstance(rows, pd.DataFrame):
        df = rows
    else:
        df = pd.DataFrame(list(rows))
    docs: list[BodyDocument] = []
    for _, row in df.iterrows():
        hostname = str(row["hostname"])
        letter = _str(row.get("pl_letter"))
        if not letter:
            continue
        docs.append(
            BodyDocument(
                id=body_id(hostname, letter),
                host_id=host_id(hostname),
                pl_name=_str(row.get("pl_name")),
                source=SourceRef(kind="nasa", snapshot=snapshot, manual_entry=False),
                pl_letter=letter,
                pl_bmasse=_num(row.get("pl_bmasse")),
                pl_rade=_num(row.get("pl_rade")),
                pl_eqt=_num(row.get("pl_eqt")),
                pl_orbsmax=_num(row.get("pl_orbsmax")),
                class_guess=None,
                role=None,
            )
        )
    return docs
