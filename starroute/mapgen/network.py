"""Build a Sol-rooted jump/gate network with a KD-tree neighbor search."""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from starroute.mapgen.ranking import composite_ranking
from starroute.paths import NETWORK_CSV, SYSTEMS_CSV, ensure_data_dirs

DEFAULT_NETWORK = {
    "max_jump_ly": 50.0,
    "preferred_ly": 16.0,
    "max_neighbors": 8,
    "hard_rank": 0.20,
    "soft_rank": 0.30,
    "max_linked_nodes": 101,
    "min_stellar_mass": 0.25,
    "root_hostname": "Sol",
}


def _valid_row(row: pd.Series, min_mass: float) -> bool:
    coords = (row["calculated_x"], row["calculated_y"], row["calculated_z"])
    if not all(np.isfinite(c) for c in coords):
        return False
    if coords == (0, 0, 0) and row["hostname"] != "Sol":
        return False
    mass = row.get("st_mass")
    if row["hostname"] == "Sol":
        return True
    if pd.isna(mass) or float(mass) < min_mass:
        return False
    return True


def _score_row(row: pd.Series, distance: float, preferred_ly: float, weights: dict | None) -> float:
    return composite_ranking(
        row.get("carbon_ranking"),
        row.get("sulfur_ranking"),
        row.get("silicon_ranking"),
        row.get("stability_score"),
        row.get("sy_snum"),
        row.get("sy_pnum"),
        row.get("sy_mnum"),
        row.get("cb_flag"),
        row.get("st_met"),
        distance,
        preferred_ly=preferred_ly,
        weights=weights,
    )


def _select_neighbors(
    candidates: list[dict],
    parent: str | None,
    current: str,
    connections: dict[str, set[str]],
    max_neighbors: int,
    soft_rank: float,
    linked_count: int,
    max_linked: int,
) -> list[dict]:
    chosen: list[dict] = []
    if not candidates or linked_count >= max_linked:
        return chosen
    for neighbor in candidates:
        if len(chosen) >= max_neighbors:
            break
        local = neighbor.get("near") or neighbor["hostname"] == parent
        if not local and chosen and neighbor["ranking"] < soft_rank:
            continue
        chosen.append(neighbor)
    for neighbor in chosen:
        connections[current].add(neighbor["hostname"])
        connections[neighbor["hostname"]].add(current)
    return chosen


def generate_network(
    systems_path: str | None = None,
    output_path: str | None = None,
    params: dict | None = None,
    weights: dict | None = None,
) -> dict[str, Any]:
    """Walk outward from Sol, attaching highly ranked neighbors within jump range."""
    ensure_data_dirs()
    cfg = {**DEFAULT_NETWORK, **(params or {})}
    systems_path = systems_path or str(SYSTEMS_CSV)
    output_path = output_path or str(NETWORK_CSV)

    df = pd.read_csv(systems_path)
    required = {"hostname", "calculated_x", "calculated_y", "calculated_z"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"systems table missing columns: {sorted(missing)}")

    df = df[df.apply(lambda r: _valid_row(r, cfg["min_stellar_mass"]), axis=1)].reset_index(drop=True)
    if df["hostname"].duplicated().any():
        df = df.drop_duplicates(subset="hostname", keep="first").reset_index(drop=True)

    root = cfg["root_hostname"]
    if root not in set(df["hostname"]):
        raise ValueError(f"Root system '{root}' is not in the ingested dataset.")

    coords = df[["calculated_x", "calculated_y", "calculated_z"]].to_numpy(dtype=float)
    hostnames = df["hostname"].to_numpy()
    index_of = {name: i for i, name in enumerate(hostnames)}
    tree = cKDTree(coords)
    connections: dict[str, set[str]] = {name: set() for name in hostnames}

    rows: list[dict] = []
    visited: set[str] = set()
    process_order = 0
    queue: deque[tuple[int, str | None]] = deque([(index_of[root], None)])

    max_jump = float(cfg["max_jump_ly"])
    max_neighbors = int(cfg["max_neighbors"])
    max_linked = int(cfg["max_linked_nodes"])
    hard_rank = float(cfg["hard_rank"])
    soft_rank = float(cfg["soft_rank"])
    preferred = float(cfg["preferred_ly"])

    while queue:
        idx, parent = queue.popleft()
        name = hostnames[idx]
        if name in visited:
            continue
        visited.add(name)
        process_order += 1
        row = df.iloc[idx]
        ranking = _score_row(row, 0.0, preferred, weights)

        neighbors: list[dict] = []
        if process_order <= max_linked:
            near: list[dict] = []
            far: list[dict] = []
            for j in tree.query_ball_point(coords[idx], max_jump):
                if j == idx:
                    continue
                other = hostnames[j]
                if other in connections[name] or len(connections[other]) >= max_neighbors:
                    continue
                dist = float(np.linalg.norm(coords[idx] - coords[j]))
                if dist > max_jump:
                    continue
                other_row = df.iloc[j]
                score = _score_row(other_row, dist, preferred, weights)
                item = {
                    "hostname": other,
                    "distance_ly": round(dist, 4),
                    "ranking": round(score, 4),
                    "near": dist <= preferred,
                }
                # Local stars always get a gate. Beyond preferred_ly, ranking is the filter.
                if dist <= preferred or other == parent or score >= hard_rank:
                    (near if dist <= preferred or other == parent else far).append(item)
            near.sort(key=lambda item: item["distance_ly"])
            far.sort(key=lambda item: item["ranking"], reverse=True)
            # Ranking-only selection skipped Alpha Cen / ε Eri from Sol. Local
            # systems (≤ preferred_ly) are always eligible; longer jumps still
            # need the ranking floors.
            ranked_pool = near + [n for n in far if n["ranking"] >= soft_rank] + [
                n for n in far if n["ranking"] < soft_rank
            ]
            neighbors = _select_neighbors(
                ranked_pool,
                parent,
                name,
                connections,
                max_neighbors,
                soft_rank,
                process_order,
                max_linked,
            )

        record = row.to_dict()
        record["source_hostname"] = name
        record["composite_ranking"] = round(ranking, 4)
        record["parent_hostname"] = parent or ""
        record["process_order"] = process_order
        record["gate_distance"] = None
        for i, neighbor in enumerate(neighbors, start=1):
            record[f"neighbor_{i}_hostname"] = neighbor["hostname"]
            record[f"neighbor_{i}_distance"] = neighbor["distance_ly"]
            record[f"neighbor_{i}_ranking"] = neighbor["ranking"]
        rows.append(record)

        if process_order <= max_linked:
            for neighbor in neighbors:
                if neighbor["hostname"] not in visited:
                    queue.append((index_of[neighbor["hostname"]], name))

    # Isolated systems inside the jump sphere, for the map only.
    connected = {name for name, links in connections.items() if links}
    remaining = df[~df["hostname"].isin(connected | visited)]
    root_xyz = coords[index_of[root]]
    extras = []
    for i, row in remaining.iterrows():
        dist = float(np.linalg.norm(coords[i] - root_xyz))
        if dist <= max_jump:
            extras.append((dist, i, row))
    extras.sort(key=lambda item: item[0])
    for _, i, row in extras:
        process_order += 1
        record = row.to_dict()
        record["source_hostname"] = row["hostname"]
        record["composite_ranking"] = round(_score_row(row, 0.0, preferred, weights), 4)
        record["parent_hostname"] = ""
        record["process_order"] = process_order
        record["gate_distance"] = None
        rows.append(record)

    network = pd.DataFrame(rows)
    network["gate_distance"] = _gate_distances(network, root, max_neighbors)
    network.to_csv(output_path, index=False)

    linked = int(network["gate_distance"].notna().sum())
    return {
        "output_path": output_path,
        "nodes": int(len(network)),
        "linked_nodes": linked,
        "root": root,
        "params": cfg,
    }


def _gate_distances(df: pd.DataFrame, root: str, max_neighbors: int) -> pd.Series:
    graph: dict[str, set[str]] = {row["source_hostname"]: set() for _, row in df.iterrows()}
    neighbor_cols = [c for c in df.columns if c.startswith("neighbor_") and c.endswith("_hostname")]
    for _, row in df.iterrows():
        src = row["source_hostname"]
        for col in neighbor_cols:
            dest = row.get(col)
            if pd.notna(dest):
                graph.setdefault(src, set()).add(dest)
                graph.setdefault(dest, set()).add(src)

    distances = {name: None for name in graph}
    if root not in graph:
        return pd.Series([None] * len(df), index=df.index)
    distances[root] = 0
    queue = deque([root])
    seen = {root}
    while queue:
        current = queue.popleft()
        for nxt in graph[current]:
            if nxt not in seen:
                seen.add(nxt)
                distances[nxt] = distances[current] + 1
                queue.append(nxt)
    return pd.Series([distances.get(name) for name in df["source_hostname"]], index=df.index)


def shortest_path(df: pd.DataFrame, start: str, end: str) -> list[str]:
    neighbor_cols = [c for c in df.columns if c.startswith("neighbor_") and c.endswith("_hostname")]
    graph: dict[str, set[str]] = {row["hostname"]: set() for _, row in df.iterrows()}
    for _, row in df.iterrows():
        src = row["hostname"]
        for col in neighbor_cols:
            dest = row.get(col)
            if pd.notna(dest):
                graph.setdefault(src, set()).add(dest)
                graph.setdefault(dest, set()).add(src)
    if start not in graph or end not in graph:
        return []
    queue = deque([(start, [start])])
    seen = {start}
    while queue:
        current, path = queue.popleft()
        if current == end:
            return path
        for nxt in graph[current]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, path + [nxt]))
    return []


def network_payload(df: pd.DataFrame) -> dict[str, Any]:
    """JSON for the Plotly.js map."""
    neighbor_cols = [c for c in df.columns if c.startswith("neighbor_") and c.endswith("_hostname")]
    nodes = []
    for _, row in df.iterrows():
        nodes.append(
            {
                "hostname": row["hostname"],
                "sy_name": row.get("sy_name") if pd.notna(row.get("sy_name")) else row["hostname"],
                "x": float(row["calculated_x"]),
                "y": float(row["calculated_y"]),
                "z": float(row["calculated_z"]),
                "sy_pnum": None if pd.isna(row.get("sy_pnum")) else float(row["sy_pnum"]),
                "ranking": None if pd.isna(row.get("composite_ranking")) else float(row["composite_ranking"]),
                "symbol": row.get("stability_symbol") if pd.notna(row.get("stability_symbol")) else "circle",
                "spectype": row.get("st_spectype") if pd.notna(row.get("st_spectype")) else "",
                "dist_ly": None if pd.isna(row.get("distance_from_sol_ly")) else float(row["distance_from_sol_ly"]),
                "gate_distance": None if pd.isna(row.get("gate_distance")) else int(row["gate_distance"]),
                "species": row.get("Species") if pd.notna(row.get("Species")) else "",
                "nation": row.get("Nation") if pd.notna(row.get("Nation")) else "",
                "group": row.get("Group") if pd.notna(row.get("Group")) else "",
                "is_hub": bool(row.get("is_hub")) if pd.notna(row.get("is_hub")) else False,
                "process_order": None if pd.isna(row.get("process_order")) else int(row["process_order"]),
            }
        )

    seen_edges: set[tuple[str, str]] = set()
    edges = []
    host_set = set(df["hostname"])
    for _, row in df.iterrows():
        src = row["hostname"]
        for col in neighbor_cols:
            dest = row.get(col)
            if pd.isna(dest) or dest not in host_set:
                continue
            key = tuple(sorted((src, dest)))
            if key in seen_edges:
                continue
            seen_edges.add(key)
            dist_col = col.replace("_hostname", "_distance")
            edges.append(
                {
                    "a": src,
                    "b": dest,
                    "distance": None if dist_col not in row or pd.isna(row.get(dist_col)) else float(row[dist_col]),
                }
            )
    return {"nodes": nodes, "edges": edges}
