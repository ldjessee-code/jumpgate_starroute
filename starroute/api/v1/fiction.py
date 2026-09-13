"""Slider 2–4 writes: overrides, extra edges, generated hosts, xyz."""

from __future__ import annotations

from typing import Any, Optional

from starroute.api.v1.catalog import load_systems_df, system_document
from starroute.api.v1.errors import Problem
from starroute.api.v1.resolve import resolve_host
from starroute.api.v1.settings import require_reality
from starroute.ids import edge_id, host_id
from starroute.schemas.system import CoordCard, SourceRef, SystemDocument
from starroute.store.documents import JsonStore


def _store() -> JsonStore:
    return JsonStore()


def _ensure_system(hostname: str, setting_id: Optional[str]) -> dict[str, Any]:
    sid = host_id(hostname)
    stored = _store().get("systems", sid)
    if stored:
        return stored
    doc = system_document(hostname, setting_id)
    return _store().put("systems", sid, doc)


def _get_path(doc: dict[str, Any], path: str) -> Any:
    cur: Any = doc
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _set_path(doc: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur: Any = doc
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def apply_overrides(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    for item in list(out.get("overrides") or []):
        path = item.get("path")
        if path:
            _set_path(out, path, item.get("to"))
    return out


def put_override(system_id: str, body: dict[str, Any], setting_id: Optional[str]) -> dict[str, Any]:
    instance = f"/systems/{system_id}/overrides"
    require_reality(setting_id, 2, instance)
    df = load_systems_df()
    hostname = resolve_host(system_id, df, instance=instance)
    system = _ensure_system(hostname, setting_id)
    path = str(body.get("path") or "")
    if not path:
        raise Problem(400, "validation_error", "path is required", instance=instance)
    current = _get_path(system, path)
    expected = body.get("from", current)
    if expected != current and body.get("from") is not None and current != body.get("from"):
        raise Problem(409, "etag_mismatch", f"{path} is not {body.get('from')!r}", instance=instance)
    entry = {
        "path": path,
        "from": current,
        "to": body.get("to"),
        "reason": body.get("reason"),
    }
    overrides = [o for o in list(system.get("overrides") or []) if o.get("path") != path]
    overrides.append(entry)
    system["overrides"] = overrides
    return _store().put("systems", system["id"], system)


def put_extra_edge(
    network_id: str,
    a: str,
    b: str,
    body: dict[str, Any],
    setting_id: Optional[str],
) -> dict[str, Any]:
    instance = f"/networks/{network_id}/edges/{a}/{b}"
    stop = require_reality(setting_id, 3, instance)
    df = load_systems_df()
    store = _store()
    a_host = _resolve_any_host(a, df, store, instance)
    b_host = _resolve_any_host(b, df, store, instance)
    if stop < 4:
        for hostname in (a_host, b_host):
            doc = store.get("systems", host_id(hostname)) or {}
            kind = (doc.get("source") or {}).get("kind")
            if kind == "generated":
                raise Problem(409, "reality_forbidden", "Generated hosts require reality >= 4", instance=instance)
            if hostname not in set(df["hostname"].astype(str)):
                raise Problem(409, "reality_forbidden", "Extra edges at stop 3 must join catalog hosts", instance=instance)
    a_id, b_id = host_id(a_host), host_id(b_host)
    edge = {
        "id": edge_id(a_host, b_host),
        "a": a_id,
        "b": b_id,
        "a_hostname": a_host,
        "b_hostname": b_host,
        "distance_ly": body.get("distance_ly"),
        "band": body.get("band") or "setting",
        "flavor": body.get("flavor") or "gate",
        "source": {"kind": "setting_edge"},
    }
    net = store.get("networks", network_id) or {
        "id": network_id,
        "setting_id": setting_id,
        "nodes": [],
        "edges": [],
        "extra_edges": [],
    }
    extras = [e for e in list(net.get("extra_edges") or []) if e.get("id") != edge["id"]]
    extras.append(edge)
    net["extra_edges"] = extras
    edges = [e for e in list(net.get("edges") or []) if e.get("id") != edge["id"]]
    edges.append(edge)
    net["edges"] = edges
    return store.put("networks", network_id, net)


def _resolve_any_host(token: str, df, store: JsonStore, instance: str) -> str:
    try:
        return resolve_host(token, df, instance=instance)
    except Problem:
        if store.get("systems", token) or store.get("systems", host_id(token) if token else ""):
            doc = store.get("systems", token) or store.get("systems", host_id(token))
            return doc["hostname"]
        raise


def create_generated_host(body: dict[str, Any], setting_id: Optional[str]) -> dict[str, Any]:
    instance = "/systems"
    require_reality(setting_id, 4, instance)
    hostname = str(body.get("hostname") or "").strip()
    if not hostname:
        raise Problem(400, "validation_error", "hostname is required", instance=instance)
    sid = body.get("id") or host_id(hostname)
    if _store().get("systems", sid):
        raise Problem(409, "id_collision", f"System {sid!r} already exists", instance=instance)
    xyz = list(body.get("xyz_ly") or [0.0, 0.0, 0.0])
    doc = SystemDocument(
        id=sid,
        hostname=hostname,
        setting_id=setting_id,
        source=SourceRef(kind="generated", snapshot=None, manual_entry=True),
        coords=CoordCard(xyz_ly=xyz, origin_hostname=body.get("origin_hostname") or "Sol"),
    )
    payload = doc.model_dump(by_alias=True)
    payload["source"]["seed"] = body.get("seed")
    return _store().put("systems", sid, payload)


def put_xyz(system_id: str, body: dict[str, Any], setting_id: Optional[str]) -> dict[str, Any]:
    instance = f"/systems/{system_id}/xyz"
    require_reality(setting_id, 4, instance)
    store = _store()
    doc = store.get("systems", system_id) or store.get("systems", host_id(system_id))
    if not doc:
        df = load_systems_df()
        hostname = resolve_host(system_id, df, instance=instance)
        doc = _ensure_system(hostname, setting_id)
    xyz = body.get("xyz_ly")
    if not isinstance(xyz, list) or len(xyz) != 3:
        raise Problem(400, "validation_error", "xyz_ly must be [x, y, z]", instance=instance)
    coords = dict(doc.get("coords") or {})
    coords["xyz_ly"] = xyz
    doc["coords"] = coords
    return store.put("systems", doc["id"], doc)


def merge_extra_edges(network: dict[str, Any]) -> dict[str, Any]:
    extras = list(network.get("extra_edges") or [])
    if not extras:
        return network
    edges = list(network.get("edges") or [])
    by_id = {e.get("id"): e for e in edges}
    for extra in extras:
        by_id[extra["id"]] = extra
    network["edges"] = list(by_id.values())
    return network
