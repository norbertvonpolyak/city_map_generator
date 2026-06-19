from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory

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
    uniform_margins = STYLE_REGISTRY[style_name].engine == EngineType.LINE
    layout = build_poster_layout(spec.width_cm, spec.height_cm, uniform_margins=uniform_margins)
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

    with TemporaryDirectory(prefix="city_map_layer_") as temp_dir_raw:
        temp_output_dir = Path(temp_dir_raw)

        if style_def.engine == EngineType.BLOCK:

            map_result = render_map_block(
                center_lat=center_lat,
                center_lon=center_lon,
                spec=spec,
                map_width_cm=layout.visible_width_cm,
                map_height_cm=layout.visible_height_cm,
                viewport_half_width_m=viewport_half_width_m,
                viewport_half_height_m=viewport_half_height_m,
                output_dir=temp_output_dir,
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
                output_dir=temp_output_dir,
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
                output_dir=temp_output_dir,
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
            _bg = style_cfg.background.lstrip("#")
            _r, _g, _b = int(_bg[0:2], 16), int(_bg[2:4], 16), int(_bg[4:6], 16)
            _lum = (0.2126 * _r + 0.7152 * _g + 0.0722 * _b) / 255
            _text_color = "#F2F0EB" if _lum < 0.4 else "#1C1C1C"
            _fade_color = "#000000" if _lum < 0.4 else "#F6F3EE"
            theme = PosterTheme(
                background_color=style_cfg.background,
                passepartout_color="#F6F3EE",
                bottom_fade_color=_fade_color,
                title_color=_text_color,
                subtitle_color=_text_color,
                coordinates_color=_text_color,
                custom_text_color=_text_color,
                title_font_family="Montserrat-Bold",
                subtitle_font_family="Montserrat-Medium",
                body_font_family="Montserrat-Medium",
                bottom_fade=True,
                center_title=True,
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