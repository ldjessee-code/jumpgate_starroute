const FACTION_COLORS = {
  Sol: "#ffffff",
  Human: "#3dbbff",
  Kessari: "#ff8c1a",
  Methan: "#00c48c",
  Crystomorphs: "#d14cff",
  "Echryon & Echtol": "#ffe14a",
  Aboreals: "#4dff88",
  Bazzar: "#ff4d6d",
  Schettel: "#b8c0cc",
  "Turquenish Empire": "#5ad4ff",
  "Mardat Coalition": "#7a8cff",
  "Industrial Hegemony": "#ffd166",
  "League of The Faithful": "#e0aaff",
  "Other Human": "#9ad4ff",
  "Gap filler": "#c9a227",
};

const CONTRAST_PALETTE = [
  "#3dbbff",
  "#ff8c1a",
  "#00c48c",
  "#d14cff",
  "#ffe14a",
  "#ff4d6d",
  "#4dff88",
  "#7a8cff",
  "#ffd166",
  "#e0aaff",
  "#00e5d1",
  "#ff6b6b",
  "#c3f584",
  "#64d2ff",
  "#f72585",
  "#bde0fe",
];

const colorOverrides = loadColorOverrides();

function loadColorOverrides() {
  try {
    return JSON.parse(localStorage.getItem("starroute-colors") || "{}") || {};
  } catch {
    return {};
  }
}

function saveColorOverrides() {
  try {
    localStorage.setItem("starroute-colors", JSON.stringify(colorOverrides));
  } catch {
    /* ignore quota / private mode */
  }
}

function hashName(name) {
  let h = 0;
  for (let i = 0; i < name.length; i += 1) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return h;
}

function getGroupColor(name) {
  if (!name) return "#9aa7b8";
  if (colorOverrides[name]) return colorOverrides[name];
  if (FACTION_COLORS[name]) return FACTION_COLORS[name];
  return CONTRAST_PALETTE[hashName(name) % CONTRAST_PALETTE.length];
}

let factionConfig = null;
let cultureList = [];
let factionPresets = { max_cultures: 16, presets: [] };
let networkData = null;
let lastSnapshot = null;
let catalogOrigin = "Sol";

const CATALOG_DEFAULTS = {
  origin: "Sol",
  maxDistanceLy: 60,
  minSolarMass: 0.25,
};

const NETWORK_DEFAULTS = {
  maxJumpLy: 25,
  mediumPct: 40,
  longPct: 60,
  maxNeighbors: 6,
  maxLinked: 80,
  hardRank: 0.15,
  softRank: 0.25,
  minSolarMass: 0.25,
};

const $ = (id) => document.getElementById(id);

const CAMPAIGN_KEY = "starroute-campaigns-v1";
let shippedFactionConfig = null;
let mapFull = false;
let settingIdTouched = false;

function slugify(name) {
  return String(name || "setting").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "setting";
}

function readCampaigns() {
  try {
    const data = JSON.parse(localStorage.getItem(CAMPAIGN_KEY) || "null");
    if (data && Array.isArray(data.items)) return data;
  } catch {
    /* ignore */
  }
  return { current: null, items: [] };
}

function writeCampaigns(store) {
  try {
    localStorage.setItem(CAMPAIGN_KEY, JSON.stringify(store));
  } catch {
    /* quota / private mode */
  }
}

function termHtml(term) {
  if (!term) return "<p>No help is available for that item yet.</p>";
  const also = term.alsoCalled ? `<p class="also">Also called: ${term.alsoCalled}</p>` : "";
  return `<h3>${term.title}</h3>${also}<p>${term.meaning}</p><p class="impact"><strong>If you change it:</strong> ${term.impact}</p>`;
}

function showTermPopover(button) {
  const pop = $("term-pop");
  const term = GLOSSARY_BY_ID[button.dataset.term];
  pop.innerHTML = termHtml(term);
  pop.classList.remove("hidden");
  const rect = button.getBoundingClientRect();
  const width = pop.offsetWidth;
  const left = Math.min(Math.max(8, rect.left), window.innerWidth - width - 8);
  let top = rect.bottom + 8;
  if (top + pop.offsetHeight > window.innerHeight - 8) {
    top = Math.max(8, rect.top - pop.offsetHeight - 8);
  }
  pop.style.left = `${left}px`;
  pop.style.top = `${top}px`;
}

function hideTermPopover() {
  $("term-pop").classList.add("hidden");
}

function renderGlossary(filter) {
  const needle = (filter || "").trim().toLowerCase();
  const body = $("glossary-body");
  body.innerHTML = "";
  const groups = [];
  GLOSSARY.forEach((term) => {
    const blob = `${term.title} ${term.alsoCalled || ""} ${term.meaning} ${term.impact}`.toLowerCase();
    if (needle && !blob.includes(needle)) return;
    let group = groups.find((g) => g.name === term.group);
    if (!group) {
      group = { name: term.group, items: [] };
      groups.push(group);
    }
    group.items.push(term);
  });
  if (!groups.length) {
    body.innerHTML = "<p class='muted'>No matching terms.</p>";
    return;
  }
  groups.forEach((group) => {
    const section = document.createElement("section");
    section.className = "glossary-group";
    section.innerHTML = `<h3>${group.name}</h3>` + group.items.map((term) => `
      <article class="glossary-item">
        <h4>${term.title}</h4>
        ${term.alsoCalled ? `<p class="also">Also called: ${term.alsoCalled}</p>` : ""}
        <p>${term.meaning}</p>
        <p class="impact"><strong>If you change it:</strong> ${term.impact}</p>
      </article>
    `).join("");
    body.appendChild(section);
  });
}

function openGlossary() {
  renderGlossary($("glossary-search").value);
  $("glossary").classList.remove("hidden");
  $("glossary-search").focus();
}

function closeGlossary() {
  $("glossary").classList.add("hidden");
}

function toggleCardCollapse(card, btn) {
  if (!card) return;
  const collapsed = card.classList.toggle("collapsed");
  if (btn) {
    btn.textContent = collapsed ? "+" : "−";
    btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
  }
  window.setTimeout(() => {
    const plot = $("star-map");
    if (plot && window.Plotly) Plotly.Plots.resize(plot);
  }, 50);
}

function bindCardCollapse() {
  document.querySelectorAll(".collapse-btn").forEach((btn) => {
    if (btn.dataset.bound === "1") return;
    btn.dataset.bound = "1";
    const card = btn.closest("[data-card], .card");
    const head = btn.closest(".card-head");
    const onToggle = (event) => {
      if (event.target.closest("a, input, select, textarea, button.info")) return;
      event.preventDefault();
      toggleCardCollapse(card, btn);
    };
    if (head) {
      head.addEventListener("click", onToggle);
    } else {
      btn.addEventListener("click", onToggle);
    }
  });
}

bindCardCollapse();

document.addEventListener("click", (event) => {
  const info = event.target.closest(".info");
  if (info) {
    event.preventDefault();
    event.stopPropagation();
    showTermPopover(info);
    return;
  }
  if (!$("term-pop").contains(event.target)) hideTermPopover();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    hideTermPopover();
    closeGlossary();
    const modal = $("save-map-modal");
    if (modal && !modal.classList.contains("hidden")) {
      modal.classList.add("hidden");
      return;
    }
    if (mapFull) setMapFull(false);
  }
});

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
  if (name === "factions") {
    ensurePresets().then(() => fillPresetSelects());
  }
  updateBandReadout();
  if (networkData) {
    fillFocusOptions(networkData.nodes);
    drawMap();
  }
  window.setTimeout(() => {
    const plot = $("star-map");
    if (plot && window.Plotly) Plotly.Plots.resize(plot);
  }, 50);
}

function toggleDrawer() {
  window.setTimeout(() => {
    const plot = $("star-map");
    if (plot && window.Plotly) Plotly.Plots.resize(plot);
  }, 80);
}

function showSelectedSystem(node) {
  const box = $("selected-system");
  if (!box) return;
  if (!node) {
    box.className = "empty";
    box.textContent = "Click a star on the map.";
    return;
  }
  box.className = "";
  const bits = [
    `<strong>${esc(node.hostname)}</strong>`,
    node.group ? `Culture: ${esc(node.group)}` : "",
    node.spectype ? `Star: ${esc(node.spectype)}` : "",
    node.dist_ly != null ? `${Number(node.dist_ly).toFixed(1)} ly from Sol` : "",
    node.gate_distance != null ? `Gate hops from root: ${node.gate_distance}` : "",
  ].filter(Boolean);
  box.innerHTML = bits.join("<br>");
}

function renderFactionList(nodes) {
  const list = $("faction-list");
  if (!list) return;
  const names = groupsOnMap(nodes);
  list.innerHTML = names.length
    ? names.map((n) => `<li>${esc(n)}</li>`).join("")
    : "<li class='empty'>No cultures on the saved map yet.</li>";
}

function shortestPathLocal(start, end) {
  if (!networkData || !start || !end) return [];
  if (start === end) return [start];
  const graph = {};
  networkData.nodes.forEach((n) => { graph[n.hostname] = []; });
  (networkData.edges || []).forEach((e) => {
    if (!graph[e.a]) graph[e.a] = [];
    if (!graph[e.b]) graph[e.b] = [];
    graph[e.a].push(e.b);
    graph[e.b].push(e.a);
  });
  const queue = [[start, [start]]];
  const seen = new Set([start]);
  while (queue.length) {
    const [cur, path] = queue.shift();
    for (const nxt of graph[cur] || []) {
      if (seen.has(nxt)) continue;
      const nextPath = path.concat(nxt);
      if (nxt === end) return nextPath;
      seen.add(nxt);
      queue.push([nxt, nextPath]);
    }
  }
  return [];
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.disabled || btn.getAttribute("aria-disabled") === "true") return;
    showScreen(btn.dataset.screen);
  });
});

function bindHostSearch(input, list, hostPathFrom) {
  let timer = null;
  input.addEventListener("input", () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => suggestHosts(input, list, hostPathFrom), 180);
  });
  input.addEventListener("focus", () => suggestHosts(input, list, hostPathFrom));
  document.addEventListener("click", (event) => {
    if (!input.parentElement.contains(event.target)) list.hidden = true;
  });
}

async function suggestHosts(input, list, hostPathFrom) {
  const query = input.value.trim();
  const body = { query, limit: 20 };
  if (hostPathFrom && $(hostPathFrom) && $(hostPathFrom).value) {
    body.host_path = $(hostPathFrom).value;
  }
  try {
    const data = await api("/api/hosts/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    list.innerHTML = "";
    (data.matches || []).forEach((name) => {
      const li = document.createElement("li");
      li.textContent = name;
      li.addEventListener("mousedown", (event) => {
        event.preventDefault();
        input.value = name;
        list.hidden = true;
      });
      list.appendChild(li);
    });
    list.hidden = list.children.length === 0;
  } catch (err) {
    list.hidden = true;
  }
}

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
    const origin = $("origin-host").value.trim() || "Sol";
    const data = await api("/api/ingest/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        planet_path: $("planet-path").value,
        host_path: $("host-path").value,
        max_distance_ly: Number($("ingest-max-ly").value),
        min_stellar_mass: Number($("ingest-min-mass").value),
        origin_hostname: origin,
      }),
    });
    catalogOrigin = data.origin_hostname || origin;
    $("root-host").value = catalogOrigin;
    $("ingest-box").classList.remove("hidden");
    $("ingest-box").textContent = JSON.stringify(data, null, 2);
    toast(`Star list ready: ${data.systems_written} systems around ${catalogOrigin}.`);
  } catch (err) {
    toast(err.message, true);
  } finally {
    $("btn-ingest").disabled = false;
    $("btn-ingest").textContent = "Build the star list";
  }
});

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/"/g, "&quot;");
}

function inferPresetId(item) {
  if (item.preset) return item.preset;
  const presets = factionPresets.presets || [];
  const byName = presets.find((p) => p.name === item.name);
  if (byName) return byName.id;
  const op = item.filters && item.filters[0] && item.filters[0].op;
  if (op === "from_host" || op === "near_host" || op === "far_host") return op;
  return "";
}

function presetsByUse(use) {
  return (factionPresets.presets || []).filter((p) => p.use === use);
}

function inferNeedBias(item) {
  const preset = (factionPresets.presets || []).find((p) => p.id === item.preset);
  if (!item.need) item.need = (preset && preset.need) || (preset && preset.use === "need" ? preset.id : "need_any");
  if (!item.bias) {
    const op = item.filters && item.filters.find((f) => f.op === "from_host" || f.op === "near_host" || f.op === "far_host");
    item.bias = (preset && preset.bias) || (op && op.op) || (preset && preset.use === "bias" ? preset.id : "bias_none");
  }
  return item;
}

function culturesFromConfig(config) {
  const rows = [
    ...(config.species || []).map((item) => ({ ...item, kind: item.kind || "species" })),
    ...(config.nations || []).map((item) => ({ ...item, kind: item.kind || "nation" })),
  ];
  return rows.map((item) => {
    const presetId = inferPresetId(item);
    const preset = (factionPresets.presets || []).find((p) => p.id === presetId);
    return inferNeedBias({
      ...item,
      preset: presetId,
      description: item.description || (preset && preset.description) || "",
    });
  });
}

function flattenConfigFromCultures() {
  if (!factionConfig) factionConfig = {};
  syncCulturesFromDom();
  factionConfig.human_root = $("human-root").value.trim() || "Sol";
  factionConfig.human_root_group = $("human-root-group").value.trim() || "Turquenish Empire";
  factionConfig.species = cultureList.filter((c) => c.kind === "species");
  factionConfig.nations = cultureList.filter((c) => c.kind === "nation");
  const big = cultureList.filter((c) => (c.count || 0) >= 20).map((c) => c.name);
  factionConfig.multi_route_groups = [...new Set([...(factionConfig.multi_route_groups || []), ...big])];
  return factionConfig;
}

function syncCulturesFromDom() {
  $("faction-cards").querySelectorAll(".faction-card").forEach((card) => {
    const idx = Number(card.dataset.idx);
    const item = cultureList[idx];
    if (!item) return;
    const name = card.querySelector("[data-field=name]");
    const count = card.querySelector("[data-field=count]");
    const prefix = card.querySelector("[data-field=prefix]");
    const kind = card.querySelector("[data-field=kind]");
    const preset = card.querySelector("[data-field=preset]");
    if (name) item.name = name.value.trim() || item.name;
    if (count) item.count = Number(count.value);
    if (prefix) item.prefix = prefix.value.trim().toUpperCase() || item.prefix;
    if (kind) item.kind = kind.value;
    if (preset) item.preset = preset.value;
    const need = card.querySelector("[data-field=need]");
    const bias = card.querySelector("[data-field=bias]");
    if (need) item.need = need.value;
    if (bias) item.bias = bias.value;
    composePickFilters(item, card);
  });
}

function composePickFilters(item, card) {
  const need = (factionPresets.presets || []).find((p) => p.id === item.need);
  const biasId = item.bias || "bias_none";
  const host = card && card.querySelector("[data-field=place-host]");
  const filters = [];
  if (need && Array.isArray(need.filters)) filters.push(...JSON.parse(JSON.stringify(need.filters)));
  if (biasId === "from_host") {
    filters.push({
      op: "from_host",
      host: (host && host.value.trim()) || "Sol",
      bearing_deg: Number((card && card.querySelector("[data-field=bearing]")?.value) || 0),
      wedge_deg: Number((card && card.querySelector("[data-field=wedge]")?.value) || 15),
    });
  } else if (biasId === "near_host") {
    filters.push({
      op: "near_host",
      host: (host && host.value.trim()) || "Sol",
      max_ly: Number((card && card.querySelector("[data-field=near-ly]")?.value) || 80),
    });
  } else if (biasId === "far_host") {
    filters.push({
      op: "far_host",
      host: (host && host.value.trim()) || "Sol",
      min_ly: Number((card && card.querySelector("[data-field=far-ly]")?.value) || 400),
    });
  } else {
    const bias = (factionPresets.presets || []).find((p) => p.id === biasId);
    if (bias && Array.isArray(bias.filters)) filters.push(...JSON.parse(JSON.stringify(bias.filters)));
  }
  item.filters = filters;
}

function placeExtraHtml(item) {
  const loc = (item.filters || []).find((f) => f.op === "from_host" || f.op === "near_host" || f.op === "far_host") || {};
  const host = loc.host || "Sol";
  const preset = item.bias || item.preset || loc.op;
  if (preset === "from_host") {
    const bearing = Number(loc.bearing_deg || 0);
    const wedge = Number(loc.wedge_deg || 15);
    const bearings = Array.from({ length: 24 }, (_, i) => i * 15)
      .map((d) => `<option value="${d}" ${bearing === d ? "selected" : ""}>${d}°–${d + 15}°</option>`)
      .join("");
    const wedges = [15, 30, 45, 60, 90]
      .map((w) => `<option value="${w}" ${wedge === w ? "selected" : ""}>${w}° wide</option>`)
      .join("");
    return `<div class="place-extra">
      <label>Home star<input data-field="place-host" type="text" value="${esc(host)}" autocomplete="off" /></label>
      <label>Slice<select data-field="bearing">${bearings}</select></label>
      <label>Width<select data-field="wedge">${wedges}</select></label>
    </div>`;
  }
  if (preset === "near_host") {
    return `<div class="place-extra">
      <label>Home star<input data-field="place-host" type="text" value="${esc(host)}" autocomplete="off" /></label>
      <label>Within (ly)<input data-field="near-ly" type="number" min="1" value="${loc.max_ly || 80}" /></label>
    </div>`;
  }
  if (preset === "far_host") {
    return `<div class="place-extra">
      <label>Home star<input data-field="place-host" type="text" value="${esc(host)}" autocomplete="off" /></label>
      <label>Farther than (ly)<input data-field="far-ly" type="number" min="1" value="${loc.min_ly || 400}" /></label>
    </div>`;
  }
  return "";
}

function applyPresetToCulture(item, presetId) {
  const preset = (factionPresets.presets || []).find((p) => p.id === presetId);
  if (!preset) return item;
  item.preset = preset.id;
  item.description = preset.description;
  item.need = preset.need || (preset.use === "need" ? preset.id : item.need || "need_any");
  item.bias = preset.bias || (preset.use === "bias" ? preset.id : item.bias || "bias_none");
  item.sort = JSON.parse(JSON.stringify(preset.sort || {}));
  composePickFilters(item, null);
  return item;
}

async function ensurePresets() {
  if (factionPresets.presets && factionPresets.presets.length) return;
  try {
    factionPresets = await api("/api/factions/presets");
  } catch {
    try {
      const script = document.querySelector('script[src*="app.js"]');
      const url = script
        ? script.src.replace(/js\/app\.js.*$/, "engine/config/faction_presets.json")
        : "/static/engine/config/faction_presets.json";
      factionPresets = await (await fetch(url)).json();
    } catch {
      factionPresets = { max_cultures: 16, presets: [] };
    }
  }
}

function fillPresetSelects() {
  const add = $("preset-pick");
  if (!add) return;
  const presets = (factionPresets.presets || []).filter((p) => !p.use || p.use === "template");
  const parts = [];
  if (presets.length) {
    parts.push(
      `<optgroup label="Named cultures (templates)">` +
        presets.map((p) => `<option value="${p.id}">${esc(p.label || p.name)}</option>`).join("") +
      `</optgroup>`
    );
  }
  if (cultureList.length) {
    parts.push(
      `<optgroup label="Copy one already on this tab">` +
        cultureList.map((c, i) => `<option value="copy:${i}">Copy of ${esc(c.name)}</option>`).join("") +
      `</optgroup>`
    );
  }
  add.innerHTML = parts.join("") || `<option value="">No templates loaded — hard-refresh the page</option>`;
}

function pickOptions(use, selected) {
  const presets = presetsByUse(use);
  const known = presets.some((p) => p.id === selected);
  const fallback = use === "need" ? "need_any" : "bias_none";
  const current = known ? selected : fallback;
  return presets
    .map((p) => `<option value="${p.id}" ${p.id === current ? "selected" : ""}>${esc(p.label || p.name)}</option>`)
    .join("");
}

function updateCultureCount() {
  const max = factionPresets.max_cultures || 16;
  const n = cultureList.length;
  $("culture-count").textContent = `${n} / ${max} cultures`;
  $("btn-add-culture").disabled = n >= max;
}

function renderFactionEditor(config) {
  if (config) {
    factionConfig = config;
    cultureList = culturesFromConfig(config);
  }
  $("human-root").value = (factionConfig && factionConfig.human_root) || "Sol";
  $("human-root-group").value = (factionConfig && factionConfig.human_root_group) || "Human";
  fillPresetSelects();
  const box = $("faction-cards");
  box.innerHTML = "";
  cultureList.forEach((item, idx) => {
    const card = document.createElement("article");
    card.className = "faction-card";
    card.dataset.idx = String(idx);
    const lore = item.description || "Rename this culture and pick how they choose stars.";
    card.innerHTML = `
      <header>
        <input class="name-input" data-field="name" type="text" value="${esc(item.name || "")}" aria-label="Culture name" />
        <button type="button" class="btn-remove" data-remove="${idx}" aria-label="Remove culture">Remove culture</button>
      </header>
      <p class="lore">${esc(lore)}</p>
      <label>
        <span class="label-row">Habitat need <button type="button" class="info" data-term="pickNeed" aria-label="About habitat need">?</button></span>
        <select data-field="need">${pickOptions("need", item.need)}</select>
      </label>
      <label>
        <span class="label-row">Start / direction bias <button type="button" class="info" data-term="pickBias" aria-label="About start bias">?</button></span>
        <select data-field="bias">${pickOptions("bias", item.bias)}</select>
      </label>
      ${placeExtraHtml(item)}
      <div class="faction-fields">
        <label>
          <span class="label-row">How many systems <button type="button" class="info" data-term="factionCount" aria-label="About culture size">?</button></span>
          <input data-field="count" type="number" min="0" value="${item.count || 0}" />
        </label>
        <label>Prefix
          <input class="prefix-input" data-field="prefix" type="text" maxlength="4" value="${item.prefix || ""}" />
        </label>
      </div>
      <label>
        <span class="label-row">Kind</span>
        <select data-field="kind">
          <option value="species" ${item.kind === "species" ? "selected" : ""}>Species (placed first)</option>
          <option value="nation" ${item.kind === "nation" ? "selected" : ""}>Human nation (leftovers)</option>
        </select>
      </label>
      <p class="match-line muted" data-match="${idx}"></p>
    `;
    box.appendChild(card);
  });
  updateCultureCount();
}

function collectFactions() {
  return flattenConfigFromCultures();
}

$("btn-add-culture").addEventListener("click", () => {
  const max = factionPresets.max_cultures || 16;
  if (cultureList.length >= max) {
    toast(`You can have at most ${max} cultures for now.`, true);
    return;
  }
  syncCulturesFromDom();
  const presetId = $("preset-pick").value;
  if (String(presetId).startsWith("copy:")) {
    const src = cultureList[Number(presetId.split(":")[1])];
    if (!src) return;
    const clone = JSON.parse(JSON.stringify(src));
    clone.name = `${src.name} copy`;
    cultureList.push(clone);
    renderFactionEditor();
    toast(`Copied ${src.name}. Rename them, then save.`);
    return;
  }
  const preset = (factionPresets.presets || []).find((p) => p.id === presetId)
    || { name: "New people", kind: "species", count: 10, prefix: "NW", description: "", filters: [], sort: {} };
  const used = new Set(cultureList.map((c) => c.name));
  let name = preset.name;
  let n = 2;
  while (used.has(name)) {
    name = `${preset.name} ${n}`;
    n += 1;
  }
  const item = applyPresetToCulture({
    name,
    kind: preset.kind || "species",
    count: preset.count || 10,
    prefix: preset.prefix || "NW",
    description: preset.description || "",
    filters: [],
    sort: {},
  }, preset.id || "");
  item.name = name;
  cultureList.push(item);
  renderFactionEditor();
  toast(`Added ${name}. Rename them if you like, then save.`);
});

$("faction-cards").addEventListener("click", (event) => {
  const btn = event.target.closest("[data-remove]");
  if (!btn) return;
  syncCulturesFromDom();
  const idx = Number(btn.dataset.remove);
  const gone = cultureList[idx];
  cultureList.splice(idx, 1);
  renderFactionEditor();
  toast(`Removed ${gone ? gone.name : "culture"}.`);
});

$("faction-cards").addEventListener("change", (event) => {
  const select = event.target.closest("select[data-field=need], select[data-field=bias]");
  if (!select || !select.value) return;
  const card = event.target.closest(".faction-card");
  if (!card) return;
  syncCulturesFromDom();
  const idx = Number(card.dataset.idx);
  const item = cultureList[idx];
  if (!item) return;
  composePickFilters(item, card);
  renderFactionEditor();
});

$("btn-faction-save").addEventListener("click", async () => {
  try {
    const factions = collectFactions();
    await api("/api/factions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ factions }),
    });
    persistCampaign();
    toast("Factions saved to this campaign. You can generate the map later.");
  } catch (err) {
    persistCampaign();
    toast("Factions saved in this browser campaign (no map needed). Server: " + err.message, true);
  }
});

$("btn-faction-preview").addEventListener("click", async () => {
  try {
    const factions = collectFactions();
    const data = await api("/api/factions/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ factions }),
    });
    $("faction-box").classList.remove("hidden");
    $("faction-box").textContent = JSON.stringify(data, null, 2);
    (data.groups || []).forEach((group, idx) => {
      const line = document.querySelector(`[data-match="${idx}"]`);
      if (line) {
        line.textContent = `${group.matching} stars in the list fit this taste; would take ${group.claimed} of the ${group.count} asked for.`;
      }
    });
    toast(`Previewed against ${data.catalog_systems} catalog systems.`);
  } catch (err) {
    toast(err.message, true);
  }
});

function fillPathSelects(nodes) {
  const connected = nodes
    .filter((n) => n.gate_distance !== null && n.gate_distance !== undefined)
    .sort((a, b) => (a.gate_distance - b.gate_distance) || a.hostname.localeCompare(b.hostname));
  const opts = connected.map((n) => `<option value="${n.hostname}">${n.hostname} (${n.gate_distance})</option>`).join("");
  $("path-start").innerHTML = opts;
  $("path-end").innerHTML = opts;
  const root = $("root-host").value || catalogOrigin || "Sol";
  $("path-start").value = connected.some((n) => n.hostname === root) ? root : (connected[0] && connected[0].hostname);
  const farthest = connected[connected.length - 1];
  if (farthest) $("path-end").value = farthest.hostname;
}

function fillFocusOptions(nodes) {
  const current = $("focus-faction").value || "all";
  const groups = [...new Set(nodes.map((n) => n.group).filter(Boolean))].sort();
  $("focus-faction").innerHTML = `<option value="all">Everyone (full color)</option>`
    + groups.map((g) => `<option value="${g}">${g}</option>`).join("");
  $("focus-faction").value = [...$("focus-faction").options].some((o) => o.value === current) ? current : "all";
}

function hexToRgba(hex, alpha) {
  const raw = hex.replace("#", "");
  const n = parseInt(raw, 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}

function nodeColor(node, byFaction, focus) {
  const base = getGroupColor(node.group || node.species);
  if (node.hostname === catalogOrigin || node.hostname === "Sol") {
    if (focus === "all" || node.group === focus) return "#ffffff";
    return "rgba(255,255,255,0.28)";
  }
  if (!byFaction) return undefined;
  if (focus === "all" || node.group === focus) return base;
  return hexToRgba(base, 0.22);
}

function groupsOnMap(nodes) {
  return [...new Set((nodes || []).map((n) => n.group).filter(Boolean))].sort();
}

function renderLegend(nodes) {
  const box = $("map-legend");
  if (!box) return;
  const byFaction = $("color-faction") && $("color-faction").checked;
  const groups = groupsOnMap(nodes);
  const rows = [];
  rows.push(`<div class="legend-row"><span class="legend-swatch" style="background:#fff"></span><span>Sol / map center</span></div>`);
  if (byFaction) {
    groups.forEach((g) => {
      const color = getGroupColor(g);
      rows.push(`<label class="legend-row">
        <input type="color" class="legend-pick" data-group="${esc(g)}" value="${color}" title="Change ${esc(g)} color" />
        <span>${esc(g)}</span>
      </label>`);
    });
  } else {
    rows.push(`<div class="legend-row"><span class="legend-swatch heat"></span><span>Color = world score</span></div>`);
  }
  rows.push(`<div class="legend-row"><span class="legend-line"></span><span>Jump route</span></div>`);
  rows.push(`<div class="legend-row"><span class="legend-line path"></span><span>Highlighted path</span></div>`);
  box.innerHTML = `<p class="legend-title">Legend</p><div class="legend-rows">${rows.join("")}</div>`;
}

function drawMap(path = []) {
  const plot = $("star-map");
  if (!networkData) {
    Plotly.purge(plot);
    return;
  }
  const { nodes, edges } = networkData;
  const byFaction = $("color-faction").checked;
  const focus = $("focus-faction").value || "all";
  const lookup = Object.fromEntries(nodes.map((n) => [n.hostname, n]));
  const pathSet = new Set();
  for (let i = 0; i < path.length - 1; i += 1) {
    pathSet.add([path[i], path[i + 1]].sort().join("|"));
  }

  const dimXs = [];
  const dimYs = [];
  const dimZs = [];
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
    if (pathSet.has(key)) {
      hxs.push(a.x, b.x, null);
      hys.push(a.y, b.y, null);
      hzs.push(a.z, b.z, null);
      return;
    }
    const focused = focus === "all" || a.group === focus || b.group === focus;
    const bucketX = focused ? xs : dimXs;
    const bucketY = focused ? ys : dimYs;
    const bucketZ = focused ? zs : dimZs;
    bucketX.push(a.x, b.x, null);
    bucketY.push(a.y, b.y, null);
    bucketZ.push(a.z, b.z, null);
  });

  const originName = catalogOrigin || "Sol";
  const originNodes = nodes.filter((n) => n.hostname === originName);
  const others = nodes.filter((n) => n.hostname !== originName);
  const colors = others.map((n) => (byFaction ? nodeColor(n, true, focus) : n.ranking));
  const sizes = (list) => list.map((n) => {
    const base = 5 + Math.min(n.sy_pnum || 0, 8) * 1.6;
    if (focus === "all" || n.group === focus) return base;
    return Math.max(3, base * 0.7);
  });
  const hover = (n) =>
    `<b>${n.sy_name}</b> (${n.hostname})<br>` +
    `Founding order: ${n.process_order ?? "—"}<br>` +
    `Spectral type: ${n.spectype || "—"}<br>` +
    `Planets: ${n.sy_pnum ?? "—"}<br>` +
    `Ranking: ${n.ranking ?? "—"}<br>` +
    `Distance from Sol: ${n.dist_ly != null ? n.dist_ly.toFixed(2) : "—"} ly<br>` +
    `Distance from origin: ${n.dist_origin_ly != null ? n.dist_origin_ly.toFixed(2) : "—"} ly<br>` +
    `Gates from root: ${n.gate_distance ?? "unlinked"}<br>` +
    `${n.group || n.species || ""}`;

  const traces = [
    {
      type: "scatter3d",
      mode: "lines",
      x: dimXs, y: dimYs, z: dimZs,
      line: { color: "rgba(160,150,140,0.12)", width: 1 },
      hoverinfo: "none",
      name: "Other gates",
    },
    {
      type: "scatter3d",
      mode: "lines",
      x: xs, y: ys, z: zs,
      line: { color: "rgba(180,190,200,0.45)", width: 2 },
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
        opacity: 0.92,
      },
      name: "Systems",
    },
    {
      type: "scatter3d",
      mode: "markers",
      x: originNodes.map((n) => n.x),
      y: originNodes.map((n) => n.y),
      z: originNodes.map((n) => n.z),
      text: originNodes.map(hover),
      hoverinfo: "text",
      marker: {
        size: 14,
        color: originNodes.map((n) => nodeColor(n, true, focus)),
        symbol: "circle",
        opacity: 1,
      },
      name: originName,
    },
  ];

  renderLegend(nodes);
  const afterPlot = () => {
    plot.removeAllListeners && plot.removeAllListeners("plotly_click");
    plot.on("plotly_click", (ev) => {
      const pt = ev.points && ev.points[0];
      const raw = String((pt && pt.text) || "");
      const named = raw.match(/\(([^)]+)\)/);
      const host = named ? named[1] : "";
      const node = nodes.find((n) => n.hostname === host);
      if (node) showSelectedSystem(node);
    });
  };
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
  }, { responsive: true, displaylogo: false }).then(afterPlot);
}

function setPathMessage(text) {
  ["path-readout", "map-directions"].forEach((id) => {
    const el = $(id);
    if (el) el.textContent = text;
  });
}

function nodeDistanceLy(a, b) {
  if (!a || !b) return null;
  if ([a.x, a.y, a.z, b.x, b.y, b.z].every((n) => typeof n === "number")) {
    return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
  }
  return null;
}

function explainNoRoute(start, end) {
  const nodes = (networkData && networkData.nodes) || [];
  const a = nodes.find((n) => n.hostname === start);
  const b = nodes.find((n) => n.hostname === end);
  const maxJump = Number($("max-jump").value) || 25;
  const linkedCap = Number($("max-linked").value) || 80;
  const neighbors = Number($("max-neighbors").value) || 6;
  const reality = Number($("reality-stop").value || 0);
  const root = ($("root-host") && $("root-host").value) || "Sol";
  if (!a || !b) return `No jump path: ${start} or ${end} is not on this map.`;
  const aOn = a.gate_distance !== null && a.gate_distance !== undefined;
  const bOn = b.gate_distance !== null && b.gate_distance !== undefined;
  const dist = nodeDistanceLy(a, b);
  const distTxt = dist != null ? `${dist.toFixed(1)} ly apart` : "an unknown distance apart";
  if (!aOn || !bOn) {
    const who = !aOn && !bOn ? "Neither star is" : `${!aOn ? start : end} is`;
    return `${who} on the jump grid (${distTxt}). Isolated dots are normal: the grid grows from ${root} and stops after ${linkedCap} linked stars. Raise “how many stars get jump routes”, lower picky-ness, or raise longest jump (${maxJump} ly), then generate again. Gap-fill (reality 1) will not help — it only adds moons/bodies, not roads.`;
  }
  if (dist != null && dist > maxJump) {
    let extra = `Raise longest single jump above ${Math.ceil(dist)} ly and generate again.`;
    if (reality < 3) {
      extra += " Reality 3 (setting-scale) can add extra invented roads among catalog stars; reality 4 can add missing stars. Gap-fill does not create jump routes.";
    } else {
      extra += " This reality stop already allows invented roads or hosts; generate again or add an extra edge later.";
    }
    return `No chain of jumps from ${start} to ${end}. They are ${distTxt}; longest allowed hop is ${maxJump} ly. ${extra}`;
  }
  return `No chain of jumps from ${start} to ${end} even though they are ${distTxt} (within the ${maxJump} ly hop). The grid is grown from ${root} with at most ${neighbors} roads per star. Raise neighbors, linked-star cap, or longest jump, then generate again.`;
}

async function highlightPath() {
  if (!networkData) return;
  const start = $("path-start").value;
  const end = $("path-end").value;
  if (!start || !end) {
    setPathMessage("Pick From and To to highlight a jump path.");
    drawMap();
    return;
  }
  const path = shortestPathLocal(start, end);
  if (path.length) {
    setPathMessage(`${Math.max(path.length - 1, 0)} jump(s): ${path.join(" → ")}`);
  } else {
    setPathMessage(explainNoRoute(start, end));
  }
  drawMap(path);
}

function currentNetworkParams() {
  return {
    max_jump_ly: Number($("max-jump").value),
    medium_start_pct: Number($("medium-pct").value),
    long_start_pct: Number($("long-pct").value),
    max_neighbors: Number($("max-neighbors").value),
    max_linked_nodes: Number($("max-linked").value),
    hard_rank: Number($("hard-rank").value),
    soft_rank: Number($("soft-rank").value),
    min_stellar_mass: Number($("net-min-mass").value),
    root_hostname: $("root-host").value || catalogOrigin || "Sol",
  };
}

function snapshotEnvelope(data) {
  const payload = (data && data.payload && data.payload.nodes) ? data.payload : data;
  return {
    starroute: (data && data.starroute) || "2.0",
    kind: "network_snapshot",
    title: (data && data.title) || "Starroute map",
    origin: (data && data.origin) || { origin_hostname: catalogOrigin || "Sol" },
    params: (data && data.params) || currentNetworkParams(),
    factions: data && data.factions,
    setting_id: ($("setting-id") && $("setting-id").value) || undefined,
    reality: Number($("reality-stop") && $("reality-stop").value) || 0,
    campaign: ($("campaign-name") && $("campaign-name").value) || undefined,
    payload,
  };
}

function applyNetworkResult(data) {
  const payload = data && data.payload && data.payload.nodes ? data.payload : data;
  if (!payload || !payload.nodes) return;
  lastSnapshot = snapshotEnvelope(data && data.payload && data.payload.nodes ? data : { payload });
  networkData = payload;
  fillPathSelects(networkData.nodes);
  fillFocusOptions(networkData.nodes);
  renderFactionList(networkData.nodes);
  highlightPath();
}

$("btn-network").addEventListener("click", async () => {
  $("btn-network").disabled = true;
  $("btn-network").textContent = "Drawing routes…";
  try {
    await api("/api/factions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ factions: collectFactions() }),
    });
    const body = {
      max_jump_ly: Number($("max-jump").value),
      medium_start_pct: Number($("medium-pct").value),
      long_start_pct: Number($("long-pct").value),
      preferred_ly: Number($("max-jump").value) * (Number($("medium-pct").value) / 100),
      max_neighbors: Number($("max-neighbors").value),
      max_linked_nodes: Number($("max-linked").value),
      hard_rank: Number($("hard-rank").value),
      soft_rank: Number($("soft-rank").value),
      min_stellar_mass: Number($("net-min-mass").value),
      root_hostname: $("root-host").value || catalogOrigin || "Sol",
      assign_factions: $("assign-factions").checked,
      factions: collectFactions(),
    };
    const data = await api("/api/network/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    $("network-box").classList.remove("hidden");
    $("network-box").textContent = JSON.stringify({
      nodes: data.nodes,
      linked_nodes: data.linked_nodes,
      assigned: data.assigned,
      routes: data.routes,
      groups: data.groups,
    }, null, 2);
    applyNetworkResult(data);
    toast(`Routes drawn: ${data.linked_nodes} stars on the grid, ${data.nodes} shown.`);
  } catch (err) {
    toast(err.message, true);
  } finally {
    $("btn-network").disabled = false;
    $("btn-network").textContent = "Draw the routes";
  }
});

function collectCampaignFields() {
  return {
    name: ($("campaign-name") && $("campaign-name").value.trim()) || "Untitled",
    settingId: ($("setting-id") && $("setting-id").value.trim()) || slugify($("campaign-name") && $("campaign-name").value),
    reality: Number($("reality-stop") && $("reality-stop").value) || 0,
    chronosCampaignId: ($("chronos-campaign-id") && $("chronos-campaign-id").value.trim()) || "",
    worldstackId: ($("worldstack-id") && $("worldstack-id").value.trim()) || "",
    catalog: {
      origin: $("origin-host").value,
      maxDistanceLy: Number($("ingest-max-ly").value),
      minSolarMass: Number($("ingest-min-mass").value),
    },
    network: currentNetworkParams(),
    assignFactions: $("assign-factions").checked,
    factions: collectFactions(),
    mapTitle: (lastSnapshot && lastSnapshot.title) || "",
    snapshot: lastSnapshot,
    updatedAt: new Date().toISOString(),
  };
}

function fillCampaignSelects() {
  const store = readCampaigns();
  const named = store.items.map((c) => `<option value="${esc(c.id)}">${esc(c.name)}</option>`);
  const pick = $("campaign-pick");
  const savePick = $("save-map-campaign");
  if (pick) {
    pick.innerHTML = `<option value="">New campaign…</option>` + named.join("");
    pick.value = store.current || "";
  }
  if (savePick) {
    savePick.innerHTML = named.join("") || `<option value="">(none yet — type a new name)</option>`;
    if (store.current) savePick.value = store.current;
  }
}

function updateCampaignSummary() {
  const box = $("setting-summary");
  if (!box) return;
  const name = ($("campaign-name") && $("campaign-name").value) || "Untitled";
  const sid = ($("setting-id") && $("setting-id").value) || "—";
  const sel = $("reality-stop");
  const reality = sel && sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text : "0 Catalog";
  const mapName = (lastSnapshot && lastSnapshot.title) || "preview map";
  box.innerHTML = `Campaign <strong>${esc(name)}</strong> · setting <code>${esc(sid)}</code> · ${esc(reality)}. Current map: ${esc(mapName)}.`;
  const status = $("campaign-status");
  if (status && !status.dataset.locked) {
    const n = readCampaigns().items.length;
    status.textContent = n ? `${n} campaign(s) stored in this browser.` : "Not saved in this browser yet.";
  }
}

function updateRealityHelp() {
  const stop = String(($("reality-stop") && $("reality-stop").value) || "0");
  const term = (typeof GLOSSARY_BY_ID !== "undefined" && (GLOSSARY_BY_ID[`reality${stop}`] || GLOSSARY_BY_ID.realitySlider)) || null;
  const line = $("reality-help");
  if (line && term) line.textContent = term.meaning;
  const panel = $("gapfill-panel");
  if (panel) panel.classList.toggle("hidden", Number(stop) < 1);
  updateCampaignSummary();
}

function distLy(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

function spanningTreeMaxEdge(pts) {
  const n = pts.length;
  if (n < 2) return 0;
  const parent = pts.map((_, i) => i);
  const find = (i) => {
    while (parent[i] !== i) {
      parent[i] = parent[parent[i]];
      i = parent[i];
    }
    return i;
  };
  const pairs = [];
  for (let i = 0; i < n; i += 1) {
    for (let j = i + 1; j < n; j += 1) {
      pairs.push([distLy(pts[i], pts[j]), i, j]);
    }
  }
  pairs.sort((a, b) => a[0] - b[0]);
  let used = 0;
  let maxD = 0;
  for (let k = 0; k < pairs.length; k += 1) {
    const [d, i, j] = pairs[k];
    const a = find(i);
    const b = find(j);
    if (a === b) continue;
    parent[a] = b;
    used += 1;
    if (d > maxD) maxD = d;
    if (used === n - 1) break;
  }
  return maxD;
}

function scanJumpGaps() {
  const btn = $("btn-gap-scan");
  const box = $("gap-scan-box");
  const status = $("gapfill-status");
  const maxJump = Number($("max-jump") && $("max-jump").value) || 25;
  const nodes = ((networkData && networkData.nodes) || []).filter(
    (n) => typeof n.x === "number" && typeof n.y === "number" && typeof n.z === "number"
  );
  if (nodes.length < 2) {
    toast("Load or generate a map first, then scan.", true);
    return;
  }
  const previous = btn ? btn.textContent : "";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Scanning…";
  }
  if (status) status.textContent = `Checking ${nodes.length} stars against a ${maxJump} ly hop…`;
  window.setTimeout(() => {
    try {
      const nearest = nodes.map((node, i) => {
        let best = Infinity;
        let who = "";
        for (let j = 0; j < nodes.length; j += 1) {
          if (i === j) continue;
          const d = distLy(node, nodes[j]);
          if (d < best) {
            best = d;
            who = nodes[j].hostname;
          }
        }
        return {
          host: node.hostname,
          neighbor: who,
          ly: best,
          onGrid: node.gate_distance !== null && node.gate_distance !== undefined,
        };
      });
      const tooFar = nearest.filter((r) => r.ly > maxJump + 1e-9).sort((a, b) => a.ly - b.ly);
      const justOver = tooFar.filter((r) => r.ly <= maxJump * 1.5);
      const offGrid = nearest.filter((r) => !r.onGrid);
      const inRangeOffGrid = offGrid.filter((r) => r.ly <= maxJump + 1e-9);
      const treeHop = spanningTreeMaxEdge(nodes);
      const worst = tooFar.length ? tooFar[tooFar.length - 1].ly : 0;
      const closest = tooFar.length ? tooFar[0].ly : 0;
      const raiseTo = tooFar.length ? Math.ceil((worst + 0.05) * 10) / 10 : maxJump;
      const rows = (tooFar.length ? tooFar : [...nearest].sort((a, b) => b.ly - a.ly)).map((r) => {
        const over = r.ly - maxJump;
        const vs = over > 0
          ? `+${over.toFixed(1)} ly`
          : `${over.toFixed(1)} ly`;
        return `<tr>
          <td>${esc(r.host)}</td>
          <td>${esc(r.neighbor)}</td>
          <td>${r.ly.toFixed(1)} ly</td>
          <td>${vs}</td>
        </tr>`;
      }).join("");
      const many = (tooFar.length ? tooFar : nearest).length > 20;
      const html = `
        <dl class="gap-stats">
          <div><dt>Stars on this map</dt><dd>${nodes.length}</dd></div>
          <div><dt>Cannot hop to anyone at ${maxJump} ly</dt><dd>${tooFar.length}</dd></div>
          <div><dt>Close misses (≤ 1.5× hop)</dt><dd>${justOver.length}</dd></div>
          <div><dt>In range but off the grid</dt><dd>${inRangeOffGrid.length}</dd></div>
          <div><dt>Hop so every star has a neighbor</dt><dd>${raiseTo} ly</dd></div>
          <div><dt>Hop for a spanning tree</dt><dd>${treeHop.toFixed(1)} ly</dd></div>
        </dl>
        <p>${tooFar.length
          ? "Closest holes first:"
          : "No nearest-neighbor holes at this hop. Widest nearest-neighbor pairs:"}</p>
        <div class="gap-table-wrap${many ? " gap-table-scroll" : ""}">
          <table class="gap-table">
            <thead><tr><th>Star</th><th>Nearest</th><th>Distance</th><th>Vs hop</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
        ${tooFar.length ? `<div class="row-actions">
          <button id="btn-place-waypoints" class="btn primary" type="button">Bridge with existing stars or 0.25 M☉ midpoints</button>
          <button id="btn-fill-jump-gaps" class="btn" type="button">Or raise hop to ${raiseTo} ly and generate</button>
        </div>
        <p class="field-help">Looks for a real catalog star within ${maxJump} ly of both ends (prefers off-grid, few planets, low score). If none, places a ${Number($("net-min-mass") && $("net-min-mass").value) || 0.25} M☉ star on the line. This NASA list is planet-hosts only — if the nearest neighbor is already over the hop, there is no real first hop in the list.</p>` : `<p class="field-help">In-range but off-grid is linked-star cap or picky-ness, not distance.</p>`}
      `;
      if (box) {
        box.classList.remove("hidden");
        box.innerHTML = html;
        const fill = $("btn-fill-jump-gaps");
        if (fill) {
          fill.dataset.hop = String(raiseTo);
          fill.addEventListener("click", () => fillJumpGaps(raiseTo));
        }
        const place = $("btn-place-waypoints");
        if (place) place.addEventListener("click", () => placeJumpGapFillers(maxJump, tooFar));
        box.scrollIntoView({ block: "nearest" });
      }
      if (status) {
        status.textContent = tooFar.length
          ? `${tooFar.length} jump gap(s) larger than ${maxJump} ly. See the list below.`
          : `No nearest-neighbor jump gaps at ${maxJump} ly.`;
      }
      toast(tooFar.length
        ? `${tooFar.length} jump gap(s) larger than ${maxJump} ly.`
        : `No nearest-neighbor jump gaps at ${maxJump} ly.`);
    } catch (err) {
      toast(err.message || String(err), true);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = previous || "Scan jump gaps";
      }
    }
  }, 50);
}

function applyCampaign(item) {
  if (!item) return;
  if ($("campaign-name")) $("campaign-name").value = item.name || "";
  if ($("setting-id")) $("setting-id").value = item.settingId || item.id || "";
  if ($("reality-stop")) $("reality-stop").value = String(item.reality ?? 0);
  if ($("chronos-campaign-id")) $("chronos-campaign-id").value = item.chronosCampaignId || "";
  if ($("worldstack-id")) $("worldstack-id").value = item.worldstackId || "";
  if (item.catalog) {
    $("origin-host").value = item.catalog.origin || "Sol";
    $("ingest-max-ly").value = String(item.catalog.maxDistanceLy ?? CATALOG_DEFAULTS.maxDistanceLy);
    $("ingest-min-mass").value = String(item.catalog.minSolarMass ?? CATALOG_DEFAULTS.minSolarMass);
    catalogOrigin = item.catalog.origin || "Sol";
    if ($("root-host")) $("root-host").value = catalogOrigin;
  }
  if (item.network) {
    const n = item.network;
    if (n.max_jump_ly != null) $("max-jump").value = String(n.max_jump_ly);
    if (n.medium_start_pct != null) $("medium-pct").value = String(n.medium_start_pct);
    if (n.long_start_pct != null) $("long-pct").value = String(n.long_start_pct);
    if (n.max_neighbors != null) $("max-neighbors").value = String(n.max_neighbors);
    if (n.max_linked_nodes != null) $("max-linked").value = String(n.max_linked_nodes);
    if (n.hard_rank != null) $("hard-rank").value = String(n.hard_rank);
    if (n.soft_rank != null) $("soft-rank").value = String(n.soft_rank);
    if (n.min_stellar_mass != null) $("net-min-mass").value = String(n.min_stellar_mass);
    if (n.root_hostname) $("root-host").value = n.root_hostname;
    updateBandReadout();
  }
  if (item.assignFactions != null) $("assign-factions").checked = !!item.assignFactions;
  if (item.factions) {
    factionConfig = item.factions;
    cultureList = culturesFromConfig(item.factions);
    renderFactionEditor(item.factions);
  }
  if (item.snapshot && item.snapshot.payload && item.snapshot.payload.nodes) {
    applyNetworkResult(item.snapshot);
  }
  updateRealityHelp();
  fillCampaignSelects();
}

function persistCampaign(partial) {
  const store = readCampaigns();
  const fields = Object.assign(collectCampaignFields(), partial || {});
  const id = store.current || fields.settingId || slugify(fields.name);
  let item = store.items.find((c) => c.id === id);
  if (!item) {
    item = { id };
    store.items.push(item);
  }
  Object.assign(item, fields, { id, settingId: fields.settingId || id });
  store.current = id;
  writeCampaigns(store);
  fillCampaignSelects();
  updateCampaignSummary();
  return item;
}

function downloadSnapshot(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "starroute-map.json";
  a.click();
  URL.revokeObjectURL(url);
}

function setMapFull(on) {
  mapFull = !!on;
  document.body.classList.toggle("map-full", mapFull);
  const btn = $("btn-full-map");
  if (btn) btn.textContent = mapFull ? "Exit full view" : "Full view";
  window.setTimeout(() => {
    const plot = $("star-map");
    if (plot && window.Plotly) Plotly.Plots.resize(plot);
  }, 80);
}

$("btn-snapshot").addEventListener("click", () => {
  if (!lastSnapshot || !lastSnapshot.payload || !lastSnapshot.payload.nodes) {
    toast("No map to save yet. Generate or open a map first.", true);
    return;
  }
  fillCampaignSelects();
  $("save-map-name").value = lastSnapshot.title || $("campaign-name").value || "Starroute map";
  $("save-map-new-campaign").value = "";
  $("save-map-modal").classList.remove("hidden");
});

$("snapshot-file").addEventListener("change", async () => {
  const file = $("snapshot-file").files[0];
  if (!file) return;
  try {
    const text = await file.text();
    const data = JSON.parse(text);
    if (!data.payload || !data.payload.nodes) {
      throw new Error("That file is not a Starroute map snapshot.");
    }
    if (data.origin && data.origin.origin_hostname) {
      catalogOrigin = data.origin.origin_hostname;
      $("origin-host").value = catalogOrigin;
      $("root-host").value = catalogOrigin;
    }
    applyNetworkResult(data);
    if (data.title && $("save-map-name")) lastSnapshot.title = data.title;
    toast(`Loaded snapshot (${data.payload.nodes.length} systems). Save it into a campaign if you want it kept here.`);
  } catch (err) {
    toast(err.message, true);
  }
});

function applyCatalogDefaults() {
  $("origin-host").value = CATALOG_DEFAULTS.origin;
  $("ingest-max-ly").value = String(CATALOG_DEFAULTS.maxDistanceLy);
  $("ingest-min-mass").value = String(CATALOG_DEFAULTS.minSolarMass);
  catalogOrigin = CATALOG_DEFAULTS.origin;
}

function applyNetworkDefaults() {
  $("max-jump").value = String(NETWORK_DEFAULTS.maxJumpLy);
  $("medium-pct").value = String(NETWORK_DEFAULTS.mediumPct);
  $("long-pct").value = String(NETWORK_DEFAULTS.longPct);
  $("max-neighbors").value = String(NETWORK_DEFAULTS.maxNeighbors);
  $("max-linked").value = String(NETWORK_DEFAULTS.maxLinked);
  $("hard-rank").value = String(NETWORK_DEFAULTS.hardRank);
  $("soft-rank").value = String(NETWORK_DEFAULTS.softRank);
  $("net-min-mass").value = String(NETWORK_DEFAULTS.minSolarMass);
  $("root-host").value = catalogOrigin || CATALOG_DEFAULTS.origin;
  $("assign-factions").checked = true;
  updateBandReadout();
}

function updateBandReadout() {
  const box = $("band-readout");
  if (!box) return;
  const max = Number($("max-jump").value) || 50;
  let med = Number($("medium-pct").value);
  let lng = Number($("long-pct").value);
  if (lng <= med) {
    lng = Math.min(95, med + 5);
    $("long-pct").value = String(lng);
  }
  box.textContent =
    `Of the longest jump: short is 0–${med}% (always connect). ` +
    `Medium is ${med}–${lng}% (medium picky-ness). ` +
    `Long is ${lng}–100% (long picky-ness).`;
}

$("btn-reset-ingest").addEventListener("click", () => {
  applyCatalogDefaults();
  toast("Choose-the-stars settings reset. File paths were left alone.");
});

$("btn-reset-factions").addEventListener("click", async () => {
  try {
    let defaults = shippedFactionConfig;
    try {
      const fresh = await api("/api/factions/defaults");
      defaults = fresh;
      shippedFactionConfig = fresh;
    } catch (err) {
      if (!defaults) throw err;
    }
    factionConfig = defaults;
    cultureList = culturesFromConfig(defaults);
    renderFactionEditor(defaults);
    const card = $("screen-factions");
    if (card && card.scrollIntoView) card.scrollIntoView({ block: "nearest" });
    toast("The faction cards below now show the shipped defaults. Click Save these rules to write them to this campaign.");
  } catch (err) {
    toast(err.message, true);
  }
});

$("btn-reset-map").addEventListener("click", () => {
  applyNetworkDefaults();
  toast("Jump settings reset. The map itself is unchanged until you generate again.");
});

if ($("btn-full-map")) {
  $("btn-full-map").addEventListener("click", () => setMapFull(!mapFull));
}
if ($("reality-stop")) {
  $("reality-stop").addEventListener("change", updateRealityHelp);
}
if ($("campaign-name")) {
  $("campaign-name").addEventListener("input", () => {
    if (!settingIdTouched && $("setting-id")) $("setting-id").value = slugify($("campaign-name").value);
    updateCampaignSummary();
  });
}
if ($("setting-id")) {
  $("setting-id").addEventListener("input", () => {
    settingIdTouched = true;
    updateCampaignSummary();
  });
}
if ($("campaign-pick")) {
  $("campaign-pick").addEventListener("change", () => {
    const id = $("campaign-pick").value;
    if (!id) {
      settingIdTouched = false;
      $("campaign-name").value = "";
      $("setting-id").value = "";
      updateCampaignSummary();
      return;
    }
    const item = readCampaigns().items.find((c) => c.id === id);
    if (item) {
      settingIdTouched = true;
      applyCampaign(item);
      toast(`Loaded campaign ${item.name}.`);
    }
  });
}
if ($("btn-campaign-create")) {
  $("btn-campaign-create").addEventListener("click", () => {
    const name = ($("campaign-name").value || "").trim();
    if (!name) {
      toast("Type a campaign name first.", true);
      return;
    }
    if (!$("setting-id").value) $("setting-id").value = slugify(name);
    const item = persistCampaign();
    toast(`Saved campaign “${item.name}” (${item.id}) in this browser.`);
  });
}
if ($("btn-campaign-load")) {
  $("btn-campaign-load").addEventListener("click", () => {
    const id = $("campaign-pick").value;
    if (!id) {
      toast("Pick a saved campaign, or save this one first.", true);
      return;
    }
    const item = readCampaigns().items.find((c) => c.id === id);
    if (!item) {
      toast("That campaign is not in this browser.", true);
      return;
    }
    settingIdTouched = true;
    applyCampaign(item);
    toast(`Loaded campaign ${item.name}.`);
  });
}
if ($("btn-campaign-rename")) {
  $("btn-campaign-rename").addEventListener("click", () => {
    const name = ($("campaign-name").value || "").trim();
    if (!name) {
      toast("Type the new campaign title first.", true);
      return;
    }
    const store = readCampaigns();
    if (!store.current) {
      toast("Save the campaign once before renaming.", true);
      return;
    }
    const item = persistCampaign({ name });
    toast(`Title is now “${item.name}”. Setting id stayed ${item.id}.`);
  });
}
if ($("btn-save-map-cancel")) {
  $("btn-save-map-cancel").addEventListener("click", () => $("save-map-modal").classList.add("hidden"));
}
if ($("save-map-modal")) {
  $("save-map-modal").addEventListener("click", (event) => {
    if (event.target === $("save-map-modal")) $("save-map-modal").classList.add("hidden");
  });
}
if ($("btn-save-map-confirm")) {
  $("btn-save-map-confirm").addEventListener("click", () => {
    const mapName = ($("save-map-name").value || "").trim();
    if (!mapName) {
      toast("Give the map a name.", true);
      return;
    }
    const newCamp = ($("save-map-new-campaign").value || "").trim();
    const selectedId = $("save-map-campaign").value;
    if (newCamp) {
      $("campaign-name").value = newCamp;
      if (!settingIdTouched) $("setting-id").value = slugify(newCamp);
    } else if (selectedId) {
      const existing = readCampaigns().items.find((c) => c.id === selectedId);
      if (existing) {
        $("campaign-name").value = existing.name;
        $("setting-id").value = existing.settingId || existing.id;
        settingIdTouched = true;
        const store = readCampaigns();
        store.current = existing.id;
        writeCampaigns(store);
      }
    } else if (!($("campaign-name").value || "").trim()) {
      toast("Pick a campaign or type a new campaign name.", true);
      return;
    }
    lastSnapshot = snapshotEnvelope({ ...lastSnapshot, title: mapName });
    persistCampaign({ mapTitle: mapName, snapshot: lastSnapshot });
    downloadSnapshot(lastSnapshot, `${slugify(mapName)}.json`);
    $("save-map-modal").classList.add("hidden");
    toast(`Saved “${mapName}” to campaign ${$("campaign-name").value}.`);
  });
}

let wasmEngine = null;

async function generateNewMap() {
  const btn = $("btn-wasm-rebuild");
  const fill = $("btn-fill-jump-gaps");
  const line = $("wasm-status");
  const previous = btn ? btn.textContent : "Generate new map";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Generating…";
  }
  if (fill) fill.disabled = true;
  if (line) line.textContent = "Starting the browser engine…";
  try {
    if (typeof createWasmEngine !== "function") {
      throw new Error("Browser engine script did not load.");
    }
    if (!wasmEngine) wasmEngine = createWasmEngine();
    wasmEngine.onstatus = (message) => {
      toast(message);
      if (line) line.textContent = message;
      if (btn) btn.textContent = "Generating…";
    };
    const data = await wasmEngine.rebuild({
      params: currentNetworkParams(),
      assign_factions: $("assign-factions").checked,
    });
    applyNetworkResult(data);
    const nodes = (data.payload && data.payload.nodes && data.payload.nodes.length) || 0;
    const edges = (data.payload && data.payload.edges && data.payload.edges.length) || 0;
    if (line) line.textContent = `New map: ${nodes} systems, ${edges} jump routes.`;
    toast(`New map: ${nodes} systems, ${edges} jump routes.`);
    return data;
  } catch (err) {
    const message = err.message || String(err);
    if (line) line.textContent = message;
    toast(message, true);
    throw err;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = previous;
    }
    if (fill) fill.disabled = false;
  }
}

async function tryBodyGapFill() {
  const status = $("body-gapfill-status");
  const host = ($("gapfill-host") && $("gapfill-host").value.trim()) || "AU Mic";
  const sid = ($("setting-id") && $("setting-id").value.trim()) || "preview";
  const reality = Number($("reality-stop") && $("reality-stop").value) || 0;
  if (reality < 1) {
    toast("Set Reality to 1 Gap-fill first.", true);
    return;
  }
  try {
    try {
      await api("/v1/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: sid,
          title: ($("campaign-name") && $("campaign-name").value) || sid,
          reality,
          origin_hostname: "Sol",
          updated_by: "jumpgate",
        }),
      });
    } catch {
      const cur = await api(`/v1/settings/${encodeURIComponent(sid)}`);
      if (Number(cur.reality) < 1 && cur.etag) {
        await api(`/v1/settings/${encodeURIComponent(sid)}/reality`, {
          method: "PUT",
          headers: { "Content-Type": "application/json", "If-Match": cur.etag },
          body: JSON.stringify({ reality: 1, updated_by: "jumpgate" }),
        });
      }
    }
    const data = await api(
      `/v1/systems/${encodeURIComponent(host)}/premise?setting_id=${encodeURIComponent(sid)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          seed: "desk-try",
          need: [{ role: "warehouse_moon", g_earth_max: 0.25 }],
        }),
      }
    );
    const created = (data.created && data.created.length)
      ? data.created.join(", ")
      : "(none — that role is already filled)";
    if (status) {
      status.textContent = `Created: ${created}. Body ids on ${data.hostname || host}: ${(data.bodies || []).join(", ") || "—"}.`;
    }
    toast(data.created && data.created.length
      ? `Body gap-fill wrote ${created}.`
      : `No new stub — ${host} already has that moon.`);
  } catch (err) {
    if (status) status.textContent = err.message || String(err);
    toast(err.message || String(err), true);
  }
}

function nodeHopDist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

function findExistingBridge(a, b, maxJump, nodes) {
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const mz = (a.z + b.z) / 2;
  const ranked = [];
  nodes.forEach((n) => {
    if (!n || n.hostname === a.hostname || n.hostname === b.hostname) return;
    if (typeof n.x !== "number") return;
    const da = nodeHopDist(a, n);
    const db = nodeHopDist(b, n);
    if (da > maxJump || db > maxJump) return;
    const pnum = Number(n.sy_pnum) || 0;
    const score = Number(n.ranking != null ? n.ranking : n.combined_score) || 0;
    const offGrid = n.gate_distance === null || n.gate_distance === undefined;
    const dmid = Math.hypot(n.x - mx, n.y - my, n.z - mz);
    ranked.push({ n, pnum, score, offGrid, dmid, da, db });
  });
  ranked.sort((p, q) => (
    (q.offGrid ? 1 : 0) - (p.offGrid ? 1 : 0)
    || p.pnum - q.pnum
    || p.score - q.score
    || p.dmid - q.dmid
  ));
  return ranked[0] || null;
}

function placeJumpGapFillers(maxJump, holes) {
  if (!networkData || !holes || !holes.length) {
    toast("Scan jump gaps first.", true);
    return;
  }
  const minMass = Number($("net-min-mass") && $("net-min-mass").value) || 0.25;
  const byName = {};
  networkData.nodes.forEach((n) => { byName[n.hostname] = n; });
  const existing = new Set(Object.keys(byName));
  const seen = new Set();
  const newNodes = [];
  const newEdges = [];
  let usedReal = 0;
  let usedMinMass = 0;
  holes.forEach((hole) => {
    const key = [hole.host, hole.neighbor].sort().join("\0");
    if (seen.has(key)) return;
    seen.add(key);
    const a = byName[hole.host];
    const b = byName[hole.neighbor];
    if (!a || !b || hole.ly <= maxJump) return;
    const real = findExistingBridge(a, b, maxJump, networkData.nodes.concat(newNodes));
    if (real) {
      usedReal += 1;
      newEdges.push({ a: a.hostname, b: real.n.hostname, distance: Number(real.da.toFixed(4)) });
      newEdges.push({ a: real.n.hostname, b: b.hostname, distance: Number(real.db.toFixed(4)) });
      return;
    }
    const hops = Math.max(2, Math.ceil(hole.ly / maxJump - 1e-12));
    let prev = a.hostname;
    const nFill = hops - 1;
    for (let i = 1; i <= nFill; i += 1) {
      const t = i / hops;
      const hostname = nFill === 1
        ? `M${minMass} ${a.hostname}–${b.hostname}`
        : `M${minMass} ${a.hostname}–${b.hostname} ${i}`;
      if (!existing.has(hostname)) {
        const node = {
          hostname,
          sy_name: hostname,
          x: a.x + t * (b.x - a.x),
          y: a.y + t * (b.y - a.y),
          z: a.z + t * (b.z - a.z),
          group: "Gap filler",
          species: "",
          nation: "",
          gate_distance: 0,
          is_hub: false,
          spectype: "M",
          ranking: 0,
          sy_pnum: 0,
          st_mass: minMass,
        };
        newNodes.push(node);
        byName[hostname] = node;
        existing.add(hostname);
        usedMinMass += 1;
      }
      const here = byName[hostname];
      const from = byName[prev];
      newEdges.push({
        a: prev,
        b: hostname,
        distance: Number(nodeHopDist(here, from).toFixed(4)),
      });
      prev = hostname;
    }
    const last = byName[prev];
    newEdges.push({
      a: prev,
      b: b.hostname,
      distance: Number(nodeHopDist(b, last).toFixed(4)),
    });
  });
  if (!newNodes.length && !newEdges.length) {
    toast("No holes a catalog star or 0.25 M☉ midpoint can bridge at this hop.", true);
    return;
  }
  applyNetworkResult({
    payload: {
      nodes: networkData.nodes.concat(newNodes),
      edges: (networkData.edges || []).concat(newEdges),
    },
    title: (lastSnapshot && lastSnapshot.title) || "Map with gap fillers",
  });
  toast(`Bridged with ${usedReal} existing star(s) and ${usedMinMass} × ${minMass} M☉ midpoint star(s).`);
  scanJumpGaps();
}

async function fillJumpGaps(hopLy) {
  const hop = Number(hopLy);
  if (!hop || hop <= 0) return;
  $("max-jump").value = String(hop);
  updateBandReadout();
  toast(`Longest single jump set to ${hop} ly. Generating the map…`);
  try {
    await generateNewMap();
    scanJumpGaps();
  } catch {
    /* generateNewMap already toasted */
  }
}

$("btn-wasm-rebuild").addEventListener("click", () => {
  generateNewMap();
});

$("path-start").addEventListener("change", highlightPath);
$("path-end").addEventListener("change", highlightPath);
$("color-faction").addEventListener("change", () => highlightPath());
$("focus-faction").addEventListener("change", () => highlightPath());
document.addEventListener("input", (event) => {
  const pick = event.target.closest(".legend-pick");
  if (!pick) return;
  const group = pick.dataset.group;
  if (!group) return;
  colorOverrides[group] = pick.value;
  saveColorOverrides();
  highlightPath();
});

async function boot() {
  if (typeof loadHelp === "function") await loadHelp();
  if ($("btn-gap-scan")) $("btn-gap-scan").addEventListener("click", scanJumpGaps);
  if ($("btn-body-gapfill")) $("btn-body-gapfill").addEventListener("click", tryBodyGapFill);
  if (window.STARROUTE_DEFAULT_MAP) {
    applyNetworkResult(window.STARROUTE_DEFAULT_MAP);
    catalogOrigin = (window.STARROUTE_DEFAULT_MAP.origin && window.STARROUTE_DEFAULT_MAP.origin.origin_hostname) || "Sol";
  }
  showScreen("map");
  bindCardCollapse();
  if ($("btn-drawer")) $("btn-drawer").addEventListener("click", () => toggleDrawer());
  if ($("system-search")) {
    $("system-search").addEventListener("input", () => {
      const q = $("system-search").value.trim().toLowerCase();
      const hits = $("system-search-hits");
      const empty = $("system-search-empty");
      if (!hits) return;
      if (!q || !networkData) {
        hits.innerHTML = "";
        if (empty) empty.hidden = false;
        return;
      }
      const matches = networkData.nodes.filter((n) =>
        n.hostname.toLowerCase().includes(q) || (n.group || "").toLowerCase().includes(q)
      ).slice(0, 20);
      hits.innerHTML = matches.map((n) => `<li data-host="${esc(n.hostname)}">${esc(n.hostname)}${n.group ? " · " + esc(n.group) : ""}</li>`).join("");
      if (empty) empty.hidden = matches.length > 0;
      hits.querySelectorAll("li").forEach((li) => {
        li.addEventListener("click", () => {
          const node = networkData.nodes.find((n) => n.hostname === li.dataset.host);
          showSelectedSystem(node);
        });
      });
    });
  }
  $("btn-glossary").addEventListener("click", openGlossary);
  $("glossary-close").addEventListener("click", closeGlossary);
  $("glossary").addEventListener("click", (event) => {
    if (event.target === $("glossary")) closeGlossary();
  });
  $("glossary-search").addEventListener("input", () => renderGlossary($("glossary-search").value));
  ["max-jump", "medium-pct", "long-pct"].forEach((id) => {
    $(id).addEventListener("input", updateBandReadout);
  });
  bindHostSearch($("origin-host"), $("origin-suggest"), "host-path");
  bindHostSearch($("human-root"), $("human-root-suggest"), "host-path");
  bindHostSearch($("root-host"), $("root-suggest"), "host-path");
  applyCatalogDefaults();
  applyNetworkDefaults();
  fillCampaignSelects();
  updateRealityHelp();
  try {
    await detectSources();
    factionConfig = await api("/api/factions");
    try {
      shippedFactionConfig = await api("/api/factions/defaults");
    } catch {
      shippedFactionConfig = factionConfig;
    }
    await ensurePresets();
    renderFactionEditor(factionConfig);
    $("ingest-min-mass").value = String(CATALOG_DEFAULTS.minSolarMass);
    $("net-min-mass").value = String(NETWORK_DEFAULTS.minSolarMass);
    document.body.classList.remove("no-backend");
  } catch {
    document.body.classList.add("no-backend");
    if (factionConfig) shippedFactionConfig = shippedFactionConfig || factionConfig;
  }
  const stored = readCampaigns();
  if (stored.current) {
    const item = stored.items.find((c) => c.id === stored.current);
    if (item) {
      settingIdTouched = true;
      applyCampaign(item);
    }
  }
}

boot();
