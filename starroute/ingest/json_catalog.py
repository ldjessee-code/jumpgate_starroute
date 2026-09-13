"""Write L0–L2 JSON documents after NASA ingest (CSV remains the v2 export)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pandas as pd

from starroute.ids import host_id
from starroute.schemas.lift import lift_bodies_from_planets, lift_systems_csv
from starroute.store.documents import JsonStore


def emit_json_catalog(
    systems_path: Path | str,
    planets: pd.DataFrame,
    *,
    setting_id: Optional[str] = None,
    planet_snapshot: Optional[str] = None,
    host_snapshot: Optional[str] = None,
    store: JsonStore | None = None,
) -> dict[str, Any]:
    """Persist one system document per host and one body document per PLANET_KEEP row.

    NASA nulls stay null. Only planets whose hostname is in the systems table are written.
    """
    store = store or JsonStore()
    systems_path = Path(systems_path)
    systems_df = pd.read_csv(systems_path)
    hosts = set(systems_df["hostname"].astype(str))
    if planets is None or planets.empty:
        planet_rows = pd.DataFrame()
    else:
        planet_rows = planets[planets["hostname"].astype(str).isin(hosts)].copy()

    body_ids_by_host: dict[str, list[str]] = {h: [] for h in hosts}
    bodies = lift_bodies_from_planets(planet_rows, snapshot=planet_snapshot) if len(planet_rows) else []
    written_bodies = 0
    for body in bodies:
        hostname = next((h for h in hosts if host_id(h) == body.host_id), None)
        if hostname is None:
            continue
        store.put("bodies", body.id, body.model_dump(by_alias=True))
        body_ids_by_host[hostname].append(body.id)
        written_bodies += 1

    system_docs = lift_systems_csv(
        systems_path,
        setting_id=setting_id,
        snapshot=host_snapshot,
        body_ids_by_host=body_ids_by_host,
    )
    for doc in system_docs:
        store.put("systems", doc.id, doc.model_dump(by_alias=True))

    return {
        "systems_json": len(system_docs),
        "bodies_json": written_bodies,
        "setting_id": setting_id,
    }
