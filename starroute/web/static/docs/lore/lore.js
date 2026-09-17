(function () {
  const listEl = document.getElementById("lore-list");
  const searchEl = document.getElementById("lore-search");
  const articleEl = document.getElementById("lore-article");
  const statusEl = document.getElementById("lore-status");

  let index = { default: null, pages: [] };
  let activeId = null;

  function pageById(id) {
    return index.pages.find((page) => page.id === id);
  }

  function requestedId() {
    const hash = (location.hash || "").replace(/^#/, "").trim();
    if (hash && pageById(hash)) return hash;
    if (index.default && pageById(index.default)) return index.default;
    return index.pages[0] && index.pages[0].id;
  }

  function renderList(filter) {
    const needle = (filter || "").trim().toLowerCase();
    listEl.innerHTML = "";
    const shown = index.pages.filter((page) => {
      if (!needle) return true;
      return (
        page.title.toLowerCase().includes(needle) ||
        page.id.toLowerCase().includes(needle)
      );
    });
    if (!shown.length) {
      const empty = document.createElement("li");
      empty.className = "note";
      empty.textContent = "No matching titles.";
      listEl.appendChild(empty);
      return;
    }
    shown.forEach((page) => {
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
      while (target.includes("/../")) {
        target = target.replace(/[^/]+\/\.\.\//, "");
      }
      target = target.replace(/^\.\//, "");
      if (target.toLowerCase().endsWith(".md")) target = target.slice(0, -3);
      if (pageById(target)) {
        anchor.setAttribute("href", "#" + encodeURIComponent(target));
      }
    });
  }

  async function loadPage(id) {
    const page = pageById(id);
    if (!page) {
      articleEl.innerHTML = "<p class='note'>That page is not in the lore index.</p>";
      statusEl.textContent = "";
      return;
    }
    activeId = page.id;
    renderList(searchEl.value);
    statusEl.textContent = "Loading…";
    try {
      const res = await fetch(page.path, { cache: "no-cache" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const markdown = await res.text();
      const parse = (typeof marked === "function")
        ? marked
        : (marked && marked.parse);
      if (typeof parse !== "function") {
        throw new Error("Markdown library failed to load.");
      }
      articleEl.innerHTML = parse(markdown);
      rewriteWikiLinks(articleEl);
      statusEl.textContent = page.source;
      document.title = page.title + " · Lore · Jumpgate Starroute";
    } catch (err) {
      articleEl.innerHTML =
        "<p class='note'>Could not load that page. Serve this folder with a static server " +
        "(<code>python -m http.server</code> in <code>starroute/web/static</code>) " +
        "instead of opening the file directly.</p><pre>" +
        String(err && err.message ? err.message : err) +
        "</pre>";
      statusEl.textContent = "";
    }
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
    try {
      index = await loadIndex();
      if (!index.pages) index.pages = [];
    } catch (err) {
      articleEl.innerHTML =
        "<p class='note'>The lore index is missing. Rebuild with " +
        "<code>python -m starroute build-lore</code> and keep " +
        "<code>docs/lore/index.json</code> next to this page.</p><pre>" +
        String(err && err.message ? err.message : err) +
        "</pre>";
      return;
    }
    renderList("");
    await loadPage(requestedId());
  }

  searchEl.addEventListener("input", () => renderList(searchEl.value));
  listEl.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-id]");
    if (!link) return;
    event.preventDefault();
    const id = link.dataset.id;
    if (location.hash !== "#" + id) location.hash = id;
    else loadPage(id);
  });
  window.addEventListener("hashchange", () => loadPage(requestedId()));

  boot();
})();
