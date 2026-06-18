from pathlib import Path
from datetime import datetime

from generator.engines.render_block import render_map_block
from generator.engines.render_building import render_map_building
from generator.engines.render_line import render_map_line

from generator.specs import ProductSpec
from generator.layouts.layout_utils import build_poster_layout, compose_poster_outputs, PosterTheme, PosterCompositionResult
from generator.core.style_registry import STYLE_REGISTRY, EngineType
from generator.styles import get_style_config, BlockStyleConfig, BuildingStyleConfig, LineStyleConfig
from uuid import uuid4

# ==========================================================
# FILE NAME GENERATOR
# ==========================================================

def _generate_preview_filename(style: str, spec: ProductSpec) -> str:


    timestamp = datetime.now ().strftime ("%Y%m%d_%H%M%S")
    unique = uuid4 ().hex [:6]
    size_key = f"{spec.width_cm}x{spec.height_cm}"
    return f"{size_key}_{timestamp}_{unique}.png"


def _generate_order_filename(order_id: str, spec: ProductSpec) -> str:
    timestamp = datetime.now ().strftime ("%Y%m%d_%H%M%S")
    unique = uuid4 ().hex [:6]
    size_key = f"{spec.width_cm}x{spec.height_cm}"
    return f"{order_id}_{size_key}_{timestamp}_{unique}.pdf"


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
    use_cache: bool = True,
    output_png_path: Path | None = None,
):

    if style_name not in STYLE_REGISTRY:
        raise ValueError(f"Unknown style: {style_name}")

    style_def = STYLE_REGISTRY[style_name]
    style_cfg = get_style_config(style_name)
    layout = build_poster_layout(spec.width_cm, spec.height_cm)
    viewport_half_width_m, viewport_half_height_m = layout.map_viewport_half_sizes_m(spec.extent_m)

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
            map_width_cm=layout.visible_width_cm,
            map_height_cm=layout.visible_height_cm,
            viewport_half_width_m=viewport_half_width_m,
            viewport_half_height_m=viewport_half_height_m,
            output_dir=output_dir,
            palette_name=style_name,
            preview_mode=preview_mode,
            filename_prefix=filename_prefix,
            use_cache=use_cache,
            output_png_path=output_png_path,
        )

    elif style_def.engine == EngineType.BUILDING:

        map_result = render_map_building(
            center_lat=center_lat,
            center_lon=center_lon,
            spec=spec,
            map_width_cm=layout.visible_width_cm,
            map_height_cm=layout.visible_height_cm,
            viewport_half_width_m=viewport_half_width_m,
            viewport_half_height_m=viewport_half_height_m,
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
            map_width_cm=layout.visible_width_cm,
            map_height_cm=layout.visible_height_cm,
            viewport_half_width_m=viewport_half_width_m,
            viewport_half_height_m=viewport_half_height_m,
            output_dir=output_dir,
            palette_name=style_name,
            preview_mode=preview_mode,
            filename_prefix=filename_prefix,
        )

    else:
        raise RuntimeError("Invalid engine type")

    map_output_path = map_result.output_svg

    if isinstance(style_cfg, BlockStyleConfig):
        theme = PosterTheme(
            background_color=style_cfg.background,
            passepartout_color=style_cfg.background,
            title_color="#4E4E4E",
            subtitle_color="#4E4E4E",
            coordinates_color="#4E4E4E",
            custom_text_color="#4E4E4E",
            title_font_family="Monoton-Regular",
            subtitle_font_family="Helvetica",
            body_font_family="Helvetica",
            subtitle_letter_spacing_pt=0.5,
        )
    elif isinstance(style_cfg, BuildingStyleConfig):
        theme = PosterTheme(
            background_color=style_cfg.background,
            passepartout_color=style_cfg.background,
            title_color="#4E4E4E",
            subtitle_color="#4E4E4E",
            coordinates_color="#4E4E4E",
            custom_text_color="#4E4E4E",
            title_font_family="Monoton-Regular",
            subtitle_font_family="Helvetica",
            body_font_family="Helvetica",
        )
    elif isinstance(style_cfg, LineStyleConfig):
        theme = PosterTheme(
            background_color=style_cfg.background,
            passepartout_color=style_cfg.background,
            title_color="#4E4E4E",
            subtitle_color="#4E4E4E",
            coordinates_color="#4E4E4E",
            custom_text_color="#4E4E4E",
            title_font_family="Monoton-Regular",
            subtitle_font_family="Helvetica",
            body_font_family="Helvetica",
        )
    else:
        theme = PosterTheme(
            background_color="#FFFFFF",
            passepartout_color="#EAE4D7",
            title_color="#2A2A2A",
            subtitle_color="#4A4A4A",
            coordinates_color="#4A4A4A",
            custom_text_color="#4A4A4A",
            title_font_family="Monoton-Regular",
            subtitle_font_family="Helvetica",
            body_font_family="Helvetica",
        )

    layout_result = compose_poster_outputs(
        layout=layout,
        map_svg_path=map_output_path,
        output_dir=output_dir,
        filename_prefix=filename_prefix,
        title=title,
        subtitle=subtitle,
        coordinates=None,
        custom_text=None,
        theme=theme,
        export_pdf=not preview_mode,
    )

    return layout_result