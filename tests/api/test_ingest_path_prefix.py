"""v1 ingest refuses paths outside data/raw and data/uploads."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from starroute.web.app import create_app

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def client(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    uploads = tmp_path / "uploads"
    raw.mkdir()
    uploads.mkdir()
    systems = tmp_path / "systems.csv"
    network = tmp_path / "sol_network.csv"
    jumpgate = tmp_path / "jumpgate"
    jumpgate.mkdir()
    shutil.copy(FIXTURES / "systems_slice.csv", systems)
    shutil.copy(FIXTURES / "network_slice.csv", network)
    monkeypatch.setattr("starroute.paths.DATA_RAW", raw)
    monkeypatch.setattr("starroute.paths.DATA_UPLOADS", uploads)
    monkeypatch.setattr("starroute.paths.SYSTEMS_CSV", systems)
    monkeypatch.setattr("starroute.paths.NETWORK_CSV", network)
    monkeypatch.setattr("starroute.paths.DATA_JUMPGATE", jumpgate)
    monkeypatch.setattr("starroute.web.app.SYSTEMS_CSV", systems)
    monkeypatch.setattr("starroute.web.app.NETWORK_CSV", network)
    return TestClient(create_app()), raw, tmp_path


def test_rejects_path_outside_raw_and_uploads(client):
    http, _raw, tmp_path = client
    evil = tmp_path / "outside.csv"
    evil.write_text("hostname\nSol\n", encoding="utf-8")
    res = http.post(
        "/v1/ingest/nasa",
        json={"planet_path": str(evil), "host_path": str(evil)},
    )
    assert res.status_code == 400
    assert res.json()["code"] == "validation_error"


def test_missing_file_is_404(client):
    http, raw, _tmp = client
    res = http.post(
        "/v1/ingest/nasa",
        json={"planet_path": str(raw / "nope.csv"), "host_path": str(raw / "nope.csv")},
    )
    assert res.status_code == 404
    assert res.json()["code"] == "not_found"
