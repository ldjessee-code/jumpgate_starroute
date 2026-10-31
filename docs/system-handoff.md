# System handoff (starroute → orbit_match)

One record per star. orbit_match uses it to open a system.

Schema: [system-handoff.schema.json](system-handoff.schema.json).

Examples:

- [tau-ceti.handoff.json](examples/tau-ceti.handoff.json) — detailed lore. `system_file` is `tau-ceti.system.json`.
- [55-cnc.handoff.json](examples/55-cnc.handoff.json) — no lore file. Hostname `55 Cnc`, display name `Rho Cancri`, 5 planets.
- [55-cnc-b.handoff.json](examples/55-cnc-b.handoff.json) — hostname `55 Cnc B`, display name `Rho Cancri B`, 2 planets, normal gate evaluation.

## What a record carries

Catalog identity is `star_key` plus a Gaia `gaia_source_id` or a HYG `hyg_id` (both when the catalog has them). Star fields are `name`, `hostname`, `ra_deg`, `dec_deg`, `dist_pc`, `x`, `y`, `z` (parsecs, Sol at the origin), `mag` (Gaia G if present, else V), `bp_rp`, `ci`, `spect`, `has_known_exoplanets`, `exoplanet_count`, `tier`, and `turquenish_system`.

`tier` is one of `gate_candidate`, `exo_no_gate`, or `no_known_planets`. It is computed when the route map is built. It is not a column in the merged catalog.

`xyz` on the map snapshot stays in light-years. This handoff uses parsecs so it matches `stars_merged_v1.csv`.

## Detailed file or basic record

orbit_match should load a handoff record, then:

1. If `system_file` is a non-empty name and that file exists under orbit_match `site/data/`, load it. That file is the detailed system (bodies, orbits, rings, belts, lore). Tau Ceti points at `tau-ceti.system.json`. Field names there use `star.hostname`, `star.name`, `star.setting_name`, `star.spectype`, and `bodies[]` with `kind` `belt`.
2. If `system_file` is null or the file is missing, use this record as the star. Do not invent planets.

When both exist, the detailed file wins for bodies and orbits. This record still supplies catalog ids, tier, and `turquenish_system`.

`turquenish_system` is the setting name (`star.setting_name` in the Tau Ceti file). For Tau Ceti that name is `Turquenish`.

## Belts

Systems can have any number of belts. The handoff schema allows a `belts` array of length 0, 1, 2, or more. There is no maximum.

Each belt has `name` and may have `id`, `kind` (`belt`), `a_inner_au`, and `a_outer_au`, the same orbit fields as a belt body in `tau-ceti.system.json`.

The Tau Ceti example lists two belts, The Sombrero and the Outer Wall, copied as a summary from that file. The detailed file remains the source for belt structure. 55 Cnc has `"belts": []`.

`rings` is an optional array for planet-ring summaries. Full ring bands stay in the detailed file. When `system_file` is set, that file wins for rings. Tau Ceti keeps `"rings": []` on this record.

## Optional fields

These may be omitted. When present they use the types in the schema. Nothing here renames or removes a required field.

- `sy_pnum` — integer or null. The NASA system planet count, stored beside `exoplanet_count`. It is not the per-star count.
- `aliases` — optional list of other catalog names. Display name stays in `name`.
- `st_mass` — stellar mass in solar masses, or null when it was not measured. `mass_known` is true only when `st_mass` parses as a number. A blank mass is not a measured low mass.
- `calculated_luminosity` and `calculated_luminosity_method` — see below. Null when not computed.
- `gate_status` — string or null. The value `pending_doug` means the star is pending Doug and is not a gate.
- `mass_unknown_penalty` — integer 1 when the rating penalty applies, else null.
- `lore_version`, `rings_belts_version`, `system_file_sha256` — copied from the source row when that row has them. Tau Ceti uses lore `v2.41c`, rings and belts `v2.41j`, and the sha256 of `tau-ceti.system.json`.
- `sky` — optional object with `equirect`, `cube_dir`, `frame`, `pole_rotation_applied`, and `background_rotation`. The Tau Ceti example includes it only because those sky files exist under the orbit_match site tree. `frame` is `icrs`, `pole_rotation_applied` is false, and `background_rotation` is null. Paths are relative to that site tree. Do not invent sky paths.

## Hostname order

Handoff `hostname` prefers the row `hostname`, then `exo_hostname`. Handoff `name` prefers a Bayer form from HYG `bf`/`bayer`, then a display overlay, then `proper`. Catalog `_hostname` uses `hostname` when that cell is set, and otherwise prefers `proper` over `exo_hostname`. The 55 Cnc example is hostname `55 Cnc` and name `Rho Cancri`. Copernicus is an alias.

## Per-host planet counts

`exoplanet_count` is the number of NASA planet rows whose hostname maps to that star. `sy_pnum` is the system total and is stored beside it. A missing `exoplanet_count` is 0, including on a multi-star host whose `sy_pnum` is larger. The 55 Cnc example is 5 planets on A and `sy_pnum` 7. 55 Cnc B is 2 planets with the same `sy_pnum` 7. Both take normal gate evaluation. Mass 0.26 solar masses on B is inside the default 0.25 gate window.

A host with a component letter maps to that component. A bare hostname maps to the primary (A). HIP/HD ids keep a trailing letter.

No known planets and no known mass is never a gate, including when the hostname is the origin. That tier is `no_known_planets`. A planet host whose mass was not measured can still be `gate_candidate` when the coordinates pass. Missing mass is not below 0.25 and does not fail a max-mass window. A planet host with a known mass below the minimum or above the maximum stays `exo_no_gate`.

## calculated_luminosity

Separate from the catalog. `st_lum`, `luminosity`, `lum`, and `lum_solar` are never overwritten. A value of 0 counts as present, including the Sun's `st_lum` 0, which is log10 of 1.

Compute only when every one of those cells is blank. The band is Johnson V: `mag_v`, else `sy_vmag`. Gaia G and `render_mag` are not used. Bolometric correction: none. Solar absolute V magnitude is 4.83. Distance must be greater than 0.

`M_V = m_V - 5*log10(dist_pc) + 5`

`L/L_sun = 10**((4.83 - M_V) / 2.5)`

Units are V-band solar luminosities, L_sun. `calculated_luminosity_method` is `johnson_v_no_bc`. The 55 Cnc example leaves `calculated_luminosity` null because its `mag` is Gaia G, not Johnson V.

## Mass-unknown penalty

There is no separate variability symbol. The existing ingest penalty is one stability step: `st_rotp` under 5 days adds 1 to `stability_score` (0–3, lower is better). `composite_ranking` turns that score into `(3 - score) / 3`.

At rating time, a planet host with missing `st_mass` takes the same one stability step. The stored `stability_score` is not overwritten, and `estimate_stability` is not changed. The score passed into the composite is `stability_score + 1`, capped at 3. A blank score is passed as 1. Known mass does not take this step.

On a calm star the step moves the score from 0 to 1. That multiplies the stability term by 2/3. With the default stability weight 0.15, the composite delta is -0.05. `mass_unknown_penalty` is 1 when that step applies, else null.

## Check a file

```bash
python -m starroute handoff docs/examples/tau-ceti.handoff.json
```

Exit 0 means the record matches the schema.
