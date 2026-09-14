"""Affiliation, legal, and trade overlay documents (no tick)."""

from __future__ import annotations

from typing import Any, Optional

from starroute.api.v1.catalog import load_systems_df
from starroute.api.v1.errors import Problem
from starroute.api.v1.resolve import resolve_host
from starroute.ids import host_id
from starroute.mapgen.factions import load_faction_config
from starroute.mapgen.politics import influence_ok, renormalize
from starroute.store.documents import JsonStore


def _store() -> JsonStore:
    return JsonStore()


def faction_id(name: str) -> str:
    return host_id(name)


def seed_factions() -> list[dict[str, Any]]:
    cfg = load_faction_config()
    names = [cfg.get("human_root_group") or "Human"]
    for species in cfg.get("species") or []:
        names.append(species.get("name") or "")
    out = []
    seen = set()
    for name in names:
        if not name:
            continue
        fid = faction_id(name)
        if fid in seen:
            continue
        seen.add(fid)
        out.append({"id": fid, "name": name, "chronos_ref": f"faction.{fid}"})
    return out


def get_affiliations(setting_id: str) -> dict[str, Any]:
    doc = _store().get("overlays", f"{setting_id}-affiliations")
    if doc:
        return doc
    return {"schema": "jumpgate.affiliations.v1", "setting_id": setting_id, "systems": {}}


def put_affiliations(setting_id: str, body: dict[str, Any]) -> dict[str, Any]:
    systems = dict(body.get("systems") or {})
    for sid, row in systems.items():
        present = list(row.get("present") or [])
        if present and not influence_ok(present):
            if body.get("renormalize"):
                row["present"] = renormalize(present)
                systems[sid] = row
            else:
                raise Problem(
                    409,
                    "influence_sum",
                    f"Influence on {sid} must sum to 1",
                    instance=f"/settings/{setting_id}/affiliations",
                )
        controlling = row.get("controlling")
        if controlling and present:
            ids = {p.get("faction_id") for p in present}
            if controlling not in ids:
                raise Problem(
                    400,
                    "validation_error",
                    f"controlling {controlling!r} must be in present",
                    instance=f"/settings/{setting_id}/affiliations",
                )
    doc = {
        "schema": "jumpgate.affiliations.v1",
        "setting_id": setting_id,
        "systems": systems,
    }
    return _store().put("overlays", f"{setting_id}-affiliations", doc)


def put_system_affiliations(system_id: str, body: dict[str, Any], setting_id: Optional[str]) -> dict[str, Any]:
    if not setting_id:
        raise Problem(400, "missing_setting_id", "setting_id is required", instance=f"/systems/{system_id}/affiliations")
    df = load_systems_df()
    hostname = resolve_host(system_id, df, instance=f"/systems/{system_id}/affiliations")
    sid = host_id(hostname)
    overlay = get_affiliations(setting_id)
    systems = dict(overlay.get("systems") or {})
    systems[sid] = body
    return put_affiliations(setting_id, {"systems": systems, "renormalize": body.get("renormalize")})


def get_legal(faction_id: str) -> dict[str, Any]:
    doc = _store().get("legal", faction_id)
    if doc:
        return doc
    return {
        "schema": "jumpgate.legal.v1",
        "faction_id": faction_id,
        "government": None,
        "conflict_family": None,
        "schedule": [],
        "tariff_paid_by": "importer",
    }


def put_legal(faction_id: str, body: dict[str, Any]) -> dict[str, Any]:
    allowed = {"free", "taxed", "permit", "banned"}
    schedule = list(body.get("schedule") or [])
    for row in schedule:
        if row.get("status") not in allowed:
            raise Problem(400, "validation_error", f"Bad legal status {row.get('status')!r}", instance=f"/factions/{faction_id}/legal")
    doc = {
        "schema": "jumpgate.legal.v1",
        "faction_id": faction_id,
        "government": body.get("government"),
        "conflict_family": body.get("conflict_family"),
        "schedule": schedule,
        "tariff_paid_by": body.get("tariff_paid_by") or "importer",
    }
    return _store().put("legal", faction_id, doc)


def get_trade(network_id: str) -> dict[str, Any]:
    doc = _store().get("trade", network_id)
    if doc:
        return doc
    return {"schema": "jumpgate.trade.v1", "network_id": network_id, "practices": []}


def put_trade(network_id: str, body: dict[str, Any]) -> dict[str, Any]:
    doc = {
        "schema": "jumpgate.trade.v1",
        "network_id": network_id,
        "practices": list(body.get("practices") or []),
    }
    return _store().put("trade", network_id, doc)
