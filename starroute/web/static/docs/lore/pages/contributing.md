---
title: How to contribute
order: 90
---

# How to contribute

Flat files. No accounts, no in-browser editor.

## Which pack?

Put Turquenish-neighborhood text under `setting/crowded/`. Thin-grid
variants under `setting/sparse/`. Human-only expansion under
`setting/lonely_humans/`. Shareable tabletop notes (no char sheets) go in
`setting/source/` as `.txt` if they should stay out of the wiki index.

## Add a page

1. Create `setting/.../your-topic.md`.
2. Optional front matter:

   ```markdown
   ---
   title: Comets
   order: 50
   ---
   ```

3. Rebuild:

   ```bash
   python -m starroute build-lore
   ```

4. Commit the new `.md` **and** `starroute/web/static/docs/lore/`.

If you change who lives on the map, edit `config/map_presets.json` and run
`python -m starroute build-presets` as well.
