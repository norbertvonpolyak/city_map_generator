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


# =============================================================================
# ENGINE-SPECIFIC STYLE CONFIGS
# =============================================================================

@dataclass(frozen=True)
class BlockStyleConfig:
    background: str
    block_colors: List[str]
    road: str
    water: str
    road_style: RoadStyle


@dataclass(frozen=True)
class BuildingStyleConfig:
    background: str
    building_colors: List[str]
    road: str
    water: str
    road_style: RoadStyle


@dataclass(frozen=True)
class LineStyleConfig:
    background: str
    road: str
    water: str
    road_style: RoadStyle


# =============================================================================
# STYLE DEFINITIONS
# =============================================================================

STYLES = {

    # -------------------------------------------------------------------------
    # BLOCK-BASED
    # -------------------------------------------------------------------------

    "urban_modern": BlockStyleConfig(
        background="#D9D5C7",
        block_colors=[
            "#E8891C", "#D26A1E", "#C65A2A",
            "#E2C79F", "#F0A21A", "#7C7368", "#2F2F2F"
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
            },
        ),
    ),

    # -------------------------------------------------------------------------
    # BUILDING-BASED
    # -------------------------------------------------------------------------

    "vintage_atlas": BuildingStyleConfig(
        background="#E6D3B3",
        building_colors=[
            "#C9B28F",
            "#BFA37C",
            "#D7C2A4",
            "#A88F6C",
        ],
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

    "pretty_buildings": BuildingStyleConfig(
        background="#F4F1EB",
        building_colors=[
            "#E8891C",
            "#D26A1E",
            "#C65A2A",
            "#F0A21A",
        ],
        road="#2F2F2F",
        water="#9BBCC8",
        road_style=RoadStyle(
            base_width=1.2,
            multipliers={
                "minor": 0.6,
                "local": 1.0,
                "arterial": 1.8,
                "highway": 2.6,
            },
        ),
    ),

    # -------------------------------------------------------------------------
    # LINE-BASED
    # -------------------------------------------------------------------------

    "bw_minimal": LineStyleConfig(
        background="#0F0F10",
        road="#FFFFFF",
        water="#CFC8B8",
        road_style=RoadStyle(
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

def get_style_config(name: str):
    if name not in STYLES:
        raise ValueError(
            f"Unknown style '{name}'. Available: {list(STYLES.keys())}"
        )
    return STYLES[name]