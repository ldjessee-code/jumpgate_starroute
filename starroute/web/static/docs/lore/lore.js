(function () {
  const PACKS = [
    { id: "crowded", title: "Crowded — Turquenish neighborhood" },
    { id: "sparse", title: "Sparse — thin Turquenish grid" },
    { id: "lonely_humans", title: "Lonely humans" },
  ];
  const CUSTOM_KEY = "starroute-lore-custom";
  const PRESET_KEY = "starroute-map-preset";

  const listEl = document.getElementById("lore-list");
  const searchEl = document.getElementById("lore-search");
  const articleEl = document.getElementById("lore-article");
  const statusEl = document.getElementById("lore-status");
  const packEl = document.getElementById("lore-pack");
  const packNote = document.getElementById("lore-pack-note");
  const editorEl = document.getElementById("lore-editor");
  const editorTitle = document.getElementById("lore-editor-title");
  const editorNote = document.getElementById("lore-editor-note");
  const editorTitleInput = document.getElementById("lore-editor-title-input");
  const editorMd = document.getElementById("lore-editor-md");
  const editorPreview = document.getElementById("lore-editor-preview");
  const editorDelete = document.getElementById("lore-editor-delete");

  let shipped = { default: null, pages: [] };
  let customPages = [];
  let activeId = null;
  let editorState = null;

  const FACTION_COLOR_NAMES = [
    ["Turquenish Empire", "turquenish"],
    ["Mardat Coalition", "mardat"],
    ["Industrial Hegemony", "hegemony"],
    ["League of The Faithful", "faithful"],
    ["League of the Faithful", "faithful"],
    ["Other Human", "other-human"],
    ["Echryon & Echtol", "echryon"],
    ["Echryon/Echtol", "echryon"],
    ["Crystomorphs", "crystomorphs"],
    ["Aboreals", "aboreals"],
    ["Schettel", "schettel"],
    ["Faetheren", "faetheren"],
    ["Bazzar", "bazzar"],
    ["Methan", "methan"],
    ["Human", "human"],
  ];
  const COLOR_KEY = "starroute-lore-match-colors";

  function stripFrontMatter(text) {
    const raw = String(text || "").replace(/^\uFEFF/, "");
    if (!raw.startsWith("---")) return raw;
    const rest = raw.slice(3);
    const nl = rest.indexOf("\n");
    if (nl === -1) return raw;
    const close = rest.indexOf("\n---", nl);
    if (close === -1) return raw;
    let body = rest.slice(close + 4);
    if (body.startsWith("\n")) body = body.slice(1);
    return body;
  }

  function parseMarkdown(text) {
    const parse = (typeof marked === "function") ? marked : (marked && marked.parse);
    if (typeof parse !== "function") return "<p>Markdown library failed to load.</p>";
    return parse(stripFrontMatter(text));
  }

  function colorizeFactions(root) {
    if (!root || !document.body.classList.contains("lore-faction-colors")) return;
    const skip = "SCRIPT,STYLE,A,CODE,PRE,TEXTAREA";
    const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent || skip.includes(parent.tagName)) return NodeFilter.FILTER_REJECT;
        if (parent.closest(".fac")) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    const hits = [];
    let node;
    while ((node = walk.nextNode())) {
      const value = node.nodeValue;
      if (!value || !FACTION_COLOR_NAMES.some(([name]) => value.includes(name))) continue;
      hits.push(node);
    }
    hits.forEach((textNode) => {
      let html = textNode.nodeValue.replace(/[&<>]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[ch]));
      const tokens = [];
      FACTION_COLOR_NAMES.forEach(([name, slug]) => {
        const re = new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g");
        html = html.replace(re, () => {
          tokens.push(`<span class="fac fac-${slug}">${name}</span>`);
          return `\0${tokens.length - 1}\0`;
        });
      });
      html = html.replace(/\0(\d+)\0/g, (_, idx) => tokens[Number(idx)]);
      const wrap = document.createElement("span");
      wrap.innerHTML = html;
      textNode.parentNode.replaceChild(wrap, textNode);
    });
  }

  function matchColorsOn() {
    try {
      const stored = localStorage.getItem(COLOR_KEY);
      if (stored === "0") return false;
    } catch { /* ignore */ }
    return true;
  }

  function applyColorSetting(on) {
    document.body.classList.toggle("lore-faction-colors", on);
    try { localStorage.setItem(COLOR_KEY, on ? "1" : "0"); } catch { /* ignore */ }
  }

  function packOf(page) {
    if (page.pack && page.pack !== "custom" && page.pack !== "shared") return page.pack;
    const parts = (page.id || "").split("/");
    if (parts[0] === "user_setting" && PACKS.some((p) => p.id === parts[1])) return parts[1];
    if (parts[0] === "custom" && PACKS.some((p) => p.id === parts[1])) return parts[1];
    if (PACKS.some((p) => p.id === parts[0])) return parts[0];
    return "shared";
  }

  function currentPack() {
    return packEl.value || "crowded";
  }

  function rememberPack(id) {
    try { localStorage.setItem(PRESET_KEY, id); } catch { /* ignore */ }
  }

  function requestedPack() {
    try {
      const fromUrl = new URL(location.href).searchParams.get("pack");
      if (fromUrl && PACKS.some((p) => p.id === fromUrl)) return fromUrl;
    } catch { /* ignore */ }
    try {
      const stored = localStorage.getItem(PRESET_KEY);
      if (stored && PACKS.some((p) => p.id === stored)) return stored;
    } catch { /* ignore */ }
    return "crowded";
  }

  function loadCustom() {
    try {
      const raw = JSON.parse(localStorage.getItem(CUSTOM_KEY) || "{}");
      customPages = Array.isArray(raw.pages) ? raw.pages : [];
    } catch {
      customPages = [];
    }
  }

  function saveCustom() {
    localStorage.setItem(CUSTOM_KEY, JSON.stringify({ pages: customPages }));
  }

  function allPages() {
    return shipped.pages.concat(customPages);
  }

  function pageById(id) {
    return allPages().find((page) => page.id === id);
  }

  function visiblePages() {
    const pack = currentPack();
    const needle = (searchEl.value || "").trim().toLowerCase();
    return allPages().filter((page) => {
      const p = packOf(page);
      if (p === pack) return true;
      if (page.id === "contributing") return true;
      if (page.id === "source/player-intro" && pack !== "lonely_humans") return true;
      return false;
    }).filter((page) => {
      if (!needle) return true;
      return page.title.toLowerCase().includes(needle) || page.id.toLowerCase().includes(needle);
    });
  }

  function renderList() {
    listEl.innerHTML = "";
    const shown = visiblePages();
    if (!shown.length) {
      const empty = document.createElement("li");
      empty.className = "note";
      empty.textContent = "No matching titles in this pack.";
      listEl.appendChild(empty);
      return;
    }
    let lastGroup = "";
    shown.forEach((page) => {
      const group = page.custom ? "Your pages" : "This pack";
      if (group !== lastGroup) {
        const head = document.createElement("li");
        head.className = "lore-group";
        head.textContent = group;
        listEl.appendChild(head);
        lastGroup = group;
      }
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = "#" + encodeURIComponent(page.id);
      a.textContent = page.title;
      a.dataset.id = page.id;
      if (page.id === activeId) a.classList.add("is-active");
      li.appendChild(a);
      listEl.appendChild(li);
    });
  }

  function rewriteWikiLinks(root) {
    root.querySelectorAll("a[href]").forEach((anchor) => {
      const href = anchor.getAttribute("href") || "";
      if (/^(https?:|mailto:|#)/i.test(href)) return;
      const clean = href.split("#")[0].split("?")[0];
      if (!clean.toLowerCase().endsWith(".md")) return;
      const base = (activeId && activeId.includes("/"))
        ? activeId.slice(0, activeId.lastIndexOf("/") + 1)
        : "";
      let target = (base + clean).replace(/\\/g, "/");
      while (target.includes("/../")) target = target.replace(/[^/]+\/\.\.\//, "");
      target = target.replace(/^\.\//, "");
      if (target.toLowerCase().endsWith(".md")) target = target.slice(0, -3);
      if (pageById(target)) anchor.setAttribute("href", "#" + encodeURIComponent(target));
    });
  }

  async function markdownFor(page) {
    if (page.custom && page.markdown != null) return page.markdown;
    const res = await fetch(page.path, { cache: "no-cache" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return await res.text();
  }

  async function loadPage(id) {
    const page = pageById(id);
    if (!page) {
      articleEl.innerHTML = "<p class='note'>That page is not in this pack’s lore.</p>";
      statusEl.textContent = "";
      return;
    }
    activeId = page.id;
    renderList();
    statusEl.textContent = "Loading…";
    try {
      const markdown = await markdownFor(page);
      articleEl.innerHTML = parseMarkdown(markdown);
      colorizeFactions(articleEl);
      rewriteWikiLinks(articleEl);
      statusEl.textContent = page.custom
        ? "Your page (this browser) · " + page.id
        : page.source;
      document.title = page.title + " · Lore · Jumpgate Starroute";
    } catch (err) {
      articleEl.innerHTML =
        "<p class='note'>Could not load that page. Serve this folder with a static server " +
        "(<code>python -m http.server</code> in <code>starroute/web/static</code>).</p><pre>" +
        String(err && err.message ? err.message : err) + "</pre>";
      statusEl.textContent = "";
    }
  }

  function requestedId() {
    const hash = decodeURIComponent((location.hash || "").replace(/^#/, "")).trim();
    if (hash && pageById(hash) && visiblePages().some((p) => p.id === hash)) return hash;
    const pack = currentPack();
    const overview = pageById(pack + "/overview");
    if (overview) return overview.id;
    const first = visiblePages()[0];
    return first && first.id;
  }

  function slugify(title) {
    return (title || "page").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "page";
  }

  function previewEditor() {
    editorPreview.innerHTML = parseMarkdown(editorMd.value);
    colorizeFactions(editorPreview);
  }

  function openEditor({ mode, page, markdown }) {
    editorState = { mode, page };
    editorEl.classList.remove("hidden");
    if (mode === "new") {
      editorTitle.textContent = "Add a page";
      editorNote.textContent = "Saved in this browser under the current map pack. Does not change shipped setting/ files.";
      editorTitleInput.value = "";
      editorMd.value = "# New page\n\n";
      editorDelete.classList.add("hidden");
    } else if (mode === "copy") {
      editorTitle.textContent = "Edit a copy";
      editorNote.textContent = "Shipped lore stays as-is. This saves a copy in this browser for pack “" + currentPack() + "”.";
      editorTitleInput.value = page.title;
      editorMd.value = markdown || "";
      editorDelete.classList.add("hidden");
    } else {
      editorTitle.textContent = "Edit your page";
      editorNote.textContent = "This page lives in this browser, not in the git vault.";
      editorTitleInput.value = page.title;
      editorMd.value = markdown || page.markdown || "";
      editorDelete.classList.remove("hidden");
    }
    previewEditor();
    editorTitleInput.focus();
  }

  function closeEditor() {
    editorEl.classList.add("hidden");
    editorState = null;
  }

  async function startEdit() {
    const page = pageById(activeId);
    if (!page) return;
    if (page.custom) {
      openEditor({ mode: "edit", page, markdown: page.markdown });
      return;
    }
    const markdown = await markdownFor(page);
    openEditor({ mode: "copy", page, markdown });
  }

  function saveEditor() {
    const title = (editorTitleInput.value || "").trim() || "Untitled";
    const markdown = editorMd.value || "";
    const pack = currentPack();
    if (!editorState) return;
    if (editorState.mode === "edit" && editorState.page && editorState.page.custom) {
      editorState.page.title = title;
      editorState.page.markdown = markdown;
      editorState.page.updated = new Date().toISOString();
    } else {
      const base = editorState.page && !editorState.page.custom
        ? editorState.page.id.split("/").pop()
        : slugify(title);
      let id = "custom/" + pack + "/" + base;
      let n = 2;
      while (customPages.some((p) => p.id === id)) {
        id = "custom/" + pack + "/" + base + "-" + n;
        n += 1;
      }
      customPages.push({
        id,
        pack,
        title,
        markdown,
        custom: true,
        updated: new Date().toISOString(),
      });
      activeId = id;
    }
    saveCustom();
    closeEditor();
    renderList();
    loadPage(activeId);
    if (location.hash !== "#" + activeId) location.hash = activeId;
  }

  function deleteEditor() {
    if (!editorState || !editorState.page || !editorState.page.custom) return;
    customPages = customPages.filter((p) => p.id !== editorState.page.id);
    saveCustom();
    closeEditor();
    activeId = requestedId();
    renderList();
    if (activeId) loadPage(activeId);
  }

  function importFiles(files) {
    const pack = currentPack();
    const readers = [...files].map((file) => new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve({ name: file.name, text: String(reader.result || "") });
      reader.onerror = () => reject(reader.error);
      reader.readAsText(file);
    }));
    Promise.all(readers).then((items) => {
      items.forEach((item) => {
        if (item.name.toLowerCase().endsWith(".json")) {
          try {
            const data = JSON.parse(item.text);
            const pages = Array.isArray(data.pages) ? data.pages : [];
            pages.forEach((page) => {
              if (!page || !page.markdown) return;
              const id = page.id || ("custom/" + pack + "/" + slugify(page.title || item.name));
              customPages = customPages.filter((p) => p.id !== id);
              customPages.push({
                id,
                pack: page.pack || pack,
                title: page.title || id,
                markdown: page.markdown,
                custom: true,
                updated: new Date().toISOString(),
              });
            });
          } catch { /* skip bad json */ }
          return;
        }
        const stem = item.name.replace(/\.(md|markdown)$/i, "");
        const id = "custom/" + pack + "/" + slugify(stem);
        const heading = (item.text.match(/^#\s+(.+)$/m) || [])[1];
        customPages = customPages.filter((p) => p.id !== id);
        customPages.push({
          id,
          pack,
          title: heading || stem,
          markdown: item.text,
          custom: true,
          updated: new Date().toISOString(),
        });
      });
      saveCustom();
      renderList();
      if (customPages.length) loadPage(customPages[customPages.length - 1].id);
    });
  }

  function exportCustom() {
    const pack = currentPack();
    const pages = customPages.filter((p) => p.pack === pack);
    const blob = new Blob([JSON.stringify({ pack, pages }, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "starroute-lore-" + pack + ".json";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function loadIndex() {
    if (window.STARROUTE_LORE_INDEX && window.STARROUTE_LORE_INDEX.pages) {
      return window.STARROUTE_LORE_INDEX;
    }
    const res = await fetch("index.json", { cache: "no-cache" });
    if (!res.ok) throw new Error("Could not load lore index.json (" + res.status + ")");
    return res.json();
  }

  async function boot() {
    packEl.innerHTML = PACKS.map((p) => `<option value="${p.id}">${p.title}</option>`).join("");
    packEl.value = requestedPack();
    rememberPack(packEl.value);
    packNote.textContent = "Follows the map pack saved in this browser.";
    const colorBox = document.getElementById("lore-match-colors");
    const colorsOn = matchColorsOn();
    applyColorSetting(colorsOn);
    if (colorBox) {
      colorBox.checked = colorsOn;
      colorBox.addEventListener("change", () => {
        applyColorSetting(colorBox.checked);
        if (activeId) loadPage(activeId);
      });
    }
    loadCustom();
    try {
      shipped = await loadIndex();
      if (!shipped.pages) shipped.pages = [];
    } catch (err) {
      articleEl.innerHTML =
        "<p class='note'>The lore index is missing. Rebuild with " +
        "<code>python -m starroute build-lore</code>.</p><pre>" +
        String(err && err.message ? err.message : err) + "</pre>";
      return;
    }
    renderList();
    const id = requestedId();
    if (id) await loadPage(id);
  }

  searchEl.addEventListener("input", renderList);
  packEl.addEventListener("change", () => {
    rememberPack(packEl.value);
    const id = requestedId();
    if (id && location.hash !== "#" + id) location.hash = id;
    else if (id) loadPage(id);
    else renderList();
  });
  listEl.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-id]");
    if (!link) return;
    event.preventDefault();
    const id = link.dataset.id;
    if (location.hash !== "#" + id) location.hash = id;
    else loadPage(id);
  });
  window.addEventListener("hashchange", () => {
    const id = requestedId();
    if (id) loadPage(id);
  });
  document.getElementById("btn-lore-new").addEventListener("click", () => {
    openEditor({ mode: "new" });
  });
  document.getElementById("btn-lore-edit").addEventListener("click", () => {
    startEdit().catch((err) => { statusEl.textContent = err.message; });
  });
  document.getElementById("lore-import").addEventListener("change", (event) => {
    importFiles(event.target.files || []);
    event.target.value = "";
  });
  document.getElementById("btn-lore-export").addEventListener("click", exportCustom);
  document.getElementById("lore-editor-close").addEventListener("click", closeEditor);
  document.getElementById("lore-editor-save").addEventListener("click", saveEditor);
  document.getElementById("lore-editor-delete").addEventListener("click", deleteEditor);
  editorMd.addEventListener("input", previewEditor);
  editorEl.addEventListener("click", (event) => {
    if (event.target === editorEl) closeEditor();
  });

  boot();
})();
