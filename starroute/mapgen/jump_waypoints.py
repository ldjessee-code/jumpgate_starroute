"""Bridge a hop that is longer than Longest single jump.

Order:
1. Prefer a **real catalog star** already in the sphere that sits within
   max_jump of both ends (low score, few planets, off-grid first).
2. If none exists, place a **minimum-mass star** (default 0.25 Msun) near
   the midpoint so each hop is legal.

If A's nearest catalog neighbor is already farther than max_jump, step 1
cannot succeed: nothing in this list is close enough to be the first hop.
The NASA planet-host catalog has no planet-less field stars to pick from.
"""

from __future__ import annotations

import math
from typing import Any


def hop_count(distance_ly: float, max_jump_ly: float) -> int:
    if max_jump_ly <= 0:
        raise ValueError("max_jump_ly must be positive")
    if distance_ly <= max_jump_ly:
        return 1
    return int(math.ceil(distance_ly / max_jump_ly - 1e-12))


def waypoints_between(
    ax: float, ay: float, az: float,
    bx: float, by: float, bz: float,
    max_jump_ly: float,
) -> list[tuple[float, float, float]]:
    """Evenly spaced points on the segment so each hop is ≤ max_jump_ly."""
    dist = math.sqrt((bx - ax) ** 2 + (by - ay) ** 2 + (bz - az) ** 2)
    hops = hop_count(dist, max_jump_ly)
    if hops <= 1:
        return []
    pts: list[tuple[float, float, float]] = []
    for i in range(1, hops):
        t = i / hops
        pts.append((ax + t * (bx - ax), ay + t * (by - ay), az + t * (bz - az)))
    return pts


def _dist(ax: float, ay: float, az: float, bx: float, by: float, bz: float) -> float:
    return math.sqrt((bx - ax) ** 2 + (by - ay) ** 2 + (bz - az) ** 2)


def find_existing_bridge(
    ax: float, ay: float, az: float,
    bx: float, by: float, bz: float,
    hosts: list[dict[str, Any]],
    max_jump_ly: float,
    skip: set[str] | None = None,
) -> dict[str, Any] | None:
    """Best real host within max_jump of both ends.

    Prefer few planets, then low combined_score, then closer to the midpoint.
    """
    skip = skip or set()
    mx = (ax + bx) / 2.0
    my = (ay + by) / 2.0
    mz = (az + bz) / 2.0
    ranked: list[tuple[float, float, float, dict[str, Any]]] = []
    for host in hosts:
        name = str(host.get("hostname") or "")
        if not name or name in skip:
            continue
        x, y, z = float(host["x"]), float(host["y"]), float(host["z"])
        da = _dist(ax, ay, az, x, y, z)
        db = _dist(bx, by, bz, x, y, z)
        if da > max_jump_ly or db > max_jump_ly:
            continue
        pnum = float(host.get("sy_pnum") or 0)
        score = float(host.get("combined_score") or host.get("ranking") or 0)
        dmid = _dist(mx, my, mz, x, y, z)
        ranked.append((pnum, score, dmid, host))
    if not ranked:
        return None
    ranked.sort(key=lambda row: (row[0], row[1], row[2]))
    return ranked[0][3]


def gap_fillers_for_pairs(
    pairs: list[dict[str, Any]],
    max_jump_ly: float,
) -> list[dict[str, Any]]:
    """pairs items: {a, b, ax,ay,az, bx,by,bz}. Returns waypoint dicts."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in pairs:
        a, b = str(item["a"]), str(item["b"])
        key = tuple(sorted((a, b)))
        if key in seen or a == b:
            continue
        seen.add(key)
        pts = waypoints_between(
            float(item["ax"]), float(item["ay"]), float(item["az"]),
            float(item["bx"]), float(item["by"]), float(item["bz"]),
            max_jump_ly,
        )
        dist = math.sqrt(
            (float(item["bx"]) - float(item["ax"])) ** 2
            + (float(item["by"]) - float(item["ay"])) ** 2
            + (float(item["bz"]) - float(item["az"])) ** 2
        )
        hops = hop_count(dist, max_jump_ly)
        for i, (x, y, z) in enumerate(pts, start=1):
            out.append({
                "hostname": f"Gap {a}–{b}" if len(pts) == 1 else f"Gap {a}–{b} {i}",
                "x": x,
                "y": y,
                "z": z,
                "a": a,
                "b": b,
                "leg": i,
                "legs": hops,
                "span_ly": dist,
            })
    return out
