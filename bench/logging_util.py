"""One timestamped bench line, flushed and fsync'd immediately."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

LOG_KEYS = ("step", "format", "variant", "phase", "seconds", "gates", "routes", "rows")


def _clean(value: Any) -> str:
    text = "-" if value is None else str(value)
    return " ".join(text.replace("\r", " ").replace("\n", " ").split()) or "-"


def append_log(path: str | Path, fields: Mapping[str, Any]) -> str:
    """Append one line and fsync it before returning."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    parts = [stamp]
    for key in LOG_KEYS:
        parts.append(f"{key}={_clean(fields.get(key, '-'))}")
    for key, value in fields.items():
        if key not in LOG_KEYS:
            parts.append(f"{key}={_clean(value)}")
    line = " ".join(parts) + "\n"
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
    return line


def pass_state(path: str | Path) -> str:
    """Return empty, complete, or incomplete from the latest suite_start."""
    target = Path(path)
    if not target.is_file():
        return "empty"
    text = target.read_text(encoding="utf-8")
    start = text.rfind("step=suite_start")
    if start < 0:
        return "empty"
    tail = text[start:]
    if "step=suite_complete" in tail:
        return "complete"
    return "incomplete"
