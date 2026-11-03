"""Catalog load, trim, tiers, handoff, and CLI. Stdlib unittest only."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CASES = FIXTURES / "tier_cases.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from starroute.catalog import (  # noqa: E402
    adapt_merged_row,
    iter_catalog_rows,
    load_trimmed_frame,
    resolve_catalog_path,
    stream_trimmed_rows,
    trim_records,
)
from starroute.handoff import handoff_from_row, load_schema, validate_handoff  # noqa: E402
from starroute.luminosity import calculate_luminosity  # noqa: E402
from starroute.mapgen.network import _score_row, _valid_row, generate_network, network_payload  # noqa: E402
from starroute.mapgen.ranking import composite_ranking  # noqa: E402
from starroute.mapgen.tiers import classify_tier, meets_gate_criteria  # noqa: E402
from starroute.presets import resolve_catalog  # noqa: E402
from starroute.turquenish import apply_turquenish, lookup_turquenish  # noqa: E402


def _write_merged(path: Path) -> None:
    header = [
        "star_key", "gaia_source_id", "hyg_id", "hip", "hd", "hr", "gl", "proper",
        "exo_hostname", "ra_deg", "dec_deg", "epoch", "dist_pc", "dist_ly", "x", "y", "z",
        "parallax", "pmra", "pmdec", "radial_velocity", "mag_v", "phot_g_mean_mag",
        "render_mag", "bp_rp", "ci", "spect", "has_known_exoplanets", "exoplanet_count",
        "exo_match_method", "sources", "match_method", "turquenish_system", "st_mass",
    ]
    rows = [
        {"star_key": "hyg:0", "hyg_id": "0", "proper": "Sol", "dist_ly": "0", "dist_pc": "0",
         "x": "0", "y": "0", "z": "0", "ra_deg": "0", "dec_deg": "0", "spect": "G2V",
         "has_known_exoplanets": "false", "exoplanet_count": "0", "render_mag": "-26.7", "st_mass": ""},
        {"star_key": "gaia:111", "gaia_source_id": "111", "hyg_id": "11", "hip": "111",
         "proper": "Near Gate", "dist_ly": "10", "dist_pc": "3.066", "x": "3.066", "y": "0", "z": "0",
         "ra_deg": "0", "dec_deg": "0", "spect": "G8V", "has_known_exoplanets": "true",
         "exoplanet_count": "2", "render_mag": "5", "st_mass": "1.0"},
        {"star_key": "gaia:222", "gaia_source_id": "222", "hyg_id": "22", "hip": "222",
         "proper": "Low Mass", "dist_ly": "8", "dist_pc": "2.45", "x": "2.45", "y": "0", "z": "0",
         "spect": "M6V", "has_known_exoplanets": "true", "exoplanet_count": "1",
         "render_mag": "12", "st_mass": "0.1"},
        {"star_key": "gaia:333", "gaia_source_id": "333", "hyg_id": "33", "hip": "333",
         "proper": "Background", "dist_ly": "5", "dist_pc": "1.53", "x": "1.53", "y": "0", "z": "0",
         "spect": "K0V", "has_known_exoplanets": "false", "exoplanet_count": "0",
         "render_mag": "8", "st_mass": "1.0"},
        {"star_key": "gaia:444", "gaia_source_id": "444", "hyg_id": "44", "hip": "444",
         "proper": "Far Exo", "dist_ly": "40", "dist_pc": "12.26", "x": "12.26", "y": "0", "z": "0",
         "spect": "G2V", "has_known_exoplanets": "true", "exoplanet_count": "1",
         "render_mag": "6", "st_mass": "1.0"},
        {"star_key": "hyg:555", "hyg_id": "555", "hip": "555", "proper": "On Rim",
         "dist_ly": "20", "dist_pc": "6.13", "x": "6.13", "y": "0", "z": "0",
         "spect": "G5V", "has_known_exoplanets": "true", "exoplanet_count": "1",
         "render_mag": "7", "st_mass": "0.9"},
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            full = {key: "" for key in header}
            full.update(row)
            writer.writerow(full)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TrimTests(unittest.TestCase):
    def test_trim_keeps_only_the_radius_and_leaves_the_full_set(self):
        stars = [
            {"hostname": "in", "calculated_x": 10, "calculated_y": 0, "calculated_z": 0},
            {"hostname": "edge", "calculated_x": 20, "calculated_y": 0, "calculated_z": 0},
            {"hostname": "out", "calculated_x": 20.001, "calculated_y": 0, "calculated_z": 0},
        ]
        before = [dict(row) for row in stars]
        kept = trim_records(stars, (0, 0, 0), 20)
        self.assertEqual([row["hostname"] for row in kept], ["in", "edge"])
        self.assertEqual(stars, before)
        self.assertEqual(len(stars), 3)

    def test_stream_does_not_rewrite_the_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "merged.csv"
            _write_merged(path)
            digest = _sha(path)
            rows = stream_trimmed_rows(path, origin="Sol", max_distance_ly=20, enrichment={})
            self.assertEqual(_sha(path), digest)
            names = {row["hostname"] for row in rows}
            self.assertEqual(names, {"Sol", "Near Gate", "Low Mass", "Background", "On Rim"})
            self.assertEqual(sum(1 for _ in iter_catalog_rows(path)), 6)
            frame = load_trimmed_frame(path, "Sol", 20, enrichment={})
            tiers = dict(zip(frame["hostname"], frame.apply(
                lambda row: classify_tier(row, 0.25, None, "Sol"), axis=1
            )))
            self.assertEqual(tiers["Sol"], "gate_candidate")
            self.assertEqual(tiers["Near Gate"], "gate_candidate")
            self.assertEqual(tiers["Low Mass"], "exo_no_gate")
            self.assertEqual(tiers["Background"], "no_known_planets")
            self.assertEqual(tiers["On Rim"], "gate_candidate")


class FallbackTests(unittest.TestCase):
    def test_missing_catalog_uses_sample(self):
        preset = {
            "id": "unit",
            "origin": {"origin_hostname": "Sol", "max_distance_ly": 60},
            "network": {"min_stellar_mass": 0.25},
        }
        saved = os.environ.pop("STARROUTE_CATALOG", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                config = folder / "catalog.json"
                config.write_text(json.dumps({"merged_catalog": str(folder / "missing.csv")}), encoding="utf-8")
                raw = folder / "raw"
                raw.mkdir()
                result = resolve_catalog(preset, raw_dir=raw, config_file=config)
        finally:
            if saved is not None:
                os.environ["STARROUTE_CATALOG"] = saved
        self.assertEqual(result["source"], "sample")
        self.assertTrue(str(result["systems_path"]).endswith("sample-systems.csv"))

    def test_configured_path_resolves_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "stars.csv"
            catalog.write_text("star_key\nhyg:0\n", encoding="utf-8")
            config = Path(tmp) / "catalog.json"
            config.write_text(json.dumps({"merged_catalog": str(catalog)}), encoding="utf-8")
            saved = os.environ.pop("STARROUTE_CATALOG", None)
            try:
                found = resolve_catalog_path(config_file=config)
            finally:
                if saved is not None:
                    os.environ["STARROUTE_CATALOG"] = saved
        self.assertEqual(found, catalog)


class TierTests(unittest.TestCase):
    def test_fixture_cases(self):
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        for item in cases:
            got = classify_tier(
                item["row"],
                item["min_stellar_mass"],
                item["max_stellar_mass"],
                item["origin"],
            )
            self.assertEqual(got, item["expect"], item["name"])

    def test_gate_criteria_match_valid_row_for_planet_hosts(self):
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        for item in cases:
            row = item["row"]
            if not row.get("has_known_exoplanets") and not (row.get("exoplanet_count") or 0):
                continue
            if row.get("hostname") == item["origin"] and item["expect"] == "no_known_planets":
                continue
            series = pd.Series(row)
            self.assertEqual(
                meets_gate_criteria(series, item["min_stellar_mass"], item["max_stellar_mass"], item["origin"]),
                _valid_row(series, item["min_stellar_mass"], item["origin"], item["max_stellar_mass"]),
                item["name"],
            )

    def test_background_cannot_hold_a_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            systems = Path(tmp) / "systems.csv"
            systems.write_text(
                "hostname,calculated_x,calculated_y,calculated_z,st_mass,sy_pnum,exoplanet_count,has_known_exoplanets\n"
                "Sol,0,0,0,1,8,8,true\n"
                "Near Gate,10,0,0,1,2,2,true\n"
                "Low Mass,8,0,0,0.1,1,1,true\n"
                "Background,5,0,0,1,0,0,false\n",
                encoding="utf-8",
            )
            out = Path(tmp) / "network.csv"
            result = generate_network(
                systems_path=str(systems),
                output_path=str(out),
                params={"max_jump_ly": 30, "min_stellar_mass": 0.25, "root_hostname": "Sol"},
            )
            frame = pd.read_csv(out)
            payload = network_payload(frame)
            linked = {edge["a"] for edge in payload["edges"]} | {edge["b"] for edge in payload["edges"]}
            self.assertIn("Near Gate", linked)
            self.assertNotIn("Background", linked)
            self.assertNotIn("Low Mass", linked)
            tiers = dict(zip(frame["hostname"], frame["tier"]))
            self.assertEqual(tiers["Background"], "no_known_planets")
            self.assertEqual(tiers["Low Mass"], "exo_no_gate")
            self.assertEqual(tiers["Near Gate"], "gate_candidate")
            self.assertGreaterEqual(result["tier_counts"]["no_known_planets"], 1)

    def test_engine_copy_matches(self):
        package = ROOT / "starroute" / "mapgen"
        engine = ROOT / "starroute" / "web" / "static" / "engine" / "starroute" / "mapgen"
        for name in ("tiers.py", "network.py", "ranking.py"):
            self.assertEqual(
                (package / name).read_text(encoding="utf-8"),
                (engine / name).read_text(encoding="utf-8"),
                name,
            )
        self.assertIn("classify_frame", (engine / "network.py").read_text(encoding="utf-8"))
        self.assertIn("no_known_planets", (engine / "factions.py").read_text(encoding="utf-8"))

    def test_no_planet_no_mass_is_not_a_gate(self):
        row = {
            "hostname": "BareDark",
            "calculated_x": 5,
            "calculated_y": 0,
            "calculated_z": 0,
            "st_mass": None,
            "sy_pnum": 0,
            "has_known_exoplanets": False,
        }
        self.assertEqual(classify_tier(row), "no_known_planets")
        self.assertFalse(meets_gate_criteria(row))
        self.assertFalse(_valid_row(pd.Series(row), 0.25, "Sol", None))
        origin = {
            "hostname": "Sol",
            "calculated_x": 0,
            "calculated_y": 0,
            "calculated_z": 0,
            "st_mass": None,
            "sy_pnum": 0,
            "has_known_exoplanets": False,
        }
        self.assertEqual(classify_tier(origin), "no_known_planets")
        self.assertFalse(meets_gate_criteria(origin))
        self.assertFalse(_valid_row(pd.Series(origin), 0.25, "Sol", None))
        with tempfile.TemporaryDirectory() as tmp:
            systems = Path(tmp) / "systems.csv"
            systems.write_text(
                "hostname,calculated_x,calculated_y,calculated_z,st_mass,sy_pnum,exoplanet_count,has_known_exoplanets\n"
                "Sol,0,0,0,1,8,8,true\n"
                "Near Gate,10,0,0,1,2,2,true\n"
                "BareDark,5,0,0,,0,0,false\n",
                encoding="utf-8",
            )
            out = Path(tmp) / "network.csv"
            generate_network(
                systems_path=str(systems),
                output_path=str(out),
                params={"max_jump_ly": 30, "min_stellar_mass": 0.25, "root_hostname": "Sol"},
            )
            frame = pd.read_csv(out)
            payload = network_payload(frame)
            linked = {edge["a"] for edge in payload["edges"]} | {edge["b"] for edge in payload["edges"]}
            self.assertNotIn("BareDark", linked)
            tiers = dict(zip(frame["hostname"], frame["tier"]))
            self.assertEqual(tiers["BareDark"], "no_known_planets")

    def test_mass_unknown_host_is_a_gate_and_takes_one_stability_step(self):
        row = pd.Series({
            "hostname": "NoMass",
            "calculated_x": 6,
            "calculated_y": 0,
            "calculated_z": 0,
            "st_mass": None,
            "sy_pnum": 1,
            "exoplanet_count": 1,
            "has_known_exoplanets": True,
            "stability_score": 0,
            "carbon_ranking": 1,
            "sulfur_ranking": 1,
            "silicon_ranking": 1,
            "sy_snum": 1,
            "sy_mnum": 0,
            "cb_flag": 0,
            "st_met": 0.1,
        })
        self.assertEqual(classify_tier(row, 0.25, None, "Sol"), "gate_candidate")
        distance = 4.0
        preferred = 16.0
        got = _score_row(row, distance, preferred, None)
        expect = composite_ranking(1, 1, 1, 1, 1, 1, 0, 0, 0.1, distance, preferred_ly=preferred)
        calm = composite_ranking(1, 1, 1, 0, 1, 1, 0, 0, 0.1, distance, preferred_ly=preferred)
        self.assertAlmostEqual(got, expect)
        self.assertAlmostEqual(expect - calm, -0.05)
        self.assertEqual(row["stability_score"], 0)
        blank = row.copy()
        blank["stability_score"] = None
        blank_score = _score_row(blank, distance, preferred, None)
        self.assertAlmostEqual(blank_score, expect)

    def test_known_low_mass_does_not_take_the_unknown_mass_step(self):
        row = pd.Series({
            "hostname": "Tiny",
            "calculated_x": 8,
            "calculated_y": 0,
            "calculated_z": 0,
            "st_mass": 0.1,
            "sy_pnum": 1,
            "exoplanet_count": 1,
            "has_known_exoplanets": True,
            "stability_score": 0,
            "carbon_ranking": 1,
            "sulfur_ranking": 0,
            "silicon_ranking": 0,
            "sy_snum": 1,
            "sy_mnum": 0,
            "cb_flag": 0,
            "st_met": None,
        })
        self.assertEqual(classify_tier(row), "exo_no_gate")
        distance = 3.0
        preferred = 16.0
        got = _score_row(row, distance, preferred, None)
        plain = composite_ranking(1, 0, 0, 0, 1, 1, 0, 0, None, distance, preferred_ly=preferred)
        stepped = composite_ranking(1, 0, 0, 1, 1, 1, 0, 0, None, distance, preferred_ly=preferred)
        self.assertAlmostEqual(got, plain)
        self.assertNotAlmostEqual(got, stepped)
        self.assertEqual(int(row["stability_score"]), 0)

    def test_calculated_luminosity_johnson_v(self):
        sunlike = {"dist_pc": 10, "mag_v": 4.83}
        lum, method = calculate_luminosity(sunlike)
        self.assertAlmostEqual(lum, 1.0, delta=1e-9)
        self.assertEqual(method, "johnson_v_no_bc")
        self.assertNotIn("st_lum", sunlike)
        adapted = adapt_merged_row({
            "star_key": "gaia:sunlike",
            "gaia_source_id": "1",
            "proper": "Sunlike",
            "dist_pc": 10,
            "dist_ly": 32.6156,
            "x": 10,
            "y": 0,
            "z": 0,
            "ra_deg": 0,
            "dec_deg": 0,
            "mag_v": 4.83,
            "has_known_exoplanets": "false",
        }, {})
        self.assertAlmostEqual(adapted["calculated_luminosity"], 1.0, delta=1e-9)
        self.assertEqual(adapted["calculated_luminosity_method"], "johnson_v_no_bc")
        self.assertNotIn("st_lum", adapted)
        for value in (0.0, 1.2):
            row = {"dist_pc": 10, "mag_v": 4.83, "st_lum": value}
            blocked, blocked_method = calculate_luminosity(row)
            self.assertIsNone(blocked)
            self.assertIsNone(blocked_method)
            self.assertEqual(row["st_lum"], value)


class HandoffTests(unittest.TestCase):
    def test_examples_and_belt_counts(self):
        schema = load_schema()
        tau = json.loads((ROOT / "docs" / "examples" / "tau-ceti.handoff.json").read_text(encoding="utf-8"))
        plain = json.loads((ROOT / "docs" / "examples" / "55-cnc.handoff.json").read_text(encoding="utf-8"))
        bee = json.loads((ROOT / "docs" / "examples" / "55-cnc-b.handoff.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_handoff(tau, schema), [])
        self.assertEqual(validate_handoff(plain, schema), [])
        self.assertEqual(validate_handoff(bee, schema), [])
        self.assertEqual(tau["system_file"], "tau-ceti.system.json")
        self.assertEqual(tau["turquenish_system"], "Turquenish")
        self.assertEqual(tau["lore_version"], "v2.41c")
        self.assertEqual(tau["rings_belts_version"], "v2.41j")
        self.assertEqual(tau["rings"], [])
        self.assertEqual(tau["sky"]["frame"], "icrs")
        self.assertIs(tau["sky"]["pole_rotation_applied"], False)
        self.assertIsNone(tau["sky"]["background_rotation"])
        # Sibling checkout is read-only and is not on every machine. Hash and sky files are checked when it is present.
        tau_file = Path(r"C:\Users\DougJ\Documents\GitHub\orbit_match\site\data\tau-ceti.system.json")
        if tau_file.is_file():
            self.assertEqual(tau["system_file_sha256"], hashlib.sha256(tau_file.read_bytes()).hexdigest())
            site = Path(r"C:\Users\DougJ\Documents\GitHub\orbit_match\site")
            self.assertTrue((site / tau["sky"]["equirect"]).is_file())
            self.assertTrue((site / tau["sky"]["cube_dir"]).is_dir())
        self.assertEqual(len(tau["belts"]), 2)
        self.assertIsNone(plain["system_file"])
        self.assertEqual(plain["belts"], [])
        self.assertEqual(plain["rings"], [])
        self.assertTrue(plain["has_known_exoplanets"])
        self.assertEqual(plain["hostname"], "55 Cnc")
        self.assertEqual(plain["name"], "Rho Cancri")
        self.assertEqual(plain["exoplanet_count"], 5)
        self.assertEqual(plain["sy_pnum"], 7)
        self.assertEqual(plain["st_mass"], 0.85)
        self.assertIs(plain["mass_known"], True)
        self.assertIsNone(plain["gate_status"])
        self.assertIsNone(plain["mass_unknown_penalty"])
        self.assertIsNone(plain["calculated_luminosity"])
        self.assertEqual(bee["hostname"], "55 Cnc B")
        self.assertEqual(bee["name"], "Rho Cancri B")
        self.assertIsNone(bee["gate_status"])
        self.assertEqual(bee["tier"], "gate_candidate")
        self.assertEqual(bee["exoplanet_count"], 2)
        self.assertEqual(bee["sy_pnum"], 7)
        self.assertEqual(bee["belts"], [])
        held = {
            "hostname": bee["hostname"],
            "gaia_source_id": bee["gaia_source_id"],
            "star_key": bee["star_key"],
            "st_mass": bee["st_mass"],
            "sy_pnum": bee["sy_pnum"],
            "exoplanet_count": bee["exoplanet_count"],
            "has_known_exoplanets": True,
            "calculated_x": -24.5,
            "calculated_y": 26.1,
            "calculated_z": 19.3,
        }
        self.assertEqual(classify_tier(held), "gate_candidate")
        self.assertTrue(meets_gate_criteria(held))
        empty = dict(plain)
        empty["belts"] = []
        many = dict(plain)
        many["belts"] = [{"name": f"Belt {i}", "kind": "belt"} for i in range(4)]
        hyg_only = dict(plain)
        hyg_only["gaia_source_id"] = None
        self.assertEqual(validate_handoff(empty, schema), [])
        self.assertEqual(validate_handoff(many, schema), [])
        self.assertEqual(validate_handoff(hyg_only, schema), [])

    def test_builder_uses_turquenish_overlay(self):
        row = {
            "star_key": "gaia:2452378776434477184",
            "gaia_source_id": "2452378776434477184",
            "hyg_id": "8087",
            "hip": "8102",
            "hd": "10700",
            "hostname": "tau Cet",
            "ra_deg": 26.00905506,
            "dec_deg": -15.9336802,
            "dist_pc": 3.652171,
            "x": 3.156191,
            "y": 1.539995,
            "z": -1.00261,
            "render_mag": 3.3003998,
            "bp_rp": 1.0512211,
            "ci": 0.727,
            "spect": "G8V",
            "has_known_exoplanets": "true",
            "exoplanet_count": 3,
            "st_mass": 0.8,
            "sy_pnum": 3,
            "calculated_x": 11.75,
            "calculated_y": 4.96,
            "calculated_z": -3.23,
        }
        record = handoff_from_row(row)
        self.assertEqual(validate_handoff(record), [])
        self.assertEqual(record["name"], "Tau Ceti")
        self.assertEqual(record["system_file"], "tau-ceti.system.json")
        self.assertEqual(record["turquenish_system"], "Turquenish")
        self.assertEqual(record["tier"], "gate_candidate")
        self.assertEqual(len(record["belts"]), 2)
        bare = {
            "star_key": "gaia:704967037090946688",
            "gaia_source_id": "704967037090946688",
            "hyg_id": "43464",
            "hostname": "55 Cnc",
            "name": "55 Cnc",
            "ra_deg": 133.1,
            "dec_deg": 28.3,
            "dist_pc": 12.59,
            "x": -7.58,
            "y": 8.08,
            "z": 5.97,
            "render_mag": 5.73,
            "bp_rp": 1.0,
            "ci": 0.87,
            "spect": "G8V",
            "has_known_exoplanets": True,
            "exoplanet_count": 5,
            "st_mass": 0.85,
            "calculated_x": -24.7,
            "calculated_y": 26.4,
            "calculated_z": 19.5,
        }
        other = handoff_from_row(bare)
        self.assertIsNone(other["system_file"])
        self.assertEqual(other["belts"], [])
        self.assertEqual(other["tier"], "gate_candidate")
        counted = {
            "star_key": "gaia:704967037090946688",
            "gaia_source_id": "704967037090946688",
            "hostname": "55 Cnc",
            "proper": "55 Cnc",
            "ra_deg": 133.14676062,
            "dec_deg": 28.329783,
            "dist_pc": 12.58682,
            "x": -7.576799,
            "y": 8.083511,
            "z": 5.973023,
            "mag": 5.732681,
            "sy_pnum": 7,
            "st_mass": 0.85,
            "has_known_exoplanets": True,
            "calculated_x": -24.7,
            "calculated_y": 26.4,
            "calculated_z": 19.5,
        }
        primary = handoff_from_row(counted)
        self.assertEqual(validate_handoff(primary), [])
        self.assertEqual(primary["hostname"], "55 Cnc")
        self.assertEqual(primary["name"], "Rho Cancri")
        self.assertEqual(primary["exoplanet_count"], 0)
        self.assertEqual(primary["sy_pnum"], 7)
        self.assertIsNone(primary["calculated_luminosity"])
        self.assertIsNone(primary["gate_status"])
        self.assertIsNone(primary["mass_unknown_penalty"])
        self.assertTrue(primary["mass_known"])
        explicit = dict(counted)
        explicit["exoplanet_count"] = 4
        self.assertEqual(handoff_from_row(explicit)["exoplanet_count"], 4)
        self.assertEqual(handoff_from_row(explicit)["sy_pnum"], 7)
        companion = dict(counted)
        companion["hostname"] = "55 Cnc B"
        companion["star_key"] = "gaia:704966762213039488"
        companion["gaia_source_id"] = "704966762213039488"
        companion["st_mass"] = 0.26
        companion["exoplanet_count"] = 2
        companion_record = handoff_from_row(companion)
        self.assertEqual(companion_record["exoplanet_count"], 2)
        self.assertEqual(companion_record["sy_pnum"], 7)
        self.assertIsNone(companion_record["gate_status"])
        self.assertEqual(companion_record["tier"], "gate_candidate")


class TurquenishTests(unittest.TestCase):
    def test_mapping_by_hip(self):
        self.assertEqual(lookup_turquenish({"hip": "HIP 8102"}), "Turquenish")
        self.assertEqual(lookup_turquenish({"star_key": "gaia:2452378776434477184"}), "Turquenish")
        frame = apply_turquenish(pd.DataFrame([{"hostname": "tau Cet", "hip": "8102"}]))
        self.assertEqual(frame.iloc[0]["turquenish_system"], "Turquenish")
        self.assertEqual(frame.iloc[0]["system_file"], "tau-ceti.system.json")
        self.assertEqual(lookup_turquenish({"hip": "1"}), "")


class CliTests(unittest.TestCase):
    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env.pop("STARROUTE_CATALOG", None)
        return subprocess.run(
            [sys.executable, "-m", "starroute", *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_help_ingest_network_lore_and_handoff(self):
        help_run = self._run(["--help"])
        self.assertEqual(help_run.returncode, 0, help_run.stderr)
        self.assertIn("handoff", help_run.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            planets = folder / "planets.csv"
            hosts = folder / "hosts.csv"
            planets.write_text("hostname,pl_name,pl_bmasse,pl_rade,pl_eqt\nDemo,Demo b,2,1.2,280\n", encoding="utf-8")
            hosts.write_text("hostname,ra,dec,sy_dist,st_mass,st_spectype\nDemo,10,0,5,0.9,G5V\n", encoding="utf-8")
            preview = self._run(["ingest", "--preview", "--planets", str(planets), "--hosts", str(hosts)])
            self.assertEqual(preview.returncode, 0, preview.stderr)
            systems = folder / "systems.csv"
            systems.write_text(
                "hostname,calculated_x,calculated_y,calculated_z,st_mass,sy_pnum,exoplanet_count,has_known_exoplanets\n"
                "Sol,0,0,0,1,8,8,true\nNear,10,0,0,1,1,1,true\n",
                encoding="utf-8",
            )
            network = self._run([
                "network", "--systems", str(systems), "--output", str(folder / "net.csv"),
                "--no-factions", "--max-jump", "30",
            ])
            self.assertEqual(network.returncode, 0, network.stderr)
            self.assertIn("gate_candidate", network.stdout)
            catalog = folder / "merged.csv"
            _write_merged(catalog)
            before = _sha(catalog)
            streamed = self._run([
                "network", "--catalog", str(catalog), "--output", str(folder / "from-catalog.csv"),
                "--no-factions", "--max-jump", "30", "--max-distance", "20",
            ])
            self.assertEqual(streamed.returncode, 0, streamed.stderr)
            self.assertEqual(_sha(catalog), before)
            lore = self._run(["build-lore", "--vault", str(ROOT / "setting"), "--dest", str(folder / "lore")])
            self.assertEqual(lore.returncode, 0, lore.stderr)
            handoff = self._run(["handoff", str(ROOT / "docs" / "examples" / "tau-ceti.handoff.json")])
            self.assertEqual(handoff.returncode, 0, handoff.stderr)
            static_map = ROOT / "starroute" / "web" / "static" / "presets" / "crowded" / "map.json"
            stamp = static_map.stat().st_mtime_ns
            presets = self._run([
                "build-presets", "--id", "crowded", "--catalog", str(catalog), "--dest", str(folder / "packs"),
            ])
            self.assertEqual(presets.returncode, 0, presets.stderr)
            self.assertEqual(static_map.stat().st_mtime_ns, stamp)
            self.assertTrue((folder / "packs" / "static" / "crowded" / "map.json").is_file())


if __name__ == "__main__":
    unittest.main()
