# Jumpgate Starroute

**Version 2.0** — August 2026

A local tool for GMs and authors. It takes real NASA exoplanet catalog data
and builds a **Sol-centered jump-drive or star-gate network** you can steer
with range, ranking, and optional species/nation rules, then shows the map
in a browser.

Ptah v3 / Worldstack / Gamer Eye development continues in
[star_network](https://github.com/ldjessee-code/star_network). This repository
stays at the v2.0 map tool.

How the project got here is in [HISTORY.md](HISTORY.md). Future releases
increment the version number there and here.

## Current state (v2.0)

Browser engine on git branch `wasm-pyodide` (see [WASM.md](WASM.md)): the
same Python mapgen runs in the page via Pyodide. Not merged to `main` until
you like it.

Opens on a **ready-made 3D map**. Three **static map packs** ship as JSON
network snapshots (not 3D models). Pick **Crowded**, **Sparse**, or **Lonely
humans** in the map toolbar — the page loads that pack from files next to the
viewer. No live Python server is required to look around or switch packs.

Settings hide in a side drawer so the map can fill the window. Counts,
habitability, and the knobs used for each pack are in [PRESETS.md](PRESETS.md).

Rotate, zoom, highlight a culture, and trace a jump path in the browser.
**Generate new map** (Settings) rebuilds from the same shipped star list with
new jump settings, in the browser. Same viewer, same snapshot JSON.

**Choose the stars** (NASA CSV ingest) is last and grayed out in this
release. Hosting a processed table comes later.

This release is **v2.0**. See [HISTORY.md](HISTORY.md).

## Open the map (no install)

Python is optional for viewers. Need a web connection once (Plotly). Then
open:

`starroute/web/static/app.html`

or `preview/index.html`

GitHub Pages / Cloudflare Pages can host the repo (or just
`starroute/web/static/`). The preset picker fetches
`presets/{crowded,sparse,lonely_humans}/map.json` next to `app.html`.

If you open the HTML as a local `file://` page and the browser blocks JSON
fetch, the picker falls back to `presets/{id}/map.js`. The crowded pack also
boots from `default-map.js`.

Setting notes live in [`setting/`](setting/) as ordinary Markdown. The static
wiki is `starroute/web/static/docs/lore/` (search titles, render pages in the
browser). After adding a `.md` file, run `python -m starroute build-lore`.
See `starroute/web/static/docs/lore.html`.

## Setup (only to rebuild your own map)

Python 3.9+ (3.11+ preferred). **uv** is the lightest modern installer if
you do not already have a venv.

```bash
cd ~/Projects/exoplanet/jumpgate_starroute
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Place NASA snapshots in `data/raw/` (gitignored; ~100 MB together):

- `PSCompPars_YYYY.MM.DD_….csv`
- `STELLARHOSTS_YYYY.MM.DD_….csv`

The August 2026 pair used for v1.0 lives locally in `data/raw/`.

## Run

```bash
python -m starroute serve
```

Open http://127.0.0.1:8050

CLI equivalents:

```bash
python -m starroute ingest --preview
python -m starroute ingest --max-ly 1000 --min-mass 0.25
python -m starroute network --max-jump 50
python -m starroute network --max-jump 50 --no-factions
python -m starroute build-presets
python -m starroute build-lore
```

`build-presets` (or `python scripts/build_presets.py`) writes JSON packs to
`data/presets/{id}/` and copies them to `starroute/web/static/presets/{id}/`.
If `data/raw` NASA CSVs are missing, it uses the committed sample catalog
(`starroute/web/static/sample-systems.csv`, 60 ly around Sol). See
[PRESETS.md](PRESETS.md).

## Layout

```text
starroute/ingest/     NASA CSV → classified systems + Sol
starroute/mapgen/     ranking, Sol-rooted network, faction assignment
starroute/web/        FastAPI app + Plotly.js map
config/               default network, faction, and map-preset JSON
data/raw/             NASA snapshots (local, not committed)
data/processed/       systems.csv, sol_network.csv, route_table.csv
data/presets/         crowded / sparse / lonely_humans JSON packs
setting/              flat Markdown lore vault (static wiki on Pages)
```

Faction names, counts, prefixes, and filters live in `config/factions.json`.
The map screen can edit counts and prefixes; the JSON is the full rule set
(RA wedges, gas-giant preference, and so on). Sol is always assigned to the
configured human root nation (Turquenish Empire by default).

## Units and coordinates

- NASA `sy_dist` is parsecs. v1.0 converts with `× 3.26156` before filtering
  or linking.
- Sol is stored at RA/Dec `0, 0` and Cartesian `(0, 0, 0)`. That is a
  coordinate origin, not the Sun’s catalog position.
- Systems within the preferred link distance (default 16 ly) are always
  eligible for a gate from their parent. Longer jumps still use ranking
  floors.

## Known limitations

- Only hosts that already appear in the NASA tables can be mapped. Nearby
  stars with no confirmed planets are absent unless you add them by hand.
- Default faction counts come from a large setting (hundreds of systems) and
  will saturate a small local network. Turn counts down for a 50 ly map.
- The machine this was built on had system Python 3.9.6; libraries are
  current for that line.

## Versioning

This release is **v2.0**. Earlier experimental scripts were **v0.1–v0.9**;
the first cleaned release was **v1.0**. v2.0 is the browser-engine shift.
See [HISTORY.md](HISTORY.md).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
