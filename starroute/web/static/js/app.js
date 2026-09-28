const FACTION_COLORS = {
  Sol: "#ffffff",
  Human: "#3dbbff",
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
const ORBIT_MATCH_PAGE = "https://ldjessee-code.github.io/orbit_match/manual/";
let pinnedStar = null;
let pathRoster = [];
const pathValue = { "path-start": "", "path-end": "" };

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
let activePresetId = "crowded";
let presetLoadToken = 0;

const MAP_PRESETS = [
  {
    id: "crowded",
    title: "Crowded — Turquenish neighborhood",
    description: "Dense local space around Sol. Short jumps. Turquenish (bio-edit) and Mardat (chrome) plus tight-knit alien enclaves. Default tabletop slice.",
  },
  {
    id: "sparse",
    title: "Sparse — thin Turquenish grid",
    description: "Same Turquenish–Mardat war, fewer small stars, longer jumps. Alien enclaves remain but feel isolated.",
  },
  {
    id: "lonely_humans",
    title: "Lonely humans",
    description: "Sun-like stars only. No local aliens. Turquenish, Mardat, Hegemony, Faithful, and independents still feud and expand.",
  },
];

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

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeGlossary();
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
  const tab = document.querySelector(`.tab[data-screen="${name}"]`);
  if (tab && (tab.disabled || tab.getAttribute("aria-disabled") === "true")) return;
  document.body.classList.toggle("map-tab", name === "map");
  document.querySelectorAll(".screen").forEach((el) => {
    el.classList.toggle("is-active", el.id === `screen-${name}`);
  });
  document.querySelectorAll(".tab").forEach((el) => {
    el.classList.toggle("is-active", el.dataset.screen === name);
  });
  if (name === "factions") {
    ensurePresets().then(() => fillPresetSelects());
  }
  if (name === "map") {
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
}

function toggleDrawer(force) {
  const btn = $("btn-drawer");
  const open = force === undefined ? !document.body.classList.contains("drawer-open") : force;
  document.body.classList.toggle("drawer-open", open);
  if (btn) {
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.title = open ? "Hide settings" : "Settings";
    btn.setAttribute("aria-label", open ? "Hide settings" : "Settings");
  }
  window.setTimeout(resizeStarMap, 80);
}

function resizeStarMap() {
  const plot = $("star-map");
  if (!plot || !window.Plotly) return;
  try {
    Plotly.Plots.resize(plot);
  } catch {
    /* map not plotted yet */
  }
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
    toast(`Star list ready: ${data.systems_written} systems around ${catalogOrigin}. Next: Generate the map from this list.`);
  } catch (err) {
    toast(err.message, true);
  } finally {
    $("btn-ingest").disabled = false;
    $("btn-ingest").textContent = "Build neighborhood (star list)";
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

function culturesFromConfig(config) {
  const rows = [
    ...(config.species || []).map((item) => ({ ...item, kind: item.kind || "species" })),
    ...(config.nations || []).map((item) => ({ ...item, kind: item.kind || "nation" })),
  ];
  return rows.map((item) => {
    const presetId = inferPresetId(item);
    const preset = (factionPresets.presets || []).find((p) => p.id === presetId);
    return {
      ...item,
      preset: presetId,
      description: item.description || (preset && preset.description) || "",
    };
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
    const host = card.querySelector("[data-field=place-host]");
    if (item.preset === "from_host") {
      item.filters = [{
        op: "from_host",
        host: (host && host.value.trim()) || "Sol",
        bearing_deg: Number(card.querySelector("[data-field=bearing]")?.value || 0),
        wedge_deg: Number(card.querySelector("[data-field=wedge]")?.value || 15),
      }];
    } else if (item.preset === "near_host") {
      item.filters = [{
        op: "near_host",
        host: (host && host.value.trim()) || "Sol",
        max_ly: Number(card.querySelector("[data-field=near-ly]")?.value || 80),
      }];
    } else if (item.preset === "far_host") {
      item.filters = [{
        op: "far_host",
        host: (host && host.value.trim()) || "Sol",
        min_ly: Number(card.querySelector("[data-field=far-ly]")?.value || 400),
      }];
    }
  });
}

function placeExtraHtml(item) {
  const loc = (item.filters && item.filters[0]) || {};
  const host = loc.host || "Sol";
  const preset = item.preset || loc.op;
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
  item.filters = JSON.parse(JSON.stringify(preset.filters || []));
  item.sort = JSON.parse(JSON.stringify(preset.sort || {}));
  return item;
}

async function ensurePresets() {
  if (factionPresets.presets && factionPresets.presets.length) return;
  try {
    factionPresets = await api("/api/factions/presets");
  } catch {
    factionPresets = { max_cultures: 16, presets: [] };
  }
}

function fillPresetSelects() {
  const add = $("preset-pick");
  if (!add) return;
  const presets = factionPresets.presets || [];
  const parts = [];
  if (presets.length) {
    parts.push(
      `<optgroup label="Templates">` +
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

function criteriaOptions(selected) {
  const presets = (factionPresets.presets || []).filter((p) => !String(p.id).startsWith("custom_"));
  const known = presets.some((p) => p.id === selected);
  let html = "";
  if (!selected || !known) {
    html += `<option value="" selected>Keep this culture’s current rules</option>`;
  }
  html += presets
    .map((p) => `<option value="${p.id}" ${p.id === selected ? "selected" : ""}>${p.label || p.name}</option>`)
    .join("");
  return html;
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
        <button type="button" class="btn-remove" data-remove="${idx}" aria-label="Remove culture">Remove</button>
      </header>
      <p class="lore">${esc(lore)}</p>
      <label>
        <span class="label-row">How they pick stars</span>
        <select data-field="preset">${criteriaOptions(item.preset)}</select>
      </label>
      ${placeExtraHtml(item)}
      <div class="faction-fields">
        <label data-help="factionCount">
          <span class="label-row">How many systems</span>
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
  const roster = $("culture-roster");
  if (roster) {
    const names = cultureList.map((item) => item.name).filter(Boolean);
    roster.textContent = names.length
      ? `Turquenish cultures on this list: ${names.join(", ")}.`
      : "No cultures loaded.";
  }
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
  const select = event.target.closest("select[data-field=preset]");
  if (!select) return;
  if (!select.value) return;
  const card = event.target.closest(".faction-card");
  if (!card) return;
  syncCulturesFromDom();
  const idx = Number(card.dataset.idx);
  const item = cultureList[idx];
  if (!item) return;
  applyPresetToCulture(item, select.value);
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
    toast("Faction rules saved.");
  } catch (err) {
    toast(err.message, true);
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
  pathRoster = (nodes || [])
    .filter((n) => n.gate_distance !== null && n.gate_distance !== undefined)
    .sort((a, b) => (a.gate_distance - b.gate_distance) || a.hostname.localeCompare(b.hostname))
    .map((n) => ({ hostname: n.hostname, sy_name: n.sy_name || "", gate_distance: n.gate_distance }));
  const root = $("root-host").value || catalogOrigin || "Sol";
  pathValue["path-start"] = pathRoster.some((n) => n.hostname === root) ? root : ((pathRoster[0] && pathRoster[0].hostname) || "");
  const farthest = pathRoster[pathRoster.length - 1];
  pathValue["path-end"] = (farthest && farthest.hostname) || "";
  ["path-start", "path-end"].forEach((id) => {
    const box = $(`${id}-search`);
    if (box) box.value = "";
    renderPathOptions(id);
  });
}

function pathLabel(row) {
  const hops = row.gate_distance != null && row.gate_distance !== "" ? ` (${row.gate_distance})` : "";
  const name = row.sy_name && row.sy_name !== row.hostname ? ` · ${row.sy_name}` : "";
  return `${row.hostname}${name}${hops}`;
}

function renderPathOptions(id) {
  const sel = $(id);
  if (!sel) return;
  const q = (($(`${id}-search`) && $(`${id}-search`).value) || "").trim().toLowerCase();
  const keep = pathValue[id] || "";
  const rows = pathRoster.filter((row) => {
    if (!q) return true;
    return row.hostname.toLowerCase().includes(q) || (row.sy_name || "").toLowerCase().includes(q);
  });
  const current = pathRoster.find((row) => row.hostname === keep);
  let html = "";
  if (keep && current && !rows.some((row) => row.hostname === keep)) {
    html += `<option value="${esc(keep)}" hidden>${esc(pathLabel(current))}</option>`;
  }
  if (!rows.length) html += `<option value="" disabled>No match</option>`;
  html += rows.map((row) => `<option value="${esc(row.hostname)}">${esc(pathLabel(row))}</option>`).join("");
  sel.innerHTML = html || `<option value="" disabled>No match</option>`;
  if (keep) sel.value = keep;
}

function bindPathSearch(id) {
  const box = $(`${id}-search`);
  const sel = $(id);
  if (!box || !sel) return;
  box.addEventListener("input", () => renderPathOptions(id));
  box.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || !box.value.trim()) return;
    event.preventDefault();
    const first = [...sel.options].find((opt) => opt.value && !opt.hidden);
    if (!first) return;
    pathValue[id] = first.value;
    sel.value = first.value;
    sel.dispatchEvent(new Event("change"));
  });
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

function haloRgba(hex, towardWhite, alpha) {
  const raw = hex.replace("#", "");
  const n = parseInt(raw, 16);
  const mix = (c) => Math.round(c + (255 - c) * towardWhite);
  const r = mix((n >> 16) & 255);
  const g = mix((n >> 8) & 255);
  const b = mix(n & 255);
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
  const routes = (networkData && networkData.edges && networkData.edges.length) || 0;
  const rows = [];
  rows.push(`<div class="legend-row"><span>${nodes.length} stars · ${routes} routes</span></div>`);
  rows.push(`<div class="legend-row"><span class="legend-swatch" style="background:#fff"></span><span>Sol / map center</span></div>`);
  if (byFaction) {
    groups.forEach((g) => {
      const color = getGroupColor(g);
      const focusOn = ($("focus-faction").value || "all") === g;
      rows.push(`<div class="legend-row${focusOn ? " is-focus" : ""}">
        <input type="color" class="legend-pick" data-group="${esc(g)}" value="${color}" title="Change ${esc(g)} color" />
        <button type="button" class="legend-name" data-group="${esc(g)}">${esc(g)}${focusOn ? " · highlighted" : ""}</button>
      </div>`);
    });
  } else {
    rows.push(`<div class="legend-row"><span class="legend-swatch heat"></span><span>Color = world score</span></div>`);
  }
  const focus = $("focus-faction") && $("focus-faction").value || "all";
  if (focus !== "all") {
    rows.push(`<div class="legend-row is-focus"><span class="legend-swatch" style="background:${getGroupColor(focus)};box-shadow:0 0 12px ${getGroupColor(focus)}"></span><span>Halo = ${esc(focus)}</span></div>`);
    rows.push(`<div class="legend-row"><span class="legend-line" style="border-top-color:${getGroupColor(focus)}"></span><span>Route inside this faction</span></div>`);
    rows.push(`<div class="legend-row"><span class="legend-line"></span><span>Other route</span></div>`);
  } else if (byFaction) {
    rows.push(`<div class="legend-row"><span class="legend-line"></span><span>Color = both stars in that faction</span></div>`);
  } else {
    rows.push(`<div class="legend-row"><span class="legend-line"></span><span>Jump route</span></div>`);
  }
  rows.push(`<div class="legend-row"><span class="legend-line path"></span><span>Highlighted path</span></div>`);
  box.innerHTML = `<p class="legend-title">Legend</p>${rows.join("")}`;
}

function lineBucket() {
  return { x: [], y: [], z: [] };
}

function pushSegment(bucket, a, b) {
  bucket.x.push(a.x, b.x, null);
  bucket.y.push(a.y, b.y, null);
  bucket.z.push(a.z, b.z, null);
}

function lineTrace(name, bucket, color, width) {
  if (!bucket.x.length) return null;
  return {
    type: "scatter3d",
    mode: "lines",
    x: bucket.x,
    y: bucket.y,
    z: bucket.z,
    line: { color, width },
    hoverinfo: "none",
    name,
  };
}

function ensureStarCard() {
  let card = $("star-card");
  if (!card) {
    const stage = document.querySelector(".map-stage");
    if (!stage) return null;
    card = document.createElement("aside");
    card.id = "star-card";
    card.className = "star-card hidden";
    stage.appendChild(card);
  }
  if (!card.dataset.bound) {
    card.dataset.bound = "1";
    card.addEventListener("click", onStarCardClick);
  }
  return card;
}

function onStarCardClick(event) {
  const action = event.target.closest("[data-star-action]");
  if (!action) return;
  const host = event.currentTarget.dataset.host;
  const kind = action.dataset.starAction;
  if (kind === "close") hideStarCard();
  if (kind === "start") assignRouteEnd("path-start", host);
  if (kind === "end") assignRouteEnd("path-end", host);
}

function assignRouteEnd(selectId, hostname) {
  const sel = $(selectId);
  if (!sel || !hostname) return;
  if (!pathRoster.some((row) => row.hostname === hostname)) {
    const node = ((networkData && networkData.nodes) || []).find((n) => n.hostname === hostname);
    pathRoster.push({
      hostname,
      sy_name: (node && node.sy_name) || "",
      gate_distance: node ? node.gate_distance : null,
    });
  }
  pathValue[selectId] = hostname;
  const box = $(`${selectId}-search`);
  if (box) box.value = "";
  renderPathOptions(selectId);
  sel.value = hostname;
  highlightPath();
  if (pinnedStar) showStarCard(pinnedStar);
}

function orbitMatchHref(node) {
  const q = new URLSearchParams();
  q.set("h", "1");
  q.set("host", node.hostname);
  if (node.setting_name) q.set("name", node.setting_name);
  if (node.spectype) q.set("spec", node.spectype);
  if (node.sy_pnum != null) q.set("planets", String(node.sy_pnum));
  if (node.group) q.set("holder", node.group);
  ["x", "y", "z"].forEach((key) => {
    if (node[key] != null) q.set(key, String(Math.round(Number(node[key]) * 100) / 100));
  });
  const from = new Set();
  ((networkData && networkData.edges) || []).forEach((edge) => {
    if (edge.a === node.hostname) from.add(edge.b);
    else if (edge.b === node.hostname) from.add(edge.a);
  });
  from.forEach((host) => q.append("from", host));
  return `${ORBIT_MATCH_PAGE}#${q.toString()}`;
}

function showStarCard(hostname) {
  const node = ((networkData && networkData.nodes) || []).find((n) => n.hostname === hostname);
  const card = ensureStarCard();
  if (!node || !card) return;
  pinnedStar = hostname;
  card.dataset.host = hostname;
  card.classList.remove("hidden");
  const isStart = $("path-start") && $("path-start").value === hostname;
  const isEnd = $("path-end") && $("path-end").value === hostname;
  const lines = [
    node.group || node.species || "No faction",
    node.spectype ? `Spectral type ${node.spectype}` : "",
    node.sy_pnum != null ? `Planets ${node.sy_pnum}` : "",
    node.dist_ly != null ? `${Number(node.dist_ly).toFixed(2)} ly from Sol` : "",
    node.gate_distance != null && node.gate_distance !== "" ? `${node.gate_distance} gates from the root` : "Not on the route grid",
  ].filter(Boolean);
  card.innerHTML = `
    <button type="button" class="star-card-close" data-star-action="close" aria-label="Close">×</button>
    <h3>${esc(node.sy_name || node.hostname)}</h3>
    <p class="star-card-host">${esc(node.hostname)}</p>
    ${lines.map((line) => `<p>${esc(line)}</p>`).join("")}
    <div class="star-card-actions">
      <button type="button" class="btn" data-star-action="start">${isStart ? "Start" : "Set as start"}</button>
      <button type="button" class="btn" data-star-action="end">${isEnd ? "End" : "Set as end"}</button>
      <a class="btn" href="${esc(orbitMatchHref(node))}" target="_blank" rel="noopener noreferrer">Orbit Match</a>
    </div>
  `;
}

function hideStarCard() {
  pinnedStar = null;
  const card = $("star-card");
  if (!card) return;
  card.classList.add("hidden");
  card.innerHTML = "";
  delete card.dataset.host;
}

function bindStarClicks(plot) {
  if (!plot || plot.__starClick || typeof plot.on !== "function") return;
  plot.__starClick = true;
  plot.on("plotly_click", (ev) => {
    const pt = ev.points && ev.points[0];
    const host = pt && pt.customdata;
    if (typeof host === "string" && host) showStarCard(host);
  });
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
  const reduceMotion = $("reduce-map-motion") && $("reduce-map-motion").checked;
  const lookup = Object.fromEntries(nodes.map((n) => [n.hostname, n]));
  const pathSet = new Set();
  for (let i = 0; i < path.length - 1; i += 1) {
    pathSet.add([path[i], path[i + 1]].sort().join("|"));
  }

  const dim = lineBucket();
  const plain = lineBucket();
  const glow = lineBucket();
  const pathLine = lineBucket();
  const factionLines = new Map();
  const factionBucket = (group) => {
    let bucket = factionLines.get(group);
    if (!bucket) {
      bucket = lineBucket();
      factionLines.set(group, bucket);
    }
    return bucket;
  };
  edges.forEach((edge) => {
    const a = lookup[edge.a];
    const b = lookup[edge.b];
    if (!a || !b) return;
    const key = [edge.a, edge.b].sort().join("|");
    if (pathSet.has(key)) {
      pushSegment(pathLine, a, b);
      return;
    }
    const shared = a.group && a.group === b.group;
    if (focus !== "all") {
      if (shared && a.group === focus) {
        if (!reduceMotion) pushSegment(glow, a, b);
        pushSegment(factionBucket(focus), a, b);
      } else {
        pushSegment(dim, a, b);
      }
      return;
    }
    if (byFaction && shared) pushSegment(factionBucket(a.group), a, b);
    else pushSegment(plain, a, b);
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
  const haloNodes = (focus === "all" || reduceMotion) ? [] : nodes.filter((n) => n.group === focus);
  const factionHex = getGroupColor(focus);
  const glowColor = focus === "all" ? "rgba(255,255,255,0.2)" : haloRgba(factionHex, 0.55, 0.55);
  const factionTraces = [...factionLines.entries()].map(([group, bucket]) => lineTrace(
    group,
    bucket,
    hexToRgba(getGroupColor(group), focus === "all" ? 0.8 : 0.95),
    focus === "all" ? 2 : 3,
  ));

  const traces = [
    lineTrace("Other routes", dim, "rgba(160,150,140,0.12)", 1),
    lineTrace("Jump routes", plain, "rgba(180,190,200,0.45)", 2),
    lineTrace("Route halo", glow, haloRgba(factionHex, 0.72, 0.38), 46),
    lineTrace("Route bloom", glow, haloRgba(factionHex, 0.4, 0.5), 20),
    ...factionTraces,
    lineTrace("Highlighted path", pathLine, "#e24a3b", 7),
    {
      type: "scatter3d",
      mode: "markers",
      x: haloNodes.map((n) => n.x),
      y: haloNodes.map((n) => n.y),
      z: haloNodes.map((n) => n.z),
      hoverinfo: "none",
      marker: {
        size: haloNodes.map((n) => {
          const base = 5 + Math.min(n.sy_pnum || 0, 8) * 1.6;
          return Math.max(22, base * 3.6);
        }),
        color: glowColor,
        symbol: "circle",
        opacity: 0.35,
      },
      name: "Culture glow",
    },
    {
      type: "scatter3d",
      mode: "markers",
      x: others.map((n) => n.x),
      y: others.map((n) => n.y),
      z: others.map((n) => n.z),
      customdata: others.map((n) => n.hostname),
      hoverinfo: "none",
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
      customdata: originNodes.map((n) => n.hostname),
      hoverinfo: "none",
      marker: {
        size: 14,
        color: originNodes.map((n) => nodeColor(n, true, focus)),
        symbol: "circle",
        opacity: 1,
      },
      name: originName,
    },
  ].filter(Boolean);

  renderLegend(nodes);
  const packKey = (lastSnapshot && (lastSnapshot.id || lastSnapshot.title)) || "map";
  const prevCam = plot.layout && plot.layout.scene && plot.layout.scene.camera;
  const drawn = Plotly.react(plot, traces, {
    paper_bgcolor: "#05070c",
    plot_bgcolor: "#05070c",
    font: { color: "#d9d2c3" },
    margin: { l: 0, r: 0, t: 8, b: 0 },
    showlegend: false,
    uirevision: packKey,
    scene: {
      aspectmode: "data",
      camera: prevCam,
      xaxis: { title: "X (ly)", backgroundcolor: "#05070c", gridcolor: "#2a3140", zerolinecolor: "#3a4254", color: "#c9c2b2" },
      yaxis: { title: "Y (ly)", backgroundcolor: "#05070c", gridcolor: "#2a3140", zerolinecolor: "#3a4254", color: "#c9c2b2" },
      zaxis: { title: "Z (ly)", backgroundcolor: "#05070c", gridcolor: "#2a3140", zerolinecolor: "#3a4254", color: "#c9c2b2" },
    },
  }, { responsive: true, displaylogo: false });
  if (drawn && typeof drawn.then === "function") drawn.then(() => bindStarClicks(plot));
  else bindStarClicks(plot);
}

async function highlightPath() {
  if (!networkData) return;
  const start = $("path-start").value;
  const end = $("path-end").value;
  if (!start || !end) {
    drawMap();
    return;
  }
  const path = shortestPathLocal(start, end);
  $("path-readout").textContent = path.length
    ? `${Math.max(path.length - 1, 0)} jump(s): ${path.join(" → ")}`
    : `No jump path between ${start} and ${end}.`;
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
    id: data && data.id,
    title: (data && data.title) || "Starroute map",
    description: data && data.description,
    origin: (data && data.origin) || { origin_hostname: catalogOrigin || "Sol" },
    params: (data && data.params) || currentNetworkParams(),
    factions: data && data.factions,
    payload,
  };
}

function applySnapshotParams(data) {
  const p = (data && data.params) || {};
  if (p.max_jump_ly != null) $("max-jump").value = String(p.max_jump_ly);
  if (p.medium_start_pct != null) $("medium-pct").value = String(p.medium_start_pct);
  if (p.long_start_pct != null) $("long-pct").value = String(p.long_start_pct);
  if (p.max_neighbors != null) $("max-neighbors").value = String(p.max_neighbors);
  if (p.max_linked_nodes != null) $("max-linked").value = String(p.max_linked_nodes);
  if (p.hard_rank != null) $("hard-rank").value = String(p.hard_rank);
  if (p.soft_rank != null) $("soft-rank").value = String(p.soft_rank);
  if (p.min_stellar_mass != null) $("net-min-mass").value = String(p.min_stellar_mass);
  if (p.root_hostname) $("root-host").value = p.root_hostname;
  updateBandReadout();
}

function applyPresetCopy(data) {
  const lede = $("map-lede");
  if (!lede) return;
  const meta = MAP_PRESETS.find((item) => item.id === (data && data.id));
  const title = (data && data.title) || (meta && meta.title) || "Starroute map";
  const description = (data && data.description) || (meta && meta.description) || "";
  lede.textContent = description ? `${title}. ${description}` : title;
}

function staticRoot() {
  const script = document.querySelector("script[src*='default-map.js']");
  if (script && script.getAttribute("src")) {
    return script.getAttribute("src").replace(/default-map\.js.*$/, "");
  }
  return "";
}

function injectScript(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[data-preset-src="${src}"]`);
    if (existing) {
      resolve();
      return;
    }
    const el = document.createElement("script");
    el.src = src;
    el.async = false;
    el.dataset.presetSrc = src;
    el.onload = () => resolve();
    el.onerror = () => reject(new Error(`Could not load ${src}`));
    document.head.appendChild(el);
  });
}

async function fetchPresetSnapshot(id) {
  if (window.STARROUTE_PRESET_PACKS && window.STARROUTE_PRESET_PACKS[id]) {
    return window.STARROUTE_PRESET_PACKS[id];
  }
  const root = staticRoot();
  try {
    const res = await fetch(`${root}presets/${id}/map.json`, { cache: "no-cache" });
    if (res.ok) return await res.json();
  } catch {
    /* file:// and some static hosts block fetch; fall through to the JS pack */
  }
  await injectScript(`${root}presets/${id}/map.js`);
  if (window.STARROUTE_PRESET_PACKS && window.STARROUTE_PRESET_PACKS[id]) {
    return window.STARROUTE_PRESET_PACKS[id];
  }
  if (id === "crowded" && window.STARROUTE_DEFAULT_MAP) {
    return window.STARROUTE_DEFAULT_MAP;
  }
  throw new Error(`Could not load map pack “${id}”. Host this folder on a web server, or keep the presets/ files next to the page.`);
}

function rememberPreset(id) {
  activePresetId = id;
  try {
    localStorage.setItem("starroute-map-preset", id);
  } catch {
    /* ignore quota / private mode */
  }
  const select = $("map-preset");
  if (select && select.value !== id) select.value = id;
  try {
    const url = new URL(window.location.href);
    if (id && id !== "crowded") url.searchParams.set("preset", id);
    else url.searchParams.delete("preset");
    history.replaceState(null, "", url);
  } catch {
    /* file:// or opaque origins may refuse history updates */
  }
}

async function loadMapPreset(id, { silent } = {}) {
  const token = ++presetLoadToken;
  const data = await fetchPresetSnapshot(id);
  if (token !== presetLoadToken) return;
  if (!data || !data.payload || !data.payload.nodes) {
    throw new Error("That pack is not a Starroute map snapshot.");
  }
  data.id = data.id || id;
  rememberPreset(id);
  applyNetworkResult(data);
  if (!silent) {
    const n = data.payload.nodes.length;
    const e = (data.payload.edges && data.payload.edges.length) || 0;
    toast(`Loaded ${data.title || id}: ${n} systems, ${e} jump routes.`);
  }
}

function applyNetworkResult(data) {
  const payload = data && data.payload && data.payload.nodes ? data.payload : data;
  if (!payload || !payload.nodes) return;
  lastSnapshot = snapshotEnvelope(data && data.payload && data.payload.nodes ? data : { payload });
  networkData = payload;
  if (data && data.origin && data.origin.origin_hostname) {
    catalogOrigin = data.origin.origin_hostname;
  }
  applySnapshotParams(lastSnapshot);
  applyPresetCopy(lastSnapshot);
  fillPathSelects(networkData.nodes);
  fillFocusOptions(networkData.nodes);
  highlightPath();
  window.setTimeout(resizeStarMap, 50);
  if (pinnedStar && !networkData.nodes.some((n) => n.hostname === pinnedStar)) hideStarCard();
}

$("btn-network").addEventListener("click", async () => {
  $("btn-network").disabled = true;
  $("btn-network").textContent = "Generating the map…";
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
    showScreen("map");
  } catch (err) {
    toast(err.message, true);
  } finally {
    $("btn-network").disabled = false;
    $("btn-network").textContent = "Generate the map";
  }
});

$("btn-snapshot").addEventListener("click", async () => {
  try {
    if (!lastSnapshot || !lastSnapshot.payload || !lastSnapshot.payload.nodes) {
      throw new Error("No map to save yet.");
    }
    const data = snapshotEnvelope(lastSnapshot);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "starroute-map.json";
    a.click();
    URL.revokeObjectURL(url);
    toast("Saved map snapshot JSON.");
  } catch (err) {
    toast(err.message, true);
  }
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
    if (data.id && MAP_PRESETS.some((item) => item.id === data.id)) {
      rememberPreset(data.id);
    } else {
      showOpenedMap(data);
    }
    toast(`Loaded snapshot (${data.payload.nodes.length} systems).`);
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

if ($("btn-quick-generate")) {
  $("btn-quick-generate").addEventListener("click", () => {
    const button = $("btn-network");
    if (button) button.click();
  });
}

if ($("btn-detailed-generate")) {
  $("btn-detailed-generate").addEventListener("click", () => {
    const card = $("route-settings-card");
    if (card) card.scrollIntoView({ behavior: "smooth", block: "start" });
    const field = $("max-jump");
    if (field) field.focus();
  });
}

$("btn-reset-ingest").addEventListener("click", () => {
  applyCatalogDefaults();
  toast("Neighborhood reset. The NASA files were left alone.");
});

$("btn-reset-factions").addEventListener("click", async () => {
  try {
    factionConfig = await api("/api/factions/defaults");
    cultureList = culturesFromConfig(factionConfig);
    renderFactionEditor(factionConfig);
    toast("Culture rules reset to the shipped defaults. Click Save if you want to keep them.");
  } catch (err) {
    toast(err.message, true);
  }
});

$("btn-reset-map").addEventListener("click", () => {
  applyNetworkDefaults();
  if (lastSnapshot) applySnapshotParams(lastSnapshot);
  toast("Route settings reset. The map itself is unchanged until you draw again.");
});

let wasmEngine = null;
$("btn-wasm-rebuild").addEventListener("click", async () => {
  $("btn-wasm-rebuild").disabled = true;
  try {
    if (!wasmEngine) wasmEngine = createWasmEngine();
    wasmEngine.onstatus = (message) => {
      toast(message);
      const line = $("wasm-status");
      if (line) line.textContent = message;
    };
    const data = await wasmEngine.rebuild({
      params: currentNetworkParams(),
      assign_factions: $("assign-factions").checked,
    });
    applyNetworkResult(data);
    const nodes = (data.payload && data.payload.nodes && data.payload.nodes.length) || 0;
    const edges = (data.payload && data.payload.edges && data.payload.edges.length) || 0;
    const line = $("wasm-status");
    if (line) line.textContent = `New map: ${nodes} systems, ${edges} jump routes.`;
    toast(`New map: ${nodes} systems, ${edges} jump routes.`);
  } catch (err) {
    toast(err.message || String(err), true);
  } finally {
    $("btn-wasm-rebuild").disabled = false;
  }
});

["path-start", "path-end"].forEach((id) => {
  $(id).addEventListener("change", () => {
    if ($(id).value) pathValue[id] = $(id).value;
    highlightPath();
  });
  bindPathSearch(id);
});
$("color-faction").addEventListener("change", () => highlightPath());
$("focus-faction").addEventListener("change", () => highlightPath());
if ($("reduce-map-motion")) {
  try {
    $("reduce-map-motion").checked = localStorage.getItem("starroute-reduce-map-motion") === "1";
  } catch { /* ignore */ }
  $("reduce-map-motion").addEventListener("change", () => {
    try {
      localStorage.setItem("starroute-reduce-map-motion", $("reduce-map-motion").checked ? "1" : "0");
    } catch { /* ignore */ }
    highlightPath();
  });
}
document.addEventListener("input", (event) => {
  const pick = event.target.closest(".legend-pick");
  if (!pick) return;
  const group = pick.dataset.group;
  if (!group) return;
  colorOverrides[group] = pick.value;
  saveColorOverrides();
  highlightPath();
});

document.addEventListener("click", (event) => {
  const name = event.target.closest(".legend-name");
  if (!name) return;
  const select = $("focus-faction");
  if (!select) return;
  const group = name.dataset.group;
  select.value = select.value === group ? "all" : group;
  highlightPath();
});

function downloadNamed(url, filename) {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

if ($("btn-open-map")) {
  $("btn-open-map").addEventListener("click", () => {
    const input = $("snapshot-file");
    if (input) input.click();
  });
}
if ($("btn-save-routes")) {
  $("btn-save-routes").addEventListener("click", () => downloadNamed("/api/download/sol_network.csv", "sol_network.csv"));
}
if ($("btn-save-faction-routes")) {
  $("btn-save-faction-routes").addEventListener("click", () => downloadNamed("/api/download/route_table.csv", "route_table.csv"));
}

function applyTheme(name) {
  const theme = name === "dim" || name === "black" ? name : "light";
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("starroute-theme", theme); } catch { /* ignore */ }
  const select = $("color-theme");
  if (select) select.value = theme;
}

if ($("color-theme")) {
  let stored = "light";
  try { stored = localStorage.getItem("starroute-theme") || "light"; } catch { /* ignore */ }
  applyTheme(stored);
  $("color-theme").addEventListener("change", () => applyTheme($("color-theme").value));
}

if ($("btn-fullscreen")) {
  $("btn-fullscreen").addEventListener("click", () => {
    document.body.classList.toggle("map-fullscreen");
    const on = document.body.classList.contains("map-fullscreen");
    $("btn-fullscreen").setAttribute("aria-pressed", on ? "true" : "false");
    $("btn-fullscreen").setAttribute("aria-label", on ? "Exit full screen" : "Full screen");
    $("btn-fullscreen").title = on ? "Exit full screen" : "Full screen";
    window.setTimeout(resizeStarMap, 80);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && document.body.classList.contains("map-fullscreen")) {
      document.body.classList.remove("map-fullscreen");
      $("btn-fullscreen").setAttribute("aria-pressed", "false");
      $("btn-fullscreen").setAttribute("aria-label", "Full screen");
      $("btn-fullscreen").title = "Full screen";
      window.setTimeout(resizeStarMap, 80);
    }
  });
}

function showOpenedMap(map) {
  const select = $("map-preset");
  if (!select || !map) return;
  let opened = select.querySelector('option[value="opened"]');
  if (!opened) {
    opened = document.createElement("option");
    opened.value = "opened";
    select.insertBefore(opened, select.firstChild);
  }
  const count = map.payload && map.payload.nodes ? map.payload.nodes.length : 0;
  opened.textContent = `Your map (${count} stars)`;
  select.value = "opened";
  activePresetId = "opened";
  try { localStorage.removeItem("starroute-map-preset"); } catch { /* ignore */ }
  try {
    const url = new URL(window.location.href);
    if (url.searchParams.has("preset")) {
      url.searchParams.delete("preset");
      history.replaceState(null, "", url);
    }
  } catch { /* file:// */ }
}

async function boot() {
  showScreen("map");
  window.addEventListener("resize", resizeStarMap);
  $("btn-drawer").addEventListener("click", () => toggleDrawer());
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
  const select = $("map-preset");
  if (window.STARROUTE_DEFAULT_MAP && window.STARROUTE_DEFAULT_MAP.payload) {
    applyNetworkResult(window.STARROUTE_DEFAULT_MAP);
    showOpenedMap(window.STARROUTE_DEFAULT_MAP);
  }
  if (select) {
    select.addEventListener("change", async () => {
      const id = select.value;
      if (id === "opened") {
        if (window.STARROUTE_DEFAULT_MAP) {
          applyNetworkResult(window.STARROUTE_DEFAULT_MAP);
          showOpenedMap(window.STARROUTE_DEFAULT_MAP);
        }
        return;
      }
      try {
        await loadMapPreset(id);
      } catch (err) {
        toast(err.message, true);
        if (window.STARROUTE_DEFAULT_MAP) showOpenedMap(window.STARROUTE_DEFAULT_MAP);
      }
    });
  }
  try {
    await detectSources();
    factionConfig = await api("/api/factions");
    await ensurePresets();
    renderFactionEditor(factionConfig);
    $("ingest-min-mass").value = String(CATALOG_DEFAULTS.minSolarMass);
    if (lastSnapshot && lastSnapshot.params && lastSnapshot.params.min_stellar_mass != null) {
      $("net-min-mass").value = String(lastSnapshot.params.min_stellar_mass);
    } else {
      $("net-min-mass").value = String(NETWORK_DEFAULTS.minSolarMass);
    }
    document.body.classList.remove("no-backend");
    document.querySelectorAll(".tab.backend-only").forEach((tab) => {
      tab.classList.remove("is-disabled");
      tab.removeAttribute("aria-disabled");
      const later = tab.querySelector(".tab-later");
      if (later) later.remove();
    });
  } catch {
    document.body.classList.add("no-backend");
    const card = $("route-settings-card");
    const slot = $("drawer-route-slot");
    if (card && slot) slot.appendChild(card);
  }
  try {
    const screen = new URL(window.location.href).searchParams.get("screen");
    if (screen === "map" || screen === "factions" || screen === "ingest") showScreen(screen);
  } catch { /* ignore */ }
}

boot();
