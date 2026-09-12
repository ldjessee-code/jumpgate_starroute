"""Strong etags: SHA-256 of canonical JSON excluding ``etag`` and ``updated_at``."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

CAS_EXCLUDE = frozenset({"etag", "updated_at"})


def strip_cas_fields(document: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a mapping without the fields that must not enter the digest."""
    return {key: value for key, value in document.items() if key not in CAS_EXCLUDE}


def canonical_bytes(document: Mapping[str, Any]) -> bytes:
    """UTF-8 JSON, sorted keys, no extra whitespace (RFC 8785-style fallback)."""
    body = strip_cas_fields(document)
    return json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def compute_etag(document: Mapping[str, Any]) -> str:
    """Quoted strong tag, e.g. ``\"sha256-3b7f9c12a4d0\"``. Never a weak ``W/`` tag."""
    digest = hashlib.sha256(canonical_bytes(document)).hexdigest()[:12]
    return f'"sha256-{digest}"'


def etag_header_ok(header: str | None) -> tuple[bool, str | None]:
    """Return ``(ok, reason)``. Weak tags and missing headers fail.

    ``reason`` is ``None`` when ok, else ``missing`` or ``weak``.
    Byte-equal compare against a stored tag is the caller's job.
    """
    if header is None or not str(header).strip():
        return False, "missing"
    value = str(header).strip()
    if value.startswith("W/") or value.startswith("w/"):
        return False, "weak"
    return True, None
