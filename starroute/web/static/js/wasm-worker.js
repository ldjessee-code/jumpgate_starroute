/* Pyodide worker: same Python mapgen, same snapshot JSON, shipped star list. */
/* global loadPyodide */

const PY_FILES = [
  "starroute/__init__.py",
  "starroute/paths.py",
  "starroute/mapgen/__init__.py",
  "starroute/mapgen/ranking.py",
  "starroute/mapgen/network.py",
  "starroute/mapgen/factions.py",
];

const CONFIG_FILES = [
  "config/factions.json",
  "config/factions.default.json",
  "config/faction_presets.json",
  "config/network.json",
];

let pyodide = null;
let ready = false;

function engineBase() {
  return self.location.href.replace(/js\/wasm-worker\.js.*$/, "engine/");
}

function staticBase() {
  return self.location.href.replace(/js\/wasm-worker\.js.*$/, "");
}

async function fetchText(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not load ${url} (${res.status})`);
  return res.text();
}

async function fetchBytes(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not load ${url} (${res.status})`);
  return new Uint8Array(await res.arrayBuffer());
}

async function boot() {
  postMessage({ type: "status", message: "Loading Python in the browser (Pyodide)…" });
  pyodide = await loadPyodide({
    indexURL: "https://cdn.jsdelivr.net/pyodide/v0.27.5/full/",
  });
  postMessage({ type: "status", message: "Loading NumPy, pandas, SciPy, NetworkX…" });
  await pyodide.loadPackage(["numpy", "pandas", "scipy", "networkx"]);

  const fs = pyodide.FS;
  ["/starroute/mapgen", "/config", "/data/processed"].forEach((dir) => {
    fs.mkdirTree(dir);
  });

  const base = engineBase();
  for (const rel of PY_FILES) {
    const text = await fetchText(base + rel);
    fs.writeFile("/" + rel, text);
  }
  for (const rel of CONFIG_FILES) {
    const text = await fetchText(base + rel);
    fs.writeFile("/" + rel, text);
  }
  postMessage({ type: "status", message: "Loading the shipped 60 ly star list…" });
  const systems = await fetchBytes(staticBase() + "sample-systems.csv");
  fs.writeFile("/data/processed/systems.csv", systems);

  pyodide.runPython("import sys; sys.path.insert(0, '/')");
  ready = true;
  postMessage({ type: "ready", message: "Browser engine ready. Star list is loaded." });
}

async function rebuild(msg) {
  if (!ready) throw new Error("Engine is not ready yet.");
  postMessage({ type: "status", message: "Growing jump network from the shipped star list…" });
  const params = msg.params || {};
  pyodide.globals.set("js_params_json", JSON.stringify(params));
  pyodide.globals.set("js_assign", msg.assign_factions !== false ? 1 : 0);
  const payload = await pyodide.runPythonAsync(`
import json
import pandas as pd
from starroute.mapgen.network import generate_network, network_payload
from starroute.mapgen.factions import assign_factions, load_faction_config

keys = [
    "max_jump_ly",
    "medium_start_pct",
    "long_start_pct",
    "max_neighbors",
    "max_linked_nodes",
    "hard_rank",
    "soft_rank",
    "min_stellar_mass",
    "root_hostname",
]
raw = json.loads(js_params_json)
params = {k: raw[k] for k in keys if k in raw}
root = params.get("root_hostname", "Sol")

result = generate_network(
    systems_path="/data/processed/systems.csv",
    output_path="/data/processed/sol_network.csv",
    params=params,
)
df = pd.read_csv("/data/processed/sol_network.csv")
factions = load_faction_config("/config/factions.json")
if int(js_assign):
    df, _routes = assign_factions(
        df,
        config=factions,
        output_assigned="/data/processed/assigned_systems.csv",
        output_routes="/data/processed/route_table.csv",
    )
canon = {k: result["params"][k] for k in keys if k in result["params"]}
snapshot = {
    "starroute": "2.0",
    "kind": "network_snapshot",
    "title": "Local space — generated in browser",
    "origin": {"origin_hostname": root},
    "params": canon,
    "factions": factions,
    "payload": network_payload(df),
}
json.dumps(snapshot)
`);
  return JSON.parse(payload);
}

self.onmessage = async (event) => {
  const msg = event.data || {};
  try {
    if (msg.type === "boot") {
      if (!ready) await boot();
      else postMessage({ type: "ready", message: "Browser engine ready. Star list is loaded." });
      return;
    }
    if (msg.type === "rebuild") {
      const data = await rebuild(msg);
      postMessage({ type: "result", data });
    }
  } catch (err) {
    postMessage({ type: "error", message: String(err && err.message ? err.message : err) });
  }
};

importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.5/full/pyodide.js");
