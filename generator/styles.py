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
    building_edge: str
    building_edge_width: float

    green: str
    green_edge: str
    green_edge_width: float

    water: str
    water_edge: str
    water_edge_width: float

    road: str
    road_style: RoadStyle


@dataclass(frozen=True)
class LineStyleConfig:
    background: str
    road: str
    water: str
    road_style: RoadStyle
    green: str = "#D9DEDE"


# =============================================================================
# STYLE DEFINITIONS
# =============================================================================

STYLES = {

    # -------------------------------------------------------------------------
    # BLOCK
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

    "midnight_ember": BlockStyleConfig(
        background="#F2EEE6",
        block_colors=[
            "#1E252B",  # charcoal
            "#25323A",  # dark slate
            "#31444D",  # blue grey
            "#45606D",  # steel blue
            "#6C8A99",  # light steel
            "#F2A541",  # amber
            "#E4572E",  # ember red
        ],
        road="#D9D3C8",
        water="#0F4C5C",
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


    # -------------------------------------------------------------------------
    # BUILDING ENGINE
    # -------------------------------------------------------------------------

    "midnight_blue": BuildingStyleConfig(
        background="#081519",

        building_colors=[
            "#7EA6D8",
            "#5E88C5",
            "#D8C7A8",
            "#476FAE",
            "#355B95",
            "#192C42",
        ],
        building_edge="#22313F",
        building_edge_width=0.30,

        green="#34513D",
        green_edge="#42584A",
        green_edge_width=0.06,

        water="#081519",
        water_edge="#081519",
        water_edge_width=0.08,

        road="#081519",
        road_style=RoadStyle(
            base_width=3.0,
            multipliers={
                "minor": 1.05,
                "local": 1.75,
                "arterial": 2.7,
                "highway": 4.2,
            },
        ),
    ),

    "architect_sage": BuildingStyleConfig(
        background="#BFD4D0",

        building_colors=[
            "#8EA88A",
            "#78966F",
            "#63835A",
            "#4D6F49",
            "#D6CDB6",
            "#1E2B22",
        ],
        building_edge="#324237",
        building_edge_width=0.30,

        green="#B8C3B6",
        green_edge="#27442F",
        green_edge_width=0.06,

        water="#9DB8B1",
        water_edge="#7F9A93",
        water_edge_width=0.08,

        road="#FFFFFF",
        road_style=RoadStyle(
            base_width=3.0,
            multipliers={
                "minor": 1.05,
                "local": 1.75,
                "arterial": 2.7,
                "highway": 4.2,
            },
        ),
    ),

    "warm_terracotta": BuildingStyleConfig(
        background="#F6E8D7",

        building_colors=[
            "#D77A61",
            "#C76754",
            "#B6594A",
            "#9D473D",
            "#EBC7A8",
            "#3A2A24",
        ],
        building_edge="#5A3E36",
        building_edge_width=0.30,

        green="#B8CFA5",
        green_edge="#6E7E60",
        green_edge_width=0.06,

        water="#C4D9E3",
        water_edge="#607D8A",
        water_edge_width=0.08,

        road="#5A3E36",
        road_style=RoadStyle(
            base_width=3.0,
            multipliers={
                "minor": 1.05,
                "local": 1.75,
                "arterial": 2.7,
                "highway": 4.2,
            },
        ),
    ),

    "mono_black": BuildingStyleConfig(
        background="#F5F5F5",

        building_colors=[
            "#D8D8D8",
            "#BEBEBE",
            "#9F9F9F",
            "#7C7C7C",
            "#EAEAEA",
            "#1A1A1A",
        ],
        building_edge="#3A3A3A",
        building_edge_width=0.30,

        green="#C8C8C8",
        green_edge="#8A8A8A",
        green_edge_width=0.06,

        water="#EFEFEF",
        water_edge="#A5A5A5",
        water_edge_width=0.08,

        road="#3A3A3A",
        road_style=RoadStyle(
            base_width=3.0,
            multipliers={
                "minor": 1.05,
                "local": 1.75,
                "arterial": 2.7,
                "highway": 4.2,
            },
        ),
    ),

    "royal_purple": BuildingStyleConfig(
        background="#1f1e3a",

        building_colors=[
            "#9D78D1",
            "#8660BC",
            "#724EA8",
            "#e4be8d",
            "#DCCBEF",
            "#241A35",
        ],
        building_edge="#45335E",
        building_edge_width=0.30,

        green="#3d3657",
        green_edge="#3d3657",
        green_edge_width=0.06,

        water="#1f1e3a",
        water_edge="#1f1e3a",
        water_edge_width=0.08,

        road="#1f1e3a",
        road_style=RoadStyle(
            base_width=3.0,
            multipliers={
                "minor": 1.05,
                "local": 1.75,
                "arterial": 2.7,
                "highway": 4.2,
            },
        ),
    ),

    "sandstone_beige": BuildingStyleConfig(
        background="#F7F1E8",

        building_colors=[
            "#D8C4A5",
            "#C8B18F",
            "#B69E79",
            "#A28A64",
            "#ECE2D4",
            "#4B4035",
        ],
        building_edge="#6B5A48",
        building_edge_width=0.30,

        green="#8B9B82",
        green_edge="#56604E",
        green_edge_width=0.06,

        water="#D9E5EB",
        water_edge="#7A8D97",
        water_edge_width=0.08,

        road="#6B5A48",
        road_style=RoadStyle(
            base_width=1.785,
            multipliers={
                "minor": 1.05,
                "local": 1.75,
                "arterial": 2.7,
                "highway": 4.2,
            },
        ),
    ),

    "luxury_gold": BuildingStyleConfig(
        background="#111111",

        building_colors=[
            "#D8B25A",
            "#C79C44",
            "#B58630",
            "#9D7122",
            "#F0D89B",
            "#F7E7B6",
        ],
        building_edge="#3D2D12",
        building_edge_width=0.30,

        green="#8A815B",
        green_edge="#4C4730",
        green_edge_width=0.06,

        water="#4E5C6A",
        water_edge="#8896A3",
        water_edge_width=0.08,

        road="#F0D89B",
        road_style=RoadStyle(
            base_width=3.0,
            multipliers={
                "minor": 1.05,
                "local": 1.75,
                "arterial": 2.7,
                "highway": 4.2,
            },
        ),
    ),

    # -------------------------------------------------------------------------
    # LINE ENGINE
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

    "nordic_teal": LineStyleConfig(
        background="#EFF2F2",
        road="#242B2F",
        water="#78959D",
        road_style=RoadStyle(
            base_width=1.4,
            multipliers={
                "minor": 0.35,
                "local": 0.7,
                "arterial": 2.2,
                "highway": 4.0,
            },
        ),
        green="#D7DBDB",
    ),

    "blueprint": LineStyleConfig(
        background="#0D1B2A",
        road="#E0E1DD",
        water="#415A77",
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

    "desert_sand": LineStyleConfig(
        background="#F2E9DC",
        road="#3E3A36",
        water="#6B8FA3",
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

    "ivory_bw": LineStyleConfig(
        background="#FAF8F3",
        road="#161616",
        water="#D9D9D9",
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