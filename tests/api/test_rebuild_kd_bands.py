"""v1 rebuild uses config/network.json bands; v2 payload keeps a/b/distance."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from starroute.mapgen.network import _band_limits, edge_band, merged_network_params, network_payload
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
    return TestClient(create_app()), network


def test_shipped_defaults_are_preview_not_pydantic():
    cfg = merged_network_params()
    assert cfg["max_jump_ly"] == 25
    assert cfg["medium_start_pct"] == 40
    assert cfg["long_start_pct"] == 60
    assert cfg["max_linked_nodes"] == 80
    short_end, long_start = _band_limits(25, 40, 60)
    assert short_end == 10.0
    assert long_start == 15.0
    assert edge_band(9.9, short_end, long_start) == "short"
    assert edge_band(10.0, short_end, long_start) == "short"
    assert edge_band(12.0, short_end, long_start) == "medium"
    assert edge_band(15.0, short_end, long_start) == "long"


def test_v2_payload_keeps_keys_and_adds_band(client):
    _http, network_path = client
    import pandas as pd

    payload = network_payload(pd.read_csv(network_path), {"max_jump_ly": 25, "medium_start_pct": 40, "long_start_pct": 60})
    edge = payload["edges"][0]
    assert set(edge) >= {"a", "b", "distance", "band", "flavor"}
    assert edge["a"] == "Sol" or edge["b"] == "Sol"
    assert "hostname" in payload["nodes"][0]
    assert "id" not in payload["nodes"][0]
    dist = edge["distance"]
    assert dist == pytest.approx(31.709212476)
    assert edge["band"] == "long"
    assert edge["flavor"] == "gate"


def test_rebuild_writes_csv_and_json(client):
    http, _network_path = client
    res = http.post("/v1/networks/preview/rebuild", json={"max_jump_ly": 50})
    assert res.status_code == 200
    body = res.json()
    assert body["network_id"] == "preview"
    assert body["params"]["preferred_ly"] == pytest.approx(
        _band_limits(body["params"]["max_jump_ly"], body["params"]["medium_start_pct"], body["params"]["long_start_pct"])[0]
    )
    assert body["network"]["starroute"] == "3.0"
    assert body["network"]["nodes"][0]["id"]
    assert body["network"]["nodes"][0]["hostname"]
    got = http.get("/v1/networks/preview")
    assert got.status_code == 200
    assert got.json()["id"] == "preview"
    ui = http.get("/api/network")
    assert ui.status_code == 200
    edge = ui.json()["edges"][0]
    assert "a" in edge and "b" in edge and "distance" in edge
