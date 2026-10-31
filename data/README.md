# Data directories

| Path | What | License |
| --- | --- | --- |
| `raw/` | NASA Exoplanet Archive CSVs (not committed) | See `catalog/NOTICE.md` |
| `processed/` | Derived tables from ingest (gitignored) | Derived from the catalog |
| `presets/` | Generated map JSON (stars + painted labels) | Geometry follows MIT tool; culture *names* refer to `setting/` |

Do not drop Turquenish prose in here. Do not drop your homebrew in here —
that belongs in `user_setting/`.

The NASA TAP select for a pscomppars re-pull is in
`starroute/ingest/nasa_tap.py` (`PSCOMPPARS_TAP_SQL`). New columns
`sy_snum`, `st_mass`, `disc_year`, and `pl_controv_flag` are optional at
read time. Current snapshots omit them. Ingest still runs.
