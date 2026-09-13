"""Slider 2: overrides; extra edges and new hosts still forbidden."""

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
    http.post("/v1/settings", json={"title": "Soft", "id": "soft", "reality": 2})
    return http


def test_override_effective_vs_catalog(client: TestClient):
    res = client.put(
        "/v1/systems/au-mic/overrides",
        params={"setting_id": "soft"},
        json={"path": "star.st_teff", "to": 9999, "reason": "story"},
    )
    assert res.status_code == 200
    effective = client.get("/v1/systems/au-mic", params={"setting_id": "soft"})
    catalog = client.get("/v1/systems/au-mic", params={"setting_id": "soft", "view": "catalog"})
    assert effective.json()["star"]["st_teff"] == 9999
    assert catalog.json()["star"]["st_teff"] == pytest.approx(3540.0)
    assert catalog.json()["overrides"]


def test_stop2_forbids_extra_edge_and_new_host(client: TestClient):
    edge = client.put(
        "/v1/networks/preview/edges/sol/au-mic",
        params={"setting_id": "soft"},
        json={"distance_ly": 31.7},
    )
    assert edge.status_code == 409
    assert edge.json()["code"] == "reality_forbidden"
    host = client.post(
        "/v1/systems",
        params={"setting_id": "soft"},
        json={"hostname": "Ghost Star", "xyz_ly": [1, 2, 3]},
    )
    assert host.status_code == 409
