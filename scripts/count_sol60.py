"""One Sol 60 ly trim of the merged catalog. Output stays in the court job folder."""

from __future__ import annotations

import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

REPO = Path(r"C:\Users\DougJ\Documents\GitHub\jumpgate_starroute")
JOB = Path(r"F:\Dropbox\TheCourt\research\_jobs\jumpgate-starroute\catalog_20261020")
CATALOG = Path(
    r"F:\Dropbox\TheCourt\research\_jobs\star-catalog\multisource_20261019\stars_merged_v1.csv"
)
sys.path.insert(0, str(REPO))

from starroute.catalog import load_trimmed_frame  # noqa: E402
from starroute.mapgen.network import generate_network  # noqa: E402
from starroute.mapgen.tiers import classify_tier  # noqa: E402


def _newlines(path: Path) -> int:
    total = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8 * 1024 * 1024)
            if not chunk:
                break
            total += chunk.count(b"\n")
    return total


def main() -> int:
    if not CATALOG.is_file():
        print("MISSING", CATALOG)
        return 2
    summary: dict = {
        "catalog": str(CATALOG),
        "catalog_bytes": CATALOG.stat().st_size,
        "origin": "Sol",
        "max_distance_ly": 60,
    }
    counted = time.perf_counter()
    summary["newline_count"] = _newlines(CATALOG)
    summary["newline_seconds"] = round(time.perf_counter() - counted, 2)
    started = time.perf_counter()
    frame = load_trimmed_frame(CATALOG, origin="Sol", max_distance_ly=60)
    summary["stream_seconds"] = round(time.perf_counter() - started, 2)
    summary["trimmed_rows"] = int(len(frame))
    systems = JOB / "sol_60ly_systems.csv"
    frame.to_csv(systems, index=False)
    floors = {
        "crowded_min_0.25": (0.25, None),
        "sparse_min_0.37": (0.37, None),
        "lonely_humans_0.66_to_1.5": (0.66, 1.5),
    }
    tier_sets = {}
    for label, (floor, ceiling) in floors.items():
        counts: Counter = Counter()
        for _, row in frame.iterrows():
            counts[classify_tier(row, floor, ceiling, "Sol")] += 1
        tier_sets[label] = dict(counts)
    summary["tier_sets"] = tier_sets
    if "st_mass" in frame.columns:
        filled = 0
        for value in frame["st_mass"]:
            if str(value).strip() not in {"", "nan", "None", "<NA>"}:
                filled += 1
        summary["st_mass_filled"] = filled
    if "has_known_exoplanets" in frame.columns:
        summary["exoplanet_flag_true"] = int(
            frame["has_known_exoplanets"].astype(str).str.lower().isin(["true", "1"]).sum()
        )
    network_path = JOB / "sol_60ly_network.csv"
    build_started = time.perf_counter()
    try:
        result = generate_network(
            systems_path=str(systems),
            output_path=str(network_path),
            params={
                "max_jump_ly": 16,
                "min_stellar_mass": 0.25,
                "root_hostname": "Sol",
                "medium_start_pct": 40,
                "long_start_pct": 60,
                "hard_rank": 0.15,
                "soft_rank": 0.25,
                "max_neighbors": 6,
                "max_linked_nodes": 80,
            },
        )
        summary["network_seconds"] = round(time.perf_counter() - build_started, 2)
        summary["network_error"] = ""
        small = {}
        for key, value in result.items():
            if isinstance(value, (int, float, str)) or value is None or key == "tier_counts":
                small[key] = value
        summary["network"] = small
    except Exception as exc:
        summary["network_seconds"] = round(time.perf_counter() - build_started, 2)
        summary["network_error"] = f"{type(exc).__name__}: {exc}"
        summary["network_trace"] = traceback.format_exc()[-2000:]
    out = JOB / "sol_60ly_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in summary if k != "network_trace"}, indent=2, default=str))
    return 0 if not summary.get("network_error") else 1


if __name__ == "__main__":
    raise SystemExit(main())
