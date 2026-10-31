"""Star tiers for a route build.

Tiers are computed when a map is built. They are not written into the catalog.

A star may be ``gate_candidate`` only when it is an exoplanet host and it
passes the same checks as ``starroute.mapgen.network._valid_row``:

- ``calculated_x/y/z`` are finite
- the coordinate origin is rejected unless the row is the root hostname
- the root is accepted before the mass check
- a root with no known planets and no known mass is not a gate
- a planet host with ``st_mass`` missing passes the mass check: missing mass
  is not below ``min_stellar_mass`` and does not fail a max-mass window
- a known ``st_mass`` must be ``>= min_stellar_mass`` (``config/network.json``
  default 0.25; a preset may override it) and, when ``max_stellar_mass`` is
  set, at or below that maximum
- an explicit ``gate_status`` of ``pending_doug`` is not a gate

Optional criteria default off, so a map built without them matches the rule
above. When a caller turns a criterion on, a gate is also refused for:

- a variable star, or a flare star
- a pulsar or neutron star, including when only a companion in the same
  system is one (see ``apply_system_blocks``)
- a dynamically unstable multiple (``unstable_rule`` ``standard`` or ``strict``)

The root hostname is still accepted once it has passed the coordinate and
``pending_doug`` checks, including when those optional criteria are on.

``hard_rank`` and ``soft_rank`` still decide medium and long edges. They do
not change the tier. ``no_known_planets`` never holds a gate, including when
the row sits on the coordinate origin.
"""

from __future__ import annotations

import math
import re
from typing import Any, Mapping

import numpy as np
import pandas as pd

TIER_GATE = "gate_candidate"
TIER_EXO = "exo_no_gate"
TIER_BACKGROUND = "no_known_planets"
TIERS = (TIER_GATE, TIER_EXO, TIER_BACKGROUND)

DEFAULT_MIN_STELLAR_MASS = 0.25
PENDING_DOUG = "pending_doug"
SYSTEM_BLOCK = "_system_block"
DISTANCE_CAP_LY = 500.0

_VAR_RE = re.compile(r"(?i)(?:\bvariable\b|\bvar\b)")
_FLARE_RE = re.compile(r"(?i)(?:\bflare\b|\bdme\b|\bdm\d*e\b|uv\s*ceti)")
_PSR_RE = re.compile(
    r"(?i)(?:\bpulsar\b|\bpsr\b|\bneutron(?:\s*star)?\b|(?<![A-Za-z0-9])NS(?![A-Za-z0-9]))"
)
_SB_RE = re.compile(r"(?i)\bSB\d*\b")
_VAR_FIELDS = ("variable", "var", "is_variable", "variable_flag")
_FLARE_FIELDS = ("flare", "is_flare", "flare_star", "flare_flag")
_KIND_FIELDS = ("object_type", "star_class", "pulsar", "is_pulsar", "neutron", "is_neutron")
_CRITERION_FLAGS = (
    "exclude_variable",
    "exclude_flare",
    "exclude_pulsar_neutron",
    "exclude_unstable_multiple",
)


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"", "nan", "none", "<na>"}
    try:
        if value != value:  # NaN
            return True
    except Exception:
        return False
    return False


def as_float(value: Any) -> float | None:
    if _blank(value) or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def flag_true(value: Any) -> bool | None:
    """True, False, or None when the cell is blank."""
    if _blank(value):
        return None
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {"true", "yes", "y", "1"}:
            return True
        if low in {"false", "no", "n", "0"}:
            return False
        return None
    if isinstance(value, bool):
        return value
    number = as_float(value)
    if number is None:
        return None
    return number != 0.0


def is_exoplanet_host(row: Mapping[str, Any]) -> bool:
    """NASA flag or per-host ``exoplanet_count``. ``sy_pnum`` is the system total."""
    flag = flag_true(row.get("has_known_exoplanets"))
    if flag is True:
        return True
    count = as_float(row.get("exoplanet_count"))
    if count is not None and count > 0:
        return True
    return False


def gate_status_for(row: Mapping[str, Any]) -> str | None:
    """Return an explicit ``gate_status`` when the cell is set, else None."""
    explicit = row.get("gate_status")
    if not _blank(explicit):
        return str(explicit).strip()
    return None


def _coords(row: Mapping[str, Any]) -> tuple[float, float, float] | None:
    parts = []
    for key in ("calculated_x", "calculated_y", "calculated_z"):
        number = as_float(row.get(key))
        if number is None:
            return None
        parts.append(number)
    return parts[0], parts[1], parts[2]


def criteria_from_params(params: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return optional gate criteria, or None when every extra flag is off.

    None keeps the historical acceptance rule. A dict is returned only when
    at least one exclusion flag is true.
    """
    if not params:
        return None
    if not any(params.get(name) for name in _CRITERION_FLAGS):
        return None
    rule = str(params.get("unstable_rule") or "standard").strip().lower()
    if rule not in {"standard", "strict"}:
        rule = "standard"
    return {
        "exclude_variable": bool(params.get("exclude_variable")),
        "exclude_flare": bool(params.get("exclude_flare")),
        "exclude_pulsar_neutron": bool(params.get("exclude_pulsar_neutron")),
        "exclude_unstable_multiple": bool(params.get("exclude_unstable_multiple")),
        "unstable_rule": rule,
    }


def _criterion(criteria: Mapping[str, Any] | None, name: str) -> bool:
    return bool(criteria and criteria.get(name))


def _unstable_rule(criteria: Mapping[str, Any] | None) -> str:
    if not criteria:
        return "standard"
    rule = str(criteria.get("unstable_rule") or "standard").strip().lower()
    return rule if rule in {"standard", "strict"} else "standard"


def _blob(row: Mapping[str, Any], fields: tuple[str, ...]) -> str:
    parts: list[str] = []
    for key in ("spect", "st_spectype", *fields):
        if key not in row:
            continue
        value = row.get(key)
        if _blank(value):
            continue
        parts.append(str(value))
    return " ".join(parts)


def _any_flag(row: Mapping[str, Any], fields: tuple[str, ...]) -> bool:
    for key in fields:
        if key in row and flag_true(row.get(key)) is True:
            return True
    return False


def is_variable_star(row: Mapping[str, Any]) -> bool:
    """True for a variability flag or a spectral note that says variable.

    The luminosity class ``V`` is not a variability mark.
    """
    if _any_flag(row, _VAR_FIELDS):
        return True
    return _VAR_RE.search(_blob(row, _VAR_FIELDS)) is not None


def is_flare_star(row: Mapping[str, Any]) -> bool:
    """True for a flare flag, ``dMe`` / ``dM#e``, or an UV Ceti note."""
    if _any_flag(row, _FLARE_FIELDS):
        return True
    return _FLARE_RE.search(_blob(row, _FLARE_FIELDS)) is not None


def is_pulsar_or_neutron(row: Mapping[str, Any]) -> bool:
    """True for a pulsar or neutron star. A bare carbon class ``N`` is not one."""
    if _any_flag(row, ("pulsar", "is_pulsar", "neutron", "is_neutron")):
        return True
    return _PSR_RE.search(_blob(row, _KIND_FIELDS)) is not None


def is_multiple_star(row: Mapping[str, Any]) -> bool:
    """True when ``sy_snum`` is at least 2 or the spectrum says spectroscopic binary."""
    count = as_float(row.get("sy_snum"))
    if count is not None and count >= 2:
        return True
    return _SB_RE.search(_blob(row, ())) is not None


def is_unstable_multiple(row: Mapping[str, Any], rule: str = "standard") -> bool:
    """True when a multiple is a poor place for a gate.

    ``standard`` refuses a spectroscopic binary (``SB``) or a multiple whose
    ``stability_score`` is 2 or worse (0 is calm, 3 is worst). ``strict``
    refuses every multiple.
    """
    if not is_multiple_star(row):
        return False
    if str(rule).strip().lower() == "strict":
        return True
    score = as_float(row.get("stability_score"))
    if score is not None and score >= 2:
        return True
    return _SB_RE.search(_blob(row, ())) is not None


def _block_reasons(row: Mapping[str, Any]) -> set[str]:
    raw = row.get(SYSTEM_BLOCK)
    if _blank(raw):
        return set()
    return {part for part in str(raw).split(",") if part}


def extra_gate_block(row: Mapping[str, Any], criteria: Mapping[str, Any] | None) -> bool:
    """True when an optional criterion refuses this row. Default criteria do not."""
    if not criteria:
        return False
    if _criterion(criteria, "exclude_variable") and is_variable_star(row):
        return True
    if _criterion(criteria, "exclude_flare") and is_flare_star(row):
        return True
    if _criterion(criteria, "exclude_pulsar_neutron"):
        if is_pulsar_or_neutron(row) or "psr" in _block_reasons(row):
            return True
    if _criterion(criteria, "exclude_unstable_multiple"):
        if is_unstable_multiple(row, _unstable_rule(criteria)) or "unstable" in _block_reasons(row):
            return True
    return False


def _name_stem(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "<na>"}:
        return ""
    spaced = re.sub(r"\s+[A-Da-d]$", "", text).strip()
    glued = re.sub(r"(?<=\d)\s*[A-Da-d]$", "", spaced).strip()
    return glued.casefold()


def _gl_stem(value: Any) -> str:
    stem = _name_stem(value)
    if not stem:
        return ""
    return re.sub(r"(?i)^(?:gliese|gl|gj)\s*", "gl ", stem).strip()


def _interesting_mask(df: pd.DataFrame) -> pd.Series:
    mask = pd.Series(False, index=df.index)
    if "hostname" in df.columns:
        host = df["hostname"].fillna("").astype(str)
        mask = mask | host.str.contains(r"(?:\s+[A-Da-d]$|\d\s*[A-Da-d]$)", regex=True)
    if "proper" in df.columns:
        proper = df["proper"].fillna("").astype(str)
        mask = mask | proper.str.contains(r"(?:\s+[A-Da-d]$|\d\s*[A-Da-d]$)", regex=True)
    if "gl" in df.columns:
        gl = df["gl"].fillna("").astype(str)
        mask = mask | gl.str.contains(r"[A-Da-d]$", regex=True)
    if "spect" in df.columns or "st_spectype" in df.columns:
        spect = df["spect"].fillna("").astype(str) if "spect" in df.columns else ""
        kind = df["st_spectype"].fillna("").astype(str) if "st_spectype" in df.columns else ""
        blob = spect + " " + kind
        mask = mask | blob.str.contains(r"(?i)\bSB\d*\b|\bpulsar\b|\bpsr\b|\bneutron\b|(?<![A-Za-z0-9])NS(?![A-Za-z0-9])")
    if "sy_snum" in df.columns:
        count = pd.to_numeric(df["sy_snum"], errors="coerce")
        mask = mask | count.ge(2)
    for key in ("pulsar", "is_pulsar", "neutron", "is_neutron"):
        if key in df.columns:
            mask = mask | df[key].map(lambda value: flag_true(value) is True)
    return mask.fillna(False)


def apply_system_blocks(df: pd.DataFrame, criteria: Mapping[str, Any] | None) -> pd.DataFrame:
    """Mark companions that share a pulsar/neutron or an unstable multiple.

    The input frame is not modified. With criteria off, the copy is unchanged
    and ``_system_block`` is not added. A pulsar or neutron star marks every
    star that shares its Gliese stem or hostname stem, including itself.
    ``strict`` also marks every star in a stem group of two or more.
    ``standard`` marks the group when any member is unstable on its own.
    """
    if df is None:
        return df
    wants_psr = _criterion(criteria, "exclude_pulsar_neutron")
    wants_unstable = _criterion(criteria, "exclude_unstable_multiple")
    if not wants_psr and not wants_unstable:
        return df
    out = df.copy()
    if out.empty:
        out[SYSTEM_BLOCK] = []
        return out
    interesting = _interesting_mask(out)
    labels = np.array([""] * len(out), dtype=object)
    if not bool(interesting.any()):
        out[SYSTEM_BLOCK] = labels
        return out
    positions = {label: pos for pos, label in enumerate(out.index)}
    host = out["hostname"].fillna("").astype(str) if "hostname" in out.columns else pd.Series("", index=out.index)
    proper = out["proper"].fillna("").astype(str) if "proper" in out.columns else pd.Series("", index=out.index)
    gl = out["gl"].fillna("").astype(str) if "gl" in out.columns else pd.Series("", index=out.index)
    name_stem = host.map(_name_stem)
    missing_name = name_stem.eq("")
    name_stem = name_stem.where(~missing_name, proper.map(_name_stem))
    gl_stem = gl.map(_gl_stem)
    key_names: set[str] = set()
    key_gl: set[str] = set()
    interesting_pos = np.flatnonzero(interesting.to_numpy())
    for pos in interesting_pos:
        stem = name_stem.iloc[pos]
        gstem = gl_stem.iloc[pos]
        if stem:
            key_names.add(stem)
        if gstem:
            key_gl.add(gstem)
    member = interesting.copy()
    if key_names:
        member = member | name_stem.isin(key_names)
    if key_gl:
        member = member | gl_stem.isin(key_gl)
    member_pos = np.flatnonzero(member.to_numpy())
    parent = {int(pos): int(pos) for pos in member_pos}

    def find(pos: int) -> int:
        while parent[pos] != pos:
            parent[pos] = parent[parent[pos]]
            pos = parent[pos]
        return pos

    def union(left: int, right: int) -> None:
        ra, rb = find(left), find(right)
        if ra != rb:
            parent[rb] = ra

    buckets: dict[str, int] = {}
    for pos in member_pos:
        pos = int(pos)
        for prefix, stem in (("name", name_stem.iloc[pos]), ("gl", gl_stem.iloc[pos])):
            if not stem:
                continue
            key = prefix + ":" + stem
            if key in buckets:
                union(pos, buckets[key])
            else:
                buckets[key] = pos
    groups: dict[int, list[int]] = {}
    for pos in member_pos:
        groups.setdefault(find(int(pos)), []).append(int(pos))
    rule = _unstable_rule(criteria)
    columns = list(out.columns)
    for members in groups.values():
        reasons: list[str] = []
        rows = [out.iloc[pos] for pos in members]
        if wants_psr and any(is_pulsar_or_neutron(row) for row in rows):
            reasons.append("psr")
        if wants_unstable:
            strict_group = rule == "strict" and len(members) >= 2
            if strict_group or any(is_unstable_multiple(row, rule) for row in rows):
                reasons.append("unstable")
        if not reasons:
            continue
        text = ",".join(reasons)
        for pos in members:
            labels[pos] = text
    out[SYSTEM_BLOCK] = labels
    del positions, columns
    return out


def host_mask(df: pd.DataFrame) -> pd.Series:
    """Vector form of ``is_exoplanet_host`` for a frame. ``sy_pnum`` is ignored.

    String tokens match ``flag_true`` (``true``, ``yes``, ``y``, ``1``). A numeric
    cell that is not a bool is a host when it is not zero. The string ``1.0`` is
    not a host flag. ``exoplanet_count`` above zero is a host.
    """
    mask = pd.Series(False, index=df.index)
    if "has_known_exoplanets" in df.columns:
        col = df["has_known_exoplanets"]
        if pd.api.types.is_bool_dtype(col):
            flagged = col.fillna(False)
        elif pd.api.types.is_numeric_dtype(col):
            flagged = pd.to_numeric(col, errors="coerce").fillna(0).ne(0)
        else:
            lowered = col.astype(str).str.strip().str.lower()
            text_flag = lowered.isin({"true", "yes", "y", "1"})

            def object_number(value: Any) -> bool:
                if isinstance(value, (bool, str)):
                    return False
                number = as_float(value)
                return number is not None and number != 0.0

            flagged = text_flag | col.map(object_number)
        mask = mask | flagged.fillna(False)
    if "exoplanet_count" in df.columns:
        count = pd.to_numeric(df["exoplanet_count"], errors="coerce")
        mask = mask | count.fillna(0).gt(0)
    return mask.fillna(False)


def meets_gate_criteria(
    row: Mapping[str, Any],
    min_stellar_mass: float = DEFAULT_MIN_STELLAR_MASS,
    max_stellar_mass: float | None = None,
    origin: str = "Sol",
    criteria: Mapping[str, Any] | None = None,
) -> bool:
    """Same acceptance rule as ``network._valid_row`` (mass and coordinates).

    ``criteria`` defaults to None. Optional exclusions then stay off.
    """
    coords = _coords(row)
    if coords is None:
        return False
    host = str(row.get("hostname") or "")
    if coords == (0.0, 0.0, 0.0) and host != origin:
        return False
    if gate_status_for(row) == PENDING_DOUG:
        return False
    mass = as_float(row.get("st_mass"))
    if not is_exoplanet_host(row) and mass is None:
        return False
    if host == origin:
        return True
    if mass is None:
        return True
    if mass < float(min_stellar_mass):
        return False
    if max_stellar_mass is not None and mass > float(max_stellar_mass):
        return False
    if extra_gate_block(row, criteria):
        return False
    return True


def classify_tier(
    row: Mapping[str, Any],
    min_stellar_mass: float = DEFAULT_MIN_STELLAR_MASS,
    max_stellar_mass: float | None = None,
    origin: str = "Sol",
    criteria: Mapping[str, Any] | None = None,
) -> str:
    if not is_exoplanet_host(row):
        return TIER_BACKGROUND
    if meets_gate_criteria(row, min_stellar_mass, max_stellar_mass, origin, criteria):
        return TIER_GATE
    return TIER_EXO


def classify_frame(
    df,
    min_stellar_mass: float = DEFAULT_MIN_STELLAR_MASS,
    max_stellar_mass: float | None = None,
    origin: str = "Sol",
    criteria: Mapping[str, Any] | None = None,
):
    """Return a copy with a ``tier`` column. The input frame is not modified.

    Non-hosts are background without a per-row call. Hosts use ``classify_tier``,
    so the tier matches the row rule. Optional ``criteria`` default to off.
    """
    out = apply_system_blocks(df.copy(), criteria)
    tiers = np.full(len(out), TIER_BACKGROUND, dtype=object)
    mask = host_mask(out)
    if bool(mask.any()):
        records = out.loc[mask].to_dict("records")
        host_tiers = [
            classify_tier(row, min_stellar_mass, max_stellar_mass, origin, criteria)
            for row in records
        ]
        tiers[mask.to_numpy()] = host_tiers
    out["tier"] = tiers
    return out
