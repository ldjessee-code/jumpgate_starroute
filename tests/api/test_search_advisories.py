"""Search prefixes and derived travel advisories."""

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
    http.post("/v1/settings", json={"title": "Search", "id": "search", "reality": 1})
    http.put(
        "/v1/settings/search/affiliations",
        json={
            "systems": {
                "sol": {
                    "controlling": "turquenish-empire",
                    "contention": "none",
                    "present": [{"faction_id": "turquenish-empire", "role": "controlling", "influence": 1.0}],
                },
                "au-mic": {
                    "controlling": "kessari",
                    "contention": "war",
                    "present": [{"faction_id": "kessari", "role": "controlling", "influence": 1.0}],
                },
            }
        },
    )
    return http


def test_bare_name_and_stellar(client: TestClient):
    res = client.get("/v1/search", params={"setting_id": "search", "q": "AU stellar:M*"})
    assert res.status_code == 200
    ids = {h["id"] for h in res.json()["hits"]}
    assert "au-mic" in ids
    assert "sol" not in ids


def test_alleg_and_zone_denied(client: TestClient):
    alleg = client.get("/v1/search", params={"setting_id": "search", "q": "alleg:kessari"})
    assert {h["id"] for h in alleg.json()["hits"]} == {"au-mic"}
    zone = client.get("/v1/search", params={"setting_id": "search", "q": "zone:denied"})
    assert {h["id"] for h in zone.json()["hits"]} == {"au-mic"}
    binary = client.get("/v1/search", params={"setting_id": "search", "q": "binary:"})
    assert "55-cnc" in {h["id"] for h in binary.json()["hits"]}


def test_advisory_endpoint(client: TestClient):
    sol = client.get("/v1/systems/sol/advisory", params={"setting_id": "search"})
    au = client.get("/v1/systems/au-mic/advisory", params={"setting_id": "search"})
    assert sol.json()["advisory"] == "clear"
    assert au.json()["advisory"] == "denied"
    assert au.json()["contention"] == "war"


def test_avoid_denied_returns_unconstrained(client: TestClient):
    res = client.get(
        "/v1/networks/preview/route",
        params={"start": "sol", "end": "au-mic", "setting_id": "search", "avoid": "denied"},
    )
    assert res.status_code == 409
    assert res.json()["code"] == "no_safe_route"
    unconstrained = res.json()["unconstrained"]
    assert unconstrained["path_hostnames"] == ["Sol", "AU Mic"]
