"""Project-root path helpers.

The package lives at ``<repo>/starroute``. Data and config sit next to it, not
inside the package, so a clone can gitignore the large NASA CSVs.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_UPLOADS = ROOT / "data" / "uploads"
CONFIG_DIR = ROOT / "config"

SYSTEMS_CSV = DATA_PROCESSED / "systems.csv"
NETWORK_CSV = DATA_PROCESSED / "sol_network.csv"
ASSIGNED_CSV = DATA_PROCESSED / "assigned_systems.csv"
ROUTES_CSV = DATA_PROCESSED / "route_table.csv"
FACTIONS_JSON = CONFIG_DIR / "factions.json"
NETWORK_JSON = CONFIG_DIR / "network.json"


def ensure_data_dirs() -> None:
    for path in (DATA_RAW, DATA_PROCESSED, DATA_UPLOADS, CONFIG_DIR):
        path.mkdir(parents=True, exist_ok=True)
