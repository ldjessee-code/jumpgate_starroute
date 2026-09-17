---
title: How to contribute
order: 90
---

# How to contribute

This vault is flat files. No accounts, no in-browser editor.

## Add lore

1. Add a Markdown file under `setting/` (subfolders are allowed).
2. Optional front matter:

   ```markdown
   ---
   title: Comets
   order: 50
   ---
   ```

3. Rebuild the static index (no NASA data required):

   ```bash
   python -m starroute build-lore
   ```

4. Commit **both** the new `.md` and the generated copies under
   `starroute/web/static/docs/lore/`.

The public GitHub Pages site only publishes `starroute/web/static/`. The
builder copies vault pages there so visitors can read them without cloning
the repo.

## Style

- Keep pages short. Link instead of repeating the map docs.
- Catalog spellings (`tau Cet`, not “Tau Ceti”) match the map.
- Do not add Wiki.js, Docker wikis, or Obsidian as a runtime.

More detail: `docs/lore.html` on the static site, or `setting/README.md` in
the repo.
