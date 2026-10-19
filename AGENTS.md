# AGENTS.md

## Purpose

Jumpgate Starroute v2.0: a tool for tabletop RPG GMs, players, and authors to build and track jump-gate (or other FTL) routes through real nearby stars, painted with factions and cultures (README.md). Package `starroute`. The public site is the static map in `starroute/web/static/`, deployed to GitHub Pages (https://ldjessee-code.github.io/jumpgate_starroute/). Optional Python rebuilds maps and serves the same UI locally through FastAPI. Ptah v3 / Worldstack / Gamer Eye work lives in the separate `star_network` repo, not here. Sibling for planets and orbits: `../orbit_match`.

This is the live checkout (`C:\Users\DougJ\Documents\GitHub\jumpgate_starroute`). The copy under `F:\Dropbox\Projects\jumpgate_starroute` is old; do not work there.

## Stack

- Python 3.9+ (README.md; 3.11+ preferred). The local `.venv` is Python 3.13 (`.venv\pyvenv.cfg`).
- Dependencies (`requirements.txt`): pandas, numpy, scipy, networkx, fastapi, uvicorn[standard], python-multipart, jinja2. There is no pyproject.toml, so no installed console script; run the package with `python -m starroute`.
- Browser side: HTML/CSS/JS and Plotly.js in `starroute/web/static/`; optional in-browser map generation through Pyodide (WASM.md).
- No tests folder, no pytest config, no linter config, no package.json, no Makefile.
- CI: `.github/workflows/pages.yml` only. It deploys `starroute/web/static/` to GitHub Pages on push to `main` when that folder or the workflow changes.

## Layout

- `starroute/__main__.py` - CLI (`serve`, `ingest`, `network`, `build-presets`, `build-lore`)
- `starroute/ingest/` - NASA CSV to classified systems plus Sol
- `starroute/mapgen/` - ranking, Sol-rooted network, faction assignment
- `starroute/web/app.py` - FastAPI app; `starroute/web/templates/`
- `starroute/web/static/` - the static site: `app.html`, `index.html`, `js/`, `css/`, `docs/` (including `docs/lore/`), `presets/{crowded,sparse,lonely_humans}/`, `sample-systems.csv`, `default-map.json`
- `starroute/web/static/engine/` - second copy of the mapgen modules and config that the browser (Pyodide) runs. A change to `starroute/mapgen/` may need the same change here; read WASM.md first.
- `starroute/presets.py`, `starroute/lore.py`, `starroute/paths.py`, `starroute/coords.py`; wrappers in `scripts/build_presets.py` and `scripts/build_lore.py`
- `config/` - `network.json`, `factions.json`, `factions.default.json`, `faction_presets.json`, `map_presets.json`
- `setting/` - Turquenish-Mardat lore packs (author copyright, not MIT; `setting/COPYRIGHT.md`)
- `user_setting/` - homebrew lore added by users
- `authoring/` - writing sheets; `catalog/NOTICE.md` - NASA data notice; `preview/` - static preview
- `data/` - local NASA snapshots and generated tables (mostly gitignored)
- Docs: README.md, SITE.md, PRESETS.md, WASM.md, HISTORY.md, GAME_SYSTEMS.md, How_to_Use-Integrate.md, TURQUENISH_SOURCE.md
- Open work: `TODO-between-stars.md` (agreed feature list) and `BUG-map-fullscreen.md` (open layout bug)

## Commands (Windows PowerShell, from the repo root)

Taken from README.md, `starroute/__main__.py`, and the workflow. Not executed when this file was written.

- Map without Python: open `starroute/web/static/app.html`, or serve that folder with any static server (see `starroute/web/static/docs/run-local.html`, which uses 127.0.0.1:8765)
- Set up (only if `.venv` is missing): `python -m venv .venv` then `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
- Run the local app: `.\.venv\Scripts\python.exe -m starroute serve` then open http://127.0.0.1:8050 (flags `--host`, `--port`)
- Ingest preview: `.\.venv\Scripts\python.exe -m starroute ingest --preview` (needs NASA CSVs in `data/raw/`)
- Network: `.\.venv\Scripts\python.exe -m starroute network --max-jump 50` (add `--no-factions` to skip factions)
- Rebuild the preset packs: `.\.venv\Scripts\python.exe -m starroute build-presets` (writes `data/presets/` and `starroute/web/static/presets/`; uses `sample-systems.csv` when `data/raw/` has no NASA CSVs)
- Rebuild the lore index: `.\.venv\Scripts\python.exe -m starroute build-lore`
- Tests / lint: none exist; ask Doug before adding a framework

## Proof of change

| Change type | Command to prove it | Expected result |
|---|---|---|
| Python change | `.\.venv\Scripts\python.exe -m compileall -q starroute scripts` then `.\.venv\Scripts\python.exe -m starroute --help` | No errors; help lists the five commands |
| Web app / API change | `.\.venv\Scripts\python.exe -m starroute serve`, open http://127.0.0.1:8050 | Map loads; the changed screen works |
| Static site change (`starroute/web/static/`) | Serve the folder or run `serve`, open `app.html` | Map and docs load with no console errors |
| Mapgen or preset change | `.\.venv\Scripts\python.exe -m starroute build-presets`, then `git diff --stat` | Only the intended packs change |
| Lore change | `.\.venv\Scripts\python.exe -m starroute build-lore`, then `git diff --stat` | Only the intended lore index files change |
| Docs-only change | none | No docs checker exists |

## Definition of done

- The proof rows that apply have been run and match.
- Commit and push only on branch `review` (see Git). A push to `main` that touches `starroute/web/static/` publishes the public site.
- No new NASA blobs committed under `data/raw/`; no secrets.
- Report what was run and what was not.

## Coding conventions

- Python: 4-space indent, double quotes, `from __future__ import annotations` at the top of modules (as in the existing files).
- Static JS/CSS has no lint config; match the file you edit. Context help lives in `js/help.js` and `js/glossary.js` (SITE.md).
- Faction rules live in `config/factions.json` (README.md).
- Files in this repo use CRLF line endings.

## Do not touch

- `.git/`, `.venv/`, `.env` or other secrets, keys, and credential files
- Gitignored local data: `data/raw/*`, `data/processed/*`, `data/uploads/*` (keep `.gitkeep`), `data/presets/**/*.csv`
- `setting/` prose: author copyright, and `TODO-between-stars.md` says setting prose is edited only in the Dropbox Turquenish folder. Do not rewrite it here unless Doug asks.
- `user_setting/` belongs to users; do not mix the example Turquenish text into it
- The `star_network` repo and the old Dropbox copy of this repo
- See Git: agents commit and push only on `review`.

## Git

Bots and Grok Build commit and push only to `review`. Before committing, check `git branch --show-current` is `review`. Make small commits, one per section or change, with a conventional message. Never commit or push to `main` or `master`. Never merge, rebase, force-push, or delete branches. Doug merges and may cherry-pick. Read-only git (`status`, `diff`, `log`, `show`) is fine. Do not write under `.git\`.

## Todos

### Ports: configurable, fallback, and the orbit_match peer (added 2026-09-28)

Current state (read from files on 2026-09-28; not run): the port is set only by `starroute/__main__.py` (`serve --host`, default 127.0.0.1; `serve --port`, default 8050). There is no env var or config entry. README.md, WASM.md, `starroute/web/static/docs/run-local.html`, and BUG-map-fullscreen.md all say 8050. **8050 clash:** `star_network` (Ptah v3, gamer_eye family) also defaults to 8050, so the two cannot run at once on their defaults. The gamer_eye family keeps 8050-8119 for its own apps. orbit_match is a static site; its `site/config.json` `other_page` already makes the address of this map configurable (the shipped file uses the public GitHub Pages URL). Its local example in orbit_match `BRIEF.md` is `http://127.0.0.1:8080/app.html`, which matches neither side today. Suggested pair: jumpgate_starroute 8130, orbit_match 8131 (Doug decides).

- [ ] Make the listen port config, not only a CLI default. Precedence: `serve --port`, then an env var (for example `STARROUTE_PORT`; avoid `PTAH_PORT` so it is not confused with Ptah v3), then a config entry (for example in `config/network.json` or a new small config file), then the built-in default. Refuse the macOS AirPlay ports (5000, 6000, 7000, 7100).
- [ ] Move the default off 8050 so it stops colliding with `star_network`. Pick a value outside 8050-8119 (suggested 8130). Update README.md, WASM.md, `starroute/web/static/docs/run-local.html`, and the orbit_match local `other_page` example to the same number.
- [ ] If the port is in use, fall back instead of failing: try a short list the app picks (for example 8130, 8132, 8134) or a user list (`--port-fallback` repeatable, or `STARROUTE_PORT_FALLBACKS=8130,8132`).
- [ ] Keep jumpgate_starroute and orbit_match on adjacent ports: orbit_match on this port + 1. If this app falls back, move as a pair where possible.
- [ ] Peer discovery: let the user say where orbit_match is (`--orbit-match-url` / `ORBIT_MATCH_URL` / config). If not given, try this port + 1, then a discovery file such as `~/.jumpgate/ports/orbit_match.json`. Write the port this app actually bound to `~/.jumpgate/ports/jumpgate_starroute.json` on start and remove it on clean exit. Optional handshake: `GET /v1/provider` returns product key and bound port.
- [ ] Print one clear startup line naming both ports, for example `jumpgate_starroute listening on http://127.0.0.1:8130/ (configured 8130); orbit_match peer: http://127.0.0.1:8131 (found via adjacent port)`. If the peer is missing, say so and how to point at it.
- [ ] Document it in README.md and this file: default port, env var and flags, fallback order, discovery file, and how to point either app at the other by hand.
