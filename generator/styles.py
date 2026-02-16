from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


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
    blocks: List[str]
    road: str
    water: str
    road_style: RoadStyle


# =============================================================================
# SHARED COLORS
# =============================================================================

WATER_LIGHT_BLUE = "#a9c9d8"
WATER_LIGHT_BLUE_EDGE = "#a9c9d8"


# =============================================================================
# PALETTES
# =============================================================================

PALETTES: Dict[str, PaletteConfig] = {

    "warm": PaletteConfig(
        background="#e6e0cf",
        blocks=["#e28c41","#cd6d40","#e7b573","#e39f55","#c86a3d","#b55a3a","#9b4d37"],
        road="#ffffff",
        water="#5BA29D",
        road_style=DEFAULT_ROAD_STYLE
    ),

    "urban_modern": PaletteConfig(
        background="#D9D5C7",
        blocks=["#E8891C","#D26A1E","#C65A2A","#E2C79F","#F0A21A","#7C7368","#2F2F2F"],
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

    "amber_district": PaletteConfig(
        background="#e8e2d2",
        blocks=["#2f2f33","#4a4a4a","#8c7a5b","#b89b5e","#d4b35f","#e2cfa4","#c76a3a"],
        road="#ffffff",
        water="#5BA29D",
        road_style=DEFAULT_ROAD_STYLE,
    ),

    "white_minimal": PaletteConfig(
        background="#f8f8f8",
        blocks=["#ffffff"] * 7,
        road="#2a2a2a",
        water=WATER_LIGHT_BLUE,
        road_style=RoadStyle(
            base_width=1.3,
            multipliers={
                "minor": 0.7,
                "local": 1.0,
                "arterial": 1.8,
                "highway": 2.8,
            },
        ),
    ),

    "black_minimal": PaletteConfig(
        background="#000000",
        blocks=["#000000"] * 7,
        road="#ffffff",
        water=WATER_LIGHT_BLUE,
        road_style=RoadStyle(
            base_width=1.3,
            multipliers={
                "minor": 0.7,
                "local": 1.0,
                "arterial": 1.8,
                "highway": 2.8,
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
