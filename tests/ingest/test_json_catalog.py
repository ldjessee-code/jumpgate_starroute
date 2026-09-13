"""JSON emit preserves NASA numbers and nulls; only catalog hosts get bodies."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from starroute.ingest.json_catalog import emit_json_catalog
from starroute.ingest.pipeline import PLANET_KEEP
from starroute.store.documents import JsonStore

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_emit_au_mic_bodies_and_sol_empty(tmp_path):
    store = JsonStore(tmp_path)
    planets = pd.read_csv(FIXTURES / "planets_keep_sample.csv")
    result = emit_json_catalog(
        FIXTURES / "systems_slice.csv",
        planets,
        setting_id="fixture",
        planet_snapshot="PSCompPars_fixture",
        host_snapshot="STELLARHOSTS_fixture",
        store=store,
    )
    assert result["systems_json"] == 4
    au_b = store.get("bodies", "au-mic.b")
    assert au_b["pl_bmasse"] == 8.99
    assert au_b["pl_rade"] == 4.79
    au_d = store.get("bodies", "au-mic.d")
    assert au_d["pl_eqt"] is None
    assert au_d["pl_orbsmax"] is None
    sol = store.get("systems", "sol")
    assert sol["hostname"] == "Sol"
    assert sol["bodies"] == []
    assert store.get("bodies", "sol.b") is None
    au = store.get("systems", "au-mic")
    assert au["bodies"] == ["au-mic.b", "au-mic.c", "au-mic.d", "au-mic.e"]
    assert au["setting_id"] == "fixture"
    assert set(PLANET_KEEP) >= {"hostname", "pl_name", "pl_letter", "pl_bmasse", "pl_rade", "pl_eqt", "pl_orbsmax"}
