"""Read façade: JSON store first, then v2 CSV files (looked up at request time)."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from starroute.api.v1.errors import Problem
from starroute.ids import host_id
from starroute import paths
from starroute.schemas.lift import lift_systems_csv
from starroute.store.documents import JsonStore


def _store() -> JsonStore:
    return JsonStore()


def setting_ids() -> list[str]:
    return _store().list_ids("settings")


def require_setting_id(setting_id: Optional[str]) -> Optional[str]:
    known = setting_ids()
    if setting_id:
        return setting_id
    if len(known) > 1:
        raise Problem(400, "missing_setting_id", "setting_id is required when more than one setting exists")
    if len(known) == 1:
        return known[0]
    return None


def load_systems_df() -> pd.DataFrame:
    if not paths.SYSTEMS_CSV.exists():
        raise Problem(404, "not_found", "No systems catalog (run ingest or generate)")
    return pd.read_csv(paths.SYSTEMS_CSV)


def load_network_df() -> pd.DataFrame:
    if not paths.NETWORK_CSV.exists():
        raise Problem(404, "not_found", "No network has been generated yet")
    return pd.read_csv(paths.NETWORK_CSV)


def system_document(hostname: str, setting_id: Optional[str]) -> dict:
    sid = host_id(hostname)
    stored = _store().get("systems", sid)
    if stored:
        return stored
    df = load_systems_df()
    row = df[df["hostname"].astype(str) == hostname]
    if row.empty:
        raise Problem(404, "not_found", f"Unknown host {hostname!r}")
    docs = lift_systems_csv(
        paths.SYSTEMS_CSV,
        setting_id=setting_id,
    )
    for doc in docs:
        if doc.hostname == hostname:
            return doc.model_dump(by_alias=True)
    raise Problem(404, "not_found", f"Unknown host {hostname!r}")
