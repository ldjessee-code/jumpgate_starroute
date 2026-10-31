"""Per-host planet counts, companion-aware join, Rho Cancri rulings."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from starroute.catalog import adapt_merged_row, load_enrichment  # noqa: E402
from starroute.handoff import handoff_from_row, load_schema, validate_handoff  # noqa: E402
from starroute.ingest.nasa_tap import (  # noqa: E402
    OPTIONAL_PLANET_COLUMNS,
    PSCOMPPARS_COLUMNS,
    PSCOMPPARS_TAP_SELECT,
    PSCOMPPARS_TAP_SQL,
    PSCOMPPARS_TAP_URL,
)
from starroute.ingest.pipeline import PLANET_KEEP, _read_nasa_csv  # noqa: E402
from starroute.mapgen.tiers import classify_tier, gate_status_for, is_exoplanet_host, meets_gate_criteria  # noqa: E402
from starroute.names import (  # noqa: E402
    aliases_for,
    bayer_from_bf,
    catalog_id_token,
    components_compatible,
    display_name_for,
    gliese_token,
    split_host_component,
)

AFFECTED = Path(r"F:\Dropbox\TheCourt\research\_jobs\star-catalog\cnc55b_investigate_20261021\affected_systems.csv")

ZERO_PLANET_HOSTS = [
    "alf Cen A",
    "alf Cen B",
    "GJ 338 A",
    "HIP 55846",
    "Gl 617B",
    "Gl 667A",
    "HIP 96895",
]


def _coords(host: str, mass: float | None = 1.0) -> dict:
    row = {
        "hostname": host,
        "calculated_x": 10,
        "calculated_y": 0,
        "calculated_z": 0,
        "st_mass": mass,
    }
    return row


class ComponentParseTests(unittest.TestCase):
    def test_split_space_and_glued_letters(self):
        self.assertEqual(split_host_component("55 Cnc B"), ("55 Cnc", "B"))
        self.assertEqual(split_host_component("55 Cnc"), ("55 Cnc", ""))
        self.assertEqual(split_host_component("Gl 324B"), ("Gl 324", "B"))
        self.assertEqual(split_host_component("Gl 324 A"), ("Gl 324", "A"))
        self.assertEqual(split_host_component("HD 41004 B"), ("HD 41004", "B"))
        self.assertEqual(split_host_component("HIP 28393 A"), ("HIP 28393", "A"))
        self.assertFalse(components_compatible("55 Cnc", "55 Cnc B"))
        self.assertTrue(components_compatible("55 Cnc", "55 Cnc A"))
        self.assertTrue(components_compatible("Gl 324A", "55 Cnc"))

    def test_hip_letter_suffix_stays(self):
        self.assertEqual(catalog_id_token("HIP 28393 A", "HIP"), "28393A")
        self.assertEqual(catalog_id_token("HIP 28393 B", "HIP"), "28393B")
        self.assertEqual(catalog_id_token("HIP 28393", "HIP"), "28393")
        self.assertEqual(catalog_id_token("HD 41004 A", "HD"), "41004A")
        self.assertNotEqual(catalog_id_token("HIP 28393 A", "HIP"), catalog_id_token("HIP 28393 B", "HIP"))
        self.assertEqual(gliese_token("Gl 324B"), "324B")
        self.assertEqual(gliese_token("GJ 324 A"), "324A")


class PlanetCountTests(unittest.TestCase):
    def test_sy_pnum_is_not_the_per_star_count(self):
        companion = adapt_merged_row(
            {
                "star_key": "hyg:45211",
                "hyg_id": "45211",
                "hip": "45343",
                "hd": "79210",
                "gl": "Gl 338A",
                "proper": "",
                "hostname": "GJ 338 A",
                "ra_deg": 10,
                "dec_deg": 10,
                "dist_pc": 6,
                "dist_ly": 20,
                "x": 6,
                "y": 0,
                "z": 0,
                "has_known_exoplanets": "false",
                "exoplanet_count": "0",
            },
            {
                "host:gj 338 a": {"st_mass": "0.69", "sy_pnum": "1", "sy_snum": "2"},
                "hip:45343": {"st_mass": "0.69", "sy_pnum": "1"},
            },
        )
        self.assertEqual(float(companion["exoplanet_count"]), 0)
        self.assertEqual(str(companion["has_known_exoplanets"]).lower(), "false")
        self.assertEqual(float(companion["sy_pnum"]), 1)
        self.assertEqual(float(companion["st_mass"]), 0.69)
        self.assertFalse(is_exoplanet_host(companion))
        self.assertEqual(classify_tier(companion), "no_known_planets")

        counted = dict(_coords("HIP 84709", 0.59))
        counted["sy_pnum"] = 5
        counted["sy_snum"] = 3
        counted["has_known_exoplanets"] = False
        self.assertEqual(handoff_from_row(counted)["exoplanet_count"], 0)
        self.assertEqual(handoff_from_row(counted)["sy_pnum"], 5)
        self.assertEqual(classify_tier(counted), "no_known_planets")

        host = dict(_coords("GJ 667 C", 0.31))
        host["exoplanet_count"] = 5
        host["sy_pnum"] = 5
        host["has_known_exoplanets"] = True
        self.assertEqual(handoff_from_row(host)["exoplanet_count"], 5)

    def test_zero_planet_companions_from_affected_list(self):
        masses = {
            "alf Cen A": 1.06,
            "alf Cen B": 0.88,
            "GJ 338 A": 0.69,
            "HIP 55846": 1.0,
            "Gl 617B": 0.455567,
            "Gl 667A": 0.59,
            "HIP 96895": 1.02,
        }
        for host in ZERO_PLANET_HOSTS:
            row = adapt_merged_row(
                {
                    "star_key": "hyg:" + host,
                    "hyg_id": "1",
                    "hip": catalog_id_token(host, "HIP") or "1",
                    "gl": host if host.startswith("Gl") else "",
                    "hostname": host,
                    "proper": host,
                    "ra_deg": 1,
                    "dec_deg": 1,
                    "dist_pc": 2,
                    "dist_ly": 6,
                    "x": 2,
                    "y": 0,
                    "z": 0,
                    "has_known_exoplanets": "false",
                    "exoplanet_count": "0",
                    "st_mass": masses[host],
                },
                {"host:" + host.lower(): {"sy_pnum": "5", "st_mass": str(masses[host])}},
            )
            self.assertEqual(float(row["exoplanet_count"]), 0, host)
            self.assertEqual(str(row["has_known_exoplanets"]).lower(), "false", host)
            self.assertEqual(classify_tier(row), "no_known_planets", host)
            self.assertEqual(handoff_from_row(row)["exoplanet_count"], 0, host)

    def test_55_cnc_counts_and_masses(self):
        primary = adapt_merged_row(
            {
                "star_key": "gaia:704967037090946688",
                "gaia_source_id": "704967037090946688",
                "hyg_id": "43464",
                "hip": "43587",
                "hd": "75732",
                "gl": "Gl 324A",
                "proper": "Copernicus",
                "exo_hostname": "55 Cnc",
                "hostname": "55 Cnc",
                "bf": "55Rho1Cnc",
                "con": "Cnc",
                "ra_deg": 133.14676,
                "dec_deg": 28.329783,
                "dist_pc": 12.58682,
                "dist_ly": 41.05,
                "x": -7.576799,
                "y": 8.083511,
                "z": 5.973023,
                "has_known_exoplanets": "true",
                "exoplanet_count": "5",
                "spect": "G8V",
            },
            {
                "host:55 cnc": {"st_mass": "0.85", "sy_pnum": "7", "sy_snum": "2"},
                "hip:43587": {"st_mass": "0.85", "sy_pnum": "7"},
                "host:55 cnc b": {"st_mass": "0.26", "sy_pnum": "7"},
            },
        )
        companion = adapt_merged_row(
            {
                "star_key": "gaia:704966762213039488",
                "gaia_source_id": "704966762213039488",
                "hyg_id": "118569",
                "gl": "Gl 324B",
                "exo_hostname": "55 Cnc B",
                "hostname": "55 Cnc B",
                "bf": "55Rho1Cnc",
                "con": "Cnc",
                "ra_deg": 133.167832,
                "dec_deg": 28.315252,
                "dist_pc": 12.553978,
                "dist_ly": 40.95,
                "x": -7.561028,
                "y": 8.060741,
                "z": 5.954635,
                "has_known_exoplanets": "true",
                "exoplanet_count": "2",
                "spect": "M4.5 V",
            },
            {
                "host:55 cnc": {"st_mass": "0.85", "sy_pnum": "7", "sy_snum": "2"},
                "hip:43587": {"st_mass": "0.85", "sy_pnum": "7"},
                "host:55 cnc b": {"st_mass": "0.26", "sy_pnum": "7", "sy_snum": "2"},
            },
        )
        self.assertEqual(float(primary["exoplanet_count"]), 5)
        self.assertEqual(float(companion["exoplanet_count"]), 2)
        self.assertEqual(float(primary["sy_pnum"]), 7)
        self.assertEqual(float(companion["sy_pnum"]), 7)
        self.assertAlmostEqual(float(primary["st_mass"]), 0.85)
        self.assertAlmostEqual(float(companion["st_mass"]), 0.26)
        self.assertNotEqual(primary["star_key"], companion["star_key"])
        primary["calculated_x"] = -24.7
        primary["calculated_y"] = 26.4
        primary["calculated_z"] = 19.5
        companion["calculated_x"] = -24.5
        companion["calculated_y"] = 26.1
        companion["calculated_z"] = 19.3
        self.assertEqual(classify_tier(primary), "gate_candidate")
        self.assertEqual(classify_tier(companion), "gate_candidate")
        self.assertTrue(meets_gate_criteria(companion))
        self.assertIsNone(gate_status_for(companion))
        self.assertNotEqual(gate_status_for(companion), "pending_doug")
        a_hand = handoff_from_row(primary)
        b_hand = handoff_from_row(companion)
        self.assertEqual(a_hand["exoplanet_count"], 5)
        self.assertEqual(b_hand["exoplanet_count"], 2)
        self.assertEqual(a_hand["name"], "Rho Cancri")
        self.assertEqual(b_hand["name"], "Rho Cancri B")
        self.assertEqual(a_hand["hostname"], "55 Cnc")
        self.assertEqual(b_hand["hostname"], "55 Cnc B")
        self.assertIsNone(a_hand["gate_status"])
        self.assertIsNone(b_hand["gate_status"])
        self.assertEqual(a_hand["tier"], "gate_candidate")
        self.assertEqual(b_hand["tier"], "gate_candidate")
        for needle in ("55 Cnc", "55 Cnc A", "rho Cnc", "Copernicus", "HD 75732", "HIP 43587", "Gliese 324 A", "Gl 324 A", "GJ 324 A"):
            self.assertIn(needle, a_hand["aliases"])
        for needle in ("55 Cnc B", "rho Cnc B", "Gliese 324 B", "Gl 324 B", "GJ 324 B"):
            self.assertIn(needle, b_hand["aliases"])

    def test_missing_count_on_binary_is_zero_not_sy_pnum(self):
        row = dict(_coords("55 Cnc", 0.85))
        row["sy_pnum"] = 7
        row["sy_snum"] = 2
        row["has_known_exoplanets"] = True
        self.assertEqual(handoff_from_row(row)["exoplanet_count"], 0)
        bee = dict(_coords("55 Cnc B", 0.26))
        bee["sy_pnum"] = 7
        bee["sy_snum"] = 2
        bee["exoplanet_count"] = 2
        bee["has_known_exoplanets"] = True
        self.assertEqual(handoff_from_row(bee)["exoplanet_count"], 2)
        self.assertEqual(classify_tier(bee), "gate_candidate")

    def test_gl_725_keeps_one_each_beside_sy_pnum_two(self):
        a = adapt_merged_row(
            {
                "star_key": "gaia:a",
                "hostname": "Gl 725 A",
                "ra_deg": 1,
                "dec_deg": 1,
                "dist_pc": 3,
                "dist_ly": 10,
                "x": 3,
                "y": 0,
                "z": 0,
                "has_known_exoplanets": "true",
                "exoplanet_count": "1",
            },
            {"host:gl 725 a": {"st_mass": "0.33", "sy_pnum": "2"}},
        )
        b = adapt_merged_row(
            {
                "star_key": "hyg:b",
                "hostname": "Gl 725 B",
                "ra_deg": 1,
                "dec_deg": 1,
                "dist_pc": 3,
                "dist_ly": 10,
                "x": 3,
                "y": 0,
                "z": 0,
                "has_known_exoplanets": "true",
                "exoplanet_count": "1",
            },
            {"host:gl 725 b": {"st_mass": "0.25", "sy_pnum": "2"}},
        )
        self.assertEqual(float(a["exoplanet_count"]), 1)
        self.assertEqual(float(b["exoplanet_count"]), 1)
        self.assertEqual(float(a["sy_pnum"]), 2)
        self.assertEqual(float(b["sy_pnum"]), 2)
        self.assertAlmostEqual(float(a["st_mass"]), 0.33)
        self.assertAlmostEqual(float(b["st_mass"]), 0.25)


class JoinAndMassTests(unittest.TestCase):
    def test_companion_mass_not_copied_onto_primary(self):
        primary = adapt_merged_row(
            {
                "star_key": "gaia:primary",
                "hostname": "55 Cnc",
                "hip": "43587",
                "gl": "Gl 324A",
                "ra_deg": 1,
                "dec_deg": 1,
                "dist_pc": 12,
                "dist_ly": 40,
                "x": 12,
                "y": 0,
                "z": 0,
                "has_known_exoplanets": "true",
                "exoplanet_count": "5",
            },
            {
                "host:55 cnc b": {"st_mass": "0.26", "sy_pnum": "7"},
                "hip:43587": {"st_mass": "0.85", "sy_pnum": "7"},
            },
        )
        self.assertAlmostEqual(float(primary["st_mass"]), 0.85)
        companion = adapt_merged_row(
            {
                "star_key": "gaia:bee",
                "hostname": "55 Cnc B",
                "gl": "Gl 324B",
                "ra_deg": 1,
                "dec_deg": 1,
                "dist_pc": 12,
                "dist_ly": 40,
                "x": 12,
                "y": 0,
                "z": 0,
                "has_known_exoplanets": "true",
                "exoplanet_count": "2",
                "st_mass": "0.26",
            },
            {"hip:43587": {"st_mass": "0.85", "sy_pnum": "7"}},
        )
        self.assertAlmostEqual(float(companion["st_mass"]), 0.26)

    def test_bare_hostname_maps_to_primary_lettered_maps_to_component(self):
        index = {
            "host:hd 41004": {"st_mass": "0.7", "sy_pnum": "2"},
            "host:hd 41004 a": {"st_mass": "0.7", "sy_pnum": "2", "exoplanet_count": "1"},
            "host:hd 41004 b": {"st_mass": "0.4", "sy_pnum": "2"},
            "hip:28393": {"st_mass": "0.7", "sy_pnum": "2"},
            "hip:28393A": {"st_mass": "0.7", "sy_pnum": "2"},
            "hip:28393B": {"st_mass": "0.4", "sy_pnum": "2"},
        }
        a = adapt_merged_row(
            {
                "star_key": "gaia:a41004",
                "hostname": "HD 41004 A",
                "hip": "28393 A",
                "hd": "41004 A",
                "ra_deg": 1,
                "dec_deg": -1,
                "dist_pc": 40,
                "dist_ly": 130,
                "x": 40,
                "y": 0,
                "z": 0,
                "has_known_exoplanets": "true",
                "exoplanet_count": "1",
            },
            index,
        )
        b = adapt_merged_row(
            {
                "star_key": "gaia:b41004",
                "hostname": "HD 41004 B",
                "hip": "28393 B",
                "hd": "41004 B",
                "ra_deg": 1,
                "dec_deg": -1,
                "dist_pc": 40,
                "dist_ly": 130,
                "x": 40,
                "y": 0,
                "z": 0,
                "has_known_exoplanets": "true",
                "exoplanet_count": "1",
            },
            index,
        )
        self.assertEqual(a["hip"], "28393 A")
        self.assertEqual(b["hip"], "28393 B")
        self.assertEqual(float(a["exoplanet_count"]), 1)
        self.assertEqual(float(b["exoplanet_count"]), 1)
        self.assertAlmostEqual(float(a["st_mass"]), 0.7)
        self.assertAlmostEqual(float(b["st_mass"]), 0.4)
        self.assertNotEqual(a["star_key"], b["star_key"])

    def test_per_host_st_mass_column_when_present(self):
        row = adapt_merged_row(
            {
                "star_key": "gaia:bee",
                "hostname": "55 Cnc B",
                "ra_deg": 1,
                "dec_deg": 1,
                "dist_pc": 12,
                "dist_ly": 40,
                "x": 12,
                "y": 0,
                "z": 0,
                "has_known_exoplanets": "true",
                "exoplanet_count": "2",
                "st_mass": "0.26",
            },
            {},
        )
        self.assertAlmostEqual(float(row["st_mass"]), 0.26)


class DisplayNameTests(unittest.TestCase):
    def test_bayer_from_hyg_bf(self):
        self.assertEqual(bayer_from_bf("55Rho1Cnc", "Cnc"), "Rho Cancri")
        row = {"hostname": "55 Cnc", "bf": "55Rho1Cnc", "con": "Cnc", "proper": "Copernicus"}
        self.assertEqual(display_name_for(row), "Rho Cancri")
        bee = {"hostname": "55 Cnc B", "bf": "55Rho1Cnc", "con": "Cnc"}
        self.assertEqual(display_name_for(bee), "Rho Cancri B")
        names = aliases_for({"hostname": "55 Cnc", "proper": "Copernicus", "hd": "75732", "hip": "43587", "gl": "Gl 324A", "bf": "55Rho1Cnc", "con": "Cnc"})
        for needle in ("55 Cnc", "55 Cnc A", "Copernicus", "HD 75732", "HIP 43587", "Gliese 324 A", "Gl 324 A", "GJ 324 A", "Rho Cancri"):
            self.assertIn(needle, names)


class NasaTapTests(unittest.TestCase):
    def test_query_lists_new_columns_and_ingest_skips_missing(self):
        for col in ("sy_snum", "st_mass", "disc_year", "pl_controv_flag"):
            self.assertIn(col, PSCOMPPARS_COLUMNS)
            self.assertIn(col, PSCOMPPARS_TAP_SELECT)
            self.assertIn(col, PSCOMPPARS_TAP_SQL)
            self.assertIn(col, PSCOMPPARS_TAP_URL)
        self.assertEqual(OPTIONAL_PLANET_COLUMNS, ["disc_year", "pl_controv_flag", "sy_snum", "st_mass"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "planets.csv"
            path.write_text("hostname,pl_name,pl_bmasse,pl_rade,pl_eqt\nDemo,Demo b,2,1.2,280\n", encoding="utf-8")
            frame = _read_nasa_csv(path, PLANET_KEEP)
            self.assertEqual(list(frame.columns), [c for c in PLANET_KEEP if c in {"hostname", "pl_name", "pl_bmasse", "pl_rade", "pl_eqt"}])
            wide = Path(tmp) / "wide.csv"
            wide.write_text(
                "hostname,pl_name,pl_bmasse,pl_rade,pl_eqt,disc_year,pl_controv_flag,sy_snum,st_mass\n"
                "Demo,Demo b,2,1.2,280,2025,0,2,0.9\n",
                encoding="utf-8",
            )
            filled = _read_nasa_csv(wide, PLANET_KEEP)
            self.assertIn("disc_year", filled.columns)
            self.assertIn("pl_controv_flag", filled.columns)


class ExampleAndGrepTests(unittest.TestCase):
    def test_handoff_examples(self):
        schema = load_schema()
        plain = json.loads((ROOT / "docs" / "examples" / "55-cnc.handoff.json").read_text(encoding="utf-8"))
        bee = json.loads((ROOT / "docs" / "examples" / "55-cnc-b.handoff.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_handoff(plain, schema), [])
        self.assertEqual(validate_handoff(bee, schema), [])
        self.assertEqual(plain["name"], "Rho Cancri")
        self.assertEqual(plain["hostname"], "55 Cnc")
        self.assertEqual(plain["exoplanet_count"], 5)
        self.assertEqual(plain["sy_pnum"], 7)
        self.assertEqual(plain["tier"], "gate_candidate")
        self.assertIsNone(plain["gate_status"])
        self.assertEqual(bee["name"], "Rho Cancri B")
        self.assertEqual(bee["hostname"], "55 Cnc B")
        self.assertEqual(bee["exoplanet_count"], 2)
        self.assertEqual(bee["sy_pnum"], 7)
        self.assertEqual(bee["tier"], "gate_candidate")
        self.assertIsNone(bee["gate_status"])
        self.assertNotEqual(bee["gate_status"], "pending_doug")

    def test_no_55_cnc_special_case_code(self):
        roots = [
            ROOT / "starroute" / "catalog.py",
            ROOT / "starroute" / "handoff.py",
            ROOT / "starroute" / "mapgen" / "tiers.py",
            ROOT / "starroute" / "mapgen" / "network.py",
            ROOT / "starroute" / "web" / "static" / "js" / "tiers.js",
            ROOT / "starroute" / "web" / "static" / "engine" / "starroute" / "mapgen" / "tiers.py",
        ]
        banned = (
            "_is_55_cnc",
            "CNC_B_NAME",
            "CNC_B_GAIA",
            "CNC_B_STAR_KEY",
            '== "55 Cnc"',
            "== '55 Cnc'",
            '=== "55 Cnc B"',
            '== "55 Cnc B"',
        )
        for path in roots:
            text = path.read_text(encoding="utf-8")
            for token in banned:
                self.assertNotIn(token, text, f"{path.name} still has {token}")

    def test_engine_copies_match(self):
        package = ROOT / "starroute" / "mapgen"
        engine = ROOT / "starroute" / "web" / "static" / "engine" / "starroute" / "mapgen"
        for name in ("tiers.py", "network.py", "ranking.py"):
            self.assertEqual((package / name).read_text(encoding="utf-8"), (engine / name).read_text(encoding="utf-8"), name)

    def test_affected_csv_zero_planet_hosts_have_no_own_rows(self):
        with AFFECTED.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        by_host = {row["host_as_NASA"]: row for row in rows}
        for host in ("GJ 338 A", "HIP 55846", "alf Cen B", "alf Cen A", "HIP 79762", "HIP 84709", "HIP 96895"):
            self.assertEqual(by_host[host]["issue_type"], "jumpgate_would_copy_sy_pnum_onto_nonhost")
            self.assertEqual(by_host[host]["planets_NASA"] or "0", "0")


if __name__ == "__main__":
    unittest.main()
