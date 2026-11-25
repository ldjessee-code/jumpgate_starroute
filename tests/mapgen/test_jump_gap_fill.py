"""When a longer hop actually draws roads for nearest-neighbor holes."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from starroute.mapgen.network import generate_network

CSV = Path(__file__).resolve().parents[2] / "starroute" / "web" / "static" / "sample-systems.csv"


def _nn_pairs(df: pd.DataFrame) -> list[tuple[float, str, str]]:
    xyz = df[["calculated_x", "calculated_y", "calculated_z"]].to_numpy(float)
    names = df["hostname"].astype(str).to_numpy()
    out = []
    for i, name in enumerate(names):
        delta = xyz - xyz[i]
        dist = np.sqrt((delta * delta).sum(axis=1))
        dist[i] = np.inf
        j = int(dist.argmin())
        out.append((float(dist[j]), str(name), str(names[j])))
    out.sort()
    return out


def _edges(network_df: pd.DataFrame) -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for _, row in network_df.iterrows():
        a = str(row.get("source_hostname") or row.get("hostname") or "")
        for i in range(1, 17):
            col = f"neighbor_{i}_hostname"
            b = row.get(col)
            if col in network_df.columns and pd.notna(b) and str(b).strip():
                edges.add(tuple(sorted((a, str(b)))))
    return edges


def _generate(tmp_path: Path, hop: float) -> pd.DataFrame:
    out = tmp_path / f"net_{hop}.csv"
    generate_network(
        systems_path=str(CSV),
        output_path=str(out),
        params={
            "max_jump_ly": hop,
            "medium_start_pct": 40,
            "long_start_pct": 60,
            "max_neighbors": 8,
            "max_linked_nodes": 200,
            "hard_rank": 0.15,
            "soft_rank": 0.25,
            "min_stellar_mass": 0.25,
            "root_hostname": "Sol",
        },
    )
    return pd.read_csv(out)


def test_sixteen_ly_hop_does_not_close_fifteen_ly_scan_holes(tmp_path):
    """Closest catalog miss is 16.38 ly; 13–16 ly hops never include that pair."""
    df = pd.read_csv(CSV)
    holes = [t for t in _nn_pairs(df) if t[0] > 15]
    assert min(t[0] for t in holes) > 16.0
    edges = _edges(_generate(tmp_path, 16))
    linked = sum(1 for _, a, b in holes if tuple(sorted((a, b))) in edges)
    assert linked == 0


def test_twenty_five_ly_hop_draws_most_of_those_roads(tmp_path):
    df = pd.read_csv(CSV)
    holes = [t for t in _nn_pairs(df) if t[0] > 15]
    edges = _edges(_generate(tmp_path, 25))
    linked = sum(1 for _, a, b in holes if tuple(sorted((a, b))) in edges)
    assert linked >= 10
