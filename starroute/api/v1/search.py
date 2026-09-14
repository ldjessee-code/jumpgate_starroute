"""TravellerMap-style AND tokens. Advisories are derived from contention."""

from __future__ import annotations

import fnmatch
from typing import Any, Optional

from starroute.api.v1.catalog import load_systems_df
from starroute.api.v1.errors import Problem
from starroute.api.v1.overlays import get_affiliations
from starroute.ids import host_id
from starroute.mapgen.phenomena import classify_star
from starroute.mapgen.politics import advisory_for
from starroute.store.documents import JsonStore


def parse_query(q: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    for raw in (q or "").split():
        if ":" in raw:
            prefix, _, value = raw.partition(":")
            tokens.append((prefix.lower(), value))
        else:
            tokens.append(("name", raw))
    return tokens


def _affiliation_row(setting_id: Optional[str], sid: str, hostname: str) -> dict[str, Any]:
    if not setting_id:
        return {}
    systems = (get_affiliations(setting_id).get("systems") or {})
    return dict(systems.get(sid) or systems.get(hostname) or {})


def _present_ids(row: dict[str, Any]) -> set[str]:
    ids = set()
    if row.get("controlling"):
        ids.add(str(row["controlling"]))
    for item in row.get("present") or []:
        if item.get("faction_id"):
            ids.add(str(item["faction_id"]))
    return ids


def _roles(sid: str) -> set[str]:
    store = JsonStore()
    doc = store.get("systems", sid) or {}
    roles = {str(r) for r in doc.get("roles_stub") or [] if r}
    for bid in doc.get("bodies") or []:
        body = store.get("bodies", bid) or {}
        if body.get("role"):
            roles.add(str(body["role"]))
        for tag in body.get("tags") or []:
            roles.add(str(tag))
    return roles


def system_card(row, setting_id: Optional[str]) -> dict[str, Any]:
    hostname = str(row["hostname"])
    sid = host_id(hostname)
    aff = _affiliation_row(setting_id, sid, hostname)
    contention = aff.get("contention") or "none"
    payload = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    return {
        "id": sid,
        "hostname": hostname,
        "sy_name": str(row.get("sy_name") or hostname),
        "st_spectype": None if row.get("st_spectype") != row.get("st_spectype") else row.get("st_spectype"),
        "controlling": aff.get("controlling"),
        "factions": sorted(_present_ids(aff)),
        "contention": contention,
        "advisory": advisory_for(contention),
        "hazards": classify_star(payload),
        "binary": bool(
            (row.get("sy_snum") == row.get("sy_snum") and float(row.get("sy_snum") or 0) >= 2)
            or (row.get("cb_flag") == row.get("cb_flag") and float(row.get("cb_flag") or 0) >= 1)
        ),
    }


def _match(card: dict[str, Any], prefix: str, value: str) -> bool:
    hostname = card["hostname"]
    sid = card["id"]
    if prefix == "name":
        needle = value.lower()
        return needle in hostname.lower() or needle in str(card.get("sy_name") or "").lower() or needle in sid
    if prefix in {"alleg", "faction"}:
        return value.lower() in {x.lower() for x in card.get("factions") or []}
    if prefix == "zone":
        return card["advisory"] == value.lower()
    if prefix == "contention":
        return card["contention"] == value.lower()
    if prefix == "stellar":
        spec = str(card.get("st_spectype") or "")
        return fnmatch.fnmatch(spec.upper(), value.upper())
    if prefix == "host":
        return hostname.lower() == value.lower() or sid == host_id(value)
    if prefix == "binary":
        if value.lower() in {"", "1", "true", "yes"}:
            return card["binary"]
        if value.lower() in {"0", "false", "no"}:
            return not card["binary"]
        return card["binary"]
    if prefix == "hazard":
        return value in card["hazards"] or any(value.lower() in h.lower() for h in card["hazards"])
    if prefix == "role":
        return value.lower() in {r.lower() for r in _roles(sid)}
    return False


def search_systems(q: str, setting_id: Optional[str]) -> dict[str, Any]:
    if not (q or "").strip():
        raise Problem(400, "validation_error", "q is required", instance="/search")
    tokens = parse_query(q)
    df = load_systems_df()
    hits = []
    for _, row in df.iterrows():
        card = system_card(row, setting_id)
        if all(_match(card, prefix, value) for prefix, value in tokens):
            hits.append(card)
    return {"setting_id": setting_id, "q": q, "count": len(hits), "hits": hits}


def get_advisory(system_id: str, setting_id: Optional[str]) -> dict[str, Any]:
    df = load_systems_df()
    from starroute.api.v1.resolve import resolve_host

    hostname = resolve_host(system_id, df, instance=f"/systems/{system_id}/advisory")
    row = df[df["hostname"].astype(str) == hostname].iloc[0]
    card = system_card(row, setting_id)
    return {
        "system_id": card["id"],
        "hostname": hostname,
        "contention": card["contention"],
        "advisory": card["advisory"],
        "setting_id": setting_id,
    }
