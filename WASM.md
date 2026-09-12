# v2.0 browser engine (branch `wasm-pyodide`)

## This release

Same map viewer. Same snapshot JSON. New maps from the **already-processed**
star list (`starroute/web/static/sample-systems.csv`, 148 systems, 60 ly around
Sol). Change jump length, short/medium/long percents, neighbors, and generate
again. NASA CSV download and ingest are **not** in this pass.

You can host a processed CSV later (Cloudflare is a reasonable place; GitHub
LFS is not required for an 81 KB file). That is the next ingest step, not this
one.

## Research conclusion

We do **not** have to rewrite the Python engine.

[Pyodide](https://pyodide.org) is CPython compiled to WebAssembly. The libraries
this project actually uses for compute are all in the official Pyodide build:

| We use | In Pyodide 0.27+ / 0.28+ |
| --- | --- |
| NumPy | yes |
| pandas | yes |
| SciPy (`scipy.spatial.cKDTree`) | yes |
| NetworkX | yes |

Not needed in the browser for this iteration:

- FastAPI / uvicorn / jinja2 — those only serve files. The map is already Plotly.js.
- Ingest (`PSCompPars` / `STELLARHOSTS` parsers).
- A new WASM neighbor-search written from scratch.

What we *do* adapt:

- File paths (`Path` on a real disk) → Pyodide’s virtual filesystem.
- First **Generate new map** click downloads the interpreter plus SciPy
  (tens of MB). Slow once; then cached.
- Culture coloring uses the shipped Human / Kessari rules that match the
  preview map. The culture editor still talks to FastAPI when that is running.

## How to try it locally

1. Serve the static app (any static server; FastAPI is fine as a file host):

   ```bash
   python -m starroute serve
   ```

2. Open http://127.0.0.1:8050 — the shipped 60 ly map appears immediately
   (no WASM yet). Same Plotly viewer as before.

3. **Settings → Generate new map.** First click pulls Pyodide + packages
   (can take a minute). Status line in the drawer while it loads. Then it
   runs `generate_network` + faction assignment in the worker and redraws.

4. Change longest jump or the short/medium percents and generate again.
   **Save this map** writes the same `network_snapshot` JSON the viewer
   already loads.

5. No venv is required for *viewing* or for generating from the shipped
   star list. You still need HTTP (GitHub Pages or a tiny static server).
   Double-clicking `app.html` as `file://` may block the Pyodide CDN/worker.

## Snapshot JSON (unchanged)

```json
{
  "starroute": "2.0",
  "kind": "network_snapshot",
  "title": "...",
  "origin": { "origin_hostname": "Sol" },
  "params": { "max_jump_ly": 25, "medium_start_pct": 40, "...": "..." },
  "factions": { },
  "payload": { "nodes": [], "edges": [] }
}
```

The viewer only needs `payload.nodes` and `payload.edges`. Saved maps from
this button open with **Open a saved map** the same way the preview file does.

## Later

- Ingest NASA CSVs (browser or a hosted processed table on Cloudflare).
- If this feels good: merge `wasm-pyodide` into `main` and keep Python as an
  optional native CLI.
- If SciPy download is too large, next step is a smaller worker — not a full
  rewrite yet.
