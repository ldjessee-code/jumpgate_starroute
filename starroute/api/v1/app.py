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
from starroute.api.v1 import ingest as ingest_api
from starroute.api.v1 import settings as settings_api
from starroute.ids import host_id
from starroute.ingest.pipeline import detect_default_sources, preview_sources
from starroute.mapgen.network import network_payload, shortest_path


def _v3_network(setting_id: Optional[str], network_id: str) -> dict:
    df = load_network_df()
    payload = network_payload(df)
    nodes = []
    for node in payload["nodes"]:
        hostname = node["hostname"]
        nodes.append(
            {
                "id": host_id(hostname),
                "hostname": hostname,
                "xyz_ly": [node.get("x"), node.get("y"), node.get("z")],
                "gate_distance": node.get("gate_distance"),
                "group": node.get("group") or "",
            }
        )
    edges = []
    for edge in payload["edges"]:
        a_host, b_host = edge["a"], edge["b"]
        a_id, b_id = host_id(a_host), host_id(b_host)
        edges.append(
            {
                "id": f"{a_id}--{b_id}",
                "a": a_id,
                "b": b_id,
                "a_hostname": a_host,
                "b_hostname": b_host,
                "distance_ly": edge.get("distance"),
            }
        )
    return {
        "schema": "jumpgate.network.v1",
        "layer": "L11",
        "id": network_id,
        "setting_id": setting_id,
        "starroute": "3.0",
        "nodes": nodes,
        "edges": edges,
    }


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
    def get_system(system_id: str, setting_id: Optional[str] = Query(default=None)) -> dict:
        sid = require_setting_id(setting_id)
        df = load_systems_df()
        hostname = resolve_host(system_id, df, instance=f"/systems/{system_id}")
        return system_document(hostname, sid)

    @app.get("/stars/{star_id}", operation_id="get_star")
    def get_star(star_id: str, setting_id: Optional[str] = Query(default=None)) -> dict:
        doc = get_system(star_id, setting_id)
        return {"id": doc["id"], "hostname": doc["hostname"], "star": doc.get("star"), "coords": doc.get("coords")}

    @app.get("/networks/{network_id}", operation_id="get_network")
    def get_network(network_id: str, setting_id: Optional[str] = Query(default=None)) -> dict:
        sid = require_setting_id(setting_id)
        return _v3_network(sid, network_id)

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
