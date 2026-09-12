"""Accept NASA hostname or v3 slug; return the hostname row key."""

from __future__ import annotations

import pandas as pd

from starroute.api.v1.errors import Problem
from starroute.ids import host_id


def resolve_host(token: str, systems: pd.DataFrame, *, instance: str | None = None) -> str:
    if "hostname" not in systems.columns:
        raise Problem(404, "not_found", "No systems catalog", instance=instance)
    names = systems["hostname"].astype(str)
    if (names == token).any():
        return token
    matches = [h for h in names.unique() if host_id(h) == token]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise Problem(409, "id_collision", f"Ambiguous id {token!r}", instance=instance)
    raise Problem(404, "not_found", f"Unknown host {token!r}", instance=instance)
