from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory
from PIL import Image

from generator.engines.render_block import render_map_block
from generator.engines.render_building import render_map_building
from generator.engines.render_line import render_map_line

from generator.specs import ProductSpec
from generator.layouts.layout_utils import build_poster_layout, compose_poster_outputs, PosterTheme, PosterCompositionResult, svg_to_pdf
from generator.layouts.layout_block import compose_layout_block
from generator.layouts.layout_building import compose_layout_building
from generator.core.style_registry import STYLE_REGISTRY, EngineType
from generator.styles import get_style_config, BlockStyleConfig, BuildingStyleConfig, MaptoposterLineStyleConfig
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
# VIEWPORT HELPER
# ==========================================================

def get_viewport_for_style(style_name: str, spec) -> tuple[float, float]:
    """Return (half_width_m, half_height_m) for the given style and spec.

    This replicates the layout computation from render_product so that callers
    can pre-warm the OSM bundle cache for every unique viewport before rendering.
    """
    if style_name not in STYLE_REGISTRY:
        raise ValueError(f"Unknown style: {style_name}")

    style_cfg = get_style_config(style_name)

    if isinstance(style_cfg, MaptoposterLineStyleConfig):
        uniform_margins = style_cfg.layout.uniform_margins
    else:
        uniform_margins = STYLE_REGISTRY[style_name].engine == EngineType.LINE

    bottom_margin_ratio = None
    layout_config = None

    if isinstance(style_cfg, MaptoposterLineStyleConfig):
        bottom_margin_ratio = style_cfg.layout.bottom_margin_ratio
        if style_name == "vintage_atlas":
            layout_config = {
                'side_margin_ratio': style_cfg.layout.side_margin_ratio,
                'bottom_margin_multiplier': style_cfg.layout.bottom_margin_multiplier,
                'text_vertical_centering': style_cfg.layout.text_vertical_centering,
                'title_above_coordinates': style_cfg.layout.title_above_coordinates,
            }
    elif style_name == "old_time_fantasy" and STYLE_REGISTRY[style_name].engine == EngineType.LINE:
        bottom_margin_ratio = 0.15

    layout = build_poster_layout(
        spec.width_cm,
        spec.height_cm,
        uniform_margins=uniform_margins,
        bottom_margin_ratio=bottom_margin_ratio,
        style_name=style_name,
        layout_config=layout_config,
    )
    return layout.map_viewport_half_sizes_m(spec.extent_m)


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

    if isinstance(style_cfg, MaptoposterLineStyleConfig):
        uniform_margins = style_cfg.layout.uniform_margins
    else:
        uniform_margins = STYLE_REGISTRY[style_name].engine == EngineType.LINE

    use_poster_level_texture = (
        isinstance(style_cfg, MaptoposterLineStyleConfig)
        and style_cfg.layout.passepartout_opacity <= 0.001
        and bool(style_cfg.render.background_texture_path)
        and style_cfg.render.background_texture_opacity > 0
    )

    bottom_margin_ratio = None
    layout_config = None

    if isinstance(style_cfg, MaptoposterLineStyleConfig):
        bottom_margin_ratio = style_cfg.layout.bottom_margin_ratio
        # Prepare vintage_atlas layout config
        if style_name == "vintage_atlas":
            layout_config = {
                'side_margin_ratio': style_cfg.layout.side_margin_ratio,
                'bottom_margin_multiplier': style_cfg.layout.bottom_margin_multiplier,
                'text_vertical_centering': style_cfg.layout.text_vertical_centering,
                'title_above_coordinates': style_cfg.layout.title_above_coordinates,
            }
    elif style_name == "old_time_fantasy" and STYLE_REGISTRY[style_name].engine == EngineType.LINE:
        # Taller lower passepartout to match premium reference composition.
        bottom_margin_ratio = 0.15

    layout = build_poster_layout(
        spec.width_cm,
        spec.height_cm,
        uniform_margins=uniform_margins,
        bottom_margin_ratio=bottom_margin_ratio,
        style_name=style_name,
        layout_config=layout_config,
    )
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
                use_cache=use_cache,
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
                use_cache=use_cache,
                draw_background_texture=not use_poster_level_texture,
                transparent_map_background=use_poster_level_texture,
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
                block_engine_layout=True,
            )
        elif isinstance(style_cfg, BuildingStyleConfig):
            if style_name == "midnight_blue":
                mustard_text = "#C9A227"
                passepartout_color = "#081519"
                background_color = "#081519"
                title_color = mustard_text
                subtitle_color = mustard_text
                coordinates_color = mustard_text
                custom_text_color = mustard_text
            elif style_name == "sandstone_beige":
                brown_text = "#4B4035"
                passepartout_color = style_cfg.background
                background_color = style_cfg.background
                title_color = brown_text
                subtitle_color = brown_text
                coordinates_color = brown_text
                custom_text_color = brown_text
            elif style_name == "luxury_gold":
                gold_text = "#F0D89B"
                passepartout_color = style_cfg.background
                background_color = style_cfg.background
                title_color = gold_text
                subtitle_color = gold_text
                coordinates_color = gold_text
                custom_text_color = gold_text
            elif style_name == "royal_purple":
                mustard_text = "#C9A227"
                passepartout_color = "#1f1e3a"
                background_color = "#1f1e3a"
                title_color = mustard_text
                subtitle_color = mustard_text
                coordinates_color = mustard_text
                custom_text_color = mustard_text
            elif style_name == "architect_sage":
                forest_text = "#1E2B22"
                passepartout_color = "#BFD4D0"
                background_color = "#BFD4D0"
                title_color = forest_text
                subtitle_color = forest_text
                coordinates_color = forest_text
                custom_text_color = forest_text
            else:
                passepartout_color = style_cfg.background
                background_color = style_cfg.background
                title_color = "#4E4E4E"
                subtitle_color = "#4E4E4E"
                coordinates_color = "#4E4E4E"
                custom_text_color = "#4E4E4E"

            theme = PosterTheme(
                background_color=background_color,
                passepartout_color=passepartout_color,
                title_color=title_color,
                subtitle_color=subtitle_color,
                coordinates_color=coordinates_color,
                custom_text_color=custom_text_color,
                title_font_family="Mathilde",
                subtitle_font_family="Helvetica",
                body_font_family="Helvetica",
                block_engine_layout=True,
            )
        elif isinstance(style_cfg, MaptoposterLineStyleConfig):
            full_background_texture_path = None
            full_background_texture_opacity = 0.0
            if use_poster_level_texture:
                full_background_texture_path = style_cfg.render.background_texture_path
                full_background_texture_opacity = style_cfg.render.background_texture_opacity

            # Custom scale factors for specific styles
            title_scale = 0.42
            coordinates_scale = 0.24
            title_fixed_size_pt = 0.0
            coordinates_fixed_size_pt = 0.0
            title_baseline_spacing_pt = 0.0
            
            if style_name == "vintage_atlas":
                # Use fixed pixel sizes instead of scaling
                # 64 px = 48 pt (at 96 DPI: 64 * 72/96)
                # 24 px = 18 pt (at 96 DPI: 24 * 72/96)
                # 24 px baseline spacing = 18 pt (increased from 13.5pt)
                title_fixed_size_pt = 48.0
                coordinates_fixed_size_pt = 18.0
                title_baseline_spacing_pt = 18.0

            theme = PosterTheme(
                background_color=style_cfg.render.background,
                passepartout_color=style_cfg.layout.passepartout_color,
                passepartout_opacity=style_cfg.layout.passepartout_opacity,
                background_texture_path=full_background_texture_path,
                background_texture_opacity=full_background_texture_opacity,
                bottom_fade_color=style_cfg.layout.bottom_fade_color,
                title_color=style_cfg.layout.title_color,
                subtitle_color=style_cfg.layout.subtitle_color,
                coordinates_color=style_cfg.layout.coordinates_color,
                custom_text_color=style_cfg.layout.custom_text_color,
                title_font_family=style_cfg.layout.title_font_family,
                subtitle_font_family=style_cfg.layout.subtitle_font_family,
                body_font_family=style_cfg.layout.body_font_family,
                coordinates_font_family=style_cfg.layout.coordinates_font_family,
                title_scale=title_scale,
                coordinates_scale=coordinates_scale,
                title_fixed_size_pt=title_fixed_size_pt,
                coordinates_fixed_size_pt=coordinates_fixed_size_pt,
                title_baseline_spacing_pt=title_baseline_spacing_pt,
                bottom_fade=style_cfg.layout.bottom_fade,
                center_title=style_cfg.layout.center_title,
                title_letter_spacing_pt=style_cfg.layout.title_letter_spacing_pt,
                coordinates_letter_spacing_pt=style_cfg.layout.coordinates_letter_spacing_pt,
                inner_border_color=style_cfg.layout.inner_border_color,
                inner_border_width_px=style_cfg.layout.inner_border_width_px,
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

        # Keep block/line behavior unchanged; only building titles are de-shouted.
        display_title = title
        if isinstance(style_cfg, BuildingStyleConfig) and title and title.isupper():
            display_title = title.title()

        # Format coordinates for display
        coordinates_str = f"{center_lat:.4f}°N  {center_lon:.4f}°E"
        
        layout_result = compose_poster_outputs(
            layout=layout,
            map_svg_path=map_output_path,
            output_dir=output_dir,
            filename_prefix=filename_prefix,
            title=display_title,
            subtitle=subtitle,
            coordinates=coordinates_str,
            custom_text=None,
            theme=theme,
            export_pdf=(not preview_mode) and (not isinstance(style_cfg, MaptoposterLineStyleConfig)),
        )

        if isinstance(style_cfg, MaptoposterLineStyleConfig):
            output_pdf = output_dir / f"{filename_prefix}.pdf"
            svg_to_pdf(
                svg_path=layout_result.output_svg,
                output_pdf=output_pdf,
                layout=layout,
                prefer_cairo=False,
            )

            output_webp = output_dir / f"{filename_prefix}.webp"
            max_webp_size_bytes = 350 * 1024
            quality_steps = [88, 82, 76, 70, 64, 58, 52, 46, 40, 35]
            methods = [6, 4]

            with Image.open(layout_result.output_png) as png_img:
                saved_under_cap = False
                for method in methods:
                    for quality in quality_steps:
                        png_img.save(
                            output_webp,
                            format="WEBP",
                            quality=quality,
                            method=method,
                            optimize=True,
                        )
                        if output_webp.stat().st_size <= max_webp_size_bytes:
                            saved_under_cap = True
                            break
                    if saved_under_cap:
                        break

                if not saved_under_cap:
                    png_img.save(
                        output_webp,
                        format="WEBP",
                        quality=30,
                        method=6,
                        optimize=True,
                    )

            layout_result = PosterCompositionResult(
                output_svg=layout_result.output_svg,
                output_png=layout_result.output_png,
                output_pdf=output_pdf,
            )

        # NOTE: Typography is now embedded in SVG for all engines
        # (block, building, line). The SVG is the single source of truth.
        # All outputs (PNG, PDF) are generated from SVG, ensuring consistency.
        # Legacy separate PDF generation via compose_layout_block/compose_layout_building is disabled.

        return layout_result