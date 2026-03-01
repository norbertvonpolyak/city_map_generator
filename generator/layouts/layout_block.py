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
from reportlab.lib.utils import ImageReader
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
    font_path: Optional[str] = None,
) -> LayoutResult:

    width_pt = spec.width_cm * cm
    height_pt = spec.height_cm * cm

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_pdf = output_dir / f"{palette_name}_{size_key}_{timestamp}.pdf"

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

    subtitle_font_name = "Helvetica-Bold"

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

    # ---------------------------------------------------------------------
    # TITLE + SUBTITLE
    # ---------------------------------------------------------------------

    strip_height = 4 * cm
    right_inner_edge = width_pt - right_margin

    title_font_size = 48
    subtitle_font_size = 17
    spacing = subtitle_font_size * 0.3

    block_height = title_font_size + spacing + subtitle_font_size
    strip_center_y = strip_height / 2
    block_bottom_y = strip_center_y - (block_height / 2)

    subtitle_y = block_bottom_y
    title_y = subtitle_y + subtitle_font_size + spacing

    title_width = pdfmetrics.stringWidth(
        title, title_font_name, title_font_size
    )

    tracking_value = 1.5

    raw_sub_width = pdfmetrics.stringWidth(
        subtitle.upper(), subtitle_font_name, subtitle_font_size
    )

    subtitle_width = raw_sub_width + (
        len(subtitle) - 1
    ) * tracking_value

    title_x = right_inner_edge - title_width
    subtitle_x = right_inner_edge - subtitle_width

    # Title
    c.setFillColor(colors.HexColor("#4E4E4E"))
    c.setFont(title_font_name, title_font_size)
    c.drawString(title_x, title_y, title)

    # Subtitle with tracking
    def draw_tracked_string(
        canvas,
        text,
        x,
        y,
        font_name,
        font_size,
        tracking=1.5,
    ):
        canvas.setFont(font_name, font_size)
        cursor_x = x
        for char in text:
            canvas.drawString(cursor_x, y, char)
            char_width = pdfmetrics.stringWidth(
                char, font_name, font_size
            )
            cursor_x += char_width + tracking

    draw_tracked_string(
        c,
        subtitle.upper(),
        subtitle_x,
        subtitle_y,
        subtitle_font_name,
        subtitle_font_size,
        tracking=tracking_value,
    )

    # ---------------------------------------------------------------------
    # LOGO
    # ---------------------------------------------------------------------

    logo_path = project_root / "Logo" / "dotty_map_logo.png"

    if logo_path.exists():
        logo = ImageReader(str(logo_path))
        logo_original_width, logo_original_height = logo.getSize()

        logo_height = strip_height * 0.6
        logo_width = logo_height * (
            logo_original_width / logo_original_height
        )

        logo_x = left_margin
        logo_y = (strip_height / 2) - (logo_height / 2)

        c.drawImage(
            logo,
            logo_x,
            logo_y,
            width=logo_width,
            height=logo_height,
            mask="auto",
        )

    # ---------------------------------------------------------------------
    # FINALIZE
    # ---------------------------------------------------------------------

    c.showPage()
    c.save()

    return LayoutResult(output_pdf=output_pdf)