"""NASA Exoplanet Archive TAP query used for pscomppars.

Jumpgate ingest reads local CSVs. This module records the TAP select list so
a re-pull and the star-catalog scripts stay aligned. New columns are optional
at read time: current snapshots omit them.
"""

from __future__ import annotations

PSCOMPPARS_COLUMNS = [
    "pl_name",
    "hostname",
    "hd_name",
    "hip_name",
    "tic_id",
    "gaia_dr3_id",
    "ra",
    "dec",
    "sy_dist",
    "sy_pnum",
    "sy_snum",
    "st_mass",
    "disc_year",
    "pl_controv_flag",
]

PSCOMPPARS_TAP_SELECT = ",".join(PSCOMPPARS_COLUMNS)

PSCOMPPARS_TAP_SQL = f"select {PSCOMPPARS_TAP_SELECT} from pscomppars"

PSCOMPPARS_TAP_URL = (
    "https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query="
    "select%20pl_name%2Chostname%2Chd_name%2Chip_name%2Ctic_id%2Cgaia_dr3_id"
    "%2Cra%2Cdec%2Csy_dist%2Csy_pnum%2Csy_snum%2Cst_mass%2Cdisc_year"
    "%2Cpl_controv_flag%20from%20pscomppars&format=csv"
)

# Planet-row fields that ingest may copy when the snapshot has them.
OPTIONAL_PLANET_COLUMNS = ["disc_year", "pl_controv_flag", "sy_snum", "st_mass"]
