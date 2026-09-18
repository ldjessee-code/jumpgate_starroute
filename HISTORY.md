# Jumpgate Starroute — history and versions

Version numbers increment when a release ships. This file is the narrative;
[README.md](README.md) is the current product.

A frozen copy of the pre-1.0 script pile (including an older `archived/`
folder) sits outside the repo at `/Users/ldjessee/Projects/Archive/starmap`.
The 444 MB Python 3.9 `env/` from that era was not copied.

---

## Unreleased — context help

Click **?** (or press `?`) then click a control, the map, or a lore panel.
Popup copy lives in `js/glossary.js`. No extra libraries.

---

## Unreleased — static lore vault

`setting/*.md` is a flat lore wiki. Pages serves a committed copy at
`docs/lore/` (Markdown rendered in the browser). Rebuild the index with
`python -m starroute build-lore` — stdlib only; NASA CSVs are irrelevant.

Three pack write-ups match the map toolbar: **crowded** is the Turquenish
neighborhood (bio-edit Empire vs chrome Coalition, local aliens);
**sparse** is the same war on a thinner gate grid; **lonely_humans** is
human factions only. Tabletop notes (text only) live in `setting/source/`.

---

## Unreleased — static map presets

Three pre-generated packs (`crowded`, `sparse`, `lonely_humans`) ship as
`kind: network_snapshot` JSON. The static viewer can switch among them
without a Python server. Rebuild with `python -m starroute build-presets`.
See [PRESETS.md](PRESETS.md).

---

## v2.0 — August 2026

Browser engine. Same map viewer and snapshot JSON; maps are grown in
WebAssembly (Pyodide runs the existing Python mapgen).

- **Generate new map** rebuilds from the shipped 60 ly star list with new
  jump settings. No FastAPI required for that path. First click downloads
  Python-in-WASM once; later runs stay in the tab.
- NASA CSV ingest is parked: **Choose the stars** sits last and is grayed
  out. Hosting a processed table (Cloudflare is a candidate) is a later step.
- Version jumps from 1.4 to 2.0 because the runtime moved: view and rebuild
  both live in the browser. Python remains an optional native CLI.

---

## v1.4 — August 2026

Map-first, no Python required to look around.

- Ships a generated **60 ly** Sol neighborhood (longest jump **25 ly**, short/medium
  at **40%**, medium/long at **60%**, **0.25** solar masses).
- Two cultures: **Human** (rocky leftovers around Sol) and **Kessari** (sulfur-band
  / gas-giant worlds, Hail Mary–style contrast, a little overlap).
- Opens on the map. Settings sit in a side drawer. The 3D view fills the window.
- Rotate, zoom, path highlight, and faction focus run in the browser. Python is
  only for rebuilding from NASA files. A future WASM engine is possible; not in
  this release.
- Open `starroute/web/static/app.html` (or `preview/index.html`) with no venv.

---

## v1.3 — August 2026

- Catalog and human-home fields sit three-across on a desktop.
- Jump range is split into short / medium / long as **percentages of the
  longest hop** (defaults 50% and 75%). Short always connects; medium and
  long use the two picky-ness scores.
- Cultures can start at a **named host** (not only the map edge): a 15°
  direction wedge, a nearby pocket, or the rim around that star.
- Add-culture templates are grouped (built-in peoples plus “copy of …”
  whatever is already on the tab).

---

## v1.2 — August 2026

Culture editor on “Who lives where.”

- Cards no longer spill prefix fields out of the grid.
- Each culture can be renamed. Add from a template (up to 16). Remove any card.
- Templates start with the original setting: Methan (gas-giant stations),
  Crystomorphs (living crystal, high on the sky), sky-quarter peoples,
  rim/poor Schettel, and the human sky wedges. Custom species/nation too.
- Each card has a “How they pick stars” dropdown that applies that template’s
  placement rule without forcing you to keep the original name.

---

## v1.1 — August 2026

Friendlier UI for people who are not astronomers.

- Tab names are now “Choose the stars,” “Who lives where,” and “Draw the routes.”
- Controls use everyday labels; the technical name sits underneath.
- A **?** on each setting opens a popover: what it means, and what happens if you change it.
- **Terms & help** in the header is a searchable glossary (light-year, star mass, Goldilocks zone, jump, rank, and so on).
- 50 on the routes tab is still jump distance in light-years; star mass stays 0.25 Suns.

---

## v1.0 — August 2026

First numbered release of the cleaned project.

- Split the work into **ingest** (NASA CSVs → systems + Sol) and **map
  generation** (parameters, network, factions, display).
- Shared local web UI (FastAPI + Plotly.js) instead of a stack of one-off
  scripts and a Dash app.
- `sy_dist` converted from parsecs to light-years before filters or links.
- Nearby stars (within the preferred jump) are always eligible; ranking
  applies to longer jumps. Sol is pinned to the human root nation.
- Species and nation rules live in `config/factions.json` and can be edited
  from the map screen (counts and prefixes).
- GitHub repo `ldjessee-code/jumpgate_starroute`; large NASA snapshots and
  generated tables are gitignored.

Dash was dropped: the last 0.x visualizer broke on a Plotly API change
(`marker.colorbar.titleside`) and the default Dash chrome was a poor fit for
a GM tool. Three.js force graphs and Earth-map stacks (deck.gl, Cesium) were
rejected because they would scramble or ignore real star positions. The page
styling borrows the parchment / navy / gold language of the Avatar Legends
character sheet without copying that layout.

---

## v0.1 – v0.9 — 2025 (experimental)

Loose labels for the script iterations that lived in this folder (and later
in `archived/`) before the rewrite. Dates and names overlap; treat the
boundaries as approximate.

**v0.1 – v0.3** — Live TAP queries against the NASA Exoplanet Archive.
Early resource-scoring sketches (planet counts, habitable-zone flags, rocky
vs gas). Hardcoded “top N systems” goals. Several query files failed on
table parse or timeout.

**v0.4 – v0.6** — Species and nation assignment for the tabletop setting
(Methan, Crystomorphs, Turquenish Empire, and the rest). Route tables and
hubs. Lots of numbered `query_exoplanets_vN` and `assign_species_routes`
retries. Sol was patched in after the fact with a separate script.

**v0.7 – v0.8** — Shift toward **local NASA CSV snapshots** (PSCompPars +
Stellar Hosts) instead of TAP. `build_systems_dataset` classified planets,
estimated stability, and wrote `systems.csv`. `generate_sol_network` grew a
Sol-rooted neighbor graph with a KD-tree and a composite ranking. Several
numbered network generators (2, 3, 4) tweaked caps, parent back-links, and
gate distance.

**v0.9** — Dash + Plotly 3D viewer (`visualize_networked_systems_4`) over
`sol_network.csv`: node size by planet count, color by ranking, shape by
stability, shortest path between two hosts. This is the last pre-1.0
interface. It is the version that hit the Plotly `titleside` error and the
unit mix-up (parsecs labeled as light-years).

Default faction lore and ranking weights in v1.0 still come from these
experiments.

---

## Unreleased / next

Nothing scheduled. The next shipped change gets **v1.1** (or **v2.0** if it
breaks the v1.0 data or UI contract). Add a dated section here when that
happens.
