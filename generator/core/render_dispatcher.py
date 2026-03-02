from pathlib import Path
from datetime import datetime

from generator.engines.render_block import render_map_block
from generator.engines.render_building import render_map_building
from generator.engines.render_line import render_map_line

from generator.specs import ProductSpec
from generator.core.style_registry import STYLE_REGISTRY, EngineType, ENGINE_LAYOUT_MAP


# ==========================================================
# FILE NAME GENERATOR
# ==========================================================

def _generate_preview_filename(style: str, spec: ProductSpec) -> str:
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    size_key = f"{spec.width_cm}x{spec.height_cm}"
    return f"{style}_{size_key}_{timestamp}.png"


def _generate_order_filename(order_id: str, spec: ProductSpec) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    size_key = f"{spec.width_cm}x{spec.height_cm}"
    return f"{order_id}_{size_key}_{timestamp}.pdf"


# ==========================================================
# MAIN DISPATCHER
# ==========================================================

def render_product(
    *,
    style_name: str,
    center_lat: float,
    center_lon: float,
    spec: ProductSpec,
    output_dir: Path,
    title: str,
    subtitle: str,
    preview_mode: bool = False,
    order_id: str | None = None,
):

    if style_name not in STYLE_REGISTRY:
        raise ValueError(f"Unknown style: {style_name}")

    style_def = STYLE_REGISTRY[style_name]

    output_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # FILE NAMING
    # ---------------------------------------------------------

    if preview_mode:
        filename = _generate_preview_filename(style_name, spec)
    else:
        if not order_id:
            raise ValueError("order_id required for print mode")
        filename = _generate_order_filename(order_id, spec)

    filename_prefix = filename.replace(".png", "").replace(".pdf", "")

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
            preview_mode=preview_mode,
            filename_prefix=filename_prefix,
        )

    elif style_def.engine == EngineType.BUILDING:

        map_result = render_map_building(
            center_lat=center_lat,
            center_lon=center_lon,
            spec=spec,
            output_dir=output_dir,
            palette_name=style_name,
            preview_mode=preview_mode,
            filename_prefix=filename_prefix,
        )

    elif style_def.engine == EngineType.LINE:

        map_result = render_map_line(
            center_lat=center_lat,
            center_lon=center_lon,
            spec=spec,
            output_dir=output_dir,
            palette_name=style_name,
            preview_mode=preview_mode,
            filename_prefix=filename_prefix,
        )

    else:
        raise RuntimeError("Invalid engine type")

    map_output_path = map_result.output_svg

    # ---------------------------------------------------------
    # PREVIEW → RETURN PNG
    # ---------------------------------------------------------

    if preview_mode:
        return map_output_path

    # ---------------------------------------------------------
    # PRINT → LAYOUT → PDF
    # ---------------------------------------------------------

    layout_func = ENGINE_LAYOUT_MAP[style_def.engine]

    final_pdf_path = layout_func(
        spec=spec,
        map_svg_path=map_output_path,
        output_dir=output_dir,
        size_key=f"{spec.width_cm}x{spec.height_cm}",
        title=title,
        subtitle=subtitle,
        palette_name=style_name,
        filename_prefix=filename_prefix,
    )

    return final_pdf_path