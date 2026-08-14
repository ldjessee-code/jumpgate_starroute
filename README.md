# Jumpgate Starroute

A local GM / author tool that turns NASA Exoplanet Archive tables into a
**Sol-centered jump or star-gate network**, then draws it in the browser.

You confirm the source CSVs, convert them (and insert Sol), then grow a network
with range, ranking, and optional species/nation rules.

This is **not** the sibling analytics-platform project
(`../analytics-platform`).

## UI stack (why not Dash)

The previous visualizer was a Dash + Plotly 3D app. It broke on a Plotly API
change (`marker.colorbar.titleside` was removed) and the default Dash chrome
was hard to restyle.

Options considered:

| Approach | Verdict |
| --- | --- |
| **FastAPI + Plotly.js** (this repo) | Best fit. Python still owns ingest and network math. The browser draws a real-space 3D scatter with hover, path highlight, and no Dash callbacks. |
| Dash / Plotly Python | Works again if the colorbar title is updated, but you inherit Dash layout and the old callback errors. |
| Three.js / 3d-force-graph | Prettier metal, but force layout **destroys real star positions**. A custom Three.js scene with fixed XYZ is more code than this first pass needs. |
| deck.gl / Cesium | Built for Earth maps and globes, not a heliocentric jump graph. |

The page styling follows the same parchment / navy / gold language as the
Avatar Legends character sheet (serif titles, dark header, card sections)
without copying that sheet’s layout.

## Units (important)

NASA `sy_dist` is **parsecs**. Older scripts in this folder treated those
numbers as light-years, so a “50 ly” network was really ~163 ly. This rewrite
converts parsecs → light-years (`× 3.26156`) before filtering or linking.

Confirmed exoplanet hosts inside a true 50 ly sphere are sparse. Raise
**Jump / gate range** (150–200 ly is a good first explore) if the map looks
thin.

## Setup

Needs Python 3.9+ (3.11+ if you have it).

```bash
cd ~/Projects/exoplanet/jumpgate_starroute
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Put NASA snapshots in `data/raw/`:

- `PSCompPars_YYYY.MM.DD_….csv`
- `STELLARHOSTS_YYYY.MM.DD_….csv`

Those files are gitignored (they are ~100 MB together). The Aug 2026 pair used
to build this version lives locally in `data/raw/`.

## Run the UI

```bash
python -m starroute serve
```

Open http://127.0.0.1:8050

1. **Ingest** — confirm the two file paths (or upload), preview row counts,
   generate `data/processed/systems.csv` with Sol at the origin.
2. **Network & map** — set jump range, neighbor cap, ranking floors, and
   faction counts. Generate the network and click two systems to highlight the
   shortest gate path.

## CLI

```bash
python -m starroute ingest --preview
python -m starroute ingest --max-ly 1000 --min-mass 0.25
python -m starroute network --max-jump 50
python -m starroute network --max-jump 50 --no-factions
```

## Layout

```text
starroute/ingest/     NASA CSV → classified systems + Sol
starroute/mapgen/     ranking, Sol-rooted network, faction assignment
starroute/web/        FastAPI app + Plotly.js map
config/               default network + faction JSON
data/raw/             NASA snapshots (local)
data/processed/       systems.csv, sol_network.csv, route_table.csv
```

Faction names, counts, prefixes, and filters are in `config/factions.json`.
The map screen can edit counts and prefixes; the JSON remains the full rule
set (RA wedges, gas-giant preference, and so on).

## What was archived

A frozen copy of the old script pile (including the previous `archived/`
folder) is at:

`/Users/ldjessee/Projects/Archive/starmap`

That snapshot is outside this git repo. The 444 MB Python 3.9 `env/` was not
copied; recreate a venv if you ever need the old Dash scripts.

## Known limitations

- Only hosts that already appear in the NASA tables can be mapped. Nearby
  stars with no confirmed planets are absent unless you add them by hand.
- Sol’s RA/Dec are stored as `0, 0` so it sits at the Cartesian origin. That
  is a coordinate convention, not the Sun’s catalog position.
- Faction counts from the original setting (hundreds of systems) will saturate
  a small local network; turn counts down for a 50 ly map.
