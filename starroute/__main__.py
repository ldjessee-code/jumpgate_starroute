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
        if not SYSTEMS_CSV.exists():
            raise SystemExit("Run ingest first (no data/processed/systems.csv).")
        result = generate_network(params={"max_jump_ly": args.max_jump})
        if not args.no_factions:
            df = __import__("pandas").read_csv(NETWORK_CSV)
            assigned, routes = assign_factions(df, config=load_faction_config())
            assigned.to_csv(NETWORK_CSV, index=False)
            result["assigned"] = int(assigned["assigned"].sum())
            result["routes"] = int(len(routes))
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
