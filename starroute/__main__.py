"""CLI: ``python -m starroute serve`` or ``python -m starroute ingest``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from starroute.ingest.pipeline import build_systems_dataset, detect_default_sources, preview_sources
from starroute.mapgen.factions import assign_factions, load_faction_config
from starroute.mapgen.network import generate_network
from starroute.paths import NETWORK_CSV, SYSTEMS_CSV


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="starroute", description="Jumpgate Starroute tools")
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="Open the local web UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8050)

    ingest = sub.add_parser("ingest", help="Build systems.csv from NASA snapshots")
    ingest.add_argument("--planets")
    ingest.add_argument("--hosts")
    ingest.add_argument("--max-ly", type=float, default=1000.0)
    ingest.add_argument("--min-mass", type=float, default=0.25)
    ingest.add_argument("--preview", action="store_true")

    net = sub.add_parser("network", help="Build the Sol-centered jump network")
    net.add_argument("--max-jump", type=float, default=50.0)
    net.add_argument("--no-factions", action="store_true")
    net.add_argument("--systems", help="Systems CSV (default: data/processed/systems.csv)")
    net.add_argument("--output", help="Network CSV to write (default: data/processed/sol_network.csv)")
    net.add_argument("--catalog", help="Stream this merged catalog instead of --systems")
    net.add_argument("--max-distance", type=float, default=None, help="Trim radius in ly when --catalog is set")
    net.add_argument("--origin", default="Sol", help="Origin hostname when --catalog is set")

    presets = sub.add_parser("build-presets", help="Write the three static map preset packs")
    presets.add_argument("--id", action="append", dest="ids", help="Build only this preset id (repeatable)")
    presets.add_argument("--catalog", help="Merged catalog CSV. Overrides STARROUTE_CATALOG and config/catalog.json")
    presets.add_argument("--dest", help="Write packs under this folder instead of the repo presets")

    handoff = sub.add_parser("handoff", help="Validate a system-handoff JSON file")
    handoff.add_argument("record", help="Path to a handoff JSON record")

    lore = sub.add_parser("build-lore", help="Write the static lore wiki index from setting/*.md")
    lore.add_argument("--vault", help="Markdown vault (default: setting/)")
    lore.add_argument("--dest", help="Static lore folder (default: starroute/web/static/docs/lore)")

    args = parser.parse_args(argv)

    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("starroute.web.app:app", host=args.host, port=args.port, reload=False)
        return

    if args.cmd == "ingest":
        detected = detect_default_sources()
        planets = args.planets or detected["planet_path"]
        hosts = args.hosts or detected["host_path"]
        if not planets or not hosts:
            raise SystemExit("Provide --planets and --hosts, or place NASA CSVs in data/raw/.")
        if args.preview:
            print(json.dumps(preview_sources(planets, hosts), indent=2))
            return
        print(json.dumps(build_systems_dataset(planets, hosts, max_distance_ly=args.max_ly, min_stellar_mass=args.min_mass), indent=2))
        return

    if args.cmd == "network":
        systems_path = args.systems
        if args.catalog:
            from starroute.catalog import load_trimmed_frame
            from starroute.paths import DATA_PROCESSED, NETWORK_JSON

            distance = args.max_distance
            if distance is None and NETWORK_JSON.is_file():
                distance = float(json.loads(NETWORK_JSON.read_text(encoding="utf-8")).get("ingest_max_distance_ly") or 60)
            distance = 60.0 if distance is None else float(distance)
            frame = load_trimmed_frame(args.catalog, origin=args.origin, max_distance_ly=distance)
            window = DATA_PROCESSED / "catalog_window.csv"
            window.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(window, index=False)
            systems_path = str(window)
        elif not systems_path and not SYSTEMS_CSV.exists():
            raise SystemExit("Run ingest first (no data/processed/systems.csv), or pass --catalog.")
        result = generate_network(
            systems_path=systems_path,
            output_path=args.output,
            params={"max_jump_ly": args.max_jump, "root_hostname": args.origin},
        )
        if not args.no_factions:
            written = result["output_path"]
            df = __import__("pandas").read_csv(written)
            assigned, routes = assign_factions(df, config=load_faction_config())
            assigned.to_csv(written, index=False)
            result["assigned"] = int(assigned["assigned"].sum())
            result["routes"] = int(len(routes))
        print(json.dumps(result, indent=2, default=str))
        return

    if args.cmd == "build-presets":
        from starroute.presets import main as build_presets_main

        extra: list[str] = []
        for preset_id in args.ids or []:
            extra.extend(["--id", preset_id])
        if args.catalog:
            extra.extend(["--catalog", args.catalog])
        if args.dest:
            extra.extend(["--dest", args.dest])
        raise SystemExit(build_presets_main(extra))

    if args.cmd == "handoff":
        from starroute.handoff import load_schema, validate_handoff

        record = json.loads(Path(args.record).read_text(encoding="utf-8"))
        errors = validate_handoff(record, load_schema())
        if errors:
            print("\n".join(errors))
            raise SystemExit(1)
        print(json.dumps({"ok": True, "star_key": record.get("star_key"), "tier": record.get("tier")}, indent=2))
        return

    if args.cmd == "build-lore":
        from starroute.lore import main as build_lore_main

        extra = []
        if args.vault:
            extra.extend(["--vault", args.vault])
        if args.dest:
            extra.extend(["--dest", args.dest])
        raise SystemExit(build_lore_main(extra))


if __name__ == "__main__":
    main()
