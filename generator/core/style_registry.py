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
    "urban_modern": StyleDefinition(
        engine=EngineType.BLOCK,
    ),

    "vintage_atlas": StyleDefinition(
        engine=EngineType.BUILDING,
    ),

    "pretty_buildings": StyleDefinition(
        engine=EngineType.BUILDING,
    ),

    "bw_minimal": StyleDefinition(
        engine=EngineType.LINE,
    ),
}