"""Read/write JSON documents under ``data/jumpgate/``."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from starroute import paths
from starroute.store.etag import compute_etag

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SAFE_COLLECTION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class JsonStore:
    """Collection/id JSON files. Etag is computed on write and echoed in the document."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else paths.DATA_JUMPGATE

    def path_for(self, collection: str, doc_id: str) -> Path:
        if not _SAFE_COLLECTION.match(collection):
            raise ValueError(f"unsafe collection: {collection!r}")
        if not _SAFE_ID.match(doc_id):
            raise ValueError(f"unsafe document id: {doc_id!r}")
        return self.root / collection / f"{doc_id}.json"

    def list_ids(self, collection: str) -> list[str]:
        if not _SAFE_COLLECTION.match(collection):
            raise ValueError(f"unsafe collection: {collection!r}")
        folder = self.root / collection
        if not folder.is_dir():
            return []
        return sorted(p.stem for p in folder.glob("*.json"))

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        path = self.path_for(collection, doc_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, collection: str, doc_id: str, document: Mapping[str, Any]) -> dict[str, Any]:
        paths.ensure_data_dirs()
        path = self.path_for(collection, doc_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(document)
        payload["etag"] = compute_etag(payload)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return payload

    def delete(self, collection: str, doc_id: str) -> bool:
        path = self.path_for(collection, doc_id)
        if not path.is_file():
            return False
        path.unlink()
        return True
