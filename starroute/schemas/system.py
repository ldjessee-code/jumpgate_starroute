"""``jumpgate.system.v1`` — L0+L1 envelope plus L2 body id list."""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    kind: str = "nasa"
    snapshot: Optional[str] = None
    manual_entry: bool = False


class StarCard(BaseModel):
    st_spectype: Optional[str] = None
    st_teff: Optional[float] = None
    st_mass: Optional[float] = None
    st_rad: Optional[float] = None
    st_lum: Optional[float] = None
    st_age: Optional[float] = None
    st_rotp: Optional[float] = None
    st_met: Optional[float] = None
    sy_snum: Optional[float] = None
    cb_flag: Optional[int] = None


class CoordCard(BaseModel):
    ra: Optional[float] = None
    dec: Optional[float] = None
    sy_dist_pc: Optional[float] = None
    distance_from_sol_ly: Optional[float] = None
    xyz_ly: List[Optional[float]] = Field(default_factory=lambda: [None, None, None])
    origin_hostname: Optional[str] = None


class FlagCard(BaseModel):
    rocky_count: Optional[int] = None
    gas_giant_count: Optional[int] = None
    ice_giant_count: Optional[int] = None
    stability_score: Optional[int] = None


class JumpNodeStub(BaseModel):
    id: str
    kind: str = "gate"
    site: str = "star"
    flavor: str = "gate"


class SystemDocument(BaseModel):
    schema_name: str = Field(default="jumpgate.system.v1", alias="schema")
    layer: List[str] = Field(default_factory=lambda: ["L0", "L1", "L2"])
    id: str
    hostname: str
    setting_id: Optional[str] = None
    source: SourceRef = Field(default_factory=SourceRef)
    star: StarCard = Field(default_factory=StarCard)
    coords: CoordCard = Field(default_factory=CoordCard)
    flags: FlagCard = Field(default_factory=FlagCard)
    bodies: List[str] = Field(default_factory=list)
    jump_nodes: List[JumpNodeStub] = Field(default_factory=list)
    roles_stub: List[Any] = Field(default_factory=list)
    overrides: List[Any] = Field(default_factory=list)
    hazards: List[str] = Field(default_factory=list)
    worldstack_url: Optional[str] = None

    model_config = {"populate_by_name": True}
