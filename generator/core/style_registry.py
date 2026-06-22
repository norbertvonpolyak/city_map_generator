from dataclasses import dataclass
from enum import Enum


class EngineType(str, Enum):
    BLOCK = "block"
    BUILDING = "building"
    LINE = "line"


@dataclass(frozen=True)
class StyleDefinition:
    engine: EngineType


from generator.layouts.layout_block import compose_layout_block
from generator.layouts.layout_building import compose_layout_building
from generator.layouts.layout_line import compose_layout_line


ENGINE_LAYOUT_MAP = {
    EngineType.BLOCK: compose_layout_block,
    EngineType.BUILDING: compose_layout_building,
    EngineType.LINE: compose_layout_line,
}


STYLE_REGISTRY = {
    # ---------------------------------------------------------
    # BLOCK ENGINE STYLES
    # ---------------------------------------------------------

    "urban_modern": StyleDefinition(
        engine=EngineType.BLOCK,
    ),

    "midnight_ember": StyleDefinition(
        engine=EngineType.BLOCK,
    ),

    "minimal_sand": StyleDefinition(
        engine=EngineType.BLOCK,
    ),

    # ---------------------------------------------------------
    # BUILDING ENGINE STYLES
    # ---------------------------------------------------------

    "midnight_blue": StyleDefinition(
        engine=EngineType.BUILDING,
    ),

    "architect_sage": StyleDefinition(
        engine=EngineType.BUILDING,
    ),

    "warm_terracotta": StyleDefinition(
        engine=EngineType.BUILDING,
    ),

    "mono_black": StyleDefinition(
        engine=EngineType.BUILDING,
    ),

    "royal_purple": StyleDefinition(
        engine=EngineType.BUILDING,
    ),

    "sandstone_beige": StyleDefinition(
        engine=EngineType.BUILDING,
    ),

    "luxury_gold": StyleDefinition(
        engine=EngineType.BUILDING,
    ),

    # ---------------------------------------------------------
    # LINE ENGINE STYLES
    # ---------------------------------------------------------

    "bw_minimal": StyleDefinition(
        engine=EngineType.LINE,
    ),

    "nordic_teal": StyleDefinition(
        engine=EngineType.LINE,
    ),

    "blueprint": StyleDefinition(
        engine=EngineType.LINE,
    ),

    "desert_sand": StyleDefinition(
        engine=EngineType.LINE,
    ),

    "ivory_bw": StyleDefinition(
        engine=EngineType.LINE,
    ),
}