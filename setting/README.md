# Setting vault

Turquenish–Mardat lore, split to match the three map packs.

| Folder | Map pack | Pitch |
| --- | --- | --- |
| `crowded/` | crowded | Dense Turquenish neighborhood. Short jumps. Local aliens. Default tabletop. |
| `sparse/` | sparse | Same war, thinner gate grid, longer hops. |
| `lonely_humans/` | lonely_humans | Sun-like stars, human factions only. |
| `custom/{pack}/` | custom | Your pages, kept separate from shipped lore. |
| `source/` | — | Copies of the tabletop notes (text only). |

`README.md` here is not in the wiki index. Other `setting/**/*.md` files are.

Tabletop originals live at `F:\Dropbox\Gaming\GURPS Turquenish-Mardat War\`.
This repo copies **lore text** only (no player `.gca5` sheets, no screenshots).

After editing Markdown:

```bash
python -m starroute build-lore
```
