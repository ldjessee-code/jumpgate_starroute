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
  const layout = $("map-layout");
  const btn = $("btn-drawer");
  if (!layout) return;
  const open = force === undefined ? !layout.classList.contains("drawer-open") : force;
  layout.classList.toggle("drawer-open", open);
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
      const focusOn = ($("focus-faction").value || "all") === g;
      rows.push(`<label class="legend-row${focusOn ? " is-focus" : ""}">
        <input type="color" class="legend-pick" data-group="${esc(g)}" value="${color}" title="Change ${esc(g)} color" />
        <span>${esc(g)}${focusOn ? " · highlighted" : ""}</span>
      </label>`);
    });
  } else {
    rows.push(`<div class="legend-row"><span class="legend-swatch heat"></span><span>Color = world score</span></div>`);
  }
  const focus = $("focus-faction") && $("focus-faction").value || "all";
  if (focus !== "all") {
    rows.push(`<div class="legend-row is-focus"><span class="legend-swatch" style="background:${getGroupColor(focus)};box-shadow:0 0 12px ${getGroupColor(focus)}"></span><span>Halo = ${esc(focus)}</span></div>`);
  }
  rows.push(`<div class="legend-row"><span class="legend-line"></span><span>Jump route</span></div>`);
  rows.push(`<div class="legend-row"><span class="legend-line path"></span><span>Highlighted path</span></div>`);
  box.innerHTML = `<p class="legend-title">Legend</p>${rows.join("")}`;
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
  const gxs = [];
  const gys = [];
  const gzs = [];
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
    const bothFocus = focus !== "all" && a.group === focus && b.group === focus;
    if (bothFocus) {
      gxs.push(a.x, b.x, null);
      gys.push(a.y, b.y, null);
      gzs.push(a.z, b.z, null);
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
  const haloNodes = focus === "all" ? [] : nodes.filter((n) => n.group === focus);
  const glowColor = focus === "all" ? "rgba(255,255,255,0.2)" : hexToRgba(getGroupColor(focus), 0.22);
  const glowLineColor = focus === "all" ? "rgba(255,255,255,0.18)" : hexToRgba(getGroupColor(focus), 0.2);
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
      x: gxs, y: gys, z: gzs,
      line: { color: glowLineColor, width: 14 },
      hoverinfo: "none",
      name: "Culture glow routes",
    },
    {
      type: "scatter3d",
      mode: "lines",
      x: xs, y: ys, z: zs,
      line: { color: focus === "all" ? "rgba(180,190,200,0.45)" : hexToRgba(getGroupColor(focus), 0.7), width: focus === "all" ? 2 : 3 },
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
      x: haloNodes.map((n) => n.x),
      y: haloNodes.map((n) => n.y),
      z: haloNodes.map((n) => n.z),
      hoverinfo: "none",
      marker: {
        size: haloNodes.map((n) => {
          const base = 5 + Math.min(n.sy_pnum || 0, 8) * 1.6;
          return Math.max(16, base * 2.8);
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
  const meta = MAP_PRESETS.find((item) => item.id === (data && data.id)) || MAP_PRESETS.find((item) => item.id === activePresetId);
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

$("btn-reset-ingest").addEventListener("click", () => {
  applyCatalogDefaults();
  toast("Choose-the-stars settings reset. File paths were left alone.");
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

function requestedPresetId() {
  try {
    const fromUrl = new URL(window.location.href).searchParams.get("preset");
    if (fromUrl && MAP_PRESETS.some((item) => item.id === fromUrl)) return fromUrl;
  } catch {
    /* ignore malformed URL */
  }
  try {
    const stored = localStorage.getItem("starroute-map-preset");
    if (stored && MAP_PRESETS.some((item) => item.id === stored)) return stored;
  } catch {
    /* ignore quota / private mode */
  }
  return "crowded";
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
  if (window.STARROUTE_DEFAULT_MAP) {
    applyNetworkResult({ ...window.STARROUTE_DEFAULT_MAP, id: window.STARROUTE_DEFAULT_MAP.id || "crowded" });
  }
  const presetId = requestedPresetId();
  if ($("map-preset")) {
    $("map-preset").value = presetId;
    $("map-preset").addEventListener("change", async () => {
      const id = $("map-preset").value;
      try {
        await loadMapPreset(id);
      } catch (err) {
        toast(err.message, true);
        $("map-preset").value = activePresetId;
      }
    });
  }
  if (presetId !== "crowded" || !window.STARROUTE_DEFAULT_MAP) {
    try {
      await loadMapPreset(presetId, { silent: true });
    } catch (err) {
      toast(err.message, true);
      if ($("map-preset")) $("map-preset").value = "crowded";
      rememberPreset("crowded");
    }
  } else {
    rememberPreset("crowded");
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
  }
}

boot();
