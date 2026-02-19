from pathlib import Path
from typing import Optional
from datetime import datetime
import numpy as np
from io import BytesIO
from PIL import Image

from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics import renderPDF
from reportlab.lib.utils import ImageReader
from svglib.svglib import svg2rlg

from generator.styles import get_palette_config


def compose_vintage_atlas_premium(
    *,
    spec,
    map_svg_path: Path,
    output_dir: Path,
    size_key: str,
    title: str,
    subtitle: str,
    palette_name: str,
    font_path: Optional[str] = None,
):

    palette_cfg = get_palette_config(palette_name)

    width_pt = spec.width_cm * cm
    height_pt = spec.height_cm * cm

    timestamp = datetime.now().strftime("%y%m%d_%H%M")
    output_pdf = output_dir / f"{palette_name}_{size_key}_{timestamp}.pdf"

    c = canvas.Canvas(str(output_pdf), pagesize=(width_pt, height_pt))

    # ============================================================
    # FONT SETUP – CENTAUREA
    # ============================================================

    project_root = Path(__file__).resolve().parents[1]
    centaurea_path = project_root / "Fonts" / "CentaureaDemo.ttf"

    title_font = "Helvetica-Bold"
    subtitle_font = "Helvetica"

    if centaurea_path.exists():
        pdfmetrics.registerFont(TTFont("Centaurea", str(centaurea_path)))
        title_font = "Centaurea"
        subtitle_font = "Helvetica"

    # ============================================================
    # BACKGROUND
    # ============================================================

    parchment = colors.HexColor(palette_cfg.background)
    outer_color = colors.HexColor("#6A4425")
    inner_color = colors.HexColor("#7C5835")

    c.setFillColor(parchment)
    c.rect(0, 0, width_pt, height_pt, fill=1, stroke=0)

    # ============================================================
    # FRAME GEOMETRY
    # ============================================================

    outer_margin = 1.1 * cm
    inner_offset = 0.55 * cm   # nagyobb térköz a dupla keret között

    inner_left = outer_margin + inner_offset
    inner_bottom = outer_margin + inner_offset
    inner_right = width_pt - (outer_margin + inner_offset)
    inner_top = height_pt - (outer_margin + inner_offset)

    # ============================================================
    # PREMIUM DOUBLE FRAME
    # ============================================================

    outer_line = width_pt * 0.0055
    inner_line = width_pt * 0.0025

    # OUTER
    c.setStrokeColor(outer_color)
    c.setLineWidth(outer_line)
    c.rect(
        outer_margin,
        outer_margin,
        width_pt - 2 * outer_margin,
        height_pt - 2 * outer_margin,
        fill=0,
        stroke=1,
    )

    # INNER
    c.setStrokeColor(inner_color)
    c.setLineWidth(inner_line)
    c.rect(
        inner_left,
        inner_bottom,
        inner_right - inner_left,
        inner_top - inner_bottom,
        fill=0,
        stroke=1,
    )

    # ============================================================
    # TEXT BAND HEIGHT
    # ============================================================

    text_band_height = 3.2 * cm
    optical_margin = 0.2 * cm

    # ============================================================
    # MAP (FILL INNER FRAME ABOVE TEXT BAND)
    # ============================================================

    map_left = inner_left + optical_margin
    map_right = inner_right - optical_margin
    map_top = inner_top - optical_margin
    map_bottom = inner_bottom + text_band_height + optical_margin

    map_width = map_right - map_left
    map_height = map_top - map_bottom

    drawing = svg2rlg(str(map_svg_path))

    scale = max(
        map_width / drawing.width,
        map_height / drawing.height
    )

    drawing.scale(scale, scale)

    scaled_w = drawing.width * scale
    scaled_h = drawing.height * scale

    offset_x = map_left - (scaled_w - map_width) / 2
    offset_y = map_bottom - (scaled_h - map_height) / 2

    c.saveState()

    clip_path = c.beginPath()
    clip_path.rect(map_left, map_bottom, map_width, map_height)
    c.clipPath(clip_path, stroke=0, fill=0)

    renderPDF.draw(drawing, c, offset_x, offset_y)

    c.restoreState()

    # ============================================================
    # TEXT BAND
    # ============================================================

    c.setFillColor(parchment)
    c.rect(
        inner_left,
        inner_bottom,
        inner_right - inner_left,
        text_band_height,
        fill=1,
        stroke=0,
    )

    # ============================================================
    # SOFT TRANSITION – parchment colored & stronger
    # ============================================================

    fade_height = text_band_height * 0.9  # vastagabb

    img_w = 600
    img_h = 500

    gradient = np.zeros ((img_h, img_w, 4), dtype=np.uint8)

    # parchment RGB komponensek
    r = int (parchment.red * 255)
    g = int (parchment.green * 255)
    b = int (parchment.blue * 255)

    for y in range (img_h):
        ratio = y / img_h
        alpha = int ((ratio ** 1.5) * 200)  # erősebb fade

        gradient [y, :, 0] = r
        gradient [y, :, 1] = g
        gradient [y, :, 2] = b
        gradient [y, :, 3] = alpha

    img = Image.fromarray (gradient, mode="RGBA")

    buffer = BytesIO ()
    img.save (buffer, format="PNG")
    buffer.seek (0)

    overlay = ImageReader (buffer)

    c.drawImage (
        overlay,
        inner_left,
        inner_bottom + text_band_height,
        width=inner_right - inner_left,
        height=fade_height,
        mask="auto",
    )

    # ============================================================
    # TYPOGRAPHY – CENTAUREA + TRACKING
    # ============================================================

    c.setFillColor(outer_color)

    title_size = text_band_height * 0.40
    subtitle_size = title_size * 0.35

    title_text = title.upper()
    subtitle_text = subtitle.upper()

    title_y = inner_bottom + text_band_height * 0.60

    c.setFont(title_font, title_size)

    # tracking
    title_tracking = title_size * 0.06

    raw_width = pdfmetrics.stringWidth(title_text, title_font, title_size)
    total_width = raw_width + (len(title_text) - 1) * title_tracking

    cursor = (width_pt - total_width) / 2

    for ch in title_text:
        c.drawString(cursor, title_y, ch)
        w = pdfmetrics.stringWidth(ch, title_font, title_size)
        cursor += w + title_tracking

    # divider (rövidebb, elegánsabb)
    line_y = inner_bottom + text_band_height * 0.45
    c.setLineWidth(width_pt * 0.0013)
    c.line(
        width_pt * 0.38,
        line_y,
        width_pt * 0.62,
        line_y,
    )

    # subtitle
    c.setFont("Helvetica", subtitle_size)

    subtitle_width = pdfmetrics.stringWidth(
        subtitle_text, subtitle_font, subtitle_size
    )

    c.drawString(
        (width_pt - subtitle_width) / 2,
        inner_bottom + text_band_height * 0.18,
        subtitle_text,
    )

    c.showPage()
    c.save()

    return output_pdf
