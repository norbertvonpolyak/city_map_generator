from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Any


# =============================================================================
# SIMPLE STYLE (nem-monochrome, legacy / blocks render)
# =============================================================================

@dataclass(frozen=True)
class Style:
    background: str
    road: str
    bridge: str
    water: str


DEFAULT_STYLE = Style(
    background="#e0dbc8",
    road="#ffffff",
    bridge="#d0d0d0",
    water="#ffffff",
)


# =============================================================================
# COLOR PALETTES (polygonize-based city blocks)
# =============================================================================
# FONTOS: világostól sötét felé rendezve

PALETTES: Dict[str, List[str]] = {
    "warm":             ["#e28c41","#cd6d40","#e7b573","#e39f55","#9dc6b4","#6f6b5e","#e2bf98"],
    "vivid_city":       ["#FFFD82","#969765","#1B998B","#246569","#FF9B71","#E84855","#2D3047"],
    "amber_dusk":       ["#EBC775","#FFA630","#9CB48F","#6D9790","#3E7990","#2E5077","#483656"],
    "sunset_noir":      ["#FFBA49","#A4A9AD","#887F7D","#20A39E","#EF5B5B","#892E3D","#23001E"],
    "coastal_modern":   ["#EDE6E3","#DADAD9","#EFA596","#5BC3EB","#497E8D","#F06449","#36382E"],
    "urban_gold":       ["#DFD5BB","#D9C590","#D3B566","#CCA43B","#786A3E","#534F3D","#2D333B"],
}

def get_palette(name: str) -> List[str]:
    try:
        return PALETTES[name]
    except KeyError as e:
        raise ValueError(
            f"Ismeretlen paletta: {name}. "
            f"Választható: {list(PALETTES.keys())}"
        ) from e


# =============================================================================
# MONOCHROME STYLE (PRETTY RENDER – SOURCE OF TRUTH)
# =============================================================================

@dataclass
class MonoStyle:
    # -------------------------------------------------------------------------
    # background / base
    # -------------------------------------------------------------------------
    background: str = "#f7f7f7"

    # -------------------------------------------------------------------------
    # landuse / parks
    # -------------------------------------------------------------------------
    land_fill: str = "#ffffff"
    park_fill: str = "#ededed"
    industrial_fill: str = "#e2e2e2"

    # -------------------------------------------------------------------------
    # water (MINDEN víz fehér – river / lake / sea)
    # -------------------------------------------------------------------------
    water_fill: str = "#ffffff"
    water_edge: str = "#000000"

    # -------------------------------------------------------------------------
    # buildings
    # -------------------------------------------------------------------------
    buildings_fill: str = "#dcdcdc"

    # -------------------------------------------------------------------------
    # rail
    # -------------------------------------------------------------------------
    rail_color: str = "#9a9a9a"

    # -------------------------------------------------------------------------
    # roads (two-pass drawing)
    # -------------------------------------------------------------------------
    highway_fill: str = "#111111"
    highway_stroke: str = "#9c9c9c"

    arterial_fill: str = "#111111"
    arterial_stroke: str = "#9c9c9c"

    local_fill: str = "#111111"
    local_stroke: str = "#9c9c9c"

    minor_fill: str = "#111111"
    minor_stroke: str = "#9c9c9c"

    # -------------------------------------------------------------------------
    # road drawing behavior
    # -------------------------------------------------------------------------
    stroke_mult: float = 1.45

    highway_stroke_enabled: bool = False
    arterial_stroke_enabled: bool = False
    local_stroke_enabled: bool = True
    minor_stroke_enabled: bool = True

    # -------------------------------------------------------------------------
    # linewidth master controls
    # -------------------------------------------------------------------------
    road_width: float = 1.25
    road_boost: float = 1.0

    # -------------------------------------------------------------------------
    # class-specific multipliers
    # -------------------------------------------------------------------------
    lw_highway_mult: float = 3.10
    lw_arterial_mult: float = 2.25
    lw_local_mult: float = 1.35
    lw_minor_mult: float = 0.95

    # -------------------------------------------------------------------------
    # helpers
    # -------------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# DEFAULT INSTANCE (használat: style = DEFAULT_MONO)
# =============================================================================

DEFAULT_MONO = MonoStyle()

MONO_PRESETS = {
    "default": DEFAULT_MONO,
    "snazzy_bw_blackwater": DEFAULT_MONO,  # alias a régi névre
}
