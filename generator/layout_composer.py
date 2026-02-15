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

from generator.specs import ProductSpec


@dataclass(frozen=True)
class LayoutResult:
    output_pdf: Path


def compose_print_pdf(
    *,
    spec: ProductSpec,
    map_image_path: Path,
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
    # FONT
    # ---------------------------------------------------------------------

    if font_path and Path(font_path).exists():
        pdfmetrics.registerFont(TTFont("MonotonCustom", font_path))
        font_name = "MonotonCustom"
    else:
        font_name = "Helvetica"

    # ---------------------------------------------------------------------
    # BACKGROUND FRAME
    # ---------------------------------------------------------------------

    c.setFillColor(frame_color)
    c.rect(0, 0, width_pt, height_pt, stroke=0, fill=1)

    # ---------------------------------------------------------------------
    # MAP IMAGE
    # ---------------------------------------------------------------------

    image = ImageReader(str(map_image_path))

    map_width = width_pt - 2 * frame_thickness
    map_height = height_pt - strip_height - frame_thickness

    c.drawImage(
        image,
        frame_thickness,
        strip_height,
        width=map_width,
        height=map_height,
        preserveAspectRatio=False,
        mask="auto",
    )

    # ---------------------------------------------------------------------
    # TITLE + SUBTITLE POSITIONING (CORRECT BLOCK CENTER)
    # ---------------------------------------------------------------------

    right_inner_edge = width_pt - frame_thickness

    title_font_size = 48
    subtitle_font_size = 17

    # valódi vizuális spacing
    spacing = subtitle_font_size * 0.3  # <-- EZ A FONTOS

    # teljes blokk magasság
    block_height = title_font_size + spacing + subtitle_font_size

    strip_center_y = strip_height / 2

    # blokk alja
    block_bottom_y = strip_center_y - (block_height / 2)

    # baseline számítás
    subtitle_y = block_bottom_y
    title_y = subtitle_y + subtitle_font_size + spacing

    # jobb igazítás
    title_width = pdfmetrics.stringWidth (title, font_name, title_font_size)
    tracking_value = 1.5
    raw_width = pdfmetrics.stringWidth (subtitle.upper (), font_name, subtitle_font_size)
    subtitle_width = raw_width + (len (subtitle) - 1) * tracking_value

    title_x = right_inner_edge - title_width
    subtitle_x = right_inner_edge - subtitle_width

    c.setFillColor (colors.HexColor ("#4E4E4E"))  # sötétebb fill
    c.setStrokeColor (colors.HexColor ("#9B978B"))  # világosabb stroke
    c.setLineWidth (0.9)  # finomabb stroke

    # TITLE
    c.setFont (font_name, title_font_size)
    c.drawString (title_x, title_y, title)

    # SUBTITLE
    def draw_tracked_string (canvas, text, x, y, font_name, font_size, tracking=1.5):
        canvas.setFont (font_name, font_size)
        cursor_x = x
        for char in text:
            canvas.drawString (cursor_x, y, char)
            char_width = pdfmetrics.stringWidth (char, font_name, font_size)
            cursor_x += char_width + tracking

    subtitle_font_name = "Helvetica-Bold"  # vagy "Helvetica-Bold" ha picit erősebb kell

    draw_tracked_string (
        c,
        subtitle.upper (),
        subtitle_x,
        subtitle_y,
        subtitle_font_name,
        subtitle_font_size,
        tracking=1.5
    )

    # ---------------------------------------------------------------------
    # LOGO (LEFT SIDE OF STRIP)
    # ---------------------------------------------------------------------

    logo_path = Path("Logo/dotty_map_logo.png")

    if logo_path.exists():

        logo = ImageReader(str(logo_path))

        logo_original_width, logo_original_height = logo.getSize()

        # kívánt logó magasság (strip 70%-a)
        logo_height = strip_height * 0.5
        logo_width = logo_height * (logo_original_width / logo_original_height)

        logo_x = frame_thickness  # bal margó belseje

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
