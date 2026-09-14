"""Tick rounds: one action per faction; enqueue does not apply."""

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
    http.post("/v1/settings", json={"title": "Tick", "id": "tick", "reality": 1})
    return http


def test_enqueue_does_not_change_contention(client: TestClient):
    queued = client.post(
        "/v1/settings/tick/actions",
        json={"action": "raid", "system_id": "sol", "faction_id": "kessari", "enqueue": True},
    )
    assert queued.status_code == 200
    assert queued.json() == {"queued": True, "seq": 1, "pending_actions_len": 1}
    aff = client.get("/v1/settings/tick/affiliations").json()
    assert aff["systems"] == {}


def test_two_factions_fire_in_one_round(client: TestClient):
    client.post(
        "/v1/settings/tick/actions",
        json={"action": "expand_claim", "system_id": "sol", "faction_id": "alpha"},
    )
    client.post(
        "/v1/settings/tick/actions",
        json={"action": "expand_claim", "system_id": "au-mic", "faction_id": "beta"},
    )
    client.post(
        "/v1/settings/tick/actions",
        json={"action": "escalate", "system_id": "sol", "faction_id": "alpha"},
    )
    tick = client.post("/v1/settings/tick/tick", json={"n": 1})
    assert tick.status_code == 200
    body = tick.json()
    assert body["t_gct"] is None
    assert len(body["applied"]) == 2
    factions = {row["faction_id"] for row in body["applied"]}
    assert factions == {"alpha", "beta"}
    assert body["pending_actions_len"] == 1
    aff = client.get("/v1/settings/tick/affiliations").json()
    assert aff["systems"]["sol"]["contention"] == "claim"
    assert aff["systems"]["au-mic"]["contention"] == "claim"


def test_empty_queue_is_noop(client: TestClient):
    res = client.post("/v1/settings/tick/tick", json={})
    assert res.status_code == 200
    assert res.json()["applied"] == []


def test_duplicate_seq_noop(client: TestClient):
    client.post(
        "/v1/settings/tick/actions",
        json={"action": "expand_claim", "system_id": "sol", "faction_id": "alpha"},
    )
    first = client.post("/v1/settings/tick/tick", json={"seq": 7})
    assert first.json()["applied"]
    second = client.post("/v1/settings/tick/tick", json={"seq": 7})
    assert second.json()["duplicate"] is True
    assert second.json()["applied"] == []


def test_enqueue_false_applies_now(client: TestClient):
    res = client.post(
        "/v1/settings/tick/actions",
        json={
            "action": "raid",
            "system_id": "sol",
            "faction_id": "kessari",
            "enqueue": False,
        },
    )
    assert res.status_code == 200
    assert res.json()["queued"] is False
    assert res.json()["contention_from"] == "none"
    assert res.json()["contention_to"] == "skirmish"
    aff = client.get("/v1/settings/tick/affiliations").json()
    assert aff["systems"]["sol"]["contention"] == "skirmish"


def test_chronos_webhook_defaults_n_to_one_round(client: TestClient):
    client.post(
        "/v1/settings/tick/actions",
        json={"action": "expand_claim", "system_id": "sol", "faction_id": "alpha"},
    )
    client.post(
        "/v1/settings/tick/actions",
        json={"action": "escalate", "system_id": "sol", "faction_id": "alpha"},
    )
    hook = client.post(
        "/v1/webhooks/chronos/advance",
        json={"setting_id": "tick", "campaign_id": "demo", "seq": 1},
    )
    assert hook.status_code == 200
    assert hook.json()["t_gct"] is None
    assert len(hook.json()["applied"]) == 1
    assert hook.json()["pending_actions_len"] == 1
