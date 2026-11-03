"""Configurable gate criteria. Defaults stay off so older maps stay the same."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.run_suite import _write_payload  # noqa: E402
from starroute.mapgen.network import _valid_row, generate_network  # noqa: E402
from starroute.mapgen.tiers import (  # noqa: E402
    apply_system_blocks,
    classify_frame,
    criteria_from_params,
    host_mask,
    is_exoplanet_host,
    is_flare_star,
    is_pulsar_or_neutron,
    is_unstable_multiple,
    is_variable_star,
    meets_gate_criteria,
)


def _star(name: str, x: float, mass: float, planets: bool, **extra) -> dict:
    spect = extra.pop("spect", "G2V")
    row = {
        "hostname": name,
        "proper": extra.pop("proper", name),
        "gl": extra.pop("gl", ""),
        "calculated_x": float(x),
        "calculated_y": 0.0,
        "calculated_z": 0.0,
        "st_mass": mass,
        "has_known_exoplanets": "true" if planets else "false",
        "exoplanet_count": 1 if planets else 0,
        "spect": spect,
        "st_spectype": spect,
        "sy_snum": extra.pop("sy_snum", 1),
        "stability_score": extra.pop("stability_score", 0),
        "distance_from_sol_ly": abs(float(x)),
        "distance_from_origin_ly": abs(float(x)),
    }
    row.update(extra)
    return row


class HostMaskTests(unittest.TestCase):
    def test_mask_matches_row_rule(self):
        frame = pd.DataFrame(
            {
                "has_known_exoplanets": ["true", "false", "1.0", "yes", "", 1, 0, True, False, "TRUE", "  true "],
                "exoplanet_count": [0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0],
                "sy_pnum": [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
            }
        )
        mask = host_mask(frame)
        for index, row in frame.iterrows():
            self.assertEqual(bool(mask.iloc[index]), is_exoplanet_host(row.to_dict()), index)

    def test_bool_and_numeric_columns(self):
        flags = pd.DataFrame({"has_known_exoplanets": pd.Series([True, False], dtype=bool)})
        self.assertEqual(host_mask(flags).tolist(), [True, False])
        numbers = pd.DataFrame({"has_known_exoplanets": pd.Series([1.0, 0.0])})
        self.assertEqual(bool(host_mask(numbers).iloc[0]), is_exoplanet_host({"has_known_exoplanets": 1.0}))
        self.assertEqual(bool(host_mask(numbers).iloc[1]), is_exoplanet_host({"has_known_exoplanets": 0.0}))

    def test_sy_pnum_alone_is_not_a_host(self):
        frame = pd.DataFrame({"sy_pnum": [5], "has_known_exoplanets": ["false"], "exoplanet_count": [0]})
        self.assertFalse(bool(host_mask(frame).iloc[0]))
        self.assertFalse(is_exoplanet_host(frame.iloc[0].to_dict()))


class CriterionTests(unittest.TestCase):
    def test_spectral_notes(self):
        self.assertFalse(is_variable_star({"spect": "G2V"}))
        self.assertTrue(is_variable_star({"spect": "M5V var"}))
        self.assertTrue(is_variable_star({"variable": "yes", "spect": "G2V"}))
        self.assertFalse(is_flare_star({"spect": "M5V"}))
        self.assertTrue(is_flare_star({"spect": "dMe"}))
        self.assertTrue(is_flare_star({"spect": "dM3e"}))
        self.assertTrue(is_flare_star({"spect": "UV Ceti"}))
        self.assertFalse(is_pulsar_or_neutron({"spect": "N"}))
        self.assertFalse(is_pulsar_or_neutron({"spect": "WN5"}))
        self.assertFalse(is_pulsar_or_neutron({"spect": "C6 N"}))
        self.assertTrue(is_pulsar_or_neutron({"spect": "NS"}))
        self.assertTrue(is_pulsar_or_neutron({"spect": "pulsar"}))
        self.assertTrue(is_unstable_multiple({"spect": "WN5 (SB1)", "sy_snum": 1}))
        wide = {"spect": "G8V", "sy_snum": 2, "stability_score": 0}
        self.assertFalse(is_unstable_multiple(wide, "standard"))
        self.assertTrue(is_unstable_multiple(wide, "strict"))

    def test_defaults_leave_variable_host_as_a_gate(self):
        row = _star("Var", 5, 0.8, True, spect="M5V var")
        self.assertTrue(meets_gate_criteria(row))
        self.assertTrue(_valid_row(pd.Series(row), 0.25, "Sol", None, None))
        frame = classify_frame(pd.DataFrame([row]))
        self.assertNotIn("_system_block", frame.columns)
        self.assertEqual(frame.iloc[0]["tier"], "gate_candidate")
        self.assertIsNone(criteria_from_params({}))
        self.assertIsNone(criteria_from_params({"exclude_variable": False}))

    def test_row_rule_matches_with_criteria(self):
        criteria = criteria_from_params({"exclude_variable": True})
        row = _star("Var", 5, 0.8, True, spect="M5V var")
        self.assertFalse(meets_gate_criteria(row, 0.25, None, "Sol", criteria))
        self.assertFalse(_valid_row(pd.Series(row), 0.25, "Sol", None, criteria))
        self.assertEqual(classify_frame(pd.DataFrame([row]), criteria=criteria).iloc[0]["tier"], "exo_no_gate")

    def test_sol_stays_a_gate_when_criteria_are_on(self):
        criteria = criteria_from_params(
            {
                "exclude_variable": True,
                "exclude_flare": True,
                "exclude_pulsar_neutron": True,
                "exclude_unstable_multiple": True,
                "unstable_rule": "strict",
            }
        )
        sol = _star("Sol", 0, 1.0, True, spect="M5V var")
        self.assertTrue(meets_gate_criteria(sol, 0.25, None, "Sol", criteria))

    def test_mass_floor_still_defaults_to_0_25(self):
        self.assertTrue(meets_gate_criteria(_star("Ok", 5, 0.25, True)))
        self.assertFalse(meets_gate_criteria(_star("Low", 5, 0.2, True)))
        self.assertTrue(meets_gate_criteria(_star("Unknown", 5, "", True)))
        self.assertFalse(meets_gate_criteria(_star("Dark", 5, "", False)))

    def test_companion_and_stability_groups(self):
        rows = [
            _star("55 Cnc", 12, 0.9, True, gl="Gl 324", spect="G8V", sy_snum=2, stability_score=0),
            _star("55 Cnc B", 12.1, 0.3, False, gl="Gl 324 B", spect="M4V", sy_snum=2, stability_score=0),
            _star("Lone", 8, 1.0, True, gl="Gl 999", spect="G2V", sy_snum=1),
            _star("NS Host", 9, 1.0, True, gl="Gl 10", spect="G2V"),
            _star("NS Host B", 9.1, 1.4, False, gl="Gl 10B", spect="NS"),
            _star("Other", 6, 1.0, True, gl="Gl 20", spect="G2V"),
            _star("SB Host", 11, 1.1, True, spect="G2V (SB1)", sy_snum=2),
            _star("Wide", 4, 0.9, True, spect="G8V", sy_snum=2, stability_score=0),
        ]
        standard = criteria_from_params(
            {
                "exclude_pulsar_neutron": True,
                "exclude_unstable_multiple": True,
                "unstable_rule": "standard",
            }
        )
        strict = criteria_from_params(
            {
                "exclude_pulsar_neutron": True,
                "exclude_unstable_multiple": True,
                "unstable_rule": "strict",
            }
        )
        standard_frame = classify_frame(pd.DataFrame(rows), criteria=standard)
        standard_tiers = dict(zip(standard_frame["hostname"], standard_frame["tier"]))
        strict_frame = classify_frame(pd.DataFrame(rows), criteria=strict)
        strict_tiers = dict(zip(strict_frame["hostname"], strict_frame["tier"]))
        self.assertEqual(standard_tiers["55 Cnc"], "gate_candidate")
        self.assertEqual(strict_tiers["55 Cnc"], "exo_no_gate")
        self.assertEqual(standard_tiers["Lone"], "gate_candidate")
        self.assertEqual(strict_tiers["Lone"], "gate_candidate")
        self.assertEqual(standard_tiers["NS Host"], "exo_no_gate")
        self.assertEqual(standard_tiers["Other"], "gate_candidate")
        self.assertEqual(standard_tiers["SB Host"], "exo_no_gate")
        self.assertEqual(standard_tiers["Wide"], "gate_candidate")
        self.assertEqual(strict_tiers["Wide"], "exo_no_gate")
        blocked = apply_system_blocks(pd.DataFrame(rows), standard)
        ns_block = blocked.loc[blocked["hostname"] == "NS Host", "_system_block"].iloc[0]
        lone_block = blocked.loc[blocked["hostname"] == "Lone", "_system_block"].iloc[0]
        self.assertIn("psr", str(ns_block))
        self.assertNotIn("psr", str(lone_block))
        untouched = apply_system_blocks(pd.DataFrame(rows), None)
        self.assertNotIn("_system_block", untouched.columns)


class NetworkCriterionTests(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        rows = [
            _star("Sol", 0, 1.0, True),
            _star("GateA", 4, 1.0, True),
            _star("GateB", 8, 1.0, True),
            _star("GateC", 12, 1.0, True),
            _star("Low", 3, 0.1, True),
            _star("Background", 6, 1.0, False),
            _star("Far", 400, 1.0, True),
            _star("Variable", 16, 1.0, True, spect="M5V var"),
            _star("NS Host", 20, 1.0, True, gl="Gl 10"),
            _star("NS Host B", 20.2, 1.4, False, gl="Gl 10B", spect="NS"),
            _star("SB Host", 24, 1.1, True, spect="G2V (SB1)", sy_snum=2),
            _star("Wide", 28, 0.9, True, spect="G8V", sy_snum=2, stability_score=0),
        ]
        return pd.DataFrame(rows)

    def _params(self, **extra) -> dict:
        params = {
            "max_jump_ly": 12,
            "max_neighbors": 2,
            "max_distance_ly": 30,
            "min_stellar_mass": 0.25,
            "max_linked_nodes": 100,
            "root_hostname": "Sol",
        }
        params.update(extra)
        return params

    def _run(self, params: dict) -> pd.DataFrame:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "network.csv"
            generate_network(systems_df=self._frame(), output_path=str(out), params=params)
            frame = pd.read_csv(out)
            payload_path = Path(tmp) / "map.json"
            _write_payload(out, payload_path)
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            self.assertTrue(any(node["hostname"] == "Sol" for node in payload["nodes"]))
            self.assertNotIn("Far", {node["hostname"] for node in payload["nodes"]})
            return frame

    def _tiers(self, frame: pd.DataFrame) -> dict[str, str]:
        return dict(zip(frame["hostname"], frame["tier"]))

    def _degree(self, frame: pd.DataFrame) -> int:
        cols = [column for column in frame.columns if column.startswith("neighbor_") and column.endswith("_hostname")]
        highest = 0
        for _, row in frame.iterrows():
            count = 0
            for column in cols:
                value = row.get(column)
                if pd.notna(value) and str(value).strip().lower() not in {"", "nan", "none"}:
                    count += 1
            highest = max(highest, count)
        return highest

    def test_distance_degree_and_optional_rules(self):
        plain = self._run(self._params())
        self.assertNotIn("Far", set(plain["hostname"]))
        self.assertEqual(len(plain), len(self._frame()) - 1)
        self.assertLessEqual(self._degree(plain), 2)
        tiers = self._tiers(plain)
        self.assertEqual(tiers["Variable"], "gate_candidate")
        self.assertEqual(tiers["NS Host"], "gate_candidate")
        self.assertEqual(tiers["SB Host"], "gate_candidate")
        self.assertEqual(tiers["Wide"], "gate_candidate")
        self.assertEqual(tiers["Sol"], "gate_candidate")
        self.assertEqual(tiers["Background"], "no_known_planets")
        self.assertEqual(tiers["Low"], "exo_no_gate")
        self.assertGreater(plain["gate_distance"].notna().sum(), 1)

        standard = self._run(
            self._params(
                exclude_variable=True,
                exclude_flare=True,
                exclude_pulsar_neutron=True,
                exclude_unstable_multiple=True,
                unstable_rule="standard",
            )
        )
        tiers = self._tiers(standard)
        self.assertEqual(tiers["Sol"], "gate_candidate")
        self.assertNotEqual(tiers["Variable"], "gate_candidate")
        self.assertNotEqual(tiers["NS Host"], "gate_candidate")
        self.assertNotEqual(tiers["SB Host"], "gate_candidate")
        self.assertEqual(tiers["Wide"], "gate_candidate")
        self.assertIn("Background", set(standard["hostname"]))
        self.assertLessEqual(self._degree(standard), 2)

        strict = self._run(
            self._params(
                exclude_variable=True,
                exclude_flare=True,
                exclude_pulsar_neutron=True,
                exclude_unstable_multiple=True,
                unstable_rule="strict",
            )
        )
        self.assertNotEqual(self._tiers(strict)["Wide"], "gate_candidate")
        self.assertEqual(self._tiers(strict)["Sol"], "gate_candidate")


if __name__ == "__main__":
    unittest.main()
