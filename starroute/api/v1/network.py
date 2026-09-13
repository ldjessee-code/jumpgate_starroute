"""v1 network rebuild — KD-tree mapgen, JSON document, CSV still for the v2 UI."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from starroute.api.v1.errors import Problem
from starroute.ids import host_id
from starroute.mapgen.network import generate_network, merged_network_params, network_payload
from starroute import paths
from starroute.store.documents import JsonStore


def _store() -> JsonStore:
    return JsonStore()


def v3_network_document(
    network_id: str,
    setting_id: Optional[str],
    df,
    params: dict[str, Any],
) -> dict[str, Any]:
    payload = network_payload(df, params)
    nodes = []
    for node in payload["nodes"]:
        hostname = node["hostname"]
        nodes.append(
            {
                "id": host_id(hostname),
                "hostname": hostname,
                "xyz_ly": [node.get("x"), node.get("y"), node.get("z")],
                "gate_distance": node.get("gate_distance"),
                "group": node.get("group") or "",
            }
        )
    edges = []
    for edge in payload["edges"]:
        a_host, b_host = edge["a"], edge["b"]
        a_id, b_id = host_id(a_host), host_id(b_host)
        edges.append(
            {
                "id": f"{a_id}--{b_id}",
                "a": a_id,
                "b": b_id,
                "a_hostname": a_host,
                "b_hostname": b_host,
                "distance_ly": edge.get("distance"),
                "band": edge.get("band"),
                "flavor": edge.get("flavor") or "gate",
                "source": {"kind": "generated_graph"},
            }
        )
    return {
        "schema": "jumpgate.network.v1",
        "layer": "L11",
        "id": network_id,
        "setting_id": setting_id,
        "starroute": "3.0",
        "params": params,
        "nodes": nodes,
        "edges": edges,
    }


def rebuild_network(
    network_id: str,
    body: dict[str, Any] | None = None,
    setting_id: Optional[str] = None,
) -> dict[str, Any]:
    instance = f"/networks/{network_id}/rebuild"
    if not paths.SYSTEMS_CSV.exists():
        raise Problem(404, "not_found", "No systems catalog (run ingest first)", instance=instance)
    body = body or {}
    skip = {"assign_factions", "setting_id", "preserve_overlays"}
    overrides = {k: v for k, v in body.items() if k not in skip}
    params = merged_network_params(overrides)
    try:
        result = generate_network(params=params)
    except ValueError as exc:
        raise Problem(400, "validation_error", str(exc), instance=instance) from exc
    df = pd.read_csv(paths.NETWORK_CSV)
    doc = v3_network_document(network_id, setting_id, df, result["params"])
    _store().put("networks", network_id, doc)
    return {
        "network_id": network_id,
        "setting_id": setting_id,
        "nodes": result["nodes"],
        "linked_nodes": result["linked_nodes"],
        "root": result["root"],
        "params": result["params"],
        "network": doc,
    }
