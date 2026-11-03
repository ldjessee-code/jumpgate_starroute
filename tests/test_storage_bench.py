"""Bench helpers on tiny frames. These tests do not read the placed catalog."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.catalog_prep import adapt_frame, filter_radius, frame_digest, read_catalog  # noqa: E402
from bench.formats_io import ALL, as_text_frame, write_format, read_format  # noqa: E402
from bench.logging_util import LOG_KEYS, append_log, pass_state  # noqa: E402
from bench.preflight import wait_until_clear  # noqa: E402
from bench.report_md import render_report, status_number  # noqa: E402
from bench.run_suite import begin_pass, execute, inspect_network, postgres_paragraphs, rank_formats  # noqa: E402
from bench.sweep import build_matrix, changed_parameters, validate_matrix, write_sweep  # noqa: E402


def _sample() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "star_key": "hyg:0",
                "gaia_source_id": "",
                "dist_ly": "0",
                "proper": "Sol",
                "spect": "G2V",
                "gl": "",
                "exoplanet_count": "8",
                "has_known_exoplanets": "true",
                "x": "0",
                "y": "0",
                "z": "0",
                "hyg_id": "0",
                "hip": "",
            },
            {
                "star_key": "gaia:704966762213039488",
                "gaia_source_id": "704966762213039488",
                "dist_ly": "10.5",
                "proper": 'Rigil "Kent", A',
                "spect": "G2V",
                "gl": "Gl 559 A",
                "exoplanet_count": "1",
                "has_known_exoplanets": "true",
                "x": "0.1",
                "y": "-0.4",
                "z": "3",
                "hyg_id": "",
                "hip": "71683",
            },
        ]
    )


class FormatRoundtripTests(unittest.TestCase):
    def test_every_format_keeps_text(self):
        original = as_text_frame(_sample())
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for fmt in ALL:
                path = folder / f"stars.{fmt}"
                info = write_format(original, fmt, path)
                self.assertTrue(info["ok"], info)
                self.assertGreater(info["bytes"], 0)
                loaded = read_format(fmt, path)
                self.assertEqual(frame_digest(original), frame_digest(loaded), fmt)
                left = as_text_frame(original).sort_values("star_key").reset_index(drop=True)
                right = as_text_frame(loaded).sort_values("star_key").reset_index(drop=True)
                self.assertEqual(left.to_dict("records"), right.to_dict("records"), fmt)
                self.assertEqual(right.loc[right["star_key"] != "hyg:0", "gaia_source_id"].iloc[0], "704966762213039488")
                self.assertEqual(right.loc[right["star_key"] != "hyg:0", "dist_ly"].iloc[0], "10.5")

    def test_optional_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stars.npz"
            with patch("bench.formats_io._write_npz", side_effect=RuntimeError("boom")):
                info = write_format(_sample(), "npz", path)
            self.assertFalse(info["ok"])
            self.assertIn("boom", info["error"])
            self.assertFalse(path.exists())

    def test_required_failure_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stars.sqlite"
            with patch("bench.formats_io._write_sqlite", side_effect=RuntimeError("disk")):
                with self.assertRaises(RuntimeError):
                    write_format(_sample(), "sqlite", path)


class CatalogPrepTests(unittest.TestCase):
    def test_radius_keeps_sol_and_drops_far_stars(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stars.csv"
            pd.DataFrame(
                [
                    {"star_key": "hyg:0", "proper": "Sol", "dist_ly": "", "x": "0", "y": "0", "z": "0"},
                    {"star_key": "gaia:near", "proper": "Near", "dist_ly": "10", "x": "1", "y": "0", "z": "0"},
                    {"star_key": "gaia:edge", "proper": "Edge", "dist_ly": "500", "x": "10", "y": "0", "z": "0"},
                    {"star_key": "gaia:far", "proper": "Far", "dist_ly": "800", "x": "200", "y": "0", "z": "0"},
                ]
            ).to_csv(path, index=False)
            kept = read_catalog(path, 900)
            self.assertEqual(set(kept["star_key"]), {"hyg:0", "gaia:near", "gaia:edge"})
            inner = filter_radius(kept, 100)
            self.assertEqual(set(inner["star_key"]), {"hyg:0", "gaia:near"})

    def test_filter_without_proper_name(self):
        frame = pd.DataFrame({"star_key": ["hyg:0", "gaia:1", "gaia:2"], "dist_ly": ["", "10", "900"]})
        kept = filter_radius(frame, 500)
        self.assertEqual(set(kept["star_key"]), {"hyg:0", "gaia:1"})

    def test_digest_ignores_row_order(self):
        frame = _sample()
        self.assertEqual(frame_digest(frame), frame_digest(frame.iloc[::-1].reset_index(drop=True)))

    def test_adapt_keeps_gl_and_variable_flag(self):
        raw = pd.DataFrame(
            [
                {
                    "star_key": "gaia:1",
                    "proper": "Near",
                    "dist_ly": "4",
                    "dist_pc": "1.2",
                    "x": "1",
                    "y": "0",
                    "z": "0",
                    "spect": "G8V",
                    "has_known_exoplanets": "false",
                    "exoplanet_count": "0",
                    "gl": "Gl 1",
                    "hyg_id": "10",
                    "hip": "",
                    "gaia_source_id": "704966762213039488",
                    "ra_deg": "0",
                    "dec_deg": "0",
                    "mag_v": "5",
                    "variable": "yes",
                }
            ]
        )
        adapted = adapt_frame(raw, {})
        self.assertEqual(adapted.iloc[0]["gl"], "Gl 1")
        self.assertEqual(adapted.iloc[0]["variable"], "yes")
        self.assertEqual(adapted.iloc[0]["gaia_source_id"], "704966762213039488")
        self.assertEqual(adapted.iloc[0]["hostname"], "Near")

    def test_adapt_suffixes_duplicate_hostnames(self):
        raw = pd.DataFrame(
            [
                {
                    "star_key": "gaia:1",
                    "proper": "Twin",
                    "dist_ly": "4",
                    "dist_pc": "1.2",
                    "x": "1",
                    "y": "0",
                    "z": "0",
                    "spect": "G8V",
                    "has_known_exoplanets": "false",
                    "exoplanet_count": "0",
                },
                {
                    "star_key": "gaia:2",
                    "proper": "Twin",
                    "dist_ly": "5",
                    "dist_pc": "1.5",
                    "x": "1.1",
                    "y": "0",
                    "z": "0",
                    "spect": "K2V",
                    "has_known_exoplanets": "false",
                    "exoplanet_count": "0",
                },
            ]
        )
        adapted = adapt_frame(raw, {})
        self.assertEqual(adapted.iloc[0]["hostname"], "Twin")
        self.assertEqual(adapted.iloc[1]["hostname"], "Twin [gaia:2]")
        self.assertEqual(adapted.iloc[1]["sy_name"], "Twin [gaia:2]")


class SweepTests(unittest.TestCase):
    def test_matrix_obeys_caps_and_one_factor_rule(self):
        matrix = build_matrix()
        validate_matrix(matrix)
        names = [item["name"] for item in matrix["variants"]]
        self.assertIn("combined_m025", names)
        self.assertIn("combined_m030", names)
        for item in matrix["variants"]:
            self.assertGreaterEqual(item["params"]["min_stellar_mass"], 0.25)
            self.assertLessEqual(item["params"]["max_neighbors"], 16)
            self.assertLessEqual(item["params"]["max_distance_ly"], 500)
        self.assertEqual(changed_parameters(matrix["baseline"]), [])
        bad = build_matrix()
        bad["variants"][0]["params"]["min_stellar_mass"] = 0.1
        with self.assertRaises(ValueError):
            validate_matrix(bad)

    def test_write_sweep_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_sweep(Path(tmp) / "sweep.json")
            payload = json.loads(path.read_text(encoding="utf-8"))
            validate_matrix(payload)


class LogAndPreflightTests(unittest.TestCase):
    def test_log_line_fields_and_restart_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "bench_log.txt"
            line = append_log(
                log,
                {
                    "step": "load",
                    "format": "csv",
                    "variant": "mass_extreme",
                    "phase": "load",
                    "seconds": 1.25,
                    "gates": 3,
                    "routes": 2,
                    "rows": 10,
                    "note": "hello",
                },
            )
            body = line.strip().split(" ", 1)[1]
            keys = [part.split("=", 1)[0] for part in body.split(" ")]
            self.assertEqual(keys[: len(LOG_KEYS)], list(LOG_KEYS))
            self.assertIn("phase=load", line)
            self.assertEqual(pass_state(log), "empty")
            append_log(log, {"step": "suite_start"})
            self.assertEqual(pass_state(log), "incomplete")
            job = Path(tmp) / "job"
            report = job / "report.md"
            job.mkdir()
            report.write_text("stale\n", encoding="utf-8")
            begin_pass(log, Path(tmp) / "staging", job, report)
            text = log.read_text(encoding="utf-8")
            self.assertIn("step=restart", text)
            self.assertFalse(report.exists())
            self.assertTrue((Path(tmp) / "staging" / "formats").is_dir())
            self.assertTrue((job / "maps").is_dir())
            self.assertEqual(pass_state(log), "incomplete")
            append_log(log, {"step": "suite_complete"})
            self.assertEqual(pass_state(log), "complete")
            begin_pass(log, Path(tmp) / "staging", job, None)
            tail = log.read_text(encoding="utf-8")
            complete_at = tail.rfind("step=suite_complete")
            self.assertNotIn("step=restart", tail[complete_at:])

    def test_reset_retries_when_a_tree_is_locked(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job"
            staging = Path(tmp) / "staging"
            locked = job / "maps" / "csv" / "combined_m025"
            locked.mkdir(parents=True)
            (locked / "summary.json").write_text("{}\n", encoding="utf-8")
            log = job / "bench_log.txt"
            calls = {"n": 0}
            real = __import__("shutil").rmtree

            def flaky(path, *args, **kwargs):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise PermissionError(13, "locked", str(path))
                return real(path, *args, **kwargs)

            with patch("bench.run_suite.shutil.rmtree", side_effect=flaky):
                with patch("bench.run_suite.time.sleep", lambda _seconds: None):
                    begin_pass(log, staging, job, None)
            self.assertFalse(locked.exists())
            self.assertIn("step=reset_wait", log.read_text(encoding="utf-8"))
            self.assertTrue((job / "maps").is_dir())

    def test_preflight_uses_the_injected_command(self):
        calls = {"n": 0}

        def runner(cmd: str):
            self.assertEqual(cmd, "fake-preflight")
            calls["n"] += 1
            if calls["n"] == 1:
                return 1, "cpu 90%"
            return 0, "CLEAR"

        slept = []
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "bench_log.txt"
            wait_until_clear(
                "fake-preflight",
                log,
                runner=runner,
                sleep_fn=slept.append,
                sleep_s=60,
                max_waits=3,
            )
            text = log.read_text(encoding="utf-8")
            self.assertEqual(slept, [60])
            self.assertIn("step=preflight_wait", text)
            self.assertIn("CLEAR", text)
            with self.assertRaises(RuntimeError):
                wait_until_clear(
                    "fake-preflight",
                    log,
                    runner=lambda _cmd: (1, "busy"),
                    sleep_fn=lambda _seconds: None,
                    sleep_s=60,
                    max_waits=2,
                )

    def test_begin_pass_raises_when_done_flag_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job"
            staging = Path(tmp) / "staging"
            job.mkdir()
            (job / "maps").mkdir()
            marker = job / "maps" / "keep.txt"
            marker.write_text("x", encoding="utf-8")
            report = job / "report.md"
            report.write_text("stale\n", encoding="utf-8")
            flag = Path(tmp) / "DONE.flag"
            flag.write_text("done\n", encoding="utf-8")
            log = job / "bench_log.txt"
            with patch.dict(os.environ, {"BENCH_DONE_FLAG": str(flag)}):
                with self.assertRaises(RuntimeError) as caught:
                    begin_pass(log, staging, job, report)
            self.assertIn("refused_done_flag", str(caught.exception))
            self.assertEqual(report.read_text(encoding="utf-8"), "stale\n")
            self.assertEqual(marker.read_text(encoding="utf-8"), "x")
            self.assertFalse((staging / "formats").exists())
            self.assertFalse(log.exists())

    def test_begin_pass_runs_when_done_flag_file_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job"
            job.mkdir()
            log = job / "bench_log.txt"
            missing = Path(tmp) / "missing.flag"
            with patch.dict(os.environ, {"BENCH_DONE_FLAG": str(missing)}):
                begin_pass(log, Path(tmp) / "staging", job, None)
            text = log.read_text(encoding="utf-8")
            self.assertIn("step=suite_start", text)
            self.assertNotIn("refused_done_flag", text)

    def test_begin_pass_runs_when_done_flag_env_is_unset_or_blank(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job"
            job.mkdir()
            staging = Path(tmp) / "staging"
            cases = (
                ("blank", {"BENCH_DONE_FLAG": "  "}, False),
                ("empty", {"BENCH_DONE_FLAG": ""}, False),
                ("unset", {"BENCH_DONE_FLAG": "sentinel"}, True),
            )
            for name, extra, pop_flag in cases:
                log = job / f"{name}.log"
                with patch.dict(os.environ, extra, clear=False):
                    if pop_flag:
                        os.environ.pop("BENCH_DONE_FLAG", None)
                    begin_pass(log, staging, job, None)
                text = log.read_text(encoding="utf-8")
                self.assertIn("step=suite_start", text, name)
                self.assertNotIn("refused_done_flag", text, name)

    def test_execute_refuses_when_done_flag_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job"
            staging = Path(tmp) / "staging"
            job.mkdir()
            staging.mkdir()
            report = job / "sb_phase2_report_20261030_r5.md"
            report.write_text("keep\n", encoding="utf-8")
            (staging / "formats").mkdir()
            kept = staging / "formats" / "keep.txt"
            kept.write_text("x", encoding="utf-8")
            flag = job / "DONE.flag"
            flag.write_text("done\n", encoding="utf-8")
            env = {
                "BENCH_JOB_DIR": str(job),
                "BENCH_STAGING": str(staging),
                "BENCH_DONE_FLAG": str(flag),
                "BENCH_CATALOG": "should-not-be-read",
                "BENCH_PREFLIGHT_CMD": "should-not-run",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("bench.run_suite.begin_pass") as begin:
                    with patch("bench.run_suite._reset_dir") as reset:
                        with patch("bench.run_suite._unlink_when_free") as unlink:
                            execute()
            self.assertEqual(begin.call_count, 0)
            self.assertEqual(reset.call_count, 0)
            self.assertEqual(unlink.call_count, 0)
            self.assertEqual(report.read_text(encoding="utf-8"), "keep\n")
            self.assertEqual(kept.read_text(encoding="utf-8"), "x")
            log = (job / "bench_log.txt").read_text(encoding="utf-8")
            self.assertEqual(log.count("step=refused_done_flag"), 1)
            self.assertEqual(log.count("\n"), 1)

    def test_execute_reaches_begin_pass_when_flag_is_unset_or_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job"
            job.mkdir()
            base = {
                "BENCH_JOB_DIR": str(job),
                "BENCH_STAGING": str(Path(tmp) / "staging"),
                "BENCH_CATALOG": str(Path(tmp) / "missing.csv"),
                "BENCH_PREFLIGHT_CMD": "should-not-run",
            }
            missing = Path(tmp) / "missing.flag"

            def run_until_begin(extra: dict[str, str], pop_flag: bool) -> None:
                updates = {**base, **extra}
                if pop_flag:
                    updates["BENCH_DONE_FLAG"] = ""
                with patch.dict(os.environ, updates, clear=False):
                    if pop_flag:
                        os.environ.pop("BENCH_DONE_FLAG", None)
                    with patch("bench.run_suite.begin_pass", side_effect=RuntimeError("reached-begin")) as begin:
                        with self.assertRaises(RuntimeError) as caught:
                            execute()
                        self.assertEqual(str(caught.exception), "reached-begin")
                        self.assertEqual(begin.call_count, 1)

            run_until_begin({}, pop_flag=True)
            run_until_begin({"BENCH_DONE_FLAG": str(missing)}, pop_flag=False)
            run_until_begin({"BENCH_DONE_FLAG": "   "}, pop_flag=False)


class InspectAndReportTests(unittest.TestCase):
    def test_inspect_counts_and_rejects_broken_caps(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.csv"
            pd.DataFrame(
                {
                    "hostname": ["Sol", "Near"],
                    "gate_distance": ["0", "1"],
                    "st_mass": ["1.0", "0.8"],
                    "neighbor_1_hostname": ["Near", "Sol"],
                    "neighbor_2_hostname": ["", ""],
                }
            ).to_csv(good, index=False)
            info = inspect_network(good, 2, 0.25)
            self.assertEqual(info["gates"], 2)
            self.assertEqual(info["routes"], 1)
            self.assertEqual(info["rows"], 2)
            low = Path(tmp) / "low.csv"
            pd.DataFrame(
                {
                    "hostname": ["Sol", "Far"],
                    "gate_distance": ["0", "1"],
                    "st_mass": ["1", "0.1"],
                    "neighbor_1_hostname": ["Far", "Sol"],
                }
            ).to_csv(low, index=False)
            with self.assertRaises(RuntimeError):
                inspect_network(low, 2, 0.25)
            wide = Path(tmp) / "wide.csv"
            pd.DataFrame(
                {
                    "hostname": ["Sol"],
                    "gate_distance": ["0"],
                    "st_mass": ["1"],
                    "neighbor_1_hostname": ["A"],
                    "neighbor_2_hostname": ["B"],
                }
            ).to_csv(wide, index=False)
            with self.assertRaises(RuntimeError):
                inspect_network(wide, 1, 0.25)

    def test_rank_ignores_later_phases_and_breaks_ties(self):
        rows = [
            {"format": "csv", "phase_group": "extreme", "load_s": 3, "generate_s": 1, "bytes": 100},
            {"format": "csv", "phase_group": "extreme", "load_s": 5, "generate_s": 1, "bytes": 100},
            {"format": "parquet", "phase_group": "extreme", "load_s": 1, "generate_s": 1, "bytes": 50},
            {"format": "parquet", "phase_group": "midpoint", "load_s": 9, "generate_s": 9, "bytes": 50},
            {"format": "feather", "phase_group": "extreme", "load_s": 1, "generate_s": 1, "bytes": 40},
        ]
        ranked = rank_formats(rows)
        self.assertEqual([item["format"] for item in ranked], ["feather", "parquet", "csv"])
        self.assertAlmostEqual(ranked[0]["mean_sum"], 2.0)
        text = " ".join(postgres_paragraphs(ranked))
        self.assertIn("Postgres is not needed", text)
        self.assertNotIn("(pending)", text)

    def test_report_has_required_sections(self):
        matrix = build_matrix()
        results = [
            {
                "format": "parquet",
                "variant": "mass_extreme",
                "phase_group": "extreme",
                "convert_s": 1,
                "load_s": 0.5,
                "generate_s": 0.5,
                "total_s": 2,
                "bytes": 1000,
                "summary_path": "C:/maps/parquet/mass_extreme/summary.json",
                "map_path": "C:/maps/parquet/mass_extreme/network.csv",
            }
        ]
        ranking = rank_formats(
            [
                {
                    "format": "parquet",
                    "phase_group": "extreme",
                    "load_s": 0.5,
                    "generate_s": 0.5,
                    "bytes": 1000,
                }
            ]
        )
        meta = {
            "catalog_rows": 3,
            "digest": "abc",
            "enrichment_keys": 4,
            "ranking": ranking,
            "selected": ["parquet", "feather"],
            "counts": [
                {
                    "name": "mass_extreme",
                    "phase": "extreme",
                    "radius": 100,
                    "mass": 0.25,
                    "route_cap": 16,
                    "spacing": 16,
                    "criteria": "standard",
                    "gates": 2,
                    "routes": 1,
                    "rows": 3,
                    "agree": "yes",
                }
            ],
            "adapt": {"100.0000": {"seconds": "0.1000", "rows": 3, "hosts": 1, "mass_known": 2}},
            "markers": {"variable_mark": 0},
            "postgres": postgres_paragraphs(ranking),
            "final_line": "FINAL: PASS - fastest parquet mean load+generate 1.0s; extreme variants 7 on 8 formats; combined_m025 gates 2 routes 1",
        }
        with tempfile.TemporaryDirectory() as tmp:
            status = Path(tmp) / "court-status.md"
            status.write_text("1. **One**\n- 19. Example\n**3)** Extra\n", encoding="utf-8")
            self.assertEqual(status_number(status), 20)
            text = render_report(
                results=results,
                matrix=matrix,
                meta=meta,
                needs=["npz: boom"],
                job_dir=Path(tmp),
                report_path=Path(tmp) / "report.md",
                status_path=status,
            )
        for heading in (
            "Timing table",
            "Gate and route counts",
            "Sweep definition",
            "Postgres recommendation",
            "Log paths",
            "Map output paths",
            "Court-status line",
            "Needs Doug",
        ):
            self.assertIn(heading, text)
        lines = [line for line in text.splitlines() if line.strip()]
        self.assertEqual(lines[-1], "RUN FINISHED")
        self.assertTrue(lines[-2].startswith("FINAL: PASS - "))
        self.assertNotIn("(pending)", text)
        self.assertIn("npz: boom", text)
        self.assertIn("20. **jumpgate_starroute storage-format benchmark (phase 2)**", text)


if __name__ == "__main__":
    unittest.main()
