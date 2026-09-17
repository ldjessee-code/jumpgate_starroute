# Setting vault

Ordinary Markdown files for Jumpgate lore. There is no Wiki.js, Obsidian, or
database here.

The static site lists these pages from a committed index and renders them in
the browser:

- Viewer: `starroute/web/static/docs/lore/index.html`
- How to add a page: `starroute/web/static/docs/lore.html`

`README.md` in this folder is for people cloning the repo. It is **not**
copied into the wiki index. Everything else matching `setting/**/*.md` is.

## Add a page

1. Create `setting/your-topic.md` (subfolders are fine).
2. Optional front matter:

   ```markdown
   ---
   title: Your topic
   order: 40
   ---

   # Your topic
   ```

   Without front matter, the first `# heading` (or the file name) is the title.
3. Regenerate the index (stdlib Python; no NASA CSVs, no pandas):

   ```bash
   python -m starroute build-lore
   # or: python scripts/build_lore.py
   ```

4. Commit the new `.md` plus the updated files under
   `starroute/web/static/docs/lore/`.
