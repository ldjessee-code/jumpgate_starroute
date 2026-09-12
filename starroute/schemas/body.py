"""``jumpgate.body.v1`` — L2 only (no climate / visitability)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from starroute.schemas.system import SourceRef


class BodyDocument(BaseModel):
    schema_name: str = Field(default="jumpgate.body.v1", alias="schema")
    layer: str = "L2"
    id: str
    host_id: str
    pl_name: Optional[str] = None
    source: SourceRef = Field(default_factory=SourceRef)
    pl_letter: Optional[str] = None
    pl_bmasse: Optional[float] = None
    pl_rade: Optional[float] = None
    pl_eqt: Optional[float] = None
    pl_orbsmax: Optional[float] = None
    class_guess: Optional[str] = None
    role: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    g_earth_max: Optional[float] = None
    worldstack_url: Optional[str] = None

    model_config = {"populate_by_name": True}
