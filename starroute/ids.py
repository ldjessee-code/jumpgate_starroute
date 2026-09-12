"""Dual identity: NASA hostname stays the v2 graph key; v3 id is a slug."""

from __future__ import annotations

import re

_SLUG_KEEP = re.compile(r"[^a-z0-9]+")


def host_id(hostname: str) -> str:
    """Slug of NASA ``hostname``. ``AU Mic`` → ``au-mic``; ``55 Cnc B`` → ``55-cnc-b``."""
    slug = _SLUG_KEEP.sub("-", str(hostname).lower()).strip("-")
    if not slug:
        raise ValueError("hostname slugs to empty id")
    return slug


def body_id(hostname: str, pl_letter: str | None) -> str:
    """``AU Mic`` + ``b`` → ``au-mic.b``."""
    letter = (pl_letter or "").strip().lower()
    if not letter:
        raise ValueError("pl_letter required for a confirmed body id")
    return f"{host_id(hostname)}.{letter}"
