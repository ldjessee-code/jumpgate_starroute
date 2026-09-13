"""Slider ≥ 1: one generated L2 stub per unsatisfied premise role."""

from __future__ import annotations

from typing import Any, Optional

from starroute.api.v1.catalog import system_document
from starroute.api.v1.errors import Problem
from starroute.api.v1.resolve import resolve_host
from starroute.api.v1.settings import get_setting
from starroute.ids import host_id
from starroute.schemas.body import BodyDocument
from starroute.schemas.system import SourceRef
from starroute.store.documents import JsonStore
from starroute.api.v1.catalog import load_systems_df


def _store() -> JsonStore:
    return JsonStore()


def _reality(setting_id: Optional[str]) -> int:
    if not setting_id:
        return 0
    try:
        return int(get_setting(setting_id).get("reality") or 0)
    except Problem as exc:
        if exc.code == "not_found":
            return 0
        raise


def _role_slug(role: str) -> str:
    return host_id(role.replace("_", " "))


def _next_stub_id(host: str, role: str, existing_ids: list[str]) -> str:
    slug = _role_slug(role)
    prefix = f"{host}.gen-{slug}-"
    n = 1
    while f"{prefix}{n}" in existing_ids:
        n += 1
    return f"{prefix}{n}"


def _ensure_system(hostname: str, setting_id: Optional[str]) -> dict[str, Any]:
    sid = host_id(hostname)
    stored = _store().get("systems", sid)
    if stored:
        return stored
    doc = system_document(hostname, setting_id)
    return _store().put("systems", sid, doc)


def _load_bodies(ids: list[str]) -> list[dict[str, Any]]:
    store = _store()
    out = []
    for bid in ids:
        doc = store.get("bodies", bid)
        if doc:
            out.append(doc)
    return out


def generate_l2_gapfill(
    system_id: str,
    *,
    setting_id: Optional[str],
    need: list[dict[str, Any]],
    seed: Optional[str] = None,
) -> dict[str, Any]:
    instance = f"/systems/{system_id}/generate-l2"
    if _reality(setting_id) < 1:
        raise Problem(
            409,
            "reality_forbidden",
            "Gap-fill bodies require reality >= 1",
            instance=instance,
            extra={"setting_id": setting_id, "reality": _reality(setting_id)},
        )
    df = load_systems_df()
    hostname = resolve_host(system_id, df, instance=instance)
    system = _ensure_system(hostname, setting_id)
    hid = system["id"]
    body_ids = list(system.get("bodies") or [])
    bodies = _load_bodies(body_ids)
    taken_roles = {b.get("role") for b in bodies if b.get("role")}
    created: list[str] = []
    store = _store()
    for item in need:
        role = str(item.get("role") or "").strip()
        if not role or role in taken_roles:
            continue
        stub_id = _next_stub_id(hid, role, body_ids)
        stub = BodyDocument(
            id=stub_id,
            host_id=hid,
            pl_name=None,
            source=SourceRef(kind="generated", snapshot=None, manual_entry=False),
            pl_letter=None,
            pl_bmasse=None,
            pl_rade=None,
            pl_eqt=None,
            pl_orbsmax=None,
            role=role,
            tags=list(item.get("tags") or []),
            g_earth_max=item.get("g_earth_max"),
        )
        payload = stub.model_dump(by_alias=True)
        payload["source"]["seed"] = seed
        store.put("bodies", stub_id, payload)
        body_ids.append(stub_id)
        taken_roles.add(role)
        created.append(stub_id)
    if created:
        system["bodies"] = body_ids
        store.put("systems", hid, system)
    return {
        "system_id": hid,
        "hostname": hostname,
        "created": created,
        "bodies": body_ids,
        "seed": seed,
    }


def set_system_premise(system_id: str, body: dict[str, Any], setting_id: Optional[str]) -> dict[str, Any]:
    instance = f"/systems/{system_id}/premise"
    if _reality(setting_id) < 1:
        raise Problem(
            409,
            "reality_forbidden",
            "Gap-fill bodies require reality >= 1",
            instance=instance,
            extra={"setting_id": setting_id, "reality": _reality(setting_id)},
        )
    need = list(body.get("need") or [])
    seed = body.get("seed")
    hid = host_id(resolve_host(system_id, load_systems_df(), instance=instance))
    _store().put(
        "premises",
        f"{hid}",
        {"id": hid, "setting_id": setting_id, "need": need, "seed": seed},
    )
    return generate_l2_gapfill(system_id, setting_id=setting_id, need=need, seed=seed)
