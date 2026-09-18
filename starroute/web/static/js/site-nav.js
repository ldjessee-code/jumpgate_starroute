/** Shared Home / Docs / Map / Lore / Deploy / Run locally / Presets links. */
(function () {
  const LINKS = [
    { href: "index.html", label: "Home", match: "home" },
    { href: "docs/index.html", label: "Docs", match: "docs-index" },
    { href: "app.html", label: "Map", match: "map" },
    { href: "docs/lore/", label: "Lore", match: "lore" },
    { href: "docs/deploy.html", label: "Deploy", match: "deploy" },
    { href: "docs/run-local.html", label: "Run locally", match: "run-local" },
    { href: "docs/presets.html", label: "Presets", match: "presets" },
  ];

  function path() {
    return (location.pathname || "").replace(/\\/g, "/");
  }

  function prefix() {
    const p = path();
    if (/\/docs\/lore(\/|$)/.test(p)) return "../../";
    if (/\/docs(\/|$)/.test(p)) return "../";
    return "";
  }

  function currentMatch() {
    const p = path();
    if (/\/docs\/help\.html$/.test(p)) return "docs-index";
    if (/\/docs\/lore(\/|$)/.test(p) || /\/docs\/lore\.html$/.test(p)) return "lore";
    if (/\/app\.html$/.test(p)) return "map";
    if (/\/docs\/deploy\.html$/.test(p)) return "deploy";
    if (/\/docs\/run-local\.html$/.test(p)) return "run-local";
    if (/\/docs\/presets\.html$/.test(p)) return "presets";
    if (/\/docs\/(index\.html)?$/.test(p)) return "docs-index";
    return "home";
  }

  function fill(nav) {
    nav.style.display = "flex";
    nav.style.flexWrap = "wrap";
    nav.style.gap = "0.35rem 1rem";
    const attr = nav.getAttribute("data-root");
    const pre = attr !== null ? attr : prefix();
    const here = document.body.classList.contains("map-first") ? "map" : currentMatch();
    nav.innerHTML = LINKS.map((link) => {
      let href = pre + link.href;
      if (link.match === "map" && pre === "/static/") href = "/";
      const current = link.match === here;
      return `<a href="${href}"${current ? ' aria-current="page"' : ""}>${link.label}</a>`;
    }).join("");
  }

  function boot() {
    document.querySelectorAll("[data-site-nav]").forEach(fill);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
