"""Reality slider: strong If-Match CAS, not last-write-wins."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
    return TestClient(create_app()), jumpgate


def test_create_and_cas_raise_slider(client):
    http, _root = client
    created = http.post("/v1/settings", json={"title": "Iron Ash", "reality": 1})
    assert created.status_code == 200
    sid = created.json()["id"]
    assert sid == "iron-ash"
    etag = created.json()["etag"]
    assert etag.startswith('"sha256-')

    missing = http.put(f"/v1/settings/{sid}/reality", json={"reality": 2, "updated_by": "worldstack"})
    assert missing.status_code == 412
    assert missing.json()["code"] == "precondition_required"

    weak = http.put(
        f"/v1/settings/{sid}/reality",
        json={"reality": 2, "updated_by": "worldstack"},
        headers={"If-Match": f'W/{etag}'},
    )
    assert weak.status_code == 412
    assert weak.json()["code"] == "weak_etag"

    wrong = http.put(
        f"/v1/settings/{sid}/reality",
        json={"reality": 2, "updated_by": "worldstack"},
        headers={"If-Match": '"sha256-ffffffffffff"'},
    )
    assert wrong.status_code == 409
    assert wrong.json()["code"] == "etag_mismatch"
    assert "current" in wrong.json()

    ok = http.put(
        f"/v1/settings/{sid}/reality",
        json={"reality": 2, "updated_by": "worldstack"},
        headers={"If-Match": etag},
    )
    assert ok.status_code == 200
    assert ok.json()["reality"] == 2
    assert ok.json()["updated_by"] == "worldstack"
    assert ok.json()["etag"] != etag


def test_chronos_cannot_write_slider(client):
    http, _root = client
    created = http.post("/v1/settings", json={"title": "No Chronos", "id": "no-chronos"})
    etag = created.json()["etag"]
    res = http.put(
        "/v1/settings/no-chronos/reality",
        json={"reality": 1, "updated_by": "chronos"},
        headers={"If-Match": etag},
    )
    assert res.status_code == 403
    assert res.json()["code"] == "forbidden_actor"


def test_same_slider_body_same_etag(client):
    http, _root = client
    created = http.post("/v1/settings", json={"title": "Stable", "id": "stable", "reality": 1})
    first = created.json()["etag"]
    again = http.put(
        "/v1/settings/stable/reality",
        json={"reality": 1, "updated_by": "jumpgate"},
        headers={"If-Match": first},
    )
    assert again.status_code == 200
    assert again.json()["etag"] == first


def test_lower_slider_conflict_without_discard(client):
    http, root = client
    created = http.post("/v1/settings", json={"title": "Down", "id": "down", "reality": 2})
    etag = created.json()["etag"]
    store = JsonStore(root)
    store.put(
        "bodies",
        "gj-667-c.gen-moon-1",
        {"id": "gj-667-c.gen-moon-1", "source": {"kind": "generated"}, "role": "warehouse_moon"},
    )
    blocked = http.put(
        "/v1/settings/down/reality",
        json={"reality": 0, "updated_by": "jumpgate"},
        headers={"If-Match": etag},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "reality_conflict"
    allowed = http.put(
        "/v1/settings/down/reality",
        json={"reality": 0, "updated_by": "jumpgate", "discard_illegal": True},
        headers={"If-Match": etag},
    )
    assert allowed.status_code == 200
    assert allowed.json()["reality"] == 0
