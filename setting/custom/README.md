# Custom lore (yours)

Put **your** Markdown here so it never mixes with the shipped Turquenish packs.

```
setting/custom/crowded/your-note.md
setting/custom/sparse/your-note.md
setting/custom/lonely_humans/your-note.md
```

Then:

```bash
python -m starroute build-lore
```

That copies into `starroute/web/static/docs/lore/pages/custom/`.

Visitors on GitHub Pages can also add/edit pages **in the browser**. Those copies
live in that browser only (`localStorage`), not in this folder, until someone
exports JSON and commits it here.

This `README.md` is not listed in the wiki index.
