"""FIFO political tick. Chronos is optional; t_gct is null without a base_url."""

from __future__ import annotations

from typing import Any, Optional

from starroute.api.v1.errors import Problem
from starroute.api.v1.overlays import get_affiliations, get_legal, put_affiliations, put_legal
from starroute.api.v1.settings import get_setting
from starroute.ids import host_id
from starroute.mapgen.politics import TransitionIllegal, event_kind, next_contention
from starroute.store.documents import JsonStore


def _store() -> JsonStore:
    return JsonStore()


def _politics_id(setting_id: str) -> str:
    return f"{setting_id}-politics"


def get_politics(setting_id: str) -> dict[str, Any]:
    doc = _store().get("overlays", _politics_id(setting_id))
    if doc:
        return doc
    return {
        "schema": "jumpgate.politics.v1",
        "setting_id": setting_id,
        "pending_actions": [],
        "next_seq": 1,
        "last_tick_seq": None,
        "last_t_gct": None,
    }


def _save_politics(doc: dict[str, Any]) -> dict[str, Any]:
    return _store().put("overlays", _politics_id(doc["setting_id"]), doc)


def _gate_distance(system_id: str) -> Optional[int]:
    try:
        from starroute.api.v1.catalog import load_network_df

        df = load_network_df()
    except Problem:
        return 0
    if "hostname" not in df.columns or "gate_distance" not in df.columns:
        return 0
    for _, row in df.iterrows():
        if str(row["hostname"]) == system_id or host_id(str(row["hostname"])) == system_id:
            val = row.get("gate_distance")
            if val is None or val != val:
                return 0
            return int(val)
    return 0


def _apply_one(setting_id: str, item: dict[str, Any]) -> dict[str, Any]:
    system_id = item.get("system_id") or "sol"
    overlay = get_affiliations(setting_id)
    systems = dict(overlay.get("systems") or {})
    row = dict(systems.get(system_id) or systems.get(host_id(system_id)) or {})
    current = row.get("contention") or "none"
    action = item.get("action")
    try:
        nxt = next_contention(current, action)
    except TransitionIllegal as exc:
        raise Problem(409, "transition_illegal", str(exc), instance=f"/settings/{setting_id}/tick") from exc
    row["contention"] = nxt
    systems[system_id] = row
    put_affiliations(setting_id, {"systems": systems, "renormalize": True})
    if action == "embargo":
        actor = item.get("actor") or item.get("faction_id")
        goods = list(item.get("goods") or [])
        if actor and goods:
            legal = get_legal(actor)
            schedule = list(legal.get("schedule") or [])
            for good in goods:
                schedule = [s for s in schedule if not (s.get("good") == good and s.get("action") == "trade")]
                schedule.append({"good": good, "action": "trade", "status": "banned"})
            legal["schedule"] = schedule
            put_legal(actor, legal)
    emit = item.get("emit_event", True)
    draft = None
    if emit:
        kind = event_kind(action, current, nxt)
        draft = {
            "kind": kind,
            "system_id": system_id,
            "from": current,
            "to": nxt,
            "needs_delta": True,
            "faction_id": item.get("faction_id"),
        }
    return {
        "seq": item.get("seq"),
        "faction_id": item.get("faction_id"),
        "action": action,
        "system_id": system_id,
        "contention_from": current,
        "contention_to": nxt,
        "draft": draft,
    }


def enqueue_action(setting_id: str, body: dict[str, Any]) -> dict[str, Any]:
    instance = f"/settings/{setting_id}/actions"
    enqueue = body.get("enqueue", True)
    action = body.get("action")
    if not action:
        raise Problem(400, "validation_error", "action is required", instance=instance)
    if not enqueue:
        applied = _apply_one(setting_id, body)
        return {
            "queued": False,
            "contention_from": applied["contention_from"],
            "contention_to": applied["contention_to"],
            "drafts": [applied["draft"]] if applied.get("draft") else [],
        }
    pol = get_politics(setting_id)
    seq = int(pol.get("next_seq") or 1)
    item = {
        "seq": seq,
        "faction_id": body.get("faction_id") or body.get("actor"),
        "action": action,
        "system_id": body.get("system_id") or "sol",
        "actor": body.get("actor") or body.get("faction_id"),
        "target": body.get("target"),
        "goods": body.get("goods"),
        "emit_event": body.get("emit_event", True),
    }
    pending = list(pol.get("pending_actions") or [])
    pending.append(item)
    pol["pending_actions"] = pending
    pol["next_seq"] = seq + 1
    _save_politics(pol)
    return {"queued": True, "seq": seq, "pending_actions_len": len(pending)}


def tick_setting(setting_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    pol = get_politics(setting_id)
    req_seq = body.get("seq")
    req_gct = body.get("t_gct")
    if req_seq is not None and req_seq == pol.get("last_tick_seq"):
        return {"applied": [], "duplicate": True, "t_gct": None}
    if req_gct is not None and req_gct == pol.get("last_t_gct"):
        return {"applied": [], "duplicate": True, "t_gct": None}

    n = int(body.get("n") or 1)
    horizon = body.get("horizon_ly")
    faction_filter = body.get("faction_id")
    pending = list(pol.get("pending_actions") or [])
    applied: list[dict[str, Any]] = []

    for _round in range(max(n, 0)):
        fired: set[str] = set()
        still: list[dict[str, Any]] = []
        round_applied = 0
        for item in pending:
            fid = item.get("faction_id") or ""
            if faction_filter and fid != faction_filter:
                still.append(item)
                continue
            if horizon is not None:
                dist = _gate_distance(item.get("system_id") or "sol")
                if dist is not None and dist > float(horizon):
                    still.append(item)
                    continue
            if fid in fired:
                still.append(item)
                continue
            result = _apply_one(setting_id, item)
            applied.append(result)
            fired.add(fid)
            round_applied += 1
        pending = still
        if round_applied == 0:
            break

    pol["pending_actions"] = pending
    if body.get("seq") is not None:
        pol["last_tick_seq"] = body.get("seq")
    if body.get("t_gct") is not None:
        pol["last_t_gct"] = body.get("t_gct")
    _save_politics(pol)

    t_gct = None
    try:
        setting = get_setting(setting_id)
        if (setting.get("chronos") or {}).get("base_url"):
            t_gct = body.get("t_gct")
    except Problem:
        t_gct = None

    drafts = [row["draft"] for row in applied if row.get("draft")]
    return {
        "applied": [{k: v for k, v in row.items() if k != "draft"} for row in applied],
        "duplicate": False,
        "t_gct": t_gct,
        "pending_actions_len": len(pending),
        "drafts": drafts,
    }


def chronos_advance_hook(body: dict[str, Any]) -> dict[str, Any]:
    setting_id = body.get("setting_id")
    if not setting_id:
        raise Problem(400, "missing_setting_id", "setting_id is required", instance="/webhooks/chronos/advance")
    payload = dict(body)
    if payload.get("n") is None:
        payload["n"] = 1
    return tick_setting(setting_id, payload)
