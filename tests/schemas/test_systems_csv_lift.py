"""Golden lift of systems.csv rows into jumpgate.system.v1 / body.v1."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from starroute.ids import body_id, host_id
from starroute.schemas.lift import lift_bodies_from_planets, lift_systems_csv

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_host_id_slugs():
    assert host_id("AU Mic") == "au-mic"
    assert host_id("55 Cnc B") == "55-cnc-b"
    assert host_id("Sol") == "sol"
    assert body_id("AU Mic", "b") == "au-mic.b"


def test_lift_four_hosts():
    systems = lift_systems_csv(FIXTURES / "systems_slice.csv", setting_id="fixture")
    by_id = {s.id: s for s in systems}
    assert set(by_id) == {"sol", "au-mic", "55-cnc", "55-cnc-b"}

    sol = by_id["sol"]
    assert sol.hostname == "Sol"
    assert sol.source.kind == "hand"
    assert sol.source.manual_entry is True
    assert sol.star.st_spectype == "G2 V"
    assert sol.star.st_mass == 1.0
    assert sol.coords.xyz_ly == [0.0, 0.0, 0.0]

    au = by_id["au-mic"]
    assert au.hostname == "AU Mic"
    assert au.source.kind == "nasa"
    assert au.star.st_spectype == "M1 V"
    assert au.star.st_mass == pytest.approx(0.635)
    assert au.star.st_rotp == pytest.approx(4.86)
    assert au.star.st_age == pytest.approx(0.019)
    assert au.flags.stability_score == 2

    cnc = by_id["55-cnc"]
    cnc_b = by_id["55-cnc-b"]
    assert cnc.hostname == "55 Cnc"
    assert cnc_b.hostname == "55 Cnc B"
    assert cnc.id != cnc_b.id


def test_lift_au_mic_bodies_use_snapshot_numbers():
    bodies = lift_bodies_from_planets(
        FIXTURES / "planets_keep_sample.csv",
        snapshot="PSCompPars_2026.08.08_21.51.22",
    )
    by_id = {b.id: b for b in bodies}
    b = by_id["au-mic.b"]
    assert b.pl_name == "AU Mic b"
    assert b.host_id == "au-mic"
    assert b.pl_bmasse == pytest.approx(8.99)
    assert b.pl_rade == pytest.approx(4.79)
    assert b.pl_eqt == pytest.approx(554.8)
    assert b.pl_orbsmax == pytest.approx(0.07)
    assert b.source.kind == "nasa"
    d = by_id["au-mic.d"]
    assert d.pl_eqt is None
    assert d.pl_orbsmax is None
    assert "sol." not in by_id
    assert not any(x.host_id == "55-cnc-b" for x in bodies)


def test_id_collision_raises(tmp_path: Path):
    csv = tmp_path / "clash.csv"
    csv.write_text("hostname\nAU Mic\nau mic\n", encoding="utf-8")
    with pytest.raises(ValueError, match="id_collision"):
        lift_systems_csv(csv)


def test_attach_body_ids_to_system_envelope():
    by_host: dict[str, list[str]] = {}
    planets = pd.read_csv(FIXTURES / "planets_keep_sample.csv")
    for hostname, group in planets.groupby("hostname"):
        by_host[str(hostname)] = [
            body_id(str(hostname), str(letter)) for letter in group["pl_letter"]
        ]
    systems = lift_systems_csv(
        FIXTURES / "systems_slice.csv",
        body_ids_by_host=by_host,
    )
    au = next(s for s in systems if s.id == "au-mic")
    assert au.bodies == ["au-mic.b", "au-mic.c", "au-mic.d", "au-mic.e"]
    sol = next(s for s in systems if s.id == "sol")
    assert sol.bodies == []
