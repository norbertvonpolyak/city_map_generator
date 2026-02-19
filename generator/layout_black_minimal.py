from pathlib import Path
from typing import Optional
from datetime import datetime
import numpy as np
from io import BytesIO
from PIL import Image

from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.graphics import renderPDF
from reportlab.lib.utils import ImageReader
from svglib.svglib import svg2rlg
from generator.styles import get_palette_config

def compose_black_minimal(
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

    # ============================================================
    # PAGE SETUP
    # ============================================================

    width_pt = spec.width_cm * cm
    height_pt = spec.height_cm * cm
    frame = 1 * cm

    timestamp = datetime.now().strftime("%y%m%d_%H%M")
    output_pdf = output_dir / f"{palette_name}_{size_key}_{timestamp}.pdf"

    c = canvas.Canvas(str(output_pdf), pagesize=(width_pt, height_pt))

    # --- FRAME COLOR ---
    palette_cfg = get_palette_config (palette_name)
    frame_color = colors.HexColor (palette_cfg.water)

    c.setFillColor (frame_color)
    c.rect (0, 0, width_pt, height_pt, fill=1, stroke=0)

    # --- INNER AREA ---
    inner_x = frame
    inner_y = frame
    inner_w = width_pt - 2 * frame
    inner_h = height_pt - 2 * frame

    inner_bg_color = colors.HexColor (palette_cfg.background)

    c.setFillColor (inner_bg_color)
    c.rect (inner_x, inner_y, inner_w, inner_h, fill=1, stroke=0)

    # ============================================================
    # MAP
    # ============================================================

    drawing = svg2rlg(str(map_svg_path))
    scale_x = inner_w / drawing.width
    scale_y = inner_h / drawing.height
    drawing.scale(scale_x, scale_y)
    drawing.width *= scale_x
    drawing.height *= scale_y

    renderPDF.draw(drawing, c, inner_x, inner_y)

    # ============================================================
    # FADE (BOTTOM GRADIENT)
    # ============================================================

    fade_ratio = 0.27
    fade_height = inner_h * fade_ratio

    img_w = 1600
    img_h = 2000

    gradient = np.zeros((img_h, img_w, 4), dtype=np.uint8)

    for y in range(img_h):
        ratio = y / img_h
        intensity = (ratio ** 2.2) * 1.15
        alpha = int(min(intensity, 1.0) * 255)
        gradient[y, :, 3] = alpha

    img = Image.fromarray(gradient, mode="RGBA")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    overlay = ImageReader(buffer)

    c.drawImage(
        overlay,
        inner_x,
        inner_y,
        width=inner_w,
        height=fade_height,
        mask="auto",
    )

    # ============================================================
    # FONT SETUP
    # ============================================================

    project_root = Path(__file__).resolve().parents[1]
    montserrat_path = project_root / "Fonts" / "Montserrat-Bold.ttf"

    title_font = "Helvetica-Bold"
    subtitle_font = "Helvetica"

    if montserrat_path.exists():
        pdfmetrics.registerFont(
            TTFont("MontserratBold", str(montserrat_path))
        )
        title_font = "MontserratBold"

    c.setFillColor(colors.white)

    # ============================================================
    # TYPOGRAPHY SIZING
    # ============================================================

    title_ratio = 0.065
    title_size = inner_h * title_ratio

    subtitle_size = title_size * 0.18
    tracking = subtitle_size * 0.15

    title_text = title.upper()
    subtitle_text = subtitle.upper()

    # ============================================================
    # TEXT BLOCK POSITION – LOWER 18% OF IMAGE
    # ============================================================

    bottom_zone_ratio = 0.18
    bottom_zone_height = inner_h * bottom_zone_ratio
    bottom_zone_center_y = inner_y + (bottom_zone_height / 2)

    # FIX 1 cm sortáv
    subtitle_gap = 1 * cm

    # teljes blokk magasság
    text_block_height = title_size + subtitle_gap

    # blokk középre igazítva a bottom zone-ban
    block_bottom_y = bottom_zone_center_y - (text_block_height / 2)

    subtitle_y = block_bottom_y
    title_y = subtitle_y + subtitle_gap

    # ============================================================
    # DRAW TITLE
    # ============================================================

    c.setFont(title_font, title_size)

    title_width = pdfmetrics.stringWidth(
        title_text, title_font, title_size
    )

    c.drawString(
        inner_x + (inner_w - title_width) / 2,
        title_y,
        title_text,
    )

    # ============================================================
    # DRAW SUBTITLE (TRACKED)
    # ============================================================

    c.setFont(subtitle_font, subtitle_size)

    raw_width = pdfmetrics.stringWidth(
        subtitle_text, subtitle_font, subtitle_size
    )

    total_width = raw_width + (len(subtitle_text) - 1) * tracking
    start_x = inner_x + (inner_w - total_width) / 2

    cursor = start_x
    for ch in subtitle_text:
        c.drawString(cursor, subtitle_y, ch)
        w = pdfmetrics.stringWidth(ch, subtitle_font, subtitle_size)
        cursor += w + tracking

    # ============================================================
    # DIVIDER LINES
    # ============================================================

    line_y = subtitle_y + (subtitle_size * 0.5)

    gap = inner_w * 0.02
    edge_stop = inner_w * 0.08

    left_limit = inner_x + edge_stop
    right_limit = inner_x + inner_w - edge_stop

    left_line_end = start_x - gap
    right_line_start = start_x + total_width + gap

    c.setLineWidth(inner_h * 0.0015)
    c.setStrokeColor(colors.white)

    if left_line_end > left_limit:
        c.line(left_limit, line_y, left_line_end, line_y)

    if right_line_start < right_limit:
        c.line(right_line_start, line_y, right_limit, line_y)

    # ============================================================
    # FINALIZE
    # ============================================================

    c.showPage()
    c.save()

    return output_pdf
