"""Call the court preflight command and wait until it is clear."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Callable

from bench.logging_util import append_log

Runner = Callable[[str], tuple[int, str]]
Sleeper = Callable[[float], None]


def run_command(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    text = (proc.stdout or proc.stderr or "").strip()
    return proc.returncode, text


def wait_until_clear(
    cmd: str,
    log_path: str | Path,
    *,
    runner: Runner | None = None,
    sleep_fn: Sleeper | None = None,
    sleep_s: float = 60.0,
    max_waits: int = 120,
    step_format: str = "-",
    step_variant: str = "-",
) -> None:
    """Run ``cmd`` until it exits 0. Each wait is its own log line."""
    if not str(cmd).strip():
        raise RuntimeError("BENCH_PREFLIGHT_CMD is empty")
    runner = runner or run_command
    sleep_fn = sleep_fn or time.sleep
    waits = 0
    while True:
        started = time.perf_counter()
        code, output = runner(cmd)
        elapsed = time.perf_counter() - started
        if code == 0:
            append_log(
                log_path,
                {
                    "step": "preflight",
                    "format": step_format,
                    "variant": step_variant,
                    "phase": "preflight",
                    "seconds": f"{elapsed:.4f}",
                    "gates": 0,
                    "routes": 0,
                    "rows": 0,
                    "note": "CLEAR",
                },
            )
            return
        append_log(
            log_path,
            {
                "step": "preflight_wait",
                "format": step_format,
                "variant": step_variant,
                "phase": "preflight",
                "seconds": f"{elapsed:.4f}",
                "gates": 0,
                "routes": 0,
                "rows": 0,
                "note": output or "busy",
            },
        )
        waits += 1
        if waits >= max_waits:
            raise RuntimeError("preflight stayed busy")
        sleep_fn(sleep_s)
