# Jumpgate Starroute map presets

Three pre-generated **network snapshots** (JSON, not 3D models) for static hosting.
Viewers open `starroute/web/static/app.html` and switch packs in the map toolbar.
No live Python server is required to look at or switch maps.

## Catalog

data/raw NASA CSVs were missing; used the committed 60 ly sample catalog (starroute/web/static/sample-systems.csv).

Regenerate after editing `config/map_presets.json`:

```bash
python -m starroute build-presets
# or: python scripts/build_presets.py
```

Packs are written to `data/presets/{id}/map.json` and copied to
`starroute/web/static/presets/{id}/` for the static viewer.

## Quality targets

- About **30–100** systems in the largest connected component.
- At least **~75%** of *linked* systems habitable by someone under that pack’s
  faction/habitat rules (a non-empty culture `group` after assignment).
- NASA carbon/sulfur/gas flags on the 60 ly sample are sparse; those counts are
  reported separately and are **not** the 75% metric. Best NASA-flag rate on this
  sample is **63 / 148** catalog stars (42.6%). The knobs below still meet 75%
  under pack assignment rules.

## `crowded` — Crowded neighborhood

Dense local space. Small stars stay on the map; jumps are short. Humans share the neighborhood with methane-breathers, living crystal, and hot-world gas-giant people.

- Catalog source: **sample**
- Knobs: min/max stellar mass 0.25 M☉; max jump **16 ly**;
  max neighbors 6; linked cap 80;
  short/medium 40% / long 60%.
- Snapshot nodes: **90** (205 jump edges).
- Linked / largest component: **90** / **90**.
- Habitable by someone (linked, pack rules): **90** (100.0%).
- Cultures on the grid: Human 41, Kessari 17, Crystomorphs 16, Methan 16.
- NASA habitat flags on linked systems: carbon-zone 7, sulfur-zone 15, gas-giant 36 (any of those: 36).

## `sparse` — Sparse neighborhood

Fewer stars: the smallest red dwarfs are dropped. Jumps run longer so the remaining systems still form one network. Several habitat classes remain.

- Catalog source: **sample**
- Knobs: min/max stellar mass 0.37 M☉; max jump **28 ly**;
  max neighbors 5; linked cap 60;
  short/medium 40% / long 60%.
- Snapshot nodes: **98** (242 jump edges).
- Linked / largest component: **98** / **98**.
- Habitable by someone (linked, pack rules): **98** (100.0%).
- Cultures on the grid: Human 65, Methan 12, Kessari 11, Crystomorphs 10.
- NASA habitat flags on linked systems: carbon-zone 8, sulfur-zone 21, gas-giant 48 (any of those: 48).

## `lonely_humans` — Lonely humans

Sun-like stars only (about 0.66–1.5 solar masses). Longer jumps keep one thin network. Only oxygen-breathing humans; no alien cultures.

- Catalog source: **sample**
- Knobs: min/max stellar mass 0.66–1.5 M☉; max jump **36 ly**;
  max neighbors 4; linked cap 80;
  short/medium 40% / long 65%.
- Snapshot nodes: **58** (149 jump edges).
- Linked / largest component: **58** / **58**.
- Habitable by someone (linked, pack rules): **58** (100.0%).
- Cultures on the grid: Human 58.
- NASA habitat flags on linked systems: carbon-zone 5, sulfur-zone 17, gas-giant 36 (any of those: 36).
