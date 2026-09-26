/** Home, Docs, and Map. The other guides are cards on the docs page. */
(function () {
  const LINKS = [
    { href: "index.html", label: "Home", match: "home" },
    { href: "docs/index.html", label: "Docs", match: "docs-index" },
    { href: "app.html", label: "Map", match: "map" },
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
    if (/\/app\.html$/.test(p)) return "map";
    if (/\/docs(\/|$)/.test(p)) return "docs-index";
    if (/\/(index\.html)?$/.test(p)) return "home";
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
    const onServer = path().startsWith("/static/") || pre === "/static/";
    nav.innerHTML = LINKS.map((link) => {
      let href = pre + link.href;
      if (link.match === "map" && onServer) href = "/";
      if (link.match === "home" && onServer) href = "/static/index.html";
      const current = link.match === here;
      return `<a href="${href}"${current ? ' aria-current="page"' : ""}>${link.label}</a>`;
    }).join("");
  }

  function brandInner(pre) {
    const img = (pre || "") + "img/true-eyed-jack.svg";
    return (
      `<img src="${img}" alt="" width="36" height="36" />` +
      "<span>A True Eyed Jack app: Local First. Always Intelligent.</span>"
    );
  }

  function brandHtml(pre) {
    return (
      '<a class="tej-brand" href="https://trueeyedjack.com/" target="_blank" rel="noopener noreferrer">' +
      brandInner(pre) +
      "</a>"
    );
  }

  function preFromNav() {
    const nav = document.querySelector("[data-site-nav]");
    return nav && nav.getAttribute("data-root") !== null ? nav.getAttribute("data-root") : prefix();
  }

  function addFavicons(pre) {
    if (document.querySelector("link[data-tej-icon]")) return;
    [
      { rel: "icon", type: "image/png", sizes: "32x32", href: (pre || "") + "img/favicon-32.png" },
      { rel: "icon", type: "image/png", sizes: "16x16", href: (pre || "") + "img/favicon-16.png" },
      { rel: "apple-touch-icon", href: (pre || "") + "img/apple-touch-icon.png" },
    ].forEach((spec) => {
      const link = document.createElement("link");
      Object.entries(spec).forEach(([key, value]) => link.setAttribute(key, value));
      link.setAttribute("data-tej-icon", "1");
      document.head.appendChild(link);
    });
  }

  function fillBrand() {
    const pre = preFromNav();
    const html = brandHtml(pre);
    document.querySelectorAll("[data-tej-brand]").forEach((el) => {
      if (el.tagName === "A") {
        el.href = "https://trueeyedjack.com/";
        el.target = "_blank";
        el.rel = "noopener noreferrer";
        el.classList.add("tej-brand");
        if (!el.querySelector("img")) el.innerHTML = brandInner(pre);
        return;
      }
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

  function applyStoredTheme() {
    let theme = "light";
    try { theme = localStorage.getItem("starroute-theme") || "light"; } catch { /* ignore */ }
    if (theme !== "dim" && theme !== "black") theme = "light";
    document.documentElement.dataset.theme = theme;
  }

  function ensureFooter() {
    if (document.body.classList.contains("map-first")) return;
    let foot = document.querySelector("footer");
    if (!foot) {
      foot = document.createElement("footer");
      document.body.appendChild(foot);
    }
    foot.className = "site-foot";
    foot.innerHTML =
      '<div class="foot-left"><a class="tej-brand" data-tej-brand href="https://trueeyedjack.com/" target="_blank" rel="noopener noreferrer"></a>' +
      '<a href="https://github.com/ldjessee-code/jumpgate_starroute/blob/main/LICENSE">MIT License</a></div>' +
      '<p class="foot-mid">Turquenish setting, characters, and fiction © Lloyd Douglass Jessee 2025–2026</p>' +
      '<p class="foot-right">v2.0 · GM / author tool</p>';
  }

  function boot() {
    applyStoredTheme();
    ensureFooter();
    if (!document.body.classList.contains("map-first") && !document.querySelector("link[data-starroute-chrome]")) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = (preFromNav() || "") + "css/chrome.css";
      link.setAttribute("data-starroute-chrome", "1");
      document.head.appendChild(link);
    }
    document.querySelectorAll("[data-site-nav]").forEach(fill);
    fillBrand();
    addFavicons(preFromNav());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
