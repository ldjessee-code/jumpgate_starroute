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

Public site (no Python): **https://ldjessee-code.github.io/jumpgate_starroute/**

Three **static map packs** ship as JSON network snapshots (not 3D models):

- **Crowded** — Turquenish neighborhood (short jumps, bio vs chrome, local aliens)
- **Sparse** — same war on a thinner gate grid
- **Lonely humans** — Sun-like stars only; human factions, no local aliens

Switch packs in the map toolbar. Lore follows the pack you last picked.
Settings sit in a side drawer. **Generate new map** rebuilds from the shipped
star list in the browser (Pyodide). NASA ingest is still grayed out.

**Context help:** on the map, click the **?** next to **Terms & Help docs**
(or press `?`), then click a control, the map, the legend, or a lore panel.
Settings is the gear above those. HTML/CSS/JS only. See
[docs/help.html](starroute/web/static/docs/help.html).

Counts and knobs: [PRESETS.md](PRESETS.md). How we got here: [HISTORY.md](HISTORY.md).

## Open the map (no install)

Hosted: https://ldjessee-code.github.io/jumpgate_starroute/app.html

Or locally (do not use raw `file://` — fetches get blocked):

```bash
cd starroute/web/static
python -m http.server 8765
```

Then http://127.0.0.1:8765/

The preset picker loads `presets/{crowded,sparse,lonely_humans}/map.json`.
If JSON fetch fails, it falls back to `map.js`. Crowded also boots from
`default-map.js`.

**Lore:** [`setting/`](setting/) is the Markdown vault. The viewer is
`docs/lore/` and lists only the current pack. Add/Edit in the browser saves a
copy in that browser (`setting/custom/{pack}/` is the git folder so your files
stay separate). Rebuild the committed index with `python -m starroute build-lore`.
Details: `starroute/web/static/docs/lore.html`.

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
setting/              lore vault (crowded / sparse / lonely_humans / custom)
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
