"""Slider 0: no generated bodies."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from starroute.ingest.json_catalog import emit_json_catalog
from starroute.store.documents import JsonStore
from starroute.web.app import create_app

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def client(tmp_path, monkeypatch):
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
    emit_json_catalog(
        systems,
        pd.read_csv(FIXTURES / "planets_keep_sample.csv"),
        store=JsonStore(jumpgate),
    )
    http = TestClient(create_app())
    http.post("/v1/settings", json={"title": "Locked", "id": "locked", "reality": 0})
    return http


def test_stop0_rejects_gapfill(client: TestClient):
    res = client.post(
        "/v1/systems/au-mic/premise",
        params={"setting_id": "locked"},
        json={"need": [{"role": "warehouse_moon", "g_earth_max": 0.25}]},
    )
    assert res.status_code == 409
    assert res.json()["code"] == "reality_forbidden"
    nasa = client.get("/v1/bodies/au-mic.b")
    assert nasa.status_code == 200
    assert nasa.json()["source"]["kind"] == "nasa"
    assert nasa.json()["pl_bmasse"] == 8.99
