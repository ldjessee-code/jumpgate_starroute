"""Slider 1: one stub per role; NASA bodies byte-stable; bodies[] append-only."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from starroute.ingest.json_catalog import emit_json_catalog
from starroute.store.documents import JsonStore
from starroute.store.etag import canonical_bytes
from starroute.web.app import create_app

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def env(tmp_path, monkeypatch):
    systems = tmp_path / "systems.csv"
    network = tmp_path / "sol_network.csv"
    jumpgate = tmp_path / "jumpgate"
    jumpgate.mkdir()
    shutil.copy(FIXTURES / "systems_slice.csv", systems)
    shutil.copy(FIXTURES / "network_slice.csv", network)
    monkeypatch.setattr("starroute.paths.SYSTEMS_CSV", systems)
    monkeypatch.setattr("starroute.paths.NETWORK_CSV", network)
    monkeypatch.setattr("starroute.paths.DATA_JUMPGATE", jumpgate)
    monkeypatch.setattr("starroute.web.app.SYSTEMS_CSV", systems)
    monkeypatch.setattr("starroute.web.app.NETWORK_CSV", network)
    store = JsonStore(jumpgate)
    emit_json_catalog(
        systems,
        pd.read_csv(FIXTURES / "planets_keep_sample.csv"),
        store=store,
    )
    http = TestClient(create_app())
    http.post("/v1/settings", json={"title": "Gaps", "id": "gaps", "reality": 1})
    return http, store


def test_one_stub_null_physics_nasa_unchanged(env):
    http, store = env
    before = json.loads(json.dumps(store.get("bodies", "au-mic.b")))
    before_bytes = canonical_bytes(
        {k: before[k] for k in ("pl_bmasse", "pl_rade", "pl_eqt", "pl_orbsmax", "source", "pl_name")}
    )
    res = http.post(
        "/v1/systems/AU Mic/premise",
        params={"setting_id": "gaps"},
        json={
            "seed": "ws-au-mic-0001",
            "need": [{"role": "warehouse_moon", "g_earth_max": 0.25}],
        },
    )
    assert res.status_code == 200
    created = res.json()["created"]
    assert created == ["au-mic.gen-warehouse-moon-1"]
    stub = http.get("/v1/bodies/au-mic.gen-warehouse-moon-1").json()
    assert stub["source"]["kind"] == "generated"
    assert stub["role"] == "warehouse_moon"
    assert stub["pl_bmasse"] is None
    assert stub["pl_rade"] is None
    assert stub["pl_eqt"] is None
    assert stub["pl_orbsmax"] is None
    assert stub["g_earth_max"] == 0.25
    after = store.get("bodies", "au-mic.b")
    after_bytes = canonical_bytes(
        {k: after[k] for k in ("pl_bmasse", "pl_rade", "pl_eqt", "pl_orbsmax", "source", "pl_name")}
    )
    assert after_bytes == before_bytes
    assert after["pl_bmasse"] == 8.99
    sysdoc = http.get("/v1/systems/au-mic", params={"setting_id": "gaps"}).json()
    assert "au-mic.b" in sysdoc["bodies"]
    assert "au-mic.gen-warehouse-moon-1" in sysdoc["bodies"]
    assert sysdoc["bodies"].index("au-mic.b") < sysdoc["bodies"].index("au-mic.gen-warehouse-moon-1")


def test_second_gapfill_does_not_duplicate_role(env):
    http, _store = env
    first = http.post(
        "/v1/systems/au-mic/generate-l2",
        params={"setting_id": "gaps"},
        json={"need": [{"role": "warehouse_moon"}]},
    )
    second = http.post(
        "/v1/systems/au-mic/generate-l2",
        params={"setting_id": "gaps"},
        json={"need": [{"role": "warehouse_moon"}]},
    )
    assert first.json()["created"] == ["au-mic.gen-warehouse-moon-1"]
    assert second.json()["created"] == []
    assert second.json()["bodies"].count("au-mic.gen-warehouse-moon-1") == 1
