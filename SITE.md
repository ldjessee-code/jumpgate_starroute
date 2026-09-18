# Public site (static)

Jumpgate Starroute publishes a **static** demo and docs site from `starroute/web/static/`.

Live: **https://ldjessee-code.github.io/jumpgate_starroute/**

- Map: `app.html` (Turquenish / sparse / lonely-humans packs; no Python)
- Docs: `docs/` (deploy, local run, presets, context help)
- Lore: `docs/lore/` (wiki follows the selected map pack; add/edit your own pages in the browser)
- Packs: `presets/{crowded,sparse,lonely_humans}/`

**Context help:** click **?** in the header, then click a control. HTML/CSS/JS only (`js/help.js`, `js/glossary.js`).

## GitHub Pages

Workflow `.github/workflows/pages.yml` deploys `starroute/web/static/` on push to `main`. Repo setting: Pages **source = GitHub Actions**.

- Home: https://ldjessee-code.github.io/jumpgate_starroute/
- Map: https://ldjessee-code.github.io/jumpgate_starroute/app.html
- Lore: https://ldjessee-code.github.io/jumpgate_starroute/docs/lore/

## Cloudflare Pages (optional)

Same publish directory: `starroute/web/static`. Empty build command.

## Local

See `starroute/web/static/docs/run-local.html`.
