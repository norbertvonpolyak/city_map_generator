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
    filename_prefix: str,
    font_path: Optional[str] = None,
) -> LayoutResult:

    width_pt = spec.width_cm * cm
    height_pt = spec.height_cm * cm

    output_dir.mkdir(parents=True, exist_ok=True)

    output_pdf = output_dir / f"{filename_prefix}.pdf"

    c = canvas.Canvas(str(output_pdf), pagesize=(width_pt, height_pt))

    # ============================================================
    # BACKGROUND
    # ============================================================

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

    project_root = Path(__file__).resolve().parents[2]

    cormorant_path = project_root / "Fonts" / "CormorantGaramond-SemiBold.ttf"
    arsenal_path   = project_root / "Fonts" / "Arsenal-Regular.ttf"

    pdfmetrics.registerFont(TTFont("CormorantSemiBold", str(cormorant_path)))
    pdfmetrics.registerFont(TTFont("ArsenalRegular",    str(arsenal_path)))

    title_font = "CormorantSemiBold"
    coord_font = "ArsenalRegular"

    # Bottom passepartout height
    bottom_margin_height = inner_y

    # Title size: keep existing ratio-based formula (unchanged)
    title_size = (bottom_margin_height * 0.9) * 0.65

    # Coordinates: fixed 22 pt (≈ 22 px at 72 dpi)
    coord_size = 22.0

    # Gap between title and coordinates: ~20 pt (≈ 20 px)
    line_gap = 20.0

    # ---- FONT METRICS ----

    title_ascent, title_descent = getAscentDescent(title_font, title_size)
    coord_ascent, coord_descent = getAscentDescent(coord_font, coord_size)

    title_real_height = title_ascent - title_descent
    coord_real_height = coord_ascent - coord_descent

    # ---- UNIFIED BLOCK: optically centered in bottom passepartout ----
    # Mathematical center shifted down ~8% to compensate for visual top-heaviness.

    text_block_height = title_real_height + line_gap + coord_real_height
    optical_correction = bottom_margin_height * 0.08
    text_block_bottom = (bottom_margin_height - text_block_height) / 2 - optical_correction

    # Right edge aligned with map frame
    right_x = width_pt - margin

    # ---- TITLE (unchanged: font, size, color, right-aligned) ----

    c.setFillColor(title_color)
    c.setFont(title_font, title_size)

    title_text = title.upper()

    # baseline: measured from block bottom up through coord section + gap - descent
    title_baseline_y = text_block_bottom + coord_real_height + line_gap - title_descent

    c.drawRightString(right_x, title_baseline_y, title_text)

    # ---- COORDINATES: Arsenal Regular 22 pt, right-aligned ----

    c.setFillColor(subtitle_color)
    c.setFont(coord_font, coord_size)

    coord_text = subtitle.replace("° N", "°N").replace("° E", "°E")

    coord_baseline_y = text_block_bottom - coord_descent

    c.drawRightString(right_x, coord_baseline_y, coord_text)

    # ============================================================
    # FINALIZE
    # ============================================================

    c.showPage()
    c.save()

    return LayoutResult(output_pdf=output_pdf)