# Your setting files

This folder is **yours**. It is not Lloyd Jessee’s Turquenish lore and it is
not covered by the MIT software license unless you say so.

Put Markdown here so it never mixes with `setting/`:

```
user_setting/crowded/your-note.md
user_setting/sparse/your-note.md
user_setting/lonely_humans/your-note.md
```

Then:

```bash
python -m starroute build-lore
```

That copies into `starroute/web/static/docs/lore/pages/user_setting/`.

You choose the license for files you add here. If you commit them to a public
fork, say so in a `COPYRIGHT.md` of your own in this folder.

Browser-only edits (Lore → Add/Edit) stay in that browser until you Export
JSON or copy Markdown into this folder.

This `README.md` is not listed in the wiki index.
