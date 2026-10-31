"""Run the storage-format benchmark. One process, one variant at a time.

Importing this module does not start the suite. The court command runs it as a script.
"""

from __future__ import annotations

import gc
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from bench.catalog_prep import (  # noqa: E402
    adapt_frame,
    filter_radius,
    frame_digest,
    load_bench_enrichment,
    read_catalog,
)
from bench.formats_io import ALL, EXTENSIONS, REQUIRED, read_format, write_format  # noqa: E402
from bench.logging_util import append_log, pass_state  # noqa: E402
from bench.preflight import wait_until_clear  # noqa: E402
from bench.report_md import render_report  # noqa: E402
from bench.sweep import build_matrix, network_params, validate_matrix, variants_for, write_sweep  # noqa: E402
from starroute.mapgen.network import generate_network, network_payload  # noqa: E402
from starroute.mapgen.tiers import host_mask  # noqa: E402

STATUS_PATH = Path(r"F:\Dropbox\TheCourt\status\court-status.md")
REPORT_NAME = "sb_phase2_report_20261030_r5.md"
LARGE_ROWS = 80_000
PAYLOAD_ROWS = 20_000
ROOT_NAME = "Sol"

SLIM_COLUMNS = (
    "hostname",
    "sy_name",
    "calculated_x",
    "calculated_y",
    "calculated_z",
    "st_mass",
    "st_spectype",
    "spect",
    "sy_pnum",
    "sy_snum",
    "sy_mnum",
    "has_known_exoplanets",
    "exoplanet_count",
    "carbon_ranking",
    "sulfur_ranking",
    "silicon_ranking",
    "stability_score",
    "stability_symbol",
    "cb_flag",
    "st_met",
    "gate_status",
    "distance_from_sol_ly",
    "distance_from_origin_ly",
    "origin_hostname",
    "star_key",
    "gaia_source_id",
    "hyg_id",
    "hip",
    "hd",
    "gl",
    "proper",
    "comp_primary",
    "variable",
    "var",
    "is_variable",
    "variable_flag",
    "flare",
    "is_flare",
    "pulsar",
    "is_pulsar",
    "neutron",
    "is_neutron",
    "ra",
    "dec",
    "ra_deg",
    "dec_deg",
    "object_type",
    "star_class",
)

_EMPTY_MARK = {"", "nan", "none", "<na>", "nat"}


def _say(text: str) -> None:
    print(text, flush=True)


def _log(log_path: Path, step: str, **fields: Any) -> None:
    payload: dict[str, Any] = {
        "step": step,
        "format": "-",
        "variant": "-",
        "phase": "-",
        "seconds": 0,
        "gates": 0,
        "routes": 0,
        "rows": 0,
    }
    payload.update(fields)
    if isinstance(payload.get("seconds"), float):
        payload["seconds"] = f"{payload['seconds']:.4f}"
    append_log(log_path, payload)


def _locked(exc: BaseException) -> bool:
    """True when Windows or Dropbox still has the file open."""
    if not isinstance(exc, OSError):
        return False
    win = getattr(exc, "winerror", None)
    return win in (5, 32, 33) or exc.errno in (13,)


def _reset_dir(path: Path, log_path: Path | None = None) -> None:
    """Remove a tree, waiting out a sharing lock, then create it empty."""
    if path.exists():
        last: OSError | None = None
        for attempt in range(60):
            try:
                shutil.rmtree(path)
                last = None
                break
            except OSError as exc:
                if not _locked(exc):
                    raise
                last = exc
                if log_path is not None:
                    _log(
                        log_path,
                        "reset_wait",
                        phase="convert",
                        note=f"locked {path} attempt {attempt + 1}",
                    )
                time.sleep(2)
        if last is not None and path.exists():
            held = path.with_name(f"{path.name}_locked_{time.strftime('%H%M%S')}")
            path.rename(held)
            if log_path is not None:
                _log(log_path, "reset_wait", phase="convert", note=f"moved locked tree to {held.name}")
    path.mkdir(parents=True, exist_ok=True)


def _unlink_when_free(path: Path) -> None:
    if not path.exists():
        return
    last: OSError | None = None
    for _attempt in range(30):
        try:
            path.unlink()
            return
        except OSError as exc:
            if not _locked(exc):
                raise
            last = exc
            time.sleep(2)
    if last is not None:
        raise last


def _sealed_done_flag() -> Path | None:
    """Return the DONE flag file when env BENCH_DONE_FLAG names an existing file.

    An unset, blank, or not-yet-created path is not sealed. run-tests.ps1 sets the
    env var before the suite and writes the file only after a passing report.
    """
    raw = os.environ.get("BENCH_DONE_FLAG")
    if raw is None or not str(raw).strip():
        return None
    path = Path(str(raw).strip())
    if path.is_file():
        return path
    return None


def begin_pass(log_path: Path, staging: Path, job_dir: Path, report_path: Path | None = None) -> None:
    """Log a new pass. An incomplete log restarts from an empty staging tree."""
    sealed = _sealed_done_flag()
    if sealed is not None:
        raise RuntimeError(f"refused_done_flag {sealed}")
    if pass_state(log_path) == "incomplete":
        _log(
            log_path,
            "restart",
            phase="generate",
            note="previous pass incomplete; partial timings are not used",
        )
    _log(log_path, "suite_start", phase="generate", note="storage format benchmark")
    _reset_dir(staging / "formats", log_path)
    _reset_dir(staging / "maps", log_path)
    _reset_dir(job_dir / "maps", log_path)
    if report_path is not None:
        _unlink_when_free(report_path)


def radius_key(radius: float) -> str:
    return f"{float(radius):.4f}"


def slim_frame(df):
    import pandas as pd

    keep = [column for column in SLIM_COLUMNS if column in df.columns]
    missing = {"hostname", "calculated_x", "calculated_y", "calculated_z"} - set(keep)
    if missing:
        raise RuntimeError(f"adapted frame missing {sorted(missing)}")
    return df.loc[:, keep].reset_index(drop=True)


def rank_formats(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lowest mean load+generate on extreme variants. Ties break on file size, then name."""
    buckets: dict[str, dict[str, Any]] = {}
    for row in results:
        if row.get("phase_group") != "extreme":
            continue
        bucket = buckets.setdefault(
            row["format"],
            {"load": [], "generate": [], "bytes": int(row["bytes"])},
        )
        bucket["load"].append(float(row["load_s"]))
        bucket["generate"].append(float(row["generate_s"]))
        bucket["bytes"] = int(row["bytes"])
    ranked = []
    for fmt, bucket in buckets.items():
        mean_load = sum(bucket["load"]) / len(bucket["load"])
        mean_generate = sum(bucket["generate"]) / len(bucket["generate"])
        ranked.append(
            {
                "format": fmt,
                "bytes": bucket["bytes"],
                "mean_load": mean_load,
                "mean_generate": mean_generate,
                "mean_sum": mean_load + mean_generate,
            }
        )
    ranked.sort(key=lambda item: (item["mean_sum"], item["bytes"], item["format"]))
    return ranked


def postgres_paragraphs(ranking: list[dict[str, Any]]) -> list[str]:
    best = ranking[0]
    slow = ranking[-1]
    return [
        (
            f"Postgres is not needed for this workload. The fastest format on the extreme variants is {best['format']} "
            f"at {best['mean_sum']:.3f} s mean load plus generate and {best['bytes'] / 1_000_000:.1f} MB. "
            f"The slowest measured format is {slow['format']} at {slow['mean_sum']:.3f} s and {slow['bytes'] / 1_000_000:.1f} MB."
        ),
        (
            "The catalog is static and one user builds a map from a file. Every candidate is a single file with no server. "
            "generate_network does the same work on every format, so a database server would not remove that cost. "
            "Load time is paid once per map."
        ),
        (
            "Keep the placed CSV as the source catalog and build later maps from the fastest selected file format. "
            "A server would add a process, a port, and backup work that this single-user catalog does not need."
        ),
    ]


def _filled(series):
    text = series.fillna("").astype(str).str.strip().str.lower()
    return ~text.isin(_EMPTY_MARK)


def inspect_network(path: Path, max_neighbors: int, min_mass: float, root: str = ROOT_NAME) -> dict[str, Any]:
    """Count gates, routes, rows, and the highest degree. Raise when a cap breaks."""
    import pandas as pd

    def usecols(name: str) -> bool:
        return name in {"hostname", "gate_distance", "st_mass"} or (
            name.startswith("neighbor_") and name.endswith("_hostname")
        )

    gates = 0
    rows = 0
    degree_max = 0
    bad_mass = 0
    edges: set[tuple[str, str]] = set()
    reader = pd.read_csv(path, dtype=str, keep_default_na=False, usecols=usecols, chunksize=200_000)
    for chunk in reader:
        if "hostname" not in chunk.columns or "gate_distance" not in chunk.columns or "st_mass" not in chunk.columns:
            raise RuntimeError(f"network csv {path} is missing hostname, gate_distance, or st_mass")
        rows += int(len(chunk))
        linked = _filled(chunk["gate_distance"])
        gates += int(linked.sum())
        neighbor_cols = [column for column in chunk.columns if column.startswith("neighbor_") and column.endswith("_hostname")]
        degree = pd.Series(0, index=chunk.index)
        hosts = chunk["hostname"].astype(str)
        for column in neighbor_cols:
            mask = _filled(chunk[column])
            degree = degree + mask.astype(int)
            dest = chunk.loc[mask, column].astype(str).str.strip()
            src = hosts.loc[mask]
            for left, right in zip(src.tolist(), dest.tolist()):
                if left != right:
                    edges.add((left, right) if left < right else (right, left))
        if len(degree):
            degree_max = max(degree_max, int(degree.max()))
        mass = pd.to_numeric(chunk["st_mass"], errors="coerce")
        names = hosts
        bad_mass += int((linked & names.ne(root) & mass.notna() & (mass < float(min_mass) - 1e-9)).sum())
    if degree_max > int(max_neighbors):
        raise RuntimeError(f"degree {degree_max} exceeds max routes {max_neighbors} in {path}")
    if bad_mass:
        raise RuntimeError(f"{bad_mass} linked gates in {path} are below {min_mass} Msun")
    return {"gates": gates, "routes": len(edges), "rows": rows, "degree": degree_max, "edges": edges}


def spectral_marks(frame) -> dict[str, int]:
    import pandas as pd

    spect = frame["spect"].fillna("").astype(str) if "spect" in frame.columns else pd.Series("", index=frame.index)
    kind = frame["st_spectype"].fillna("").astype(str) if "st_spectype" in frame.columns else spect
    blob = spect + " " + kind
    sy = pd.to_numeric(frame["sy_snum"], errors="coerce") if "sy_snum" in frame.columns else pd.Series(0, index=frame.index)
    return {
        "variable_mark": int(blob.str.contains(r"(?i)\bvar\b|\bvariable\b", regex=True).sum()),
        "flare_mark": int(blob.str.contains(r"(?i)\bflare\b|\bdme\b|\bdm\d*e\b|uv\s*ceti", regex=True).sum()),
        "pulsar_or_neutron_mark": int(
            blob.str.contains(
                r"(?i)\bpulsar\b|\bpsr\b|\bneutron(?:\s*star)?\b|(?<![A-Za-z0-9])NS(?![A-Za-z0-9])",
                regex=True,
            ).sum()
        ),
        "spectroscopic_binary_mark": int(blob.str.contains(r"(?i)\bSB\d*\b", regex=True).sum()),
        "sy_snum_at_least_2": int(sy.fillna(0).ge(2).sum()),
    }


def _frame_stats(frame, spectral: bool) -> dict[str, int]:
    import pandas as pd

    mass = pd.to_numeric(frame["st_mass"], errors="coerce") if "st_mass" in frame.columns else pd.Series(dtype=float)
    stats = {
        "rows": int(len(frame)),
        "hosts": int(host_mask(frame).sum()),
        "mass_known": int(mass.notna().sum()) if len(frame) else 0,
    }
    if spectral:
        stats.update(spectral_marks(frame))
    return stats


def _check_caps(params: dict[str, Any], name: str) -> None:
    if float(params["min_stellar_mass"]) < 0.25:
        raise RuntimeError(f"{name} mass is below 0.25")
    if int(params["max_neighbors"]) > 16 or int(params["max_neighbors"]) < 1:
        raise RuntimeError(f"{name} routes break the 1..16 cap")
    if float(params["max_distance_ly"]) > 500 or float(params["max_distance_ly"]) <= 0:
        raise RuntimeError(f"{name} radius breaks the 500 ly cap")


def execute() -> None:
    sealed = _sealed_done_flag()
    if sealed is not None:
        job = Path(os.environ["BENCH_JOB_DIR"])
        _log(job / "bench_log.txt", "refused_done_flag", note=str(sealed))
        return
    job = Path(os.environ["BENCH_JOB_DIR"])
    staging = Path(os.environ["BENCH_STAGING"])
    catalog_path = Path(os.environ["BENCH_CATALOG"])
    preflight = os.environ["BENCH_PREFLIGHT_CMD"]
    log_path = job / "bench_log.txt"
    report_path = job / REPORT_NAME
    job.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)
    adapt_kept.clear()

    matrix = build_matrix()
    validate_matrix(matrix)
    begin_pass(log_path, staging, job, report_path)
    write_sweep(REPO / "bench" / "sweep.json", matrix)
    write_sweep(job / "sweep.json", matrix)
    _say("sweep written")

    usage = shutil.disk_usage(staging)
    _log(log_path, "disk", phase="convert", rows=usage.free, note=f"free_bytes={usage.free}")
    if usage.free < 5_000_000_000:
        raise RuntimeError(f"staging disk has only {usage.free} bytes free")

    wait_until_clear(preflight, log_path, step_format="catalog", step_variant="read")
    started = time.perf_counter()
    catalog = read_catalog(catalog_path, 500)
    read_s = time.perf_counter() - started
    digest = frame_digest(catalog)
    enrichment = load_bench_enrichment()
    catalog_rows = int(len(catalog))
    _log(
        log_path,
        "catalog",
        phase="load",
        seconds=read_s,
        rows=catalog_rows,
        note=f"digest={digest} enrichment_keys={len(enrichment)}",
    )
    _say(f"catalog rows {catalog_rows}")

    conversions: dict[str, dict[str, Any]] = {}
    needs: list[str] = []
    for fmt in ALL:
        wait_until_clear(preflight, log_path, step_format=fmt, step_variant="convert")
        target = staging / "formats" / f"stars{EXTENSIONS[fmt]}"
        started = time.perf_counter()
        info = write_format(catalog, fmt, target)
        elapsed = time.perf_counter() - started
        info["seconds"] = elapsed
        if not info["ok"]:
            needs.append(f"{fmt}: {info['error']}")
            _log(
                log_path,
                "convert",
                format=fmt,
                variant="-",
                phase="convert",
                seconds=elapsed,
                rows=0,
                note=info["error"],
            )
            _say(f"convert {fmt} failed")
            continue
        conversions[fmt] = info
        _log(
            log_path,
            "convert",
            format=fmt,
            variant="-",
            phase="convert",
            seconds=elapsed,
            rows=info["rows"],
            bytes=info["bytes"],
        )
        _say(f"convert {fmt} {info['bytes']} bytes in {elapsed:.1f}s")
    missing = [fmt for fmt in REQUIRED if fmt not in conversions]
    if missing:
        raise RuntimeError("required format failed: " + ", ".join(missing))

    radii = sorted({float(item["params"]["max_distance_ly"]) for item in matrix["variants"]})
    cache: dict[str, dict[str, Any]] = {}
    markers: dict[str, int] = {}
    for radius in radii:
        key = radius_key(radius)
        wait_until_clear(preflight, log_path, step_format="adapt", step_variant=key)
        # read_catalog already applied the 500 ly cap, so the full frame is that subset.
        subset = catalog if float(radius) >= 500 else filter_radius(catalog, radius)
        started = time.perf_counter()
        adapted = slim_frame(adapt_frame(subset, enrichment))
        elapsed = time.perf_counter() - started
        if ROOT_NAME not in set(adapted["hostname"].astype(str)):
            raise RuntimeError(f"Sol missing after adapt at {radius} ly")
        stats = _frame_stats(adapted, spectral=abs(radius - 500.0) < 1e-6)
        if abs(radius - 500.0) < 1e-6:
            markers = {name: value for name, value in stats.items() if name not in {"rows", "hosts", "mass_known"}}
        cache[key] = {
            "frame": adapted,
            "seconds": elapsed,
            "rows": int(len(adapted)),
            "hosts": stats["hosts"],
            "mass_known": stats["mass_known"],
        }
        _remember_adapt(key, elapsed, int(len(adapted)), int(stats["hosts"]), int(stats["mass_known"]))
        _log(
            log_path,
            "adapt",
            format="-",
            variant=key,
            phase="generate",
            seconds=elapsed,
            rows=len(adapted),
            note=f"hosts={stats['hosts']} mass_known={stats['mass_known']}",
        )
        _say(f"adapt {radius} ly rows {len(adapted)} in {elapsed:.1f}s")
        if subset is not catalog:
            del subset
        del adapted
        gc.collect()
    del catalog
    gc.collect()

    results: list[dict[str, Any]] = []
    signatures: dict[str, tuple[Any, ...]] = {}

    def run_one(fmt: str, variant: dict[str, Any]) -> None:
        name = variant["name"]
        params = network_params(variant)
        _check_caps(params, name)
        radius = float(params["max_distance_ly"])
        key = radius_key(radius)
        wait_until_clear(preflight, log_path, step_format=fmt, step_variant=name)
        source = staging / "formats" / f"stars{EXTENSIONS[fmt]}"
        started = time.perf_counter()
        loaded = read_format(fmt, source)
        load_s = time.perf_counter() - started
        loaded_rows = int(len(loaded))
        got = frame_digest(loaded)
        del loaded
        gc.collect()
        if got != digest:
            raise RuntimeError(f"digest mismatch for {fmt} on {name}")
        _log(
            log_path,
            "load",
            format=fmt,
            variant=name,
            phase="load",
            seconds=load_s,
            rows=loaded_rows,
        )
        cached = cache[key]
        frame = cached["frame"]
        adapt_s = float(cached["seconds"])
        job_dir = job / "maps" / fmt / name
        job_dir.mkdir(parents=True, exist_ok=True)
        if len(frame) > LARGE_ROWS:
            map_dir = staging / "maps" / fmt / name
            map_dir.mkdir(parents=True, exist_ok=True)
        else:
            map_dir = job_dir
        csv_path = map_dir / "network.csv"
        started = time.perf_counter()
        generated = generate_network(systems_df=frame, output_path=str(csv_path), params=params)
        network_s = time.perf_counter() - started
        inspected = inspect_network(csv_path, int(params["max_neighbors"]), float(params["min_stellar_mass"]))
        if int(generated["nodes"]) != len(frame) or inspected["rows"] != len(frame):
            raise RuntimeError(
                f"{fmt} {name} map rows {generated['nodes']}/{inspected['rows']} != adapted {len(frame)}"
            )
        if int(generated["linked_nodes"]) != inspected["gates"]:
            raise RuntimeError(f"{fmt} {name} gate count mismatch")
        signature = (inspected["gates"], inspected["routes"], inspected["rows"])
        previous = signatures.get(name)
        if previous is None:
            signatures[name] = signature
        elif previous != signature:
            raise RuntimeError(f"{fmt} {name} counts {signature} disagree with {previous}")
        generate_s = adapt_s + network_s
        _log(
            log_path,
            "generate",
            format=fmt,
            variant=name,
            phase="generate",
            seconds=network_s,
            gates=inspected["gates"],
            routes=inspected["routes"],
            rows=inspected["rows"],
            note=f"adapt_s={adapt_s:.4f} reported_generate_s={generate_s:.4f}",
        )
        summary = {
            "format": fmt,
            "variant": name,
            "phase": variant["phase"],
            "gates": inspected["gates"],
            "routes": inspected["routes"],
            "rows": inspected["rows"],
            "degree": inspected["degree"],
            "convert_s": conversions[fmt]["seconds"],
            "load_s": load_s,
            "adapt_s": adapt_s,
            "network_s": network_s,
            "generate_s": generate_s,
            "map_path": str(csv_path),
            "bytes": conversions[fmt]["bytes"],
            "params": params,
        }
        (job_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
        edge_rows = [{"a": left, "b": right} for left, right in sorted(inspected["edges"])]
        (job_dir / "edges.json").write_text(json.dumps(edge_rows) + "\n", encoding="utf-8")
        if inspected["rows"] <= PAYLOAD_ROWS:
            _write_payload(csv_path, job_dir / "map.json")
        convert_s = float(conversions[fmt]["seconds"])
        results.append(
            {
                "format": fmt,
                "variant": name,
                "phase_group": variant["phase"],
                "convert_s": convert_s,
                "load_s": load_s,
                "generate_s": generate_s,
                "total_s": convert_s + load_s + generate_s,
                "bytes": int(conversions[fmt]["bytes"]),
                "summary_path": str(job_dir / "summary.json"),
                "map_path": str(csv_path),
                "gates": inspected["gates"],
                "routes": inspected["routes"],
                "rows": inspected["rows"],
                "radius": radius,
                "mass": params["min_stellar_mass"],
                "route_cap": params["max_neighbors"],
                "spacing": params["max_jump_ly"],
                "criteria": variant["params"]["criteria"],
                "phase": variant["phase"],
            }
        )
        _say(
            f"{fmt} {name} load {load_s:.1f}s network {network_s:.1f}s gates {inspected['gates']} routes {inspected['routes']}"
        )
        del inspected
        gc.collect()

    active = [fmt for fmt in ALL if fmt in conversions]
    for variant in variants_for(matrix, "extreme"):
        for fmt in active:
            run_one(fmt, variant)
    ranking = rank_formats(results)
    if len(ranking) < 2:
        raise RuntimeError("fewer than two formats finished the extreme variants")
    selected = [ranking[0]["format"], ranking[1]["format"]]
    _log(
        log_path,
        "pick",
        format=",".join(selected),
        variant="-",
        phase="generate",
        seconds=ranking[0]["mean_sum"],
        note="lowest mean load+generate on extreme variants",
    )
    _say(f"selected {selected[0]} and {selected[1]}")
    later = {
        radius_key(float(item["params"]["max_distance_ly"]))
        for item in variants_for(matrix, "midpoint") + variants_for(matrix, "minimal")
    }
    for key in list(cache):
        if key not in later:
            del cache[key]["frame"]
            del cache[key]
    gc.collect()
    for phase in ("midpoint", "minimal"):
        for variant in variants_for(matrix, phase):
            for fmt in selected:
                run_one(fmt, variant)
        if phase == "midpoint":
            keep = {
                radius_key(float(item["params"]["max_distance_ly"]))
                for item in variants_for(matrix, "minimal")
            }
            for key in list(cache):
                if key not in keep:
                    del cache[key]["frame"]
                    del cache[key]
            gc.collect()

    counts = []
    seen: set[str] = set()
    for row in results:
        if row["variant"] in seen:
            continue
        seen.add(row["variant"])
        counts.append(
            {
                "name": row["variant"],
                "phase": row["phase"],
                "radius": row["radius"],
                "mass": row["mass"],
                "route_cap": row["route_cap"],
                "spacing": row["spacing"],
                "criteria": row["criteria"],
                "gates": row["gates"],
                "routes": row["routes"],
                "rows": row["rows"],
                "agree": "yes",
            }
        )
    combo = next(item for item in counts if item["name"] == "combined_m025")
    final_line = (
        f"FINAL: PASS - fastest {ranking[0]['format']} mean load+generate {ranking[0]['mean_sum']:.1f}s; "
        f"extreme variants {len(variants_for(matrix, 'extreme'))} on {len(active)} formats; "
        f"combined_m025 gates {combo['gates']} routes {combo['routes']}"
    )
    meta = {
        "catalog_rows": catalog_rows,
        "digest": digest,
        "enrichment_keys": len(enrichment),
        "ranking": ranking,
        "selected": selected,
        "counts": counts,
        "adapt": adapt_kept,
        "markers": markers,
        "postgres": postgres_paragraphs(ranking),
        "final_line": final_line,
    }
    text = render_report(
        results=results,
        matrix=matrix,
        meta=meta,
        needs=needs,
        job_dir=job,
        report_path=report_path,
        status_path=STATUS_PATH,
    )
    temporary = report_path.with_suffix(".md.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, report_path)
    _log(log_path, "suite_complete", phase="generate", rows=catalog_rows, note=final_line)
    _say(final_line)


# Filled during execute before cache entries are released. Declared here so the
# report builder can close over the measurements without a second adapt pass.
adapt_kept: dict[str, dict[str, Any]] = {}


def _remember_adapt(key: str, seconds: float, rows: int, hosts: int, mass_known: int) -> None:
    adapt_kept[key] = {
        "seconds": f"{seconds:.4f}",
        "rows": rows,
        "hosts": hosts,
        "mass_known": mass_known,
    }


def _write_payload(csv_path: Path, dest: Path) -> None:
    import pandas as pd

    frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    numeric = {
        "calculated_x",
        "calculated_y",
        "calculated_z",
        "sy_pnum",
        "composite_ranking",
        "distance_from_sol_ly",
        "distance_from_origin_ly",
        "gate_distance",
        "process_order",
    }
    for column in frame.columns:
        if column in numeric or column.endswith("_distance") or column.endswith("_ranking"):
            frame[column] = pd.to_numeric(frame[column].replace("", pd.NA), errors="coerce")
        elif column.startswith("neighbor_") and column.endswith("_hostname"):
            frame[column] = frame[column].replace("", pd.NA)
    payload = network_payload(frame)
    dest.write_text(json.dumps(payload), encoding="utf-8")
    del frame


def main() -> int:
    job = os.environ.get("BENCH_JOB_DIR", "")
    log_path = Path(job) / "bench_log.txt" if job else None
    try:
        execute()
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
        _say(message)
        if log_path is not None:
            try:
                _log(log_path, "error", phase="generate", note=message)
            except Exception:
                pass
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
