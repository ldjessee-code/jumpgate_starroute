"""Ptah v1 public API — child FastAPI app (RFC 7807 lives only here)."""

from __future__ import annotations

from typing import Optional

from fastapi import Body, FastAPI, Header, Query
from fastapi.exceptions import RequestValidationError

from starroute import __version__
from starroute.api.v1.catalog import (
    load_network_df,
    load_systems_df,
    require_setting_id,
    system_document,
)
from starroute.api.v1.errors import Problem, problem_handler, validation_handler
from starroute.api.v1.resolve import resolve_host
from starroute.api.v1 import fiction as fiction_api
from starroute.api.v1 import ingest as ingest_api
from starroute.api.v1 import network as network_api
from starroute.api.v1 import overlays as overlays_api
from starroute.api.v1 import premise as premise_api
from starroute.api.v1 import settings as settings_api
from starroute.api.v1 import tick as tick_api
from starroute.store.documents import JsonStore
from starroute.ids import edge_id, host_id
from starroute.ingest.pipeline import detect_default_sources, preview_sources
from starroute.mapgen.network import shortest_path


def _v3_network(setting_id: Optional[str], network_id: str) -> dict:
    stored = JsonStore().get("networks", network_id)
    if stored:
        return stored
    df = load_network_df()
    return network_api.v3_network_document(network_id, setting_id, df, {})


def create_v1_app() -> FastAPI:
    app = FastAPI(
        title="Ptah",
        version="3.0.0",
        description="Jumpgate Starroute public API (L0–L2, L11). UI remains on /api.",
    )
    app.add_exception_handler(Problem, problem_handler)
    app.add_exception_handler(RequestValidationError, validation_handler)

    @app.post("/settings", operation_id="create_setting")
    def create_setting(body: dict = Body(...)) -> dict:
        return settings_api.create_setting(body)

    @app.get("/settings/{setting_id}", operation_id="get_setting")
    def get_setting(setting_id: str) -> dict:
        return settings_api.get_setting(setting_id)

    @app.put("/settings/{setting_id}", operation_id="put_setting")
    def put_setting(
        setting_id: str,
        body: dict = Body(...),
        if_match: Optional[str] = Header(default=None, alias="If-Match"),
    ) -> dict:
        return settings_api.put_setting(setting_id, body, if_match)

    @app.post("/settings/{setting_id}/actions", operation_id="apply_political_action")
    def apply_political_action(setting_id: str, body: dict = Body(...)) -> dict:
        return tick_api.enqueue_action(setting_id, body)

    @app.post("/settings/{setting_id}/tick", operation_id="tick_setting")
    def tick_setting(setting_id: str, body: dict = Body(default={})) -> dict:
        return tick_api.tick_setting(setting_id, body or {})

    @app.post("/webhooks/chronos/advance", operation_id="chronos_advance_hook")
    def chronos_advance_hook(body: dict = Body(...)) -> dict:
        return tick_api.chronos_advance_hook(body)

    @app.get("/settings/{setting_id}/reality", operation_id="get_reality")
    def get_reality(setting_id: str) -> dict:
        return settings_api.get_reality(setting_id)

    @app.put("/settings/{setting_id}/reality", operation_id="put_reality")
    def put_reality(
        setting_id: str,
        body: dict = Body(...),
        if_match: Optional[str] = Header(default=None, alias="If-Match"),
    ) -> dict:
        return settings_api.put_reality(setting_id, body, if_match)

    @app.get("/ingest/detect", operation_id="ingest_detect")
    def ingest_detect() -> dict:
        return detect_default_sources()

    @app.post("/ingest/preview", operation_id="ingest_preview")
    def ingest_preview(body: dict = Body(...)) -> dict:
        try:
            return preview_sources(body["planet_path"], body["host_path"])
        except FileNotFoundError as exc:
            raise Problem(404, "not_found", str(exc), instance="/ingest/preview") from exc

    @app.post("/ingest/nasa", operation_id="ingest_nasa")
    def ingest_nasa(body: dict = Body(...)) -> dict:
        return ingest_api.ingest_nasa(body)

    @app.get("/factions", operation_id="list_factions")
    def list_factions(setting_id: Optional[str] = Query(default=None)) -> dict:
        require_setting_id(setting_id)
        return {"factions": overlays_api.seed_factions()}

    @app.get("/factions/{faction_id}", operation_id="get_faction")
    def get_faction(faction_id: str) -> dict:
        for row in overlays_api.seed_factions():
            if row["id"] == faction_id:
                legal = overlays_api.get_legal(faction_id)
                return {**row, "legal": legal}
        raise Problem(404, "not_found", f"Unknown faction {faction_id!r}", instance=f"/factions/{faction_id}")

    @app.get("/factions/{faction_id}/legal", operation_id="get_legal")
    def get_legal(faction_id: str) -> dict:
        return overlays_api.get_legal(faction_id)

    @app.put("/factions/{faction_id}/legal", operation_id="put_legal")
    def put_legal(faction_id: str, body: dict = Body(...)) -> dict:
        return overlays_api.put_legal(faction_id, body)

    @app.get("/settings/{setting_id}/affiliations", operation_id="get_affiliations")
    def get_affiliations(setting_id: str) -> dict:
        return overlays_api.get_affiliations(setting_id)

    @app.put("/settings/{setting_id}/affiliations", operation_id="put_affiliations")
    def put_affiliations(setting_id: str, body: dict = Body(...)) -> dict:
        return overlays_api.put_affiliations(setting_id, body)

    @app.put("/systems/{system_id}/affiliations", operation_id="put_system_affiliations")
    def put_system_affiliations(
        system_id: str,
        body: dict = Body(...),
        setting_id: Optional[str] = Query(default=None),
    ) -> dict:
        sid = require_setting_id(setting_id)
        return overlays_api.put_system_affiliations(system_id, body, sid)

    @app.get("/networks/{network_id}/trade", operation_id="get_trade")
    def get_trade(network_id: str) -> dict:
        return overlays_api.get_trade(network_id)

    @app.put("/networks/{network_id}/trade", operation_id="put_trade")
    def put_trade(network_id: str, body: dict = Body(...)) -> dict:
        return overlays_api.put_trade(network_id, body)

    @app.get("/provider", operation_id="get_provider")
    def get_provider() -> dict:
        return {
            "name": "ptah",
            "product": "Jumpgate Starroute",
            "version": "3.0.0",
            "package_version": __version__,
            "layers": ["L0", "L1", "L2", "L11"],
            "ui": "/api",
            "api": "/v1",
        }

    @app.get("/systems", operation_id="list_systems")
    def list_systems(setting_id: Optional[str] = Query(default=None)) -> dict:
        sid = require_setting_id(setting_id)
        df = load_systems_df()
        items = [
            {"id": host_id(str(h)), "hostname": str(h)}
            for h in df["hostname"].astype(str)
        ]
        return {"setting_id": sid, "systems": items}

    @app.get("/systems/{system_id}", operation_id="get_system")
    def get_system(
        system_id: str,
        setting_id: Optional[str] = Query(default=None),
        view: Optional[str] = Query(default=None),
    ) -> dict:
        sid = require_setting_id(setting_id)
        store = JsonStore()
        stored = None
        for candidate in (system_id,):
            try:
                stored = store.get("systems", host_id(candidate))
            except ValueError:
                stored = None
            if stored:
                break
        if stored:
            doc = stored
        else:
            df = load_systems_df()
            hostname = resolve_host(system_id, df, instance=f"/systems/{system_id}")
            doc = system_document(hostname, sid)
        if view != "catalog":
            doc = fiction_api.apply_overrides(doc)
        return doc

    @app.post("/systems", operation_id="create_generated_host")
    def create_generated_host(
        body: dict = Body(...),
        setting_id: Optional[str] = Query(default=None),
    ) -> dict:
        sid = require_setting_id(setting_id or body.get("setting_id"))
        return fiction_api.create_generated_host(body, sid)

    @app.put("/systems/{system_id}/overrides", operation_id="put_override")
    def put_override(
        system_id: str,
        body: dict = Body(...),
        setting_id: Optional[str] = Query(default=None),
    ) -> dict:
        sid = require_setting_id(setting_id)
        return fiction_api.put_override(system_id, body, sid)

    @app.put("/systems/{system_id}/xyz", operation_id="put_xyz")
    def put_xyz(
        system_id: str,
        body: dict = Body(...),
        setting_id: Optional[str] = Query(default=None),
    ) -> dict:
        sid = require_setting_id(setting_id)
        return fiction_api.put_xyz(system_id, body, sid)

    @app.get("/systems/{system_id}/bodies", operation_id="list_system_bodies")
    def list_system_bodies(system_id: str, setting_id: Optional[str] = Query(default=None)) -> dict:
        sid = require_setting_id(setting_id)
        df = load_systems_df()
        hostname = resolve_host(system_id, df, instance=f"/systems/{system_id}/bodies")
        doc = system_document(hostname, sid)
        store = JsonStore()
        items = [store.get("bodies", bid) for bid in doc.get("bodies") or []]
        return {"system_id": doc["id"], "bodies": [b for b in items if b]}

    @app.get("/bodies/{body_id}", operation_id="get_body_l2")
    def get_body_l2(body_id: str) -> dict:
        doc = JsonStore().get("bodies", body_id)
        if not doc:
            raise Problem(404, "not_found", f"Unknown body {body_id!r}", instance=f"/bodies/{body_id}")
        return doc

    @app.post("/systems/{system_id}/premise", operation_id="set_system_premise")
    def set_system_premise(
        system_id: str,
        body: dict = Body(...),
        setting_id: Optional[str] = Query(default=None),
    ) -> dict:
        sid = require_setting_id(setting_id)
        return premise_api.set_system_premise(system_id, body, sid)

    @app.post("/systems/{system_id}/generate-l2", operation_id="generate_l2_gapfill")
    def generate_l2_gapfill(
        system_id: str,
        body: dict = Body(default={}),
        setting_id: Optional[str] = Query(default=None),
    ) -> dict:
        sid = require_setting_id(setting_id)
        need = list(body.get("need") or [])
        return premise_api.generate_l2_gapfill(
            system_id, setting_id=sid, need=need, seed=body.get("seed")
        )

    @app.get("/stars/{star_id}", operation_id="get_star")
    def get_star(star_id: str, setting_id: Optional[str] = Query(default=None)) -> dict:
        doc = get_system(star_id, setting_id)
        return {"id": doc["id"], "hostname": doc["hostname"], "star": doc.get("star"), "coords": doc.get("coords")}

    @app.get("/networks/{network_id}", operation_id="get_network")
    def get_network(network_id: str, setting_id: Optional[str] = Query(default=None)) -> dict:
        sid = require_setting_id(setting_id)
        return _v3_network(sid, network_id)

    @app.put("/networks/{network_id}/edges/{a}/{b}", operation_id="put_extra_edge")
    def put_extra_edge(
        network_id: str,
        a: str,
        b: str,
        body: dict = Body(default={}),
        setting_id: Optional[str] = Query(default=None),
    ) -> dict:
        sid = require_setting_id(setting_id)
        return fiction_api.put_extra_edge(network_id, a, b, body or {}, sid)

    @app.get("/networks/{network_id}/edges/{a}/{b}", operation_id="get_edge")
    def get_edge(
        network_id: str,
        a: str,
        b: str,
        setting_id: Optional[str] = Query(default=None),
    ) -> dict:
        require_setting_id(setting_id)
        net = _v3_network(setting_id, network_id)
        net = fiction_api.merge_extra_edges(net)
        want = edge_id(a, b)
        for edge in net.get("edges") or []:
            if edge.get("id") == want:
                return edge
        raise Problem(404, "not_found", f"No edge {a}–{b}", instance=f"/networks/{network_id}/edges/{a}/{b}")

    @app.post("/networks/{network_id}/rebuild", operation_id="rebuild_network")
    def rebuild_network(
        network_id: str,
        body: dict = Body(default={}),
        setting_id: Optional[str] = Query(default=None),
    ) -> dict:
        sid = require_setting_id(setting_id or (body or {}).get("setting_id"))
        return network_api.rebuild_network(network_id, body or {}, sid)

    @app.get("/networks/{network_id}/route", operation_id="get_route")
    def get_route(
        network_id: str,
        start: str = Query(...),
        end: str = Query(...),
        setting_id: Optional[str] = Query(default=None),
    ) -> dict:
        require_setting_id(setting_id)
        systems = load_systems_df()
        net = load_network_df()
        start_host = resolve_host(start, systems, instance=f"/networks/{network_id}/route")
        end_host = resolve_host(end, systems, instance=f"/networks/{network_id}/route")
        path = shortest_path(net, start_host, end_host)
        if not path and start_host != end_host:
            raise Problem(404, "no_route", f"No path from {start_host} to {end_host}")
        return {
            "network_id": network_id,
            "start": start_host,
            "end": end_host,
            "start_id": host_id(start_host),
            "end_id": host_id(end_host),
            "path_hostnames": path,
            "path_ids": [host_id(h) for h in path],
            "jumps": max(len(path) - 1, 0),
        }

    return app
