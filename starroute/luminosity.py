"""V-band luminosity when every catalog luminosity cell is blank.

Bolometric correction: none. Solar absolute V magnitude is 4.83.
Units are V-band solar luminosities. The method string is johnson_v_no_bc.
Catalog fields st_lum, luminosity, lum, and lum_solar are never assigned.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from starroute.mapgen.tiers import as_float

SOL_ABS_V = 4.83
METHOD = "johnson_v_no_bc"
CATALOG_LUM_KEYS = ("st_lum", "luminosity", "lum", "lum_solar")


def catalog_luminosity_present(row: Mapping[str, Any]) -> bool:
    """True when any catalog luminosity cell parses as a finite float.

    0 counts as present. The Sun's st_lum 0 is log10 of 1.
    """
    for key in CATALOG_LUM_KEYS:
        if as_float(row.get(key)) is not None:
            return True
    return False


def calculate_luminosity(row: Mapping[str, Any]) -> tuple[float | None, str | None]:
    """Return calculated_luminosity and calculated_luminosity_method.

    Does not mutate ``row``. Johnson V comes from ``mag_v``, else ``sy_vmag``.
    Gaia G and ``render_mag`` are not used. Distance must be greater than 0.
    ``M_V = m_V - 5*log10(dist_pc) + 5`` and
    ``L/L_sun = 10**((4.83 - M_V) / 2.5)``.
    """
    if catalog_luminosity_present(row):
        return None, None
    mag = as_float(row.get("mag_v"))
    if mag is None:
        mag = as_float(row.get("sy_vmag"))
    dist = as_float(row.get("dist_pc"))
    if mag is None or dist is None or dist <= 0:
        return None, None
    absolute = mag - 5.0 * math.log10(dist) + 5.0
    luminosity = 10.0 ** ((SOL_ABS_V - absolute) / 2.5)
    return float(luminosity), METHOD
