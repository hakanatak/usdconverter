"""JobSpec: the validated, versioned description of a conversion job."""
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class LayerSpec(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    source: Literal["upload", "geojson_url", "arcgis", "wfs", "demo"]
    file: Optional[str] = None          # upload: client file name
    url: Optional[str] = None           # url sources; for demo: roads|buildings|trees
    type_name: Optional[str] = None     # wfs typeName
    where: str = "1=1"                  # arcgis filter
    username: Optional[str] = Field(None, exclude=True, repr=False, max_length=200)
    password: Optional[str] = Field(None, exclude=True, repr=False, max_length=500)
    token: Optional[str] = Field(None, exclude=True, repr=False, max_length=4000)
    source_crs: Optional[str] = None    # override, e.g. "EPSG:3857"
    line_width_m: float = Field(6.0, gt=0, le=500)
    height_m: float = Field(0.0, ge=0, le=2000)
    height_field: Optional[str] = None
    z_field: Optional[str] = None
    z_offset_m: float = Field(0.1, ge=-1000, le=1000)
    point_size_m: float = Field(1.5, gt=0, le=200)
    point_height_m: float = Field(3.0, ge=0, le=500)
    color: str = Field("#9aa5b1", pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("source_crs")
    @classmethod
    def _crs(cls, v):
        if v is not None and not re.fullmatch(r"EPSG:\d{4,6}", v):
            raise ValueError("source_crs must look like EPSG:3857")
        return v


class JobSpec(BaseModel):
    spec_version: Literal[1] = 1
    name: str = Field("Untitled", max_length=100)
    crs_target: str = Field("auto_utm", pattern=r"^(auto_utm|EPSG:\d{4,6})$")
    tile_size_m: float = Field(1000.0, ge=50, le=20000)
    anchor_x: Optional[float] = None   # optional manual anchor, in the target CRS (metres)
    anchor_y: Optional[float] = None
    base_elevation_m: float = Field(0.0, ge=-1000, le=10000)
    layers: list[LayerSpec] = Field(min_length=1, max_length=20)
    outputs_usd: bool = True
    outputs_glb: bool = True

    @model_validator(mode="after")
    def _anchor(self):
        if (self.anchor_x is None) != (self.anchor_y is None):
            raise ValueError("anchor_x and anchor_y must be given together")
        if self.anchor_x is not None and self.crs_target == "auto_utm":
            raise ValueError("a manual anchor needs an explicit EPSG target CRS")
        return self

    @field_validator("layers")
    @classmethod
    def _unique(cls, v):
        names = [l.name for l in v]
        if len(set(names)) != len(names):
            raise ValueError("layer names must be unique")
        return v
