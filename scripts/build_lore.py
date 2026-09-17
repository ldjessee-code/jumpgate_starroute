#!/usr/bin/env python3
"""Build the static lore index. ``python scripts/build_lore.py`` (stdlib only)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from starroute.lore import main

if __name__ == "__main__":
    raise SystemExit(main())
