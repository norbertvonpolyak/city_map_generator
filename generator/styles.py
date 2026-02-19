from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


# =============================================================================
# ROAD STYLE SYSTEM
# =============================================================================

@dataclass(frozen=True)
class RoadStyle:
    base_width: float
    multipliers: Dict[str, float]


DEFAULT_ROAD_STYLE = RoadStyle(
    base_width=1.2,
    multipliers={
        "minor": 0.6,
        "local": 1.0,
        "arterial": 1.6,
        "highway": 2.4,
    },
)


# =============================================================================
# PALETTE CONFIG
# =============================================================================

@dataclass(frozen=True)
class PaletteConfig:
    background: str
    blocks: Optional[List[str]]   # ← EZ lett Optional
    road: str
    water: str
    road_style: RoadStyle


# =============================================================================
# SHARED COLORS
# =============================================================================

WATER_LIGHT_BLUE = "#a9c9d8"


# =============================================================================
# PALETTES
# =============================================================================

PALETTES: Dict[str, PaletteConfig] = {

    "urban_modern": PaletteConfig(
        background="#D9D5C7",
        blocks=[
            "#E8891C","#D26A1E","#C65A2A",
            "#E2C79F","#F0A21A","#7C7368","#2F2F2F"
        ],
        road="#FFFFFF",
        water="#5F9F9B",
        road_style=RoadStyle(
            base_width=0.8,
            multipliers={
                "highway": 2.4,
                "arterial": 1.8,
                "local": 1.0,
                "minor": 0.6,
            }
        ),
    ),


        "vintage_atlas": PaletteConfig(
        background="#E6D3B3",
        blocks=None,
        road="#5C3D23",
        water="#8FA6AA",
        road_style=RoadStyle(
            base_width=1.0,
            multipliers={
                "minor": 0.5,
                "local": 0.8,
                "arterial": 1.4,
                "highway": 1.9,
            },
        ),
    ),



    # -------------------------------------------------------------------------
    # NEW BLACK MINIMAL (BLOCK-FREE)
    # -------------------------------------------------------------------------

    "black_minimal": PaletteConfig(
        background="#0F0F10",
        blocks=None,
        road="#FFFFFF",
        water="#CFC8B8",
        road_style=RoadStyle (
            base_width=1.4,
            multipliers={
                "minor": 0.35,
                "local": 0.7,
                "arterial": 2.2,
                "highway": 4.0,
            },
        ),

    ),

}


# =============================================================================
# PUBLIC API
# =============================================================================

def get_palette_config(name: str) -> PaletteConfig:
    if name not in PALETTES:
        raise ValueError(
            f"Unknown palette '{name}'. Available: {list(PALETTES.keys())}"
        )
    return PALETTES[name]
