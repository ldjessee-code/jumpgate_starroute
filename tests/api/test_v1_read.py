"""v1 read façade: provider, identity, route, problem+json, no calendars."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from starroute.mapgen.network import shortest_path
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


def test_get_provider(client: TestClient):
    res = client.get("/v1/provider")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "ptah"
    assert body["layers"] == ["L0", "L1", "L2", "L11"]
    assert body["api"] == "/v1"


def test_identity_hostname_or_slug(client: TestClient):
    a = client.get("/v1/systems/AU Mic")
    b = client.get("/v1/systems/au-mic")
    assert a.status_code == 200
    assert b.status_code == 200
    assert a.json()["id"] == b.json()["id"] == "au-mic"
    assert a.json()["hostname"] == "AU Mic"
    assert a.json()["star"]["st_spectype"] == "M1 V"


def test_path_hostname_equals_slug(client: TestClient):
    via_name = client.get("/v1/networks/preview/route", params={"start": "Sol", "end": "AU Mic"})
    via_slug = client.get("/v1/networks/preview/route", params={"start": "sol", "end": "au-mic"})
    assert via_name.status_code == 200
    assert via_slug.status_code == 200
    assert via_name.json()["path_ids"] == via_slug.json()["path_ids"] == ["sol", "au-mic"]
    assert via_name.json()["path_hostnames"] == ["Sol", "AU Mic"]
    net = pd.read_csv(FIXTURES / "network_slice.csv")
    assert via_name.json()["path_hostnames"] == shortest_path(net, "Sol", "AU Mic")


def test_problem_json_unknown_host(client: TestClient):
    res = client.get("/v1/systems/not-a-star")
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/problem+json")
    body = res.json()
    assert body["code"] == "not_found"
    assert body["status"] == 404
    assert "detail" in body


def test_no_calendar_routes(client: TestClient):
    spec = client.get("/v1/openapi.json")
    assert spec.status_code == 200
    paths = spec.json().get("paths", {})
    joined = " ".join(paths)
    assert "calendar" not in joined.lower()
    assert "/provider" in paths or any(p.endswith("/provider") for p in paths)


def test_v2_status_not_problem_json(client: TestClient):
    res = client.get("/api/status")
    assert res.status_code == 200
    assert not res.headers.get("content-type", "").startswith("application/problem+json")
    assert "systems_ready" in res.json()
