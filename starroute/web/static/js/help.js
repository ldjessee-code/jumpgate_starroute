/** Click “?” then click a control. Pure HTML/CSS/JS — no extra libraries. */
(function () {
  const Help = { inspect: false };

  function termById(id) {
    if (typeof GLOSSARY_BY_ID !== "undefined" && GLOSSARY_BY_ID[id]) return GLOSSARY_BY_ID[id];
    return null;
  }

  function docsUrl(page) {
    const p = (location.pathname || "").replace(/\\/g, "/");
    if (/\/docs\/lore(\/|$)/.test(p)) return "../" + page;
    if (/\/docs(\/|$)/.test(p)) return page;
    return "docs/" + page;
  }

  function rewriteDocLinks(html) {
    return String(html || "").replace(/href="docs\/([^"]+)"/g, (_, file) => `href="${docsUrl(file)}"`);
  }

  function termHtml(term) {
    if (!term) return "<p>No help is available for that item yet.</p>";
    const also = term.alsoCalled ? `<p class="also">Also called: ${term.alsoCalled}</p>` : "";
    const impact = term.impact
      ? `<p class="impact"><strong>If you change it:</strong> ${rewriteDocLinks(term.impact)}</p>`
      : "";
    return `<h3>${term.title}</h3>${also}<p>${rewriteDocLinks(term.meaning)}</p>${impact}`;
  }

  function ensurePop() {
    let pop = document.getElementById("term-pop");
    if (!pop) {
      pop = document.createElement("div");
      pop.id = "term-pop";
      pop.className = "term-pop hidden";
      pop.setAttribute("role", "dialog");
      pop.setAttribute("aria-live", "polite");
      document.body.appendChild(pop);
    }
    return pop;
  }

  function ensureHint() {
    let hint = document.getElementById("help-hint");
    if (!hint) {
      hint = document.createElement("div");
      hint.id = "help-hint";
      hint.className = "help-hint hidden";
      hint.setAttribute("role", "status");
      hint.textContent = "Help mode: click a control, the map, or a heading. Esc or ? again to stop.";
      document.body.appendChild(hint);
    }
    return hint;
  }

  function hidePop() {
    const pop = document.getElementById("term-pop");
    if (pop) pop.classList.add("hidden");
  }

  function placePop(pop, x, y) {
    pop.classList.remove("hidden");
    const width = pop.offsetWidth;
    const height = pop.offsetHeight;
    const left = Math.min(Math.max(8, x), window.innerWidth - width - 8);
    let top = y + 12;
    if (top + height > window.innerHeight - 8) top = Math.max(8, y - height - 12);
    pop.style.left = `${left}px`;
    pop.style.top = `${top}px`;
  }

  function showTerm(id, x, y) {
    const pop = ensurePop();
    pop.innerHTML = termHtml(termById(id));
    placePop(pop, x, y);
  }

  function idFromNode(el) {
    if (!el || !el.closest) return null;
    const hit = el.closest("[data-help], [data-term]");
    if (!hit) return null;
    return hit.getAttribute("data-help") || hit.getAttribute("data-term");
  }

  function helpIdFrom(el, event) {
    const direct = idFromNode(el);
    if (direct) return direct;
    if (!event || !document.elementsFromPoint) return null;
    for (const node of document.elementsFromPoint(event.clientX, event.clientY)) {
      const id = idFromNode(node);
      if (id) return id;
    }
    return null;
  }

  function makeHelpButton() {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.id = "btn-context-help";
    btn.className = "help-mode-btn";
    btn.setAttribute("aria-pressed", "false");
    btn.setAttribute("aria-label", "Context help. Click, then click something on the page.");
    btn.title = "Click, then click a control, the map, or a heading";
    btn.setAttribute("data-help", "contextHelp");
    btn.textContent = "?";
    return btn;
  }

  function ensureHelpButton() {
    if (document.getElementById("btn-context-help")) return;
    const btn = makeHelpButton();
    const row = document.querySelector(".header-help-row");
    if (row) {
      row.insertBefore(btn, row.firstChild);
      return;
    }
    const header = document.querySelector("header");
    if (!header) return;
    let tools = header.querySelector(".header-tools");
    if (!tools) {
      tools = document.createElement("div");
      tools.className = "header-tools";
      header.appendChild(tools);
    }
    tools.appendChild(btn);
  }

  function setInspect(on) {
    Help.inspect = !!on;
    document.body.classList.toggle("help-inspect", Help.inspect);
    document.querySelectorAll("#btn-context-help").forEach((btn) => {
      btn.setAttribute("aria-pressed", Help.inspect ? "true" : "false");
      btn.classList.toggle("is-active", Help.inspect);
    });
    const hint = ensureHint();
    hint.classList.toggle("hidden", !Help.inspect);
    if (!Help.inspect) hidePop();
  }

  function onClick(event) {
    const helpBtn = event.target.closest && event.target.closest("#btn-context-help");
    if (helpBtn) {
      event.preventDefault();
      event.stopPropagation();
      setInspect(!Help.inspect);
      return;
    }
    if (event.target.closest && event.target.closest("#term-pop")) return;

    if (Help.inspect) {
      const id = helpIdFrom(event.target, event);
      event.preventDefault();
      event.stopPropagation();
      if (id) {
        showTerm(id, event.clientX, event.clientY);
      } else {
        showTerm("contextHelpMiss", event.clientX, event.clientY);
      }
      return;
    }

    const info = event.target.closest && event.target.closest("button.info, [data-term].info");
    if (info) {
      event.preventDefault();
      event.stopPropagation();
      const id = info.getAttribute("data-term") || info.getAttribute("data-help");
      const rect = info.getBoundingClientRect();
      showTerm(id, rect.left, rect.bottom);
      return;
    }

    const pop = document.getElementById("term-pop");
    if (pop && !pop.classList.contains("hidden") && !pop.contains(event.target)) hidePop();
  }

  function onKey(event) {
    if (event.key === "Escape") {
      hidePop();
      setInspect(false);
    }
    if (event.key === "?" && !event.ctrlKey && !event.metaKey && !event.altKey) {
      const tag = (event.target && event.target.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || event.target.isContentEditable) return;
      event.preventDefault();
      setInspect(!Help.inspect);
    }
  }

  document.addEventListener("click", onClick, true);
  document.addEventListener("keydown", onKey);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ensureHelpButton);
  } else {
    ensureHelpButton();
  }
  window.StarrouteHelp = { setInspect, showTerm, helpIdFrom };
})();
