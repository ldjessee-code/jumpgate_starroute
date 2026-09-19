# Jumpgate Starroute

**Version 2.0** — August 2026

A tool for **tabletop RPG GMs and players**, and for **authors**, to **create,
track, and manage jump-gate (or other FTL) routes** through a neighborhood of
real nearby stars, painted with factions and cultures.

Stars come from NASA catalog data (plus Sol). You decide jump length, who
lives where, and which roads stay lit. The result is a 3D map you can rotate,
trace a path on, and brief a table from — not a video-game 3D model pack.

Try it with no install:
**https://ldjessee-code.github.io/jumpgate_starroute/**

Ptah v3 / Worldstack / Gamer Eye work continues in
[star_network](https://github.com/ldjessee-code/star_network). This repo is
the v2.0 map tool. History: [HISTORY.md](HISTORY.md).

## Example neighborhoods

Three **example** packs ship as finished JSON snapshots (same star catalog,
different rules). Switch them in the map toolbar. They are samples, not the
only way to play.

| Pack | Map | Included setting text |
| --- | --- | --- |
| **Crowded** | Short jumps, small stars kept. Dense local space. | Turquenish Empire (bio-edit) vs Mardat Coalition (chrome), plus local aliens |
| **Sparse** | Same war, fewer tiny red dwarfs, longer hops | Same peoples; thinner gate grid |
| **Lonely humans** | Sun-like stars only | Human factions only; no local aliens |

Lore pages follow the pack you last picked: [setting/](setting/) (author
copyright — not MIT). Counts and knobs: [PRESETS.md](PRESETS.md).

## Your own systems, routes, and setting

**Look around (no Python):** open the [hosted site](https://ldjessee-code.github.io/jumpgate_starroute/),
or copy `starroute/web/static/` and open it from disk / USB / NAS. Drag
`app.html` onto a browser; if fetches fail, use a tiny static server. See
[Run locally](starroute/web/static/docs/run-local.html).

**Add your own setting details** on top of a pack (lore only, same map):
blank JSON templates and steps in
[Your own setting](starroute/web/static/docs/own-setting.html). Commit
Markdown under [`user_setting/`](user_setting/) so it never mixes with the
example Turquenish text.

**Generate your own systems and routes** (optional Python): ingest NASA CSVs,
retune jump knobs, rebuild packs. That is the gray “self-host” path —
[what it adds](starroute/web/static/docs/self-host.html), then
[how to deploy](starroute/web/static/docs/deploy.html).

**Context help:** click **?** next to **Terms & Help docs**, then click a
control. Gear = Settings.

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

This is a **split** license. The map **tool** is MIT. The **setting** is not.

| Tree | What | License |
| --- | --- | --- |
| Code, static viewer, how-to docs (`starroute/`, `config/` knobs, most of `docs/`) | Software | [MIT](LICENSE) — copyright Lloyd Douglass Jessee |
| [`setting/`](setting/) | Turquenish–Mardat lore | [setting/COPYRIGHT.md](setting/COPYRIGHT.md) — author retains copyright; personal / tabletop use with this tool |
| [`user_setting/`](user_setting/) | Homebrew you add | Yours. Not MIT and not the Turquenish grant |
| NASA extracts (`data/raw/`, `sample-systems.csv`) | Star catalog | Not MIT; not fiction. See [catalog/NOTICE.md](catalog/NOTICE.md) |

MIT already keeps your copyright on the **code**; it grants others broad reuse of that code. Restricting the **lore** to personal / tabletop use is a separate grant, which is why it lives in its own root folder with its own notice.

Culture *names* on the generated map JSON are labels that point at `setting/`. The prose stays in `setting/`.

This is not legal advice.
