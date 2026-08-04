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
    background_texture_path: str | None = None
    background_texture_opacity: float = 0.0


@dataclass(frozen=True)
class MaptoposterLineLayoutConfig:
    uniform_margins: bool = True
    bottom_margin_ratio: float | None = None
    passepartout_color: str = "#F6F3EE"
    passepartout_opacity: float = 1.0
    bottom_fade_color: str = "#F6F3EE"
    title_color: str = "#1C1C1C"
    subtitle_color: str = "#1C1C1C"
    coordinates_color: str = "#1C1C1C"
    custom_text_color: str = "#1C1C1C"
    title_font_family: str = "Montserrat-Bold"
    subtitle_font_family: str = "Montserrat-Medium"
    body_font_family: str = "Montserrat-Medium"
    coordinates_font_family: str = "Montserrat-Medium"
    bottom_fade: bool = False
    center_title: bool = False
    inner_border_color: str | None = None
    inner_border_width_px: float = 0.0
    title_letter_spacing_pt: float = 0.0
    coordinates_letter_spacing_pt: float = 0.0
    # Vintage Atlas specific layout parameters
    side_margin_ratio: float = 0.04  # side margin as ratio of short side
    bottom_margin_multiplier: float = 1.0  # bottom margin = side_margin * this multiplier
    text_vertical_centering: bool = False  # vertically center text block in bottom margin
    title_above_coordinates: bool = False  # title placed above coordinates (not subtitle)


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

    "minimal_sand": BlockStyleConfig(
        background="#F3E9D7",
        block_colors=[
            "#D8C3A5",
            "#C9AE8A",
            "#B7926B",
            "#E7D8BF",
            "#A67C52",
            "#8D6E63",
            "#5D4E37",
        ],
        road="#FCF7ED",
        water="#9FC7C1",
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
            base_width=0.8925,
            multipliers={
                "minor": 1.05,
                "local": 1.35,
                "arterial": 2.3,
                "highway": 3.4,
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

    "mp_noir_gold": MaptoposterLineStyleConfig(
        render=MaptoposterLineRenderConfig(
            background="#000000",
            text="#FFFFFF",
            water="#5C5C5C",
            parks="#272727",
            road_colors={
                "motorway": "#BB9F02",      # bright gold
                "trunk": "#BB9F02",         # gold, slightly darker
                "primary": "#DD9F01",       # gold, darker
                "secondary": "#E6B800",     # darker gold
                "tertiary": "#9C9C7E",      # even darker gold
                "residential": "#817F78",   # dark gold
                "default": "#999B8F",       # very dark gold/bronze
            },
            road_widths={
                "motorway": 5.2,
                "trunk": 4.0,
                "primary": 4.0,
                "secondary": 3.7,
                "tertiary": 3.15,
                "residential": 1.5,
                "default": 1.2,
            },
        ),
        layout=MaptoposterLineLayoutConfig(
            uniform_margins=True,
            passepartout_color="#101010",
            bottom_fade_color="#000000",
            title_color="#FFD700",         # gold text
            subtitle_color="#FFD700",      # gold subtitle
            coordinates_color="#FFD700",   # gold coordinates
            custom_text_color="#FFD700",   # gold custom text
        ),
    ),

    "vintage_atlas": MaptoposterLineStyleConfig(
        render=MaptoposterLineRenderConfig(
            background="#FCFCFB32",
            text="#2B2A2A",

            water="#EFEFEF",
            parks="#7D756D",

            road_colors={
                "motorway": "#3B3B3B",
                "trunk": "#4A4A4A",
                "primary": "#4A4A4A",
                "secondary": "#4A4A4A",
                "tertiary": "#4A4A4A",
                "residential": "#838282",
                "default": "#838282",
            },

            road_widths={
                "motorway": 5.0,
                "trunk": 4.0,
                "primary": 3.3,
                "secondary": 2.6,
                "tertiary": 1.8,
                "residential": 1.1,
                "default": 0.8,
            },
            background_texture_path="assets/textures/mp_black_white_paper.jpg",
            background_texture_opacity=0.6,
        ),
        layout=MaptoposterLineLayoutConfig(
            uniform_margins=True,
            side_margin_ratio=0.04,
            bottom_margin_multiplier=2.5,
            text_vertical_centering=True,
            title_above_coordinates=True,
            passepartout_color="#FFFFFF",
            passepartout_opacity=0.0,
            bottom_fade_color="#FFFFFF",
            title_color="#2C2C2C",
            subtitle_color="#2C2C2C",
            coordinates_color="#2C2C2C",
            custom_text_color="#2C2C2C",
            title_font_family="Cormorant Garamond",
            coordinates_font_family="Arsenal",
            center_title=True,
            title_letter_spacing_pt=2.0,
            coordinates_letter_spacing_pt=1.0,
            inner_border_color="#8B6B4A",
            inner_border_width_px=4.0,
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