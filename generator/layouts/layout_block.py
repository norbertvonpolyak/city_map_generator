from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
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
# BLOCK LAYOUT (ENGINE-BASED)
# =============================================================================

def compose_layout_block(
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

    output_pdf = output_dir / f"{filename_prefix}.pdf"

    c = canvas.Canvas(str(output_pdf), pagesize=(width_pt, height_pt))

    # ---------------------------------------------------------------------
    # FONT SETUP
    # ---------------------------------------------------------------------

    project_root = Path(__file__).resolve().parents[2]
    default_font_path = project_root / "Fonts" / "Monoton-Regular.ttf"

    font_candidate = Path(font_path) if font_path else default_font_path

    if font_candidate.exists():
        pdfmetrics.registerFont(
            TTFont("MonotonCustom", str(font_candidate))
        )
        title_font_name = "MonotonCustom"
    else:
        title_font_name = "Helvetica"

    # Register CentaureaDemo for subtitle and coordinates
    centaurea_path = project_root / "Fonts" / "CentaureaDemo.ttf"
    if centaurea_path.exists():
        pdfmetrics.registerFont(
            TTFont("CentaureaDemoCustom", str(centaurea_path))
        )
        subtitle_font_name = "CentaureaDemoCustom"
        coordinates_font_name = "CentaureaDemoCustom"
    else:
        subtitle_font_name = "Helvetica-Bold"
        coordinates_font_name = "Helvetica"

    # ---------------------------------------------------------------------
    # FRAME (1cm sides/top, 4cm bottom)
    # ---------------------------------------------------------------------

    frame_color = colors.HexColor("#D9D5C7")

    left_margin = 1 * cm
    right_margin = 1 * cm
    top_margin = 1 * cm
    bottom_margin = 4 * cm

    c.setFillColor(frame_color)

    # Top
    c.rect(0, height_pt - top_margin, width_pt, top_margin, stroke=0, fill=1)

    # Bottom
    c.rect(0, 0, width_pt, bottom_margin, stroke=0, fill=1)

    # Left
    c.rect(
        0,
        bottom_margin,
        left_margin,
        height_pt - bottom_margin - top_margin,
        stroke=0,
        fill=1,
    )

    # Right
    c.rect(
        width_pt - right_margin,
        bottom_margin,
        right_margin,
        height_pt - bottom_margin - top_margin,
        stroke=0,
        fill=1,
    )

    # ---------------------------------------------------------------------
    # MAP SVG
    # ---------------------------------------------------------------------

    drawing = svg2rlg (str (map_svg_path))

    inner_width = width_pt - (left_margin + right_margin)
    inner_height = height_pt - (top_margin + bottom_margin)

    scale_x = inner_width / drawing.width
    scale_y = inner_height / drawing.height
    scale = min (scale_x, scale_y)

    drawing.scale (scale, scale)

    scaled_width = drawing.width * scale
    scaled_height = drawing.height * scale

    offset_x = left_margin + (inner_width - scaled_width) / 2
    offset_y = bottom_margin + (inner_height - scaled_height) / 2

    renderPDF.draw (drawing, c, offset_x, offset_y)

    # TITLE + SUBTITLE + COORDINATES (RENDERED IN SVG NOW)
    # =====================================================
    # Typography is now embedded in the SVG (for consistency with PNG output).
    # This PDF rendering is disabled to avoid double-rendering conflicts.
    # SVG is the single source of truth for all outputs.

    # ---------------------------------------------------------------------
    # FINALIZE
    # ---------------------------------------------------------------------

    c.showPage()
    c.save()

    return LayoutResult(output_pdf=output_pdf)