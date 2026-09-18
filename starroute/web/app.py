"""Local FastAPI UI: confirm NASA files, generate systems, then build and view the map."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from starroute.ingest.pipeline import (
    build_systems_dataset,
    detect_default_sources,
    preview_sources,
    search_hostnames,
)
from starroute.mapgen.factions import (
    assign_factions,
    load_faction_config,
    preview_faction_matches,
    save_faction_config,
)
from starroute.mapgen.network import (
    DEFAULT_NETWORK,
    generate_network,
    network_payload,
    shortest_path,
)
from starroute.paths import (
    DATA_PROCESSED,
    DATA_RAW,
    DATA_UPLOADS,
    FACTION_PRESETS_JSON,
    FACTIONS_DEFAULT_JSON,
    FACTIONS_JSON,
    NETWORK_CSV,
    NETWORK_JSON,
    ORIGIN_JSON,
    SNAPSHOT_JSON,
    SYSTEMS_CSV,
    ensure_data_dirs,
)

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES = Environment(
    loader=FileSystemLoader(WEB_DIR / "templates"),
    autoescape=select_autoescape(["html"]),
)


class IngestRequest(BaseModel):
    planet_path: str
    host_path: str
    max_distance_ly: float = 1000.0
    min_stellar_mass: float = 0.25
    origin_hostname: str = "Sol"


class HostSearchRequest(BaseModel):
    query: str = ""
    host_path: Optional[str] = None
    limit: int = 20


class FactionSaveRequest(BaseModel):
    factions: Dict[str, Any]


class PreviewRequest(BaseModel):
    planet_path: str
    host_path: str


class NetworkRequest(BaseModel):
    max_jump_ly: float = 50.0
    medium_start_pct: float = 50.0
    long_start_pct: float = 75.0
    preferred_ly: float = 25.0
    max_neighbors: int = 8
    hard_rank: float = 0.2
    soft_rank: float = 0.3
    max_linked_nodes: int = 101
    min_stellar_mass: float = 0.25
    max_stellar_mass: Optional[float] = None
    root_hostname: str = "Sol"
    assign_factions: bool = True
    factions: Optional[Dict[str, Any]] = None


class PathRequest(BaseModel):
    start: str = "Sol"
    end: str = Field(..., min_length=1)


def _load_network_defaults() -> dict[str, Any]:
    if NETWORK_JSON.exists():
        return {**DEFAULT_NETWORK, **json.loads(NETWORK_JSON.read_text())}
    return dict(DEFAULT_NETWORK)


def create_app() -> FastAPI:
    ensure_data_dirs()
    app = FastAPI(title="Jumpgate Starroute", version="2.0.0")
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        template = TEMPLATES.get_template("index.html")
        return template.render()

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        systems = SYSTEMS_CSV.exists()
        network = NETWORK_CSV.exists()
        summary: dict[str, Any] = {
            "systems_ready": systems,
            "network_ready": network,
            "systems_path": str(SYSTEMS_CSV) if systems else None,
            "network_path": str(NETWORK_CSV) if network else None,
        }
        if systems:
            df = pd.read_csv(SYSTEMS_CSV, usecols=lambda c: c in {"hostname", "distance_from_sol_ly", "origin_hostname"})
            summary["systems_count"] = int(len(df))
            summary["includes_sol"] = bool((df["hostname"] == "Sol").any())
            if "origin_hostname" in df.columns and len(df):
                summary["origin_hostname"] = str(df["origin_hostname"].iloc[0])
        if ORIGIN_JSON.exists():
            summary.update(json.loads(ORIGIN_JSON.read_text(encoding="utf-8")))
        if network:
            ndf = pd.read_csv(NETWORK_CSV, usecols=lambda c: c in {"hostname", "gate_distance"})
            summary["network_count"] = int(len(ndf))
            summary["linked_count"] = int(ndf["gate_distance"].notna().sum())
        return summary

    @app.get("/api/ingest/detect")
    def ingest_detect() -> dict[str, Any]:
        detected = detect_default_sources()
        detected["uploads"] = [str(p) for p in sorted(DATA_UPLOADS.glob("*.csv"))]
        return detected

    @app.post("/api/ingest/preview")
    def ingest_preview(req: PreviewRequest) -> dict[str, Any]:
        try:
            return preview_sources(req.planet_path, req.host_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 — surface CSV problems to the UI
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ingest/upload")
    async def ingest_upload(
        kind: str = Form(...),
        file: UploadFile = File(...),
    ) -> dict[str, Any]:
        if kind not in {"planets", "hosts"}:
            raise HTTPException(status_code=400, detail="kind must be planets or hosts")
        if not file.filename or not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Upload a NASA .csv snapshot")
        DATA_UPLOADS.mkdir(parents=True, exist_ok=True)
        dest = DATA_UPLOADS / Path(file.filename).name
        with dest.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)
        # Also copy into data/raw so detect() can find it next time.
        raw_dest = DATA_RAW / dest.name
        shutil.copy2(dest, raw_dest)
        return {"path": str(raw_dest), "kind": kind, "name": dest.name}

    @app.post("/api/ingest/run")
    def ingest_run(req: IngestRequest) -> dict[str, Any]:
        try:
            return build_systems_dataset(
                req.planet_path,
                req.host_path,
                max_distance_ly=req.max_distance_ly,
                min_stellar_mass=req.min_stellar_mass,
                origin_hostname=req.origin_hostname,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/hosts/search")
    def hosts_search(req: HostSearchRequest) -> dict[str, Any]:
        names = search_hostnames(req.query, host_path=req.host_path, limit=req.limit)
        return {"query": req.query, "matches": names}

    @app.get("/api/factions")
    def factions_get() -> dict[str, Any]:
        return load_faction_config()

    @app.get("/api/factions/defaults")
    def factions_defaults() -> dict[str, Any]:
        path = FACTIONS_DEFAULT_JSON if FACTIONS_DEFAULT_JSON.exists() else FACTIONS_JSON
        return load_faction_config(path)

    @app.get("/api/factions/presets")
    def factions_presets() -> dict[str, Any]:
        if not FACTION_PRESETS_JSON.exists():
            return {"max_cultures": 16, "presets": []}
        return json.loads(FACTION_PRESETS_JSON.read_text(encoding="utf-8"))

    @app.post("/api/factions")
    def factions_save(req: FactionSaveRequest) -> dict[str, Any]:
        path = save_faction_config(req.factions)
        return {"saved": str(path)}

    @app.post("/api/factions/preview")
    def factions_preview(req: FactionSaveRequest) -> dict[str, Any]:
        if not SYSTEMS_CSV.exists():
            raise HTTPException(status_code=400, detail="Generate the catalog on the first tab first.")
        df = pd.read_csv(SYSTEMS_CSV)
        return {"catalog_systems": int(len(df)), "groups": preview_faction_matches(df, req.factions)}

    @app.get("/api/network/defaults")
    def network_defaults() -> dict[str, Any]:
        return _load_network_defaults()

    @app.post("/api/network/generate")
    def network_generate(req: NetworkRequest) -> dict[str, Any]:
        if not SYSTEMS_CSV.exists():
            raise HTTPException(status_code=400, detail="Generate the systems table first.")
        params = req.model_dump(exclude={"assign_factions", "factions"})
        result = generate_network(params=params)
        network = pd.read_csv(NETWORK_CSV)
        if req.assign_factions:
            config = req.factions or load_faction_config()
            if req.factions:
                save_faction_config(config)
            assigned, routes = assign_factions(network, config=config)
            assigned.to_csv(NETWORK_CSV, index=False)
            result["assigned"] = int(assigned["assigned"].sum()) if "assigned" in assigned else 0
            result["routes"] = int(len(routes))
            result["groups"] = (
                assigned.loc[assigned["Group"] != "", "Group"].value_counts().to_dict()
                if "Group" in assigned
                else {}
            )
        result["payload"] = network_payload(pd.read_csv(NETWORK_CSV))
        return result

    @app.get("/api/network/snapshot")
    def network_snapshot() -> dict[str, Any]:
        if not NETWORK_CSV.exists():
            raise HTTPException(status_code=404, detail="Generate a network before saving a snapshot.")
        payload = {
            "starroute": "2.0",
            "kind": "network_snapshot",
            "payload": network_payload(pd.read_csv(NETWORK_CSV)),
            "factions": load_faction_config(),
            "params": _load_network_defaults(),
        }
        if ORIGIN_JSON.exists():
            payload["origin"] = json.loads(ORIGIN_JSON.read_text(encoding="utf-8"))
        SNAPSHOT_JSON.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    @app.get("/api/network")
    def network_get() -> dict[str, Any]:
        if not NETWORK_CSV.exists():
            raise HTTPException(status_code=404, detail="No network has been generated yet.")
        df = pd.read_csv(NETWORK_CSV)
        return network_payload(df)

    @app.post("/api/network/path")
    def network_path(req: PathRequest) -> dict[str, Any]:
        if not NETWORK_CSV.exists():
            raise HTTPException(status_code=404, detail="No network has been generated yet.")
        df = pd.read_csv(NETWORK_CSV)
        path = shortest_path(df, req.start, req.end)
        return {"start": req.start, "end": req.end, "path": path, "jumps": max(len(path) - 1, 0)}

    @app.get("/api/download/{name}")
    def download(name: str) -> FileResponse:
        allowed = {
            "systems.csv": SYSTEMS_CSV,
            "sol_network.csv": NETWORK_CSV,
            "assigned_systems.csv": DATA_PROCESSED / "assigned_systems.csv",
            "route_table.csv": DATA_PROCESSED / "route_table.csv",
            "factions.json": FACTIONS_JSON,
            "map_snapshot.json": SNAPSHOT_JSON,
        }
        path = allowed.get(name)
        if not path or not path.exists():
            raise HTTPException(status_code=404, detail=f"{name} is not available yet")
        return FileResponse(path, filename=name)

    return app


app = create_app()
