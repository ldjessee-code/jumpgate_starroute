#!/usr/bin/env python3
"""Build the three static map preset packs. ``python scripts/build_presets.py``."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from starroute.presets import main

if __name__ == "__main__":
    raise SystemExit(main())
