"""Configurable species / nation assignment and per-group route trees.

Rules are data, not Python. The default config preserves the original setting
names and RA-wedge heuristics; the UI can change counts, prefixes, and filters.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd

from starroute.paths import ASSIGNED_CSV, FACTIONS_JSON, ROUTES_CSV

OPS = {
    "eq": lambda s, v: s == v,
    "ne": lambda s, v: s != v,
    "gt": lambda s, v: s > v,
    "gte": lambda s, v: s >= v,
    "lt": lambda s, v: s < v,
    "lte": lambda s, v: s <= v,
    "abs_gt": lambda s, v: s.abs() > v,
    "abs_gte": lambda s, v: s.abs() >= v,
}


def load_faction_config(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path else FACTIONS_JSON
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_faction_config(config: dict[str, Any], path: str | Path | None = None) -> Path:
    path = Path(path) if path else FACTIONS_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


def _mask_from_filters(df: pd.DataFrame, filters: list[dict] | None) -> pd.Series:
    if not filters:
        return pd.Series(True, index=df.index)
    mask = pd.Series(True, index=df.index)
    for rule in filters:
        if "any" in rule:
            any_mask = pd.Series(False, index=df.index)
            for inner in rule["any"]:
                any_mask = any_mask | _single_filter(df, inner)
            mask = mask & any_mask
        else:
            mask = mask & _single_filter(df, rule)
    return mask


def _single_filter(df: pd.DataFrame, rule: dict) -> pd.Series:
    column = rule["column"]
    if column not in df.columns:
        return pd.Series(False, index=df.index)
    series = pd.to_numeric(df[column], errors="coerce") if rule.get("numeric", True) else df[column]
    op = rule["op"]
    value = rule.get("value")
    if op == "lt_quantile":
        valid = series.dropna()
        if valid.empty:
            return pd.Series(False, index=df.index)
        return series < valid.quantile(float(value))
    if op not in OPS:
        raise ValueError(f"Unknown filter op: {op}")
    return OPS[op](series, value)


def _sort_candidates(df: pd.DataFrame, spec: dict) -> pd.DataFrame:
    sort = spec.get("sort") or {}
    column = sort.get("column")
    if not column or column not in df.columns:
        return df
    if sort.get("key") == "abs":
        return df.assign(_sort=df[column].abs()).sort_values(
            "_sort", ascending=sort.get("ascending", False)
        ).drop(columns="_sort")
    if sort.get("key") == "prefer_hostname":
        name = sort.get("hostname", "Sol")
        return df.assign(_pref=df["hostname"].ne(name)).sort_values(
            ["_pref", column], ascending=[True, sort.get("ascending", False)]
        ).drop(columns="_pref")
    return df.sort_values(column, ascending=sort.get("ascending", False))


def assign_factions(
    df: pd.DataFrame,
    config: dict[str, Any] | None = None,
    output_assigned: str | Path | None = None,
    output_routes: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fill Species / Nation / Group / is_hub and emit a route table."""
    cfg = config or load_faction_config()
    work = df.copy()
    work["assigned"] = False
    work["Species"] = ""
    work["Nation"] = ""
    work["Group"] = ""
    work["is_hub"] = False

    for spec in cfg.get("species", []):
        _claim(work, spec, species=spec["name"], nation="")

    remaining = work.loc[~work["assigned"]].copy()
    for spec in cfg.get("nations", []):
        claimed = _claim(remaining, spec, species="Human", nation=spec["name"])
        work.loc[claimed.index, "assigned"] = True
        work.loc[claimed.index, "Species"] = "Human"
        work.loc[claimed.index, "Nation"] = spec["name"]
        remaining = remaining.drop(claimed.index)

    root = cfg.get("human_root", "Sol")
    root_group = cfg.get("human_root_group", "Turquenish Empire")
    if (work["hostname"] == root).any():
        work.loc[work["hostname"] == root, ["assigned", "Species", "Nation"]] = [
            True,
            "Human",
            root_group,
        ]

    work["Group"] = np.where(work["Species"] == "Human", work["Nation"], work["Species"])

    hub_frac = float(cfg.get("hub_percentile", 0.05))
    score_col = "combined_score" if "combined_score" in work.columns else "composite_ranking"
    if score_col not in work.columns:
        work["combined_score"] = 0.0
        score_col = "combined_score"
    for group, group_df in work.groupby("Group"):
        if not group:
            continue
        hub_count = max(1, int(len(group_df) * hub_frac))
        hubs = group_df.nlargest(hub_count, score_col)
        work.loc[hubs.index, "is_hub"] = True

    routes = _build_routes(work, cfg)
    assigned_path = Path(output_assigned) if output_assigned else ASSIGNED_CSV
    routes_path = Path(output_routes) if output_routes else ROUTES_CSV
    assigned_path.parent.mkdir(parents=True, exist_ok=True)
    work.to_csv(assigned_path, index=False)
    routes.to_csv(routes_path, index=False)
    return work, routes


def _claim(df: pd.DataFrame, spec: dict, species: str, nation: str) -> pd.DataFrame:
    available = df.loc[~df["assigned"]]
    mask = _mask_from_filters(available, spec.get("filters"))
    candidates = _sort_candidates(available.loc[mask], spec)
    take = candidates.head(int(spec.get("count", 0)))
    df.loc[take.index, "Species"] = species
    df.loc[take.index, "Nation"] = nation
    df.loc[take.index, "assigned"] = True
    return take


def _build_routes(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    prefixes = {item["name"]: item.get("prefix", item["name"][:2].upper()) for item in cfg.get("species", [])}
    prefixes.update({item["name"]: item.get("prefix", item["name"][:2].upper()) for item in cfg.get("nations", [])})
    multi = set(cfg.get("multi_route_groups", []))
    hub_link_ly = float(cfg.get("hub_extra_link_ly", 20.0))
    score_col = "combined_score" if "combined_score" in df.columns else "composite_ranking"
    if score_col not in df.columns:
        df = df.copy()
        df[score_col] = 0.0

    records: list[dict] = []
    counter: dict[str, int] = defaultdict(int)
    for group, group_df in df.groupby("Group"):
        if not group or group_df.empty:
            continue
        graph = nx.Graph()
        coords = group_df.set_index("hostname")[["calculated_x", "calculated_y", "calculated_z"]]
        names = list(coords.index)
        for name in names:
            graph.add_node(name)
        xyz = coords.to_numpy(dtype=float)
        for i, a in enumerate(names):
            deltas = xyz[i + 1 :] - xyz[i]
            dists = np.sqrt((deltas ** 2).sum(axis=1))
            for b, dist in zip(names[i + 1 :], dists):
                graph.add_edge(a, b, weight=float(dist))

        num_routes = max(1, len(group_df) // 20) if group in multi else 1
        prefix = prefixes.get(group, group[:2].upper())
        for component in nx.connected_components(graph):
            subgraph = graph.subgraph(component).copy()
            component_df = group_df[group_df["hostname"].isin(component)]
            root_name = cfg.get("human_root", "Sol")
            if group == cfg.get("human_root_group", "Turquenish Empire") and root_name in set(component_df["hostname"]):
                root = root_name
            else:
                root = component_df.loc[component_df[score_col].idxmax(), "hostname"]
            routes_needed = min(num_routes, len(component_df))
            for _ in range(routes_needed):
                if subgraph.number_of_edges() == 0:
                    break
                counter[group] += 1
                route_name = f"{prefix}{counter[group]}"
                mst = nx.minimum_spanning_tree(subgraph, weight="weight")
                if root not in mst:
                    break
                tree = nx.bfs_tree(mst, source=root)
                for node in tree.nodes:
                    row = component_df.loc[component_df["hostname"] == node].iloc[0]
                    preds = list(tree.predecessors(node))
                    succs = list(tree.successors(node))
                    records.append(
                        {
                            "Route": route_name,
                            "hostname": node,
                            "Species": row["Species"],
                            "Nation": row["Nation"],
                            "Previous Node": preds[0] if preds else node,
                            "Next Node": succs[0] if succs else node,
                            "is_hub": bool(row["is_hub"]),
                        }
                    )
                    if row["is_hub"]:
                        node_xyz = coords.loc[node].to_numpy(dtype=float)
                        others = component_df[(component_df["hostname"] != node) & (~component_df["is_hub"])]
                        if not others.empty:
                            other_xyz = coords.loc[others["hostname"]].to_numpy(dtype=float)
                            dists = np.sqrt(((other_xyz - node_xyz) ** 2).sum(axis=1))
                            close = others.loc[dists <= hub_link_ly].nlargest(2, score_col)
                            for _, extra in close.iterrows():
                                records.append(
                                    {
                                        "Route": route_name,
                                        "hostname": extra["hostname"],
                                        "Species": extra["Species"],
                                        "Nation": extra["Nation"],
                                        "Previous Node": node,
                                        "Next Node": node,
                                        "is_hub": False,
                                    }
                                )
                subgraph.remove_edges_from(mst.edges())
    return pd.DataFrame.from_records(records)
