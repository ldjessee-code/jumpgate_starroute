"""Contention ranks, action transitions, embargo matrix. No campaign clock."""

from __future__ import annotations

from typing import Optional

CONTENTION = (
    "none",
    "claim",
    "cooperative",
    "competitive_trade",
    "games",
    "skirmish",
    "war",
    "subjugation",
)

RANKS = {
    "none": 0,
    "claim": 1,
    "cooperative": 1,
    "competitive_trade": 2,
    "games": 3,
    "skirmish": 4,
    "war": 5,
    "subjugation": 6,
}

ESCALATE = {
    "none": None,
    "claim": "competitive_trade",
    "cooperative": "competitive_trade",
    "competitive_trade": "games",
    "games": "skirmish",
    "skirmish": "war",
    "war": "subjugation",
    "subjugation": "subjugation",
}

DEESCALATE = {
    "none": "none",
    "claim": "none",
    "cooperative": "none",
    "competitive_trade": "claim",
    "games": "competitive_trade",
    "skirmish": "games",
    "war": "skirmish",
    "subjugation": "war",
}

ADVISORY = {
    "none": "clear",
    "cooperative": "clear",
    "competitive_trade": "clear",
    "claim": "caution",
    "games": "caution",
    "skirmish": "hazard",
    "war": "denied",
    "subjugation": "occupied",
}

ACTIONS = (
    "expand_claim",
    "escalate",
    "deescalate",
    "embargo",
    "open_trade",
    "propaganda",
    "raid",
)


class TransitionIllegal(ValueError):
    pass


def event_kind(action: str, from_state: str, to_state: str) -> Optional[str]:
    if action == "expand_claim":
        return "claim_expanded"
    if action == "escalate":
        return "war_declared" if to_state == "war" else "tension_up"
    if action == "deescalate":
        if to_state in {"none", "cooperative"}:
            return "peace_signed"
        return "ceasefire_offered"
    if action == "embargo":
        return "embargo_declared"
    if action == "open_trade":
        return "trade_opened"
    if action == "propaganda":
        return "propaganda"
    if action == "raid":
        return "sneak_attack" if from_state == "none" else "raid"
    return None


def advisory_for(contention: str) -> str:
    return ADVISORY.get(contention, "clear")


def embargo_contention(current: str) -> str:
    if current in {"none", "claim", "cooperative"}:
        return "competitive_trade"
    return current


def next_contention(current: str, action: str) -> str:
    """Pure transition. Does not touch Chronos or the JSON store."""
    if current not in RANKS:
        raise TransitionIllegal(f"Unknown contention {current!r}")
    if action not in ACTIONS:
        raise TransitionIllegal(f"Unknown action {action!r}")
    if action == "expand_claim":
        if current == "none":
            return "claim"
        if current == "claim":
            return "claim"
        raise TransitionIllegal(f"{current} --expand_claim--> illegal")
    if action == "escalate":
        nxt = ESCALATE[current]
        if nxt is None:
            raise TransitionIllegal("none --escalate--> illegal (use expand_claim)")
        return nxt
    if action == "deescalate":
        return DEESCALATE[current]
    if action == "embargo":
        return embargo_contention(current)
    if action == "open_trade":
        if current in {"none", "claim", "cooperative"}:
            return "cooperative"
        if current == "competitive_trade":
            return "cooperative"
        raise TransitionIllegal(f"{current} --open_trade--> illegal")
    if action == "propaganda":
        return current
    if action == "raid":
        if current in {"skirmish", "war"}:
            return current
        return "skirmish"
    raise TransitionIllegal(f"{current} --{action}--> illegal")


def influence_ok(present: list[dict], *, epsilon: float = 1e-6) -> bool:
    shares = [float(p["influence"]) for p in present if p.get("influence") is not None]
    if not shares:
        return True
    if len(shares) != len(present):
        return False
    return abs(sum(shares) - 1.0) <= epsilon


def renormalize(present: list[dict]) -> list[dict]:
    total = sum(float(p.get("influence") or 0) for p in present)
    if total <= 0:
        return present
    out = []
    for item in present:
        row = dict(item)
        row["influence"] = float(item.get("influence") or 0) / total
        out.append(row)
    return out
