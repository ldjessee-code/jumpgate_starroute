const FACTION_COLORS = {
  Sol: "#ffffff",
  Human: "#d4b06a",
  Methan: "#5aa0c8",
  Crystomorphs: "#c97ad4",
  "Echryon & Echtol": "#6ecf9a",
  Aboreals: "#7aab4a",
  Bazzar: "#e07a3a",
  Schettel: "#9aa0aa",
  "Turquenish Empire": "#e6c35a",
  "Mardat Coalition": "#6a8fd4",
  "Industrial Hegemony": "#c45c26",
  "League of The Faithful": "#b8b0d4",
  "Other Human": "#c4b494",
};

let factionConfig = null;
let networkData = null;

const $ = (id) => document.getElementById(id);

function toast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.classList.remove("hidden");
  window.clearTimeout(toast._t);
  toast._t = window.setTimeout(() => el.classList.add("hidden"), 4200);
}

async function api(url, options) {
  const res = await fetch(url, options);
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const detail = data.detail || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

function showScreen(name) {
  document.querySelectorAll(".screen").forEach((el) => {
    el.classList.toggle("is-active", el.id === `screen-${name}`);
  });
  document.querySelectorAll(".tab").forEach((el) => {
    el.classList.toggle("is-active", el.dataset.screen === name);
  });
  if (name === "map" && networkData) drawMap();
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => showScreen(btn.dataset.screen));
});

async function detectSources() {
  const data = await api("/api/ingest/detect");
  if (data.planet_path) $("planet-path").value = data.planet_path;
  if (data.host_path) $("host-path").value = data.host_path;
  const nP = (data.planet_candidates || []).length;
  const nH = (data.host_candidates || []).length;
  $("detect-note").textContent = nP || nH
    ? `Found ${nP} planet snapshot(s) and ${nH} host snapshot(s) in data/raw.`
    : "No NASA CSVs in data/raw yet — paste paths or upload.";
}

async function uploadFile(kind, inputId, pathId) {
  const file = $(inputId).files[0];
  if (!file) return;
  const body = new FormData();
  body.append("kind", kind);
  body.append("file", file);
  const data = await api("/api/ingest/upload", { method: "POST", body });
  $(pathId).value = data.path;
  toast(`Saved ${data.name}`);
}

$("planet-file").addEventListener("change", () => {
  uploadFile("planets", "planet-file", "planet-path").catch((err) => toast(err.message, true));
});
$("host-file").addEventListener("change", () => {
  uploadFile("hosts", "host-file", "host-path").catch((err) => toast(err.message, true));
});

$("btn-preview").addEventListener("click", async () => {
  $("btn-preview").disabled = true;
  try {
    const data = await api("/api/ingest/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        planet_path: $("planet-path").value,
        host_path: $("host-path").value,
      }),
    });
    $("preview-box").classList.remove("hidden");
    $("preview-box").textContent = [
      `Planets: ${data.planet_rows} rows, ${data.planet_hosts} hosts`,
      `Stellar hosts: ${data.host_rows} rows, ${data.unique_hosts} unique`,
      `Hosts missing RA/Dec/distance: ${data.hosts_missing_coords}`,
      `Sample: ${(data.sample_hosts || []).join(", ")}`,
    ].join("\n");
    toast("Files look readable.");
  } catch (err) {
    toast(err.message, true);
  } finally {
    $("btn-preview").disabled = false;
  }
});

$("btn-ingest").addEventListener("click", async () => {
  $("btn-ingest").disabled = true;
  $("btn-ingest").textContent = "Working…";
  try {
    const data = await api("/api/ingest/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        planet_path: $("planet-path").value,
        host_path: $("host-path").value,
        max_distance_ly: Number($("ingest-max-ly").value),
        min_stellar_mass: Number($("ingest-min-mass").value),
      }),
    });
    $("ingest-box").classList.remove("hidden");
    $("ingest-box").textContent = JSON.stringify(data, null, 2);
    toast(`Wrote ${data.systems_written} systems (Sol included: ${data.includes_sol}).`);
  } catch (err) {
    toast(err.message, true);
  } finally {
    $("btn-ingest").disabled = false;
    $("btn-ingest").textContent = "Generate systems table";
  }
});

function renderFactionEditor(config) {
  const box = $("faction-list");
  box.innerHTML = "";
  const groups = [...(config.species || []), ...(config.nations || [])];
  groups.forEach((item, idx) => {
    const row = document.createElement("div");
    row.className = "faction-row";
    row.innerHTML = `
      <span>${item.name}</span>
      <input data-idx="${idx}" data-field="count" type="number" min="0" value="${item.count}" title="count" />
      <input data-idx="${idx}" data-field="prefix" type="text" value="${item.prefix || ""}" title="prefix" />
    `;
    box.appendChild(row);
  });
}

function collectFactions() {
  if (!factionConfig) return null;
  const speciesCount = (factionConfig.species || []).length;
  const inputs = $("faction-list").querySelectorAll("input");
  inputs.forEach((input) => {
    const idx = Number(input.dataset.idx);
    const field = input.dataset.field;
    const target = idx < speciesCount
      ? factionConfig.species[idx]
      : factionConfig.nations[idx - speciesCount];
    if (!target) return;
    target[field] = field === "count" ? Number(input.value) : input.value;
  });
  return factionConfig;
}

function fillPathSelects(nodes) {
  const connected = nodes
    .filter((n) => n.gate_distance !== null && n.gate_distance !== undefined)
    .sort((a, b) => (a.gate_distance - b.gate_distance) || a.hostname.localeCompare(b.hostname));
  const opts = connected.map((n) => `<option value="${n.hostname}">${n.hostname} (${n.gate_distance})</option>`).join("");
  $("path-start").innerHTML = opts;
  $("path-end").innerHTML = opts;
  $("path-start").value = "Sol";
  const farthest = connected[connected.length - 1];
  if (farthest) $("path-end").value = farthest.hostname;
}

function nodeColor(node, byFaction) {
  if (node.hostname === "Sol") return "#ffffff";
  if (byFaction) {
    return FACTION_COLORS[node.group] || FACTION_COLORS[node.species] || "#8aa0b8";
  }
  return undefined;
}

function drawMap(path = []) {
  const plot = $("star-map");
  if (!networkData) {
    Plotly.purge(plot);
    return;
  }
  const { nodes, edges } = networkData;
  const byFaction = $("color-faction").checked;
  const lookup = Object.fromEntries(nodes.map((n) => [n.hostname, n]));
  const pathSet = new Set();
  for (let i = 0; i < path.length - 1; i += 1) {
    pathSet.add([path[i], path[i + 1]].sort().join("|"));
  }

  const xs = [];
  const ys = [];
  const zs = [];
  const hxs = [];
  const hys = [];
  const hzs = [];
  edges.forEach((edge) => {
    const a = lookup[edge.a];
    const b = lookup[edge.b];
    if (!a || !b) return;
    const key = [edge.a, edge.b].sort().join("|");
    const bucketX = pathSet.has(key) ? hxs : xs;
    const bucketY = pathSet.has(key) ? hys : ys;
    const bucketZ = pathSet.has(key) ? hzs : zs;
    bucketX.push(a.x, b.x, null);
    bucketY.push(a.y, b.y, null);
    bucketZ.push(a.z, b.z, null);
  });

  const sol = nodes.filter((n) => n.hostname === "Sol");
  const others = nodes.filter((n) => n.hostname !== "Sol");
  const colors = others.map((n) => (byFaction ? nodeColor(n, true) : n.ranking));
  const sizes = (list) => list.map((n) => 5 + Math.min(n.sy_pnum || 0, 8) * 1.6);
  const hover = (n) =>
    `<b>${n.sy_name}</b> (${n.hostname})<br>` +
    `Founding order: ${n.process_order ?? "—"}<br>` +
    `Spectral type: ${n.spectype || "—"}<br>` +
    `Planets: ${n.sy_pnum ?? "—"}<br>` +
    `Ranking: ${n.ranking ?? "—"}<br>` +
    `Distance: ${n.dist_ly != null ? n.dist_ly.toFixed(2) : "—"} ly<br>` +
    `Gates from Sol: ${n.gate_distance ?? "unlinked"}<br>` +
    `${n.group || n.species || ""}`;

  const traces = [
    {
      type: "scatter3d",
      mode: "lines",
      x: xs, y: ys, z: zs,
      line: { color: "rgba(180,190,200,0.35)", width: 2 },
      hoverinfo: "none",
      name: "Gates",
    },
    {
      type: "scatter3d",
      mode: "lines",
      x: hxs, y: hys, z: hzs,
      line: { color: "#e24a3b", width: 7 },
      hoverinfo: "none",
      name: "Highlighted path",
    },
    {
      type: "scatter3d",
      mode: "markers",
      x: others.map((n) => n.x),
      y: others.map((n) => n.y),
      z: others.map((n) => n.z),
      text: others.map(hover),
      hoverinfo: "text",
      marker: {
        size: sizes(others),
        color: colors,
        colorscale: "Hot",
        showscale: !byFaction,
        colorbar: byFaction ? undefined : {
          title: { text: "Desirability", side: "right", font: { size: 12 } },
          thickness: 14,
          len: 0.5,
        },
        symbol: others.map((n) => n.symbol || "circle"),
        opacity: 0.88,
      },
      name: "Systems",
    },
    {
      type: "scatter3d",
      mode: "markers",
      x: sol.map((n) => n.x),
      y: sol.map((n) => n.y),
      z: sol.map((n) => n.z),
      text: sol.map(hover),
      hoverinfo: "text",
      marker: { size: 14, color: "#ffffff", symbol: "circle", opacity: 1 },
      name: "Sol",
    },
  ];

  Plotly.react(plot, traces, {
    paper_bgcolor: "#05070c",
    plot_bgcolor: "#05070c",
    font: { color: "#d9d2c3" },
    margin: { l: 0, r: 0, t: 8, b: 0 },
    showlegend: false,
    scene: {
      aspectmode: "data",
      xaxis: { title: "X (ly)", backgroundcolor: "#05070c", gridcolor: "#2a3140", zerolinecolor: "#3a4254", color: "#c9c2b2" },
      yaxis: { title: "Y (ly)", backgroundcolor: "#05070c", gridcolor: "#2a3140", zerolinecolor: "#3a4254", color: "#c9c2b2" },
      zaxis: { title: "Z (ly)", backgroundcolor: "#05070c", gridcolor: "#2a3140", zerolinecolor: "#3a4254", color: "#c9c2b2" },
    },
  }, { responsive: true, displaylogo: false });
}

async function highlightPath() {
  if (!networkData) return;
  const start = $("path-start").value;
  const end = $("path-end").value;
  if (!start || !end) return;
  try {
    const data = await api("/api/network/path", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start, end }),
    });
    $("path-readout").textContent = data.path.length
      ? `${data.jumps} jump(s): ${data.path.join(" → ")}`
      : `No gate path between ${start} and ${end}.`;
    drawMap(data.path);
  } catch (err) {
    toast(err.message, true);
  }
}

$("btn-network").addEventListener("click", async () => {
  $("btn-network").disabled = true;
  $("btn-network").textContent = "Growing network…";
  try {
    const body = {
      max_jump_ly: Number($("max-jump").value),
      preferred_ly: Number($("pref-ly").value),
      max_neighbors: Number($("max-neighbors").value),
      max_linked_nodes: Number($("max-linked").value),
      hard_rank: Number($("hard-rank").value),
      soft_rank: Number($("soft-rank").value),
      min_stellar_mass: Number($("net-min-mass").value),
      root_hostname: $("root-host").value || "Sol",
      assign_factions: $("assign-factions").checked,
      factions: collectFactions(),
    };
    const data = await api("/api/network/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    networkData = data.payload;
    $("network-box").classList.remove("hidden");
    $("network-box").textContent = JSON.stringify({
      nodes: data.nodes,
      linked_nodes: data.linked_nodes,
      assigned: data.assigned,
      routes: data.routes,
      groups: data.groups,
    }, null, 2);
    fillPathSelects(networkData.nodes);
    await highlightPath();
    toast(`Network: ${data.linked_nodes} linked of ${data.nodes} mapped.`);
  } catch (err) {
    toast(err.message, true);
  } finally {
    $("btn-network").disabled = false;
    $("btn-network").textContent = "Generate network";
  }
});

$("path-start").addEventListener("change", highlightPath);
$("path-end").addEventListener("change", highlightPath);
$("color-faction").addEventListener("change", () => highlightPath());

async function boot() {
  try {
    await detectSources();
    factionConfig = await api("/api/factions");
    renderFactionEditor(factionConfig);
    const defaults = await api("/api/network/defaults");
    $("max-jump").value = defaults.max_jump_ly;
    $("pref-ly").value = defaults.preferred_ly;
    $("max-neighbors").value = defaults.max_neighbors;
    $("max-linked").value = defaults.max_linked_nodes;
    $("hard-rank").value = defaults.hard_rank;
    $("soft-rank").value = defaults.soft_rank;
    $("net-min-mass").value = defaults.min_stellar_mass;
    $("root-host").value = defaults.root_hostname || "Sol";
    if (defaults.ingest_max_distance_ly) {
      $("ingest-max-ly").value = defaults.ingest_max_distance_ly;
    }
    const status = await api("/api/status");
    if (status.network_ready) {
      networkData = await api("/api/network");
      fillPathSelects(networkData.nodes);
    }
  } catch (err) {
    toast(err.message, true);
  }
}

boot();
