"""Celestial coordinate helpers.

NASA Exoplanet Archive ``sy_dist`` is in **parsecs**. Earlier scripts in this
project mixed parsecs and light-years (filters such as ``<= 1000`` were applied
to ``sy_dist`` while comments called the unit light-years). All public functions
here take or return light-years unless the name says otherwise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# IAU parsec in light-years; matches the factor the old TAP scripts used.
PC_TO_LY = 3.26156


def parsecs_to_ly(distance_pc: float | np.ndarray | pd.Series):
    return distance_pc * PC_TO_LY


def ra_dec_dist_to_xyz(ra_deg, dec_deg, dist_ly):
    """Equatorial RA/Dec plus distance → heliocentric Cartesian light-years.

    Sol is the origin. ``ra=0, dec=0, dist=0`` is a coordinate convention for
    Sol, not a claim about the Sun's right ascension.
    """
    ra = np.radians(ra_deg)
    dec = np.radians(dec_deg)
    x = dist_ly * np.cos(dec) * np.cos(ra)
    y = dist_ly * np.cos(dec) * np.sin(ra)
    z = dist_ly * np.sin(dec)
    return x, y, z


def add_cartesian_columns(df: pd.DataFrame, dist_pc_col: str = "sy_dist") -> pd.DataFrame:
    """Add ``distance_from_sol_ly`` and ``calculated_x/y/z`` from RA/Dec/parsecs."""
    out = df.copy()
    dist_ly = parsecs_to_ly(pd.to_numeric(out[dist_pc_col], errors="coerce"))
    # Sol (and any explicit origin row) stays at 0 ly even if sy_dist is missing.
    origin = out.get("hostname", pd.Series(index=out.index)).eq("Sol")
    dist_ly = dist_ly.where(~origin, 0.0)
    x, y, z = ra_dec_dist_to_xyz(out["ra"], out["dec"], dist_ly)
    out["distance_from_sol_ly"] = dist_ly
    out["calculated_x"] = x
    out["calculated_y"] = y
    out["calculated_z"] = z
    return out
