"""``jumpgate.setting.v1`` — collaboration unit and reality-slider SoT."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CatalogRef(BaseModel):
    planets_snapshot: Optional[str] = None
    hosts_snapshot: Optional[str] = None


class ChronosLink(BaseModel):
    campaign_id: Optional[str] = None
    base_url: Optional[str] = None
    gate_simultaneity: bool = True
    gate_handling_seconds: float = 0.0


class SettingDocument(BaseModel):
    schema_name: str = Field(default="jumpgate.setting.v1", alias="schema")
    id: str
    title: Optional[str] = None
    etag: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: str = "jumpgate"
    reality: int = 0
    origin_hostname: str = "Sol"
    catalog: CatalogRef = Field(default_factory=CatalogRef)
    network_id: Optional[str] = None
    chronos: ChronosLink = Field(default_factory=ChronosLink)
    owners: List[str] = Field(default_factory=lambda: ["jumpgate"])

    model_config = {"populate_by_name": True}
