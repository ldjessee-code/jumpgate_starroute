"""Affiliation influence must sum to 1 unless renormalize is set."""

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
    http.post("/v1/settings", json={"title": "Pol", "id": "pol", "reality": 1})
    return http


def test_influence_sum_rejected_then_renormalized(client: TestClient):
    bad = client.put(
        "/v1/settings/pol/affiliations",
        json={
            "systems": {
                "sol": {
                    "controlling": "turquenish-empire",
                    "contention": "competitive_trade",
                    "present": [
                        {"faction_id": "turquenish-empire", "role": "controlling", "influence": 0.7},
                        {"faction_id": "mardat-coalition", "role": "present", "influence": 0.7},
                    ],
                }
            }
        },
    )
    assert bad.status_code == 409
    assert bad.json()["code"] == "influence_sum"
    ok = client.put(
        "/v1/settings/pol/affiliations",
        json={
            "renormalize": True,
            "systems": {
                "sol": {
                    "controlling": "turquenish-empire",
                    "contention": "competitive_trade",
                    "present": [
                        {"faction_id": "turquenish-empire", "role": "controlling", "influence": 0.7},
                        {"faction_id": "mardat-coalition", "role": "present", "influence": 0.7},
                    ],
                }
            },
        },
    )
    assert ok.status_code == 200
    present = ok.json()["systems"]["sol"]["present"]
    assert pytest.approx(sum(p["influence"] for p in present), abs=1e-6) == 1.0


def test_legal_schedule_and_trade(client: TestClient):
    legal = client.put(
        "/v1/factions/turquenish-empire/legal",
        json={
            "government": "empire",
            "conflict_family": "autocratic",
            "schedule": [
                {"good": "slaves", "action": "trade", "status": "banned"},
                {"good": "h2", "action": "scoop", "status": "taxed", "tariff": 0.05},
            ],
        },
    )
    assert legal.status_code == 200
    assert legal.json()["tariff_paid_by"] == "importer"
    trade = client.put(
        "/v1/networks/preview/trade",
        json={"practices": [{"a": "sol", "b": "au-mic", "practice": "competitive_trade"}]},
    )
    assert trade.status_code == 200
    assert client.get("/v1/networks/preview/trade").json()["practices"][0]["practice"] == "competitive_trade"
