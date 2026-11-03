"""Write the phase-2 storage benchmark report."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any


def _num(value: float, digits: int = 3) -> str:
    return f"{float(value):.{digits}f}"


def _mb(size: int) -> str:
    return f"{size / 1_000_000:.1f} MB"


def status_number(path: str | Path) -> int:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    found = [int(item) for item in re.findall(r"(?m)^(?:- |\*\*)?(\d+)[\.\)]", text)]
    return (max(found) + 1) if found else 1


def status_label(path: str | Path) -> str:
    """Next id. The reseeded file uses C- ids. Older files use a leading number."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    c_ids = [int(item) for item in re.findall(r"\bC-(\d+)\b", text)]
    if c_ids:
        return f"C-{max(c_ids) + 1}"
    return str(status_number(path))


def render_report(
    *,
    results: list[dict[str, Any]],
    matrix: dict[str, Any],
    meta: dict[str, Any],
    needs: list[str],
    job_dir: Path,
    report_path: Path,
    status_path: Path,
) -> str:
    lines: list[str] = []
    add = lines.append
    add("# Storage-format benchmark phase 2")
    add("")
    add(f"Date: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    add(f"Catalog rows inside 500 ly: {meta['catalog_rows']}")
    add(f"Catalog digest: {meta['digest']}")
    add(f"Enrichment keys: {meta['enrichment_keys']}")
    add("")
    add("Adapt of each radius is measured once. That time is added to every variant at the same radius. The network build itself is timed on every format and variant. A format is used only after its loaded file matches the catalog digest.")
    add("")
    add("## Timing table")
    add("")
    add("Convert is done once per format and repeated on each row so the row total is convert + load + generate. Summing totals across variants counts that convert more than once.")
    add("")
    add("| format | variant | phase | convert s | load s | generate s | total s | file size |")
    add("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for row in results:
        add(
            "| {format} | {variant} | {phase_group} | {convert} | {load} | {generate} | {total} | {size} |".format(
                format=row["format"],
                variant=row["variant"],
                phase_group=row["phase_group"],
                convert=_num(row["convert_s"]),
                load=_num(row["load_s"]),
                generate=_num(row["generate_s"]),
                total=_num(row["total_s"]),
                size=_mb(row["bytes"]),
            )
        )
    add("")
    add("Generate = radius adapt + `generate_network`. Load is the format read. The digest check runs after the load clock stops. The two formats kept for the midpoint and minimal sets are the lowest mean of load + generate on the extreme variants.")
    add("")
    add("| format | file size | mean load s | mean generate s | mean load+generate s |")
    add("| --- | ---: | ---: | ---: | ---: |")
    for item in meta["ranking"]:
        add(
            f"| {item['format']} | {_mb(item['bytes'])} | {_num(item['mean_load'])} | {_num(item['mean_generate'])} | {_num(item['mean_sum'])} |"
        )
    add("")
    add(f"Selected formats: {', '.join(meta['selected'])}.")
    add("")
    add("## Gate and route counts")
    add("")
    add("Gate count is systems with a finite gate distance from Sol. Route count is unique jump edges from generate_network. Faction paint is outside this timing, and faction routes are not included. Row counts are the stars passed into the generator, and every one of those stars is on the map.")
    add("")
    add("| variant | phase | radius ly | mass | routes cap | spacing ly | criteria | gates | routes | rows | formats agree |")
    add("| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |")
    for item in meta["counts"]:
        add(
            "| {name} | {phase} | {radius} | {mass} | {routes} | {spacing} | {criteria} | {gates} | {edges} | {rows} | {agree} |".format(
                name=item["name"],
                phase=item["phase"],
                radius=item["radius"],
                mass=item["mass"],
                routes=item["route_cap"],
                spacing=item["spacing"],
                criteria=item["criteria"],
                gates=item["gates"],
                edges=item["routes"],
                rows=item["rows"],
                agree=item["agree"],
            )
        )
    add("")
    add("## Sweep definition")
    add("")
    add("Baseline is the held operating point. Extreme is the heavy end of that parameter. Minimal is the small end. Each one-factor variant changes one baseline field. `combined_m025` and `combined_m030` change mass, route cap, spacing, and radius together.")
    add("")
    add("| parameter | baseline | extreme | midpoint | minimal |")
    add("| --- | --- | --- | --- | --- |")
    base = matrix["baseline"]
    for key, levels in matrix["levels"].items():
        add(f"| {key} | {base[key]} | {levels['extreme']} | {levels['midpoint']} | {levels['minimal']} |")
    add("")
    add("Criteria levels:")
    add("")
    for name, body in matrix["criteria_levels"].items():
        flags = ", ".join(f"{key}={value}" for key, value in body.items())
        add(f"- {name}: {flags}")
    add("")
    add("Fixed for every variant: " + ", ".join(f"{key}={value}" for key, value in matrix["fixed"].items()) + ".")
    add("")
    add("Caps: min stellar mass >= 0.25 Msun, max routes per gate <= 16, distance from Sol <= 500 ly.")
    add("")
    add("The matrix file is `bench/sweep.json` in the repo and a copy in this job folder.")
    add("")
    for note in matrix["notes"]:
        add(f"- {note}")
    add("")
    adapt_lines = meta.get("adapt") or {}
    if adapt_lines:
        add("Adapt measurements:")
        add("")
        for radius, info in adapt_lines.items():
            add(
                f"- {radius} ly: {info['seconds']} s, rows {info['rows']}, planet hosts {info['hosts']}, known mass {info['mass_known']}"
            )
        add("")
    if meta.get("markers"):
        add("Spectral and multiplicity marks on the 500 ly adapted set:")
        add("")
        for key, value in meta["markers"].items():
            add(f"- {key}: {value}")
        add("")
    add("## Postgres recommendation")
    add("")
    for paragraph in meta["postgres"]:
        add(paragraph)
        add("")
    add("## Log paths")
    add("")
    add(f"- Bench log: `{job_dir / 'bench_log.txt'}`")
    add(f"- Court preflight log: `{job_dir / 'preflight.log'}`")
    add(f"- Launcher log: `{job_dir / 'run.log'}`")
    add("")
    add("## Map output paths")
    add("")
    add("Each variant has a summary and an edge list in the job folder. The full star table (every star in that variant) is the network CSV. Tables with more than 80,000 stars are under the staging directory.")
    add("")
    for row in results:
        add(f"- `{row['format']}` / `{row['variant']}`: `{row['summary_path']}` ; stars: `{row['map_path']}`")
    add("")
    add("## Court-status line")
    add("")
    label = status_label(status_path)
    done = datetime.now().strftime("%Y-%m-%d")
    if label.startswith("C-"):
        add("The status file uses C- ids in its in-motion table. This run did not edit that file.")
        add("")
        add(
            f"| {label} | jumpgate_starroute storage-format benchmark (phase 2). Paths: {report_path} | Sean | DONE PASS {done} | Doug runs Merge-Review.ps1 himself; nothing was committed or merged |"
        )
    else:
        add(f"{label}. **jumpgate_starroute storage-format benchmark (phase 2)**")
        add("   - Owner: Sean")
        add(f"   - State: DONE PASS {done}")
        add("   - Next gate: Doug runs Merge-Review.ps1 himself; nothing was committed or merged")
        add(f"   - Paths: {report_path}")
    add("")
    add("## Needs Doug")
    add("")
    add("Nothing was committed or merged. Doug runs Merge-Review.ps1 himself.")
    add("")
    if needs:
        for item in needs:
            add(f"- {item}")
    else:
        add("- No format failed. npz ran as the optional extra.")
    add("")
    add(meta["final_line"])
    add("RUN FINISHED")
    add("")
    text = "\n".join(lines)
    if "(pending)" in text:
        raise RuntimeError("report text contains a forbidden pending mark")
    return text
