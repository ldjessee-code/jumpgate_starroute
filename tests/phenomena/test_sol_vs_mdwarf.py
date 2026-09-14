"""Sol is mild; AU Mic is an active M dwarf. No dated Chronos events."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from starroute.ingest.sol import SOL_ROW
from starroute.mapgen.phenomena import classify_star
from starroute.web.app import create_app

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_sol_row_is_mild():
    classes = classify_star(SOL_ROW)
    assert "flare:sol_mild" in classes
    assert "flare:M_active" not in classes
    assert "cme:M_severe" not in classes


def test_au_mic_is_active_m_dwarf():
    row = {
        "st_spectype": "M1 V",
        "st_rotp": 4.86,
        "st_age": 0.019,
        "st_vsin": 9.2,
        "stability_score": 2,
        "sy_snum": 1.0,
        "cb_flag": 0,
    }
    classes = classify_star(row)
    assert "flare:M_active" in classes
    assert "cme:M_severe" in classes
    assert "flare:sol_mild" not in classes


def test_55_cnc_quiet_g_and_binary():
    classes = classify_star(
        {"st_spectype": "G8 V", "st_rotp": 44.0, "st_age": 5.0, "sy_snum": 2.0, "cb_flag": 0}
    )
    assert "flare:G_quiet" in classes
    assert "radiation:binary" in classes
    assert "flare:M_active" not in classes


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


def test_hazards_api_sol_vs_au_mic(client: TestClient):
    sol = client.get("/v1/systems/sol/hazards")
    au = client.get("/v1/systems/au-mic/hazards")
    assert sol.status_code == 200
    assert au.status_code == 200
    assert "flare:sol_mild" in sol.json()["classes"]
    assert "flare:M_active" in au.json()["classes"]
    assert "cme:M_severe" in au.json()["classes"]
    kinds = {t["kind"] for t in au.json()["suggestions"]}
    assert "stellar_flare" in kinds
    templates = client.get("/v1/phenomena/templates")
    assert templates.status_code == 200
    assert any(t["id"] == "tmpl-m-flare" for t in templates.json()["templates"])
