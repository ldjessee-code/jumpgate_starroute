"""v1 ingest: wrap NASA CSV ingest; never accept uploaded bytes on this router."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from starroute import paths
from starroute.api.v1.errors import Problem
from starroute.ingest.pipeline import build_systems_dataset, detect_default_sources, preview_sources


def _under_allowed(path: Path) -> bool:
    resolved = path.expanduser().resolve()
    roots = (paths.DATA_RAW.resolve(), paths.DATA_UPLOADS.resolve())
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def require_local_table(path: str, *, instance: str) -> Path:
    candidate = Path(path)
    if not candidate.is_file():
        raise Problem(404, "not_found", f"Table not found: {path}", instance=instance)
    if not _under_allowed(candidate):
        raise Problem(
            400,
            "validation_error",
            "planet_path and host_path must be under data/raw or data/uploads",
            instance=instance,
        )
    return candidate


def ingest_nasa(body: dict[str, Any]) -> dict[str, Any]:
    instance = "/ingest/nasa"
    planet = require_local_table(str(body.get("planet_path") or ""), instance=instance)
    host = require_local_table(str(body.get("host_path") or ""), instance=instance)
    setting_id: Optional[str] = body.get("setting_id")
    try:
        return build_systems_dataset(
            planet,
            host,
            max_distance_ly=float(body.get("max_distance_ly") or 1000.0),
            min_stellar_mass=float(body.get("min_stellar_mass") or 0.25),
            origin_hostname=str(body.get("origin_hostname") or "Sol"),
            setting_id=setting_id,
            emit_json=True,
        )
    except FileNotFoundError as exc:
        raise Problem(404, "not_found", str(exc), instance=instance) from exc
    except ValueError as exc:
        raise Problem(400, "validation_error", str(exc), instance=instance) from exc
