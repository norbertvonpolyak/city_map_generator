from pathlib import Path

from generator.engines.render_block import render_map_block
from generator.engines.render_building import render_map_building
from generator.engines.render_line import render_map_line

from generator.specs import ProductSpec
from generator.core.style_registry import STYLE_REGISTRY, EngineType, ENGINE_LAYOUT_MAP


def render_product(
    *,
    style_name: str,
    center_lat: float,
    center_lon: float,
    spec: ProductSpec,
    output_dir: Path,
    title: str,
    subtitle: str,
):

    if style_name not in STYLE_REGISTRY:
        raise ValueError(f"Unknown style: {style_name}")

    style_def = STYLE_REGISTRY[style_name]

    # ---------------------------------------------------------
    # ENGINE DISPATCH
    # ---------------------------------------------------------

    if style_def.engine == EngineType.BLOCK:

        map_result = render_map_block(
            center_lat=center_lat,
            center_lon=center_lon,
            spec=spec,
            output_dir=output_dir,
            palette_name=style_name,
        )

    elif style_def.engine == EngineType.BUILDING:

        map_result = render_map_building(
            center_lat=center_lat,
            center_lon=center_lon,
            spec=spec,
            output_dir=output_dir,
            palette_name=style_name,
        )

    elif style_def.engine == EngineType.LINE:

        map_result = render_map_line(
            center_lat=center_lat,
            center_lon=center_lon,
            spec=spec,
            output_dir=output_dir,
            palette_name=style_name,
        )

    else:
        raise RuntimeError("Invalid engine type")

    map_svg_path = map_result.output_svg

    # ---------------------------------------------------------
    # LAYOUT DISPATCH
    # ---------------------------------------------------------

    layout_func = ENGINE_LAYOUT_MAP[style_def.engine]

    final_pdf_path = layout_func(
        spec=spec,
        map_svg_path=map_svg_path,
        output_dir=output_dir,
        size_key=f"{spec.width_cm}x{spec.height_cm}",
        title=title,
        subtitle=subtitle,
        palette_name=style_name,
    )

    return final_pdf_path