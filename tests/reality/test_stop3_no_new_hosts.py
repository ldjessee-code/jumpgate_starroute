"""Slider 3: extra edges among catalog hosts; no generated hosts or xyz."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
    http = TestClient(create_app())
    http.post("/v1/settings", json={"title": "Scale", "id": "scale", "reality": 3})
    http.post("/v1/networks/preview/rebuild", json={"setting_id": "scale", "max_jump_ly": 50})
    return http


def test_extra_edge_among_catalog_hosts(client: TestClient):
    res = client.put(
        "/v1/networks/preview/edges/sol/55-cnc",
        params={"setting_id": "scale"},
        json={"distance_ly": 41.0, "flavor": "gate"},
    )
    assert res.status_code == 200
    edge = client.get(
        "/v1/networks/preview/edges/sol/55-cnc",
        params={"setting_id": "scale"},
    )
    assert edge.status_code == 200
    assert edge.json()["source"]["kind"] == "setting_edge"
    assert edge.json()["a_hostname"] == "Sol"
    rebuilt = client.post("/v1/networks/preview/rebuild", json={"setting_id": "scale", "max_jump_ly": 50})
    extras = rebuilt.json()["network"].get("extra_edges") or []
    assert any(e.get("source", {}).get("kind") == "setting_edge" for e in extras)


def test_stop3_forbids_generated_host_and_xyz(client: TestClient):
    host = client.post(
        "/v1/systems",
        params={"setting_id": "scale"},
        json={"hostname": "Ghost Star", "xyz_ly": [1, 2, 3]},
    )
    assert host.status_code == 409
    xyz = client.put(
        "/v1/systems/sol/xyz",
        params={"setting_id": "scale"},
        json={"xyz_ly": [9, 9, 9]},
    )
    assert xyz.status_code == 409
