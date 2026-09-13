"""K17: setting_id required when more than one setting exists."""

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
    return TestClient(create_app())


def test_list_systems_requires_setting_id_when_two_exist(client: TestClient):
    assert client.post("/v1/settings", json={"title": "Alpha", "id": "alpha"}).status_code == 200
    assert client.post("/v1/settings", json={"title": "Beta", "id": "beta"}).status_code == 200
    missing = client.get("/v1/systems")
    assert missing.status_code == 400
    assert missing.json()["code"] == "missing_setting_id"
    ok = client.get("/v1/systems", params={"setting_id": "alpha"})
    assert ok.status_code == 200
    assert ok.json()["setting_id"] == "alpha"
