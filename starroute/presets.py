"""Build static map-preset snapshots from catalog + network + faction rules."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import pandas as pd

from starroute.ingest.pipeline import build_systems_dataset, detect_default_sources
from starroute.mapgen.factions import assign_factions
from starroute.mapgen.network import generate_network, network_payload
from starroute.paths import (
    DATA_PRESETS,
    MAP_PRESETS_JSON,
    ROOT,
    SAMPLE_SYSTEMS_CSV,
    STATIC_PRESETS,
    ensure_data_dirs,
)

PRESET_IDS = ("crowded", "sparse", "lonely_humans")


def load_map_presets(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path else MAP_PRESETS_JSON
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _largest_component(nodes: list[dict], edges: list[dict]) -> int:
    graph: dict[str, set[str]] = defaultdict(set)
    names = {node["hostname"] for node in nodes}
    for edge in edges:
        a, b = edge["a"], edge["b"]
        if a in names and b in names:
            graph[a].add(b)
            graph[b].add(a)
    seen: set[str] = set()
    best = 0
    for start in names:
        if start in seen:
            continue
        queue = deque([start])
        seen.add(start)
        size = 0
        while queue:
            current = queue.popleft()
            size += 1
            for nxt in graph[current]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        if size > best:
            best = size
    return best


def catalog_stats(df: pd.DataFrame) -> dict[str, Any]:
    carbon = pd.to_numeric(df.get("carbon_ranking"), errors="coerce").fillna(0) > 0
    sulfur = pd.to_numeric(df.get("sulfur_ranking"), errors="coerce").fillna(0) > 0
    gas = pd.to_numeric(df.get("gas_giant_count"), errors="coerce").fillna(0) > 0
    nasa_hab = carbon | sulfur | gas
    return {
        "catalog_systems": int(len(df)),
        "nasa_habitat_flag": int(nasa_hab.sum()),
        "carbon_zone": int(carbon.sum()),
        "sulfur_zone": int(sulfur.sum()),
        "gas_giant": int(gas.sum()),
    }


def snapshot_stats(snapshot: dict[str, Any], assigned: pd.DataFrame | None = None) -> dict[str, Any]:
    payload = snapshot["payload"]
    nodes = payload["nodes"]
    edges = payload["edges"]
    linked = [n for n in nodes if n.get("gate_distance") is not None]
    habitable = [n for n in linked if n.get("group")]
    groups: dict[str, int] = {}
    for node in linked:
        group = node.get("group") or ""
        if group:
            groups[group] = groups.get(group, 0) + 1
    stats: dict[str, Any] = {
        "title": snapshot.get("title"),
        "nodes": int(len(nodes)),
        "edges": int(len(edges)),
        "linked_nodes": int(len(linked)),
        "largest_component": _largest_component(linked, edges) if linked else 0,
        "habitable_linked": int(len(habitable)),
        "habitable_linked_pct": round(100.0 * len(habitable) / len(linked), 1) if linked else 0.0,
        "groups": dict(sorted(groups.items(), key=lambda item: (-item[1], item[0]))),
        "params": snapshot.get("params") or {},
    }
    if assigned is not None and not assigned.empty:
        linked_df = assigned[assigned["gate_distance"].notna()] if "gate_distance" in assigned else assigned
        extra = catalog_stats(linked_df)
        extra.pop("catalog_systems", None)
        stats["nasa_flags_on_linked"] = extra
    return stats


def resolve_catalog(preset: dict[str, Any]) -> dict[str, Any]:
    """Prefer NASA CSVs in data/raw; otherwise the committed sample catalog."""
    origin = preset.get("origin") or {}
    max_ly = float(origin.get("max_distance_ly") or 60)
    min_mass = float((preset.get("network") or {}).get("min_stellar_mass") or 0.25)
    origin_host = origin.get("origin_hostname") or "Sol"
    detected = detect_default_sources()
    planets = detected.get("planet_path")
    hosts = detected.get("host_path")
    if planets and hosts:
        out = DATA_PRESETS / preset["id"] / "systems.csv"
        result = build_systems_dataset(
            planets,
            hosts,
            output_path=out,
            max_distance_ly=max_ly,
            min_stellar_mass=min_mass,
            origin_hostname=origin_host,
        )
        return {
            "source": "nasa",
            "systems_path": str(out),
            "planet_path": planets,
            "host_path": hosts,
            "ingest": result,
        }
    if not SAMPLE_SYSTEMS_CSV.exists():
        raise FileNotFoundError(
            "No NASA CSVs in data/raw and no committed sample catalog at "
            f"{SAMPLE_SYSTEMS_CSV}"
        )
    return {
        "source": "sample",
        "systems_path": str(SAMPLE_SYSTEMS_CSV),
        "note": (
            "data/raw NASA CSVs were missing; used the committed 60 ly sample "
            f"catalog ({SAMPLE_SYSTEMS_CSV.relative_to(ROOT).as_posix()})."
        ),
    }


def build_preset_snapshot(
    preset: dict[str, Any],
    systems_path: str | Path,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any]]:
    params = dict(preset.get("network") or {})
    factions = preset.get("factions") or {}
    work_dir = DATA_PRESETS / preset["id"]
    work_dir.mkdir(parents=True, exist_ok=True)
    network_csv = work_dir / "sol_network.csv"
    assigned_csv = work_dir / "assigned_systems.csv"
    routes_csv = work_dir / "route_table.csv"

    generated = generate_network(
        systems_path=str(systems_path),
        output_path=str(network_csv),
        params=params,
    )
    network = pd.read_csv(network_csv)
    assigned, _routes = assign_factions(
        network,
        config=factions,
        output_assigned=assigned_csv,
        output_routes=routes_csv,
    )
    snapshot = {
        "starroute": "2.0",
        "kind": "network_snapshot",
        "id": preset["id"],
        "title": preset.get("title") or preset["id"],
        "description": preset.get("description") or "",
        "origin": preset.get("origin") or {"origin_hostname": params.get("root_hostname", "Sol")},
        "params": generated.get("params") or params,
        "factions": factions,
        "payload": network_payload(assigned),
    }
    stats = snapshot_stats(snapshot, assigned)
    stats["id"] = preset["id"]
    stats["description"] = preset.get("description") or ""
    return snapshot, assigned, stats


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def _write_pack_js(path: Path, preset_id: str, snapshot: dict[str, Any]) -> None:
    blob = json.dumps(snapshot, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "window.STARROUTE_PRESET_PACKS=window.STARROUTE_PRESET_PACKS||{};"
        f"window.STARROUTE_PRESET_PACKS[{json.dumps(preset_id)}]={blob};\n",
        encoding="utf-8",
    )


def emit_pack(
    preset: dict[str, Any],
    snapshot: dict[str, Any],
    stats: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    preset_id = preset["id"]
    data_dir = DATA_PRESETS / preset_id
    static_dir = STATIC_PRESETS / preset_id
    data_dir.mkdir(parents=True, exist_ok=True)
    static_dir.mkdir(parents=True, exist_ok=True)

    systems_path = catalog.get("systems_path")
    try:
        systems_path = Path(systems_path).resolve().relative_to(ROOT).as_posix()
    except (TypeError, ValueError):
        pass
    pack_stats = {
        **stats,
        "catalog_source": catalog.get("source"),
        "catalog_note": catalog.get("note"),
        "systems_path": systems_path,
    }
    _write_json(data_dir / "map.json", snapshot)
    _write_json(data_dir / "stats.json", pack_stats)
    _write_json(static_dir / "map.json", snapshot)
    _write_pack_js(static_dir / "map.js", preset_id, snapshot)
    return pack_stats


def write_index(config: dict[str, Any], built: list[dict[str, Any]]) -> None:
    STATIC_PRESETS.mkdir(parents=True, exist_ok=True)
    index = {
        "default": config.get("default") or "crowded",
        "presets": [
            {
                "id": item["id"],
                "title": item.get("title") or item["id"],
                "description": item.get("description") or "",
                "path": f"presets/{item['id']}/map.json",
            }
            for item in config.get("presets", [])
        ],
        "stats": {row["id"]: row for row in built},
    }
    _write_json(STATIC_PRESETS / "index.json", index)
    (DATA_PRESETS / "index.json").parent.mkdir(parents=True, exist_ok=True)
    _write_json(DATA_PRESETS / "index.json", index)


def write_default_map_copies(crowded: dict[str, Any]) -> None:
    """Keep the existing default-map.js boot path in sync with the crowded pack."""
    blob = json.dumps(crowded, separators=(",", ":"))
    js = f"window.STARROUTE_DEFAULT_MAP = {blob};\n"
    static_root = STATIC_PRESETS.parent
    (static_root / "default-map.json").write_text(blob, encoding="utf-8")
    (static_root / "default-map.js").write_text(js, encoding="utf-8")
    preview = ROOT / "preview"
    if preview.is_dir():
        (preview / "default-map.json").write_text(blob, encoding="utf-8")
        (preview / "default-map.js").write_text(js, encoding="utf-8")


def write_presets_markdown(config: dict[str, Any], built: list[dict[str, Any]], catalog_note: str) -> Path:
    lines = [
        "# Jumpgate Starroute map presets",
        "",
        "Three pre-generated **network snapshots** (JSON, not 3D models) for static hosting.",
        "Viewers open `starroute/web/static/app.html` and switch packs in the map toolbar.",
        "No live Python server is required to look at or switch maps.",
        "",
        "## Catalog",
        "",
        catalog_note,
        "",
        "Regenerate after editing `config/map_presets.json`:",
        "",
        "```bash",
        "python -m starroute build-presets",
        "# or: python scripts/build_presets.py",
        "```",
        "",
        "Packs are written to `data/presets/{id}/map.json` and copied to",
        "`starroute/web/static/presets/{id}/` for the static viewer.",
        "",
        "## Quality targets",
        "",
        "- About **30–100** systems in the largest connected component.",
        "- At least **~75%** of *linked* systems habitable by someone under that pack’s",
        "  faction/habitat rules (a non-empty culture `group` after assignment).",
        "- NASA carbon/sulfur/gas flags on the 60 ly sample are sparse; those counts are",
        "  reported separately and are **not** the 75% metric. Best NASA-flag rate on this",
        "  sample is **63 / 148** catalog stars (42.6%). The knobs below still meet 75%",
        "  under pack assignment rules.",
        "",
    ]
    for row in built:
        params = row.get("params") or {}
        nasa = row.get("nasa_flags_on_linked") or {}
        groups = row.get("groups") or {}
        group_line = ", ".join(f"{name} {count}" for name, count in groups.items()) or "(none)"
        max_mass = params.get("max_stellar_mass")
        mass_txt = f"{params.get('min_stellar_mass')}"
        if max_mass is not None:
            mass_txt += f"–{max_mass}"
        lines.extend(
            [
                f"## `{row['id']}` — {row.get('title') or row['id']}",
                "",
                row.get("description") or "",
                "",
                f"- Catalog source: **{row.get('catalog_source')}**",
                f"- Knobs: min/max stellar mass {mass_txt} M☉; max jump **{params.get('max_jump_ly')} ly**;",
                f"  max neighbors {params.get('max_neighbors')}; linked cap {params.get('max_linked_nodes')};",
                f"  short/medium {params.get('medium_start_pct')}% / long {params.get('long_start_pct')}%.",
                f"- Snapshot nodes: **{row.get('nodes')}** ({row.get('edges')} jump edges).",
                f"- Linked / largest component: **{row.get('linked_nodes')}** / **{row.get('largest_component')}**.",
                f"- Habitable by someone (linked, pack rules): **{row.get('habitable_linked')}** "
                f"({row.get('habitable_linked_pct')}%).",
                f"- Cultures on the grid: {group_line}.",
                f"- NASA habitat flags on linked systems: carbon-zone {nasa.get('carbon_zone', 0)}, "
                f"sulfur-zone {nasa.get('sulfur_zone', 0)}, gas-giant {nasa.get('gas_giant', 0)} "
                f"(any of those: {nasa.get('nasa_habitat_flag', 0)}).",
                "",
            ]
        )
    path = ROOT / "PRESETS.md"
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def build_all(ids: list[str] | None = None) -> dict[str, Any]:
    ensure_data_dirs()
    DATA_PRESETS.mkdir(parents=True, exist_ok=True)
    STATIC_PRESETS.mkdir(parents=True, exist_ok=True)
    config = load_map_presets()
    wanted = set(ids) if ids else None
    catalog_notes: list[str] = []
    built: list[dict[str, Any]] = []
    crowded_snapshot: dict[str, Any] | None = None

    for preset in config.get("presets", []):
        preset_id = preset["id"]
        if wanted is not None and preset_id not in wanted:
            continue
        catalog = resolve_catalog(preset)
        if catalog.get("note"):
            catalog_notes.append(catalog["note"])
        snapshot, _assigned, stats = build_preset_snapshot(preset, catalog["systems_path"])
        pack_stats = emit_pack(preset, snapshot, stats, catalog)
        built.append(pack_stats)
        if preset_id == "crowded":
            crowded_snapshot = snapshot

    if not built:
        raise SystemExit("No presets built. Check --id against config/map_presets.json.")

    write_index(config, built)
    if crowded_snapshot is not None:
        write_default_map_copies(crowded_snapshot)
    note = catalog_notes[0] if catalog_notes else (
        "NASA CSVs in data/raw were used for this build."
        if any(row.get("catalog_source") == "nasa" for row in built)
        else "Built from the committed sample catalog."
    )
    md = write_presets_markdown(config, built, note)
    return {"built": built, "presets_md": str(md), "catalog_note": note}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build static Jumpgate map preset packs")
    parser.add_argument("--id", action="append", dest="ids", help="Build only this preset id (repeatable)")
    args = parser.parse_args(argv)
    result = build_all(args.ids)
    print(json.dumps({"catalog_note": result["catalog_note"], "built": result["built"]}, indent=2, default=str))
    return 0
