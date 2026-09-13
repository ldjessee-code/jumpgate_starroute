"""Settings documents and reality-slider compare-and-swap."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from starroute.api.v1.errors import Problem
from starroute.ids import host_id
from starroute.schemas.setting import SettingDocument
from starroute.store.documents import JsonStore
from starroute.store.etag import etag_header_ok


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _store() -> JsonStore:
    return JsonStore()


def _require_if_match(if_match: Optional[str], current: dict[str, Any], instance: str) -> None:
    ok, reason = etag_header_ok(if_match)
    if not ok:
        code = "precondition_required" if reason == "missing" else "weak_etag"
        status = 412
        raise Problem(status, code, "If-Match must be a strong etag", instance=instance)
    stored = current.get("etag") or ""
    if if_match.strip() != stored:
        raise Problem(
            409,
            "etag_mismatch",
            "If-Match does not match the current setting",
            instance=instance,
            extra={"current": current},
        )


def _actor_ok(updated_by: str, instance: str) -> None:
    if updated_by == "chronos":
        raise Problem(403, "forbidden_actor", "Chronos may not write the reality slider", instance=instance)
    if updated_by not in {"jumpgate", "worldstack", "agent"}:
        raise Problem(400, "validation_error", f"Unknown updated_by {updated_by!r}", instance=instance)


def _illegal_for_stop(store: JsonStore, stop: int) -> list[str]:
    bad: list[str] = []
    if stop >= 4:
        return bad
    for sid in store.list_ids("systems"):
        doc = store.get("systems", sid) or {}
        source = doc.get("source") or {}
        kind = source.get("kind")
        if stop < 4 and kind == "generated":
            bad.append(f"systems/{sid}")
        if stop < 2 and doc.get("overrides"):
            bad.append(f"systems/{sid}#overrides")
    if stop < 1:
        for bid in store.list_ids("bodies"):
            doc = store.get("bodies", bid) or {}
            kind = (doc.get("source") or {}).get("kind")
            if kind == "generated":
                bad.append(f"bodies/{bid}")
    return bad


def create_setting(body: dict[str, Any]) -> dict[str, Any]:
    title = (body.get("title") or "setting").strip()
    sid = body.get("id") or host_id(title)
    instance = f"/settings/{sid}"
    if _store().get("settings", sid):
        raise Problem(409, "id_collision", f"Setting {sid!r} already exists", instance=instance)
    reality = int(body.get("reality", 0))
    if reality < 0 or reality > 4:
        raise Problem(400, "validation_error", "reality must be 0..4", instance=instance)
    actor = body.get("updated_by") or "jumpgate"
    _actor_ok(actor, instance)
    doc = SettingDocument(
        id=sid,
        title=body.get("title") or title,
        updated_by=actor,
        reality=reality,
        origin_hostname=body.get("origin_hostname") or "Sol",
        network_id=body.get("network_id"),
    )
    payload = doc.model_dump(by_alias=True)
    if body.get("catalog"):
        payload["catalog"] = body["catalog"]
    if body.get("chronos"):
        chronos = dict(payload.get("chronos") or {})
        chronos.update(body["chronos"])
        payload["chronos"] = chronos
    payload["updated_at"] = _now()
    return _store().put("settings", sid, payload)


def get_setting(setting_id: str) -> dict[str, Any]:
    doc = _store().get("settings", setting_id)
    if not doc:
        raise Problem(404, "not_found", f"Unknown setting {setting_id!r}", instance=f"/settings/{setting_id}")
    return doc


def put_setting(setting_id: str, body: dict[str, Any], if_match: Optional[str]) -> dict[str, Any]:
    instance = f"/settings/{setting_id}"
    current = get_setting(setting_id)
    _require_if_match(if_match, current, instance)
    actor = body.get("updated_by") or current.get("updated_by") or "jumpgate"
    _actor_ok(actor, instance)
    merged = dict(current)
    merged.update(body)
    merged["id"] = setting_id
    merged["updated_by"] = actor
    merged["updated_at"] = _now()
    if "reality" in merged:
        merged["reality"] = int(merged["reality"])
        if merged["reality"] < 0 or merged["reality"] > 4:
            raise Problem(400, "validation_error", "reality must be 0..4", instance=instance)
    return _store().put("settings", setting_id, merged)


def get_reality(setting_id: str) -> dict[str, Any]:
    doc = get_setting(setting_id)
    return {
        "reality": int(doc.get("reality", 0)),
        "etag": doc.get("etag"),
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
    }


def put_reality(setting_id: str, body: dict[str, Any], if_match: Optional[str]) -> dict[str, Any]:
    instance = f"/settings/{setting_id}/reality"
    current = get_setting(setting_id)
    _require_if_match(if_match, current, instance)
    if "reality" not in body:
        raise Problem(400, "validation_error", "reality is required", instance=instance)
    new_stop = int(body["reality"])
    if new_stop < 0 or new_stop > 4:
        raise Problem(400, "validation_error", "reality must be 0..4", instance=instance)
    actor = body.get("updated_by") or "jumpgate"
    _actor_ok(actor, instance)
    old = int(current.get("reality", 0))
    if new_stop < old:
        illegal = _illegal_for_stop(_store(), new_stop)
        if illegal and not body.get("discard_illegal"):
            raise Problem(
                409,
                "reality_conflict",
                "Lowering the slider would leave illegal generated documents",
                instance=instance,
                extra={"offending": illegal, "from": old, "to": new_stop},
            )
    merged = dict(current)
    merged["reality"] = new_stop
    merged["updated_by"] = actor
    merged["updated_at"] = _now()
    written = _store().put("settings", setting_id, merged)
    return {
        "reality": new_stop,
        "etag": written["etag"],
        "updated_at": written["updated_at"],
        "updated_by": actor,
    }
