/** Shared Home / Docs / Map / Lore / Deploy / Run locally / Presets links. */
(function () {
  const LINKS = [
    { href: "index.html", label: "Home", match: "home" },
    { href: "docs/index.html", label: "Docs", match: "docs-index" },
    { href: "app.html", label: "Map", match: "map" },
    { href: "docs/lore/", label: "Lore", match: "lore" },
    { href: "docs/deploy.html", label: "Deploy", match: "deploy" },
    { href: "docs/self-host.html", label: "Self-host", match: "self-host" },
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
    if (/\/docs\/self-host\.html$/.test(p)) return "self-host";
    if (/\/docs\/own-setting\.html$/.test(p)) return "docs-index";
    if (/\/docs\/run-local\.html$/.test(p)) return "run-local";
    if (/\/docs\/presets\.html$/.test(p)) return "presets";
    if (/\/docs\/(index\.html)?$/.test(p)) return "docs-index";
    return "home";
  }

  function fill(nav) {
    nav.style.display = "flex";
    nav.style.flexWrap = "wrap";
    nav.style.gap = "0.35rem 1rem";
    nav.style.width = "fit-content";
    nav.style.maxWidth = "100%";
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

  function brandHtml(pre) {
    const img = (pre || "") + "img/true-eyed-jack.svg";
    return (
      '<a class="tej-brand" href="https://trueeyedjack.com/" rel="noopener noreferrer">' +
      `<img src="${img}" alt="True Eyed Jack" width="36" height="36" />` +
      "<span>A True Eyed Jack app: Local First, Always Intelligent.</span>" +
      "</a>"
    );
  }

  function fillBrand() {
    const nav = document.querySelector("[data-site-nav]");
    const pre = nav && nav.getAttribute("data-root") !== null ? nav.getAttribute("data-root") : prefix();
    const html = brandHtml(pre);
    document.querySelectorAll("[data-tej-brand]").forEach((el) => {
      el.innerHTML = html;
    });
    document.querySelectorAll("footer").forEach((foot) => {
      if (foot.querySelector(".tej-brand")) return;
      const p = document.createElement("p");
      p.className = "tej-wrap";
      p.innerHTML = html;
      foot.insertBefore(p, foot.firstChild);
    });
  }

  function boot() {
    document.querySelectorAll("[data-site-nav]").forEach(fill);
    fillBrand();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
