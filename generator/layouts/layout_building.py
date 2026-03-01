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

    timestamp = datetime.now().strftime("%y%m%d_%H%M")
    output_pdf = output_dir / f"{palette_name}_{size_key}_{timestamp}.pdf"

    c = canvas.Canvas(str(output_pdf), pagesize=(width_pt, height_pt))

    # ============================================================
    # BACKGROUND (NEUTRAL — ENGINE FAMILY LOOK)
    # ============================================================

    background_color = colors.HexColor("#E6D3B3")
    text_color = colors.HexColor("#5C3D23")

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

    drawing = svg2rlg(str(map_svg_path))

    scale_x = inner_w / drawing.width
    scale_y = inner_h / drawing.height

    drawing.scale(scale_x, scale_y)
    drawing.width *= scale_x
    drawing.height *= scale_y

    renderPDF.draw(drawing, c, inner_x, inner_y)

    # ============================================================
    # TYPOGRAPHY
    # ============================================================

    project_root = Path(__file__).resolve().parents[2]
    garamond_path = project_root / "Fonts" / "EBGaramond-Regular.ttf"

    title_font = "Helvetica"
    subtitle_font = "Helvetica"

    if garamond_path.exists():
        pdfmetrics.registerFont(
            TTFont("EBGaramond", str(garamond_path))
        )
        title_font = "EBGaramond"
        subtitle_font = "EBGaramond"

    title_size = inner_h * 0.055
    subtitle_size = title_size * 0.35

    c.setFillColor(text_color)

    # Title
    c.setFont(title_font, title_size)

    title_text = title.upper()
    title_width = pdfmetrics.stringWidth(
        title_text, title_font, title_size
    )

    c.drawString(
        (width_pt - title_width) / 2,
        margin * 1.1,
        title_text,
    )

    # Subtitle
    c.setFont(subtitle_font, subtitle_size)

    subtitle_text = subtitle.upper()
    subtitle_width = pdfmetrics.stringWidth(
        subtitle_text, subtitle_font, subtitle_size
    )

    c.drawString(
        (width_pt - subtitle_width) / 2,
        margin * 0.6,
        subtitle_text,
    )

    # ============================================================
    # FINALIZE
    # ============================================================

    c.showPage()
    c.save()

    return LayoutResult(output_pdf=output_pdf)