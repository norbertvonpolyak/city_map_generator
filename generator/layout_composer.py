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
# MAIN COMPOSER
# =============================================================================

def compose_print_pdf(
    *,
    spec: ProductSpec,
    map_svg_path: Path,
    output_dir: Path,
    size_key: str,
    title: str,
    subtitle: str,
    font_path: Optional[str] = None,
) -> LayoutResult:

    width_pt = spec.width_cm * cm
    height_pt = spec.height_cm * cm

    strip_height = 4 * cm
    frame_thickness = 1 * cm
    frame_color = colors.HexColor("#D9D5C7")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_pdf = output_dir / f"citymap_{size_key}_{timestamp}.pdf"

    c = canvas.Canvas(str(output_pdf), pagesize=(width_pt, height_pt))

    # ---------------------------------------------------------------------
    # FONT (STABLE PROJECT-ROOT BASED LOADING)
    # ---------------------------------------------------------------------

    project_root = Path(__file__).resolve().parents[1]
    default_font_path = project_root / "Fonts" / "Monoton-Regular.ttf"

    if font_path:
        font_candidate = Path(font_path)
    else:
        font_candidate = default_font_path

    if font_candidate.exists():
        pdfmetrics.registerFont(
            TTFont("MonotonCustom", str(font_candidate))
        )
        title_font_name = "MonotonCustom"
    else:
        print("⚠ Monoton font not found, fallback to Helvetica")
        title_font_name = "Helvetica"

    subtitle_font_name = "Helvetica-Bold"

    # ---------------------------------------------------------------------
    # FRAME OVERLAY (1cm sides & top, 4cm bottom)
    # ---------------------------------------------------------------------

    frame_color = colors.HexColor ("#D9D5C7")

    left_margin = 1 * cm
    right_margin = 1 * cm
    top_margin = 1 * cm
    bottom_margin = 4 * cm

    c.setFillColor (frame_color)

    # Top bar
    c.rect (
        0,
        height_pt - top_margin,
        width_pt,
        top_margin,
        stroke=0,
        fill=1,
    )

    # Bottom bar
    c.rect (
        0,
        0,
        width_pt,
        bottom_margin,
        stroke=0,
        fill=1,
    )

    # Left bar
    c.rect (
        0,
        bottom_margin,
        left_margin,
        height_pt - bottom_margin - top_margin,
        stroke=0,
        fill=1,
    )

    # Right bar
    c.rect (
        width_pt - right_margin,
        bottom_margin,
        right_margin,
        height_pt - bottom_margin - top_margin,
        stroke=0,
        fill=1,
    )

    # ---------------------------------------------------------------------
    # MAP SVG (VECTOR) – POSITIONED WITH FIXED MARGINS
    # ---------------------------------------------------------------------

    drawing = svg2rlg (str (map_svg_path))

    left_margin = 1 * cm
    bottom_margin = 4 * cm

    renderPDF.draw (
         drawing,
         c,
         left_margin,
         bottom_margin,
    )

    # ---------------------------------------------------------------------
    # TITLE + SUBTITLE (BLOCK CENTERED)
    # ---------------------------------------------------------------------

    right_inner_edge = width_pt - frame_thickness

    title_font_size = 48
    subtitle_font_size = 17

    spacing = subtitle_font_size * 0.3

    block_height = title_font_size + spacing + subtitle_font_size
    strip_center_y = strip_height / 2
    block_bottom_y = strip_center_y - (block_height / 2)

    subtitle_y = block_bottom_y
    title_y = subtitle_y + subtitle_font_size + spacing

    # WIDTH CALCULATION
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

    # TITLE STYLE
    c.setFillColor(colors.HexColor("#4E4E4E"))
    c.setStrokeColor(colors.HexColor("#9B978B"))
    c.setLineWidth(0.9)

    c.setFont(title_font_name, title_font_size)
    c.drawString(title_x, title_y, title)

    # SUBTITLE WITH TRACKING
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

        logo_x = frame_thickness
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
