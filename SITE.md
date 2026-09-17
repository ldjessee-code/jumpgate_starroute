# Public site (static)

Jumpgate Starroute publishes a **static** demo and docs site from `starroute/web/static/`.

- Map viewer: `app.html` (preset picker; no Python)
- Docs: `docs/` (deploy strategies + local run on Windows / macOS / Linux; browser notes for Chrome, ChromeOS, Android)
- Packs: `presets/{crowded,sparse,lonely_humans}/`

## GitHub Pages

A workflow at `.github/workflows/pages.yml` deploys that folder on pushes to `main`.

One-time repo setting: Pages **source = GitHub Actions**. After merge to `main`, the site is typically:

`https://ldjessee-code.github.io/jumpgate_starroute/`

## Cloudflare Pages (optional)

Same publish directory: `starroute/web/static`. Empty build command.

## Local

See `starroute/web/static/docs/run-local.html`.
