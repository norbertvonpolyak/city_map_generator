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


@dataclass(frozen=True)
class MaptoposterLineRenderConfig:
    background: str
    text: str
    water: str
    parks: str
    road_colors: Dict[str, str]
    road_widths: Dict[str, float]


@dataclass(frozen=True)
class MaptoposterLineLayoutConfig:
    uniform_margins: bool = True
    bottom_margin_ratio: float | None = None
    passepartout_color: str = "#F6F3EE"
    bottom_fade_color: str = "#F6F3EE"
    title_color: str = "#1C1C1C"
    subtitle_color: str = "#1C1C1C"
    coordinates_color: str = "#1C1C1C"
    custom_text_color: str = "#1C1C1C"
    title_font_family: str = "Montserrat-Bold"
    subtitle_font_family: str = "Montserrat-Medium"
    body_font_family: str = "Montserrat-Medium"
    bottom_fade: bool = False
    center_title: bool = False


@dataclass(frozen=True)
class MaptoposterLineStyleConfig:
    render: MaptoposterLineRenderConfig
    layout: MaptoposterLineLayoutConfig


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

    "mp_terracotta": MaptoposterLineStyleConfig(
        render=MaptoposterLineRenderConfig(
            background="#F5EDE4",
            text="#8B4513",
            water="#A8C4C4",
            parks="#DBD3C3",
            road_colors={
                "motorway": "#86472A",
                "trunk": "#A0522D",
                "primary": "#A0522D",
                "secondary": "#A0522D",
                "tertiary": "#D9A08A",
                "residential": "#E5C4B0",
                "default": "#9E9D9D",
            },
            road_widths={
                "motorway": 3.2,
                "trunk": 3.0,
                "primary": 3.0,
                "secondary": 3.0,
                "tertiary": 2.15,
                "residential": 1.2,
                "default": 0.90,
            },
        ),
        layout=MaptoposterLineLayoutConfig(
            uniform_margins=True,
            passepartout_color="#F6F3EE",
            bottom_fade_color="#F6F3EE",
            title_color="#8B4513",
            subtitle_color="#8B4513",
            coordinates_color="#8B4513",
            custom_text_color="#8B4513",
        ),
    ),

    "mp_noir": MaptoposterLineStyleConfig(
        render=MaptoposterLineRenderConfig(
            background="#000000",
            text="#FFFFFF",
            water="#0A0A0A",
            parks="#111111",
            road_colors={
                "motorway": "#E6E6E6",
                "trunk": "#E6E6E6",
                "primary": "#E6E6E6",
                "secondary": "#E9E9E9",
                "tertiary": "#808080",
                "residential": "#505050",
                "default": "#808080",
            },
            road_widths={
                "motorway": 3.2,
                "trunk": 3.0,
                "primary": 3.0,
                "secondary": 3.0,
                "tertiary": 2.15,
                "residential": 1.2,
                "default": 0.90,
            },
        ),
        layout=MaptoposterLineLayoutConfig(
            uniform_margins=True,
            passepartout_color="#101010",
            bottom_fade_color="#000000",
            title_color="#FFFFFF",
            subtitle_color="#FFFFFF",
            coordinates_color="#FFFFFF",
            custom_text_color="#FFFFFF",
        ),
    ),

    "mp_blueprint": MaptoposterLineStyleConfig(
        render=MaptoposterLineRenderConfig(
            background="#1A3A5C",
            text="#E8F4FF",
            water="#0F2840",
            parks="#1E4570",
            road_colors={
                "motorway": "#E8F4FF",
                "trunk": "#E8F4FF",
                "primary": "#E8F4FF",
                "secondary": "#9FC5E8",
                "tertiary": "#7BAED4",
                "residential": "#5A96C0",
                "default": "#7BAED4",
            },
            road_widths={
                "motorway": 3.2,
                "trunk": 3.0,
                "primary": 3.0,
                "secondary": 3.0,
                "tertiary": 2.15,
                "residential": 1.2,
                "default": 0.90,
            },
        ),
        layout=MaptoposterLineLayoutConfig(
            uniform_margins=True,
            passepartout_color="#1A3A5C",
            bottom_fade_color="#1A3A5C",
            title_color="#E8F4FF",
            subtitle_color="#E8F4FF",
            coordinates_color="#E8F4FF",
            custom_text_color="#E8F4FF",
        ),
    ),

    "mp_black_white": MaptoposterLineStyleConfig(
        render=MaptoposterLineRenderConfig(
            background="#FFFFFF",
            text="#2C2C2C",
            water="#D1D1D1",
            parks="#ECECEC",
            road_colors={
                "motorway": "#535353",
                "trunk": "#535353",
                "primary": "#535353",
                "secondary": "#535353",
                "tertiary": "#A0A0A0",
                "residential": "#C6C6C6",
                "default": "#DDDDDD",
            },
            road_widths={
                "motorway": 3.2,
                "trunk": 3.0,
                "primary": 3.0,
                "secondary": 3.0,
                "tertiary": 2.15,
                "residential": 1.2,
                "default": 0.90,
            },
        ),
        layout=MaptoposterLineLayoutConfig(
            uniform_margins=True,
            passepartout_color="#FFFFFF",
            bottom_fade_color="#FFFFFF",
            title_color="#2C2C2C",
            subtitle_color="#2C2C2C",
            coordinates_color="#2C2C2C",
            custom_text_color="#2C2C2C",
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