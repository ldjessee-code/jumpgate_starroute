"""Slider 4: generated hosts and xyz moves."""

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
    http.post("/v1/settings", json={"title": "Proc", "id": "proc", "reality": 4})
    return http


def test_create_generated_host_and_move(client: TestClient):
    created = client.post(
        "/v1/systems",
        params={"setting_id": "proc"},
        json={"hostname": "Ghost Star", "xyz_ly": [1.0, 2.0, 3.0], "seed": "s-1"},
    )
    assert created.status_code == 200
    assert created.json()["id"] == "ghost-star"
    assert created.json()["source"]["kind"] == "generated"
    got = client.get("/v1/systems/ghost-star", params={"setting_id": "proc"})
    assert got.status_code == 200
    assert got.json()["coords"]["xyz_ly"] == [1.0, 2.0, 3.0]
    moved = client.put(
        "/v1/systems/ghost-star/xyz",
        params={"setting_id": "proc"},
        json={"xyz_ly": [4.0, 5.0, 6.0]},
    )
    assert moved.status_code == 200
    assert moved.json()["coords"]["xyz_ly"] == [4.0, 5.0, 6.0]
