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
        road="#EFEBDD",
        water="#5F9F9B",
        road_style=RoadStyle(
            base_width=3.3,
            multipliers={
                "highway": 2.4,
                "arterial": 1.8,
                "local": 1.0,
                "minor": 0.6,
            },
        ),
    ),

    "minimal_sand": BlockStyleConfig(
        background="#E9E4DA",
        block_colors=[
            "#F2EEE6",
            "#E1DBCF",
            "#CFC6B6",
            "#B8AEA0",
            "#9C9286",
            "#6E6A63",
            "#2C2C2C",
        ],
        road="#FFFFFF",
        water="#BFD1D6",
        road_style=RoadStyle(
            base_width=0.8,
            multipliers={
                "highway": 3.0,
                "arterial": 2.0,
                "local": 1.0,
                "minor": 0.45,
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
            "#F29F1F",  # élénk, de nem neon
            "#E27A1F",  # meleg mid
            "#C65A2A",  # mély terrakotta
            "#D9BB8F",  # sötétített homok
            "#F4B942",  # világos akcent
            "#2F2F2F",  # ritka kontraszt
        ],
        road="#F4EFE6",
        water="#CFE3EC",
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