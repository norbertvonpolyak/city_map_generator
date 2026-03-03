from __future__ import annotations

from pathlib import Path
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

from generator.specs import ProductSpec


# =============================================================================
# RESULT
# =============================================================================

@dataclass(frozen=True)
class LayoutResult:
    output_pdf: Path


# =============================================================================
# BUILDING LAYOUT (ENGINE-BASED)
# =============================================================================

def compose_layout_building(
    *,
    spec: ProductSpec,
    map_svg_path: Path,
    output_dir: Path,
    size_key: str,
    title: str,
    subtitle: str,
    palette_name: str,
    font_path: Optional[str] = None,
) -> LayoutResult:

    width_pt = spec.width_cm * cm
    height_pt = spec.height_cm * cm

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    output_pdf = output_dir / f"{palette_name}_{size_key}_{timestamp}.pdf"

    c = canvas.Canvas(str(output_pdf), pagesize=(width_pt, height_pt))

    # ============================================================
    # BACKGROUND
    # ============================================================

    if palette_name == "pretty_buildings":
        background_color = colors.HexColor("#F4EFE6")
        map_background_color = colors.HexColor("#E6D3B3")
    else:
        background_color = colors.HexColor("#E6D3B3")
        map_background_color = None

    title_color = colors.HexColor("#5A3A24")
    subtitle_color = colors.HexColor("#8A6A50")

    c.setFillColor(background_color)
    c.rect(0, 0, width_pt, height_pt, fill=1, stroke=0)

    # ============================================================
    # MAP AREA
    # ============================================================

    margin = 1.5 * cm

    inner_x = margin
    inner_y = margin * 2.2
    inner_w = width_pt - (margin * 2)
    inner_h = height_pt - (margin * 3.5)

    if map_background_color:
        c.setFillColor(map_background_color)
        c.rect(inner_x, inner_y, inner_w, inner_h, fill=1, stroke=0)

    drawing = svg2rlg(str(map_svg_path))

    scale_x = inner_w / drawing.width
    scale_y = inner_h / drawing.height

    drawing.scale(scale_x, scale_y)
    drawing.width *= scale_x
    drawing.height *= scale_y

    renderPDF.draw(drawing, c, inner_x, inner_y)

    # ============================================================
    # TYPOGRAPHY (TRUE CENTERED IN LOWER MARGIN – METRIC BASED)
    # ============================================================

    from reportlab.pdfbase.pdfmetrics import getAscentDescent

    project_root = Path (__file__).resolve ().parents [2]

    cormorant_path = project_root / "Fonts" / "CormorantGaramond-SemiBold.ttf"
    inter_path = project_root / "Fonts" / "Inter_18pt-ExtraLight.ttf"

    pdfmetrics.registerFont (
        TTFont ("CormorantSemiBold", str (cormorant_path))
    )
    pdfmetrics.registerFont (
        TTFont ("InterExtraLight", str (inter_path))
    )

    title_font = "CormorantSemiBold"
    subtitle_font = "InterExtraLight"

    # Alsó margó teljes magassága
    bottom_margin_height = inner_y

    # Ennek 90%-át használjuk
    usable_height = bottom_margin_height * 0.9

    # Arányok
    title_ratio = 0.65
    subtitle_ratio = 0.25
    gap_ratio = 0.10

    title_size = usable_height * title_ratio
    subtitle_size = usable_height * subtitle_ratio
    line_gap = usable_height * gap_ratio

    # ---- VALÓDI SZÖVEGMAGASSÁG (font metrics) ----

    title_ascent, title_descent = getAscentDescent (title_font, title_size)
    subtitle_ascent, subtitle_descent = getAscentDescent (subtitle_font, subtitle_size)

    title_real_height = title_ascent - title_descent
    subtitle_real_height = subtitle_ascent - subtitle_descent

    text_block_height = title_real_height + line_gap + subtitle_real_height

    # ---- BLOKK ALSÓ POZÍCIÓ (VALÓDI KÖZÉP) ----

    text_block_bottom = (bottom_margin_height - text_block_height) / 2

    # ---- TITLE ----

    c.setFillColor (title_color)
    c.setFont (title_font, title_size)

    title_text = title.upper ()

    title_baseline_y = (
              text_block_bottom
              + subtitle_real_height
              + line_gap
              - title_descent
    )

    c.drawCentredString (
        width_pt / 2,
        title_baseline_y,
        title_text,
    )

    # ---- SUBTITLE ----

    c.setFillColor (subtitle_color)
    c.setFont (subtitle_font, subtitle_size)

    subtitle_text = subtitle.replace ("° N", "°N").replace ("° E", "°E")

    subtitle_baseline_y = text_block_bottom + subtitle_ascent

    c.drawCentredString (
        width_pt / 2,
        subtitle_baseline_y,
        subtitle_text,
    )

    # ============================================================
    # FINALIZE
    # ============================================================

    c.showPage()
    c.save()

    return LayoutResult(output_pdf=output_pdf)