from __future__ import annotations

from io import BytesIO
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from reportlab.graphics import renderPDF
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from svglib.svglib import svg2rlg

try:
    import cairosvg  # type: ignore[import-not-found]
except Exception:
    cairosvg = None


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


@dataclass(frozen=True)
class LayoutBox:
    x_cm: float
    y_cm: float
    width_cm: float
    height_cm: float

    @property
    def center_x_cm(self) -> float:
        return self.x_cm + (self.width_cm / 2)

    @property
    def center_y_cm(self) -> float:
        return self.y_cm + (self.height_cm / 2)


@dataclass(frozen=True)
class PosterLayout:
    width_cm: float
    height_cm: float
    left_margin_cm: float
    right_margin_cm: float
    top_margin_cm: float
    bottom_margin_cm: float
    map_box: LayoutBox
    title_box: LayoutBox
    subtitle_box: LayoutBox
    coordinates_box: LayoutBox
    custom_text_box: LayoutBox

    @property
    def visible_width_cm(self) -> float:
        return self.map_box.width_cm

    @property
    def visible_height_cm(self) -> float:
        return self.map_box.height_cm

    @property
    def visible_aspect_ratio(self) -> float:
        return self.visible_width_cm / self.visible_height_cm

    def map_viewport_half_sizes_m(self, extent_m: float) -> tuple[float, float]:
        half_height_m = float(extent_m)
        half_width_m = half_height_m * self.visible_aspect_ratio
        return half_width_m, half_height_m


@dataclass(frozen=True)
class PosterTheme:
    background_color: str
    passepartout_color: str
    title_color: str
    subtitle_color: str
    coordinates_color: str
    custom_text_color: str
    title_font_family: str
    subtitle_font_family: str
    body_font_family: str
    title_scale: float = 0.42
    subtitle_scale: float = 0.30
    coordinates_scale: float = 0.24
    custom_text_scale: float = 0.22
    title_align: str = "center"
    subtitle_align: str = "center"
    coordinates_align: str = "center"
    custom_text_align: str = "center"
    subtitle_letter_spacing_pt: float = 0.0
    text_padding_cm: float = 0.18


@dataclass(frozen=True)
class PosterCompositionResult:
    output_svg: Path
    output_png: Path
    output_pdf: Optional[Path] = None


def build_poster_layout(width_cm: float, height_cm: float) -> PosterLayout:
    short_side_cm = min(width_cm, height_cm)
    side_margin_cm = short_side_cm * 0.04
    top_margin_cm = side_margin_cm
    bottom_margin_cm = height_cm * 0.10

    visible_width_cm = width_cm - (side_margin_cm * 2)
    visible_height_cm = height_cm - top_margin_cm - bottom_margin_cm

    map_box = LayoutBox(
        x_cm=side_margin_cm,
        y_cm=bottom_margin_cm,
        width_cm=visible_width_cm,
        height_cm=visible_height_cm,
    )

    gap_cm = bottom_margin_cm * 0.04
    content_height_cm = bottom_margin_cm - (gap_cm * 5)
    weights = (1.5, 0.9, 0.8, 0.8)
    total_weight = sum(weights)

    title_height_cm = content_height_cm * weights[0] / total_weight
    subtitle_height_cm = content_height_cm * weights[1] / total_weight
    coordinates_height_cm = content_height_cm * weights[2] / total_weight
    custom_text_height_cm = content_height_cm * weights[3] / total_weight

    cursor_y = gap_cm
    custom_text_box = LayoutBox(side_margin_cm, cursor_y, visible_width_cm, custom_text_height_cm)
    cursor_y += custom_text_height_cm + gap_cm

    coordinates_box = LayoutBox(side_margin_cm, cursor_y, visible_width_cm, coordinates_height_cm)
    cursor_y += coordinates_height_cm + gap_cm

    subtitle_box = LayoutBox(side_margin_cm, cursor_y, visible_width_cm, subtitle_height_cm)
    cursor_y += subtitle_height_cm + gap_cm

    title_box = LayoutBox(side_margin_cm, cursor_y, visible_width_cm, title_height_cm)

    return PosterLayout(
        width_cm=width_cm,
        height_cm=height_cm,
        left_margin_cm=side_margin_cm,
        right_margin_cm=side_margin_cm,
        top_margin_cm=top_margin_cm,
        bottom_margin_cm=bottom_margin_cm,
        map_box=map_box,
        title_box=title_box,
        subtitle_box=subtitle_box,
        coordinates_box=coordinates_box,
        custom_text_box=custom_text_box,
    )


def _font_size_pt(box: LayoutBox, scale: float) -> float:
    return box.height_cm * 28.3464567 * scale


def _svg_y_from_bottom(layout: PosterLayout, y_from_bottom_cm: float) -> float:
    return layout.height_cm - y_from_bottom_cm


def _svg_box_top_y(layout: PosterLayout, box: LayoutBox) -> float:
    return layout.height_cm - box.y_cm - box.height_cm


def _text_anchor(alignment: str) -> str:
    normalized = alignment.strip().lower()
    if normalized == "left":
        return "start"
    if normalized == "right":
        return "end"
    return "middle"


def _text_x_cm(box: LayoutBox, alignment: str, padding_cm: float) -> float:
    normalized = alignment.strip().lower()
    if normalized == "left":
        return box.x_cm + padding_cm
    if normalized == "right":
        return box.x_cm + box.width_cm - padding_cm
    return box.center_x_cm


def _append_svg_text(
    parent: ET.Element,
    *,
    layout: PosterLayout,
    box: LayoutBox,
    text: str,
    fill: str,
    font_family: str,
    font_size_pt: float,
    alignment: str,
    padding_cm: float,
    letter_spacing_pt: float = 0.0,
) -> None:
    if not text:
        return

    attrs = {
        "x": f"{_text_x_cm(box, alignment, padding_cm):.4f}",
        "y": f"{_svg_y_from_bottom(layout, box.center_y_cm):.4f}",
        "fill": fill,
        "font-family": font_family,
        "font-size": f"{font_size_pt:.2f}pt",
        "dominant-baseline": "middle",
        "text-anchor": _text_anchor(alignment),
    }
    if letter_spacing_pt:
        attrs["letter-spacing"] = f"{letter_spacing_pt:.2f}pt"

    node = ET.SubElement(parent, f"{{{SVG_NS}}}text", attrs)
    node.text = text


def _append_passepartout(svg_root: ET.Element, layout: PosterLayout, color: str) -> None:
    overlay = ET.SubElement(svg_root, f"{{{SVG_NS}}}g", {"id": "passepartout-layer"})

    ET.SubElement(overlay, f"{{{SVG_NS}}}rect", {
        "x": "0",
        "y": "0",
        "width": f"{layout.width_cm:.4f}",
        "height": f"{layout.top_margin_cm:.4f}",
        "fill": color,
        "stroke": "none",
    })
    ET.SubElement(overlay, f"{{{SVG_NS}}}rect", {
        "x": "0",
        "y": f"{layout.height_cm - layout.bottom_margin_cm:.4f}",
        "width": f"{layout.width_cm:.4f}",
        "height": f"{layout.bottom_margin_cm:.4f}",
        "fill": color,
        "stroke": "none",
    })

    side_height = layout.height_cm - layout.top_margin_cm - layout.bottom_margin_cm
    ET.SubElement(overlay, f"{{{SVG_NS}}}rect", {
        "x": "0",
        "y": f"{layout.top_margin_cm:.4f}",
        "width": f"{layout.left_margin_cm:.4f}",
        "height": f"{side_height:.4f}",
        "fill": color,
        "stroke": "none",
    })
    ET.SubElement(overlay, f"{{{SVG_NS}}}rect", {
        "x": f"{layout.width_cm - layout.right_margin_cm:.4f}",
        "y": f"{layout.top_margin_cm:.4f}",
        "width": f"{layout.right_margin_cm:.4f}",
        "height": f"{side_height:.4f}",
        "fill": color,
        "stroke": "none",
    })


@dataclass(frozen=True)
class TitleTypographySpec:
    x_cm: float
    y_cm: float
    title_height_cm: float
    text_anchor: str


def _resolve_monoton_font_path() -> Optional[Path]:
    current = Path(__file__).resolve()
    candidates = [
        current.parents[2] / "Fonts" / "Monoton-Regular.ttf",
        current.parents[3] / "Fonts" / "Monoton-Regular.ttf",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _derive_title_spec(layout: PosterLayout) -> TitleTypographySpec:
    # Title is backend-controlled: right edge aligned to map area's inner right edge,
    # positioned in the lower-right area of the bottom typography band.
    return TitleTypographySpec(
        x_cm=layout.map_box.x_cm + layout.map_box.width_cm,
        y_cm=layout.bottom_margin_cm * 0.50,
        title_height_cm=layout.bottom_margin_cm * 0.50,
        text_anchor="end",
    )


def _text_path_to_svg_d(path: TextPath, *, scale: float, offset_x_cm: float, offset_y_cm: float, layout: PosterLayout) -> str:
    d_parts: list[str] = []

    # Use polygonized outlines so all backends get deterministic M/L/Z paths.
    for poly in path.to_polygons():
        if len(poly) < 2:
            continue

        first_x_cm = (poly[0][0] * scale) + offset_x_cm
        first_y_bottom_cm = (poly[0][1] * scale) + offset_y_cm
        first_y_cm = _svg_y_from_bottom(layout, first_y_bottom_cm)
        d_parts.append(f"M {first_x_cm:.4f} {first_y_cm:.4f}")

        for vx, vy in poly[1:]:
            x_cm = (vx * scale) + offset_x_cm
            y_bottom_cm = (vy * scale) + offset_y_cm
            y_cm = _svg_y_from_bottom(layout, y_bottom_cm)
            d_parts.append(f"L {x_cm:.4f} {y_cm:.4f}")

        d_parts.append("Z")

    return " ".join(d_parts)


def _append_title_typography(
    svg_root: ET.Element,
    *,
    layout: PosterLayout,
    title: str,
    theme: PosterTheme,
) -> None:
    if not title:
        return

    font_path = _resolve_monoton_font_path()
    if font_path is None:
        return

    spec = _derive_title_spec(layout)
    title_path = TextPath((0, 0), title, prop=FontProperties(fname=str(font_path)), size=1)
    bbox = title_path.get_extents()
    if bbox.height <= 0:
        return

    scale = spec.title_height_cm / bbox.height
    title_width_cm = bbox.width * scale
    title_height_cm = bbox.height * scale

    if spec.text_anchor == "end":
        offset_x_cm = spec.x_cm - title_width_cm - (bbox.x0 * scale)
    elif spec.text_anchor == "middle":
        offset_x_cm = spec.x_cm - (title_width_cm / 2) - (bbox.x0 * scale)
    else:
        offset_x_cm = spec.x_cm - (bbox.x0 * scale)

    bottom_y_cm = (spec.y_cm - (title_height_cm / 2)) - (bbox.y0 * scale)
    path_d = _text_path_to_svg_d(
        title_path,
        scale=scale,
        offset_x_cm=offset_x_cm,
        offset_y_cm=bottom_y_cm,
        layout=layout,
    )

    typography = ET.SubElement(svg_root, f"{{{SVG_NS}}}g", {"id": "typography-layer"})
    ET.SubElement(
        typography,
        f"{{{SVG_NS}}}path",
        {
            "d": path_d,
            "fill": theme.title_color,
            "stroke": "none",
            "id": "title-text",
        },
    )


def _compose_svg_document(
    *,
    layout: PosterLayout,
    map_svg_path: Path,
    title: str,
    subtitle: str,
    coordinates: Optional[str],
    custom_text: Optional[str],
    theme: PosterTheme,
) -> str:
    source_root = ET.parse(map_svg_path).getroot()
    svg_root = ET.Element(f"{{{SVG_NS}}}svg", {
        "width": f"{layout.width_cm:.4f}cm",
        "height": f"{layout.height_cm:.4f}cm",
        "viewBox": f"0 0 {layout.width_cm:.4f} {layout.height_cm:.4f}",
        "version": "1.1",
    })

    ET.SubElement(svg_root, f"{{{SVG_NS}}}rect", {
        "x": "0",
        "y": "0",
        "width": f"{layout.width_cm:.4f}",
        "height": f"{layout.height_cm:.4f}",
        "fill": theme.background_color,
        "stroke": "none",
        "id": "background-layer",
    })

    embedded_svg = ET.SubElement(svg_root, f"{{{SVG_NS}}}svg", {
        "x": f"{layout.map_box.x_cm:.4f}",
        "y": f"{_svg_box_top_y(layout, layout.map_box):.4f}",
        "width": f"{layout.map_box.width_cm:.4f}",
        "height": f"{layout.map_box.height_cm:.4f}",
        "overflow": "hidden",
        "preserveAspectRatio": "xMidYMid meet",
        "viewBox": source_root.get("viewBox") or f"0 0 {source_root.get('width', layout.map_box.width_cm)} {source_root.get('height', layout.map_box.height_cm)}",
        "id": "map-layer",
    })

    for key, value in source_root.attrib.items():
        if key in {"width", "height", "x", "y", "viewBox"}:
            continue
        embedded_svg.set(key, value)

    for child in list(source_root):
        embedded_svg.append(deepcopy(child))

    _append_passepartout(svg_root, layout, theme.passepartout_color)
    _append_title_typography(
        svg_root,
        layout=layout,
        title=title,
        theme=theme,
    )

    return ET.tostring(svg_root, encoding="unicode")


def svg_to_png(*, svg_path: Path, output_png: Path, dpi: int = 96) -> None:
    """Rasterise the composed poster SVG to PNG. No layout recalculation."""
    drawing = svg2rlg(str(svg_path))
    try:
        from reportlab import rl_config

        # Prefer native backend first; some environments auto-pick rlPyCairo.
        rl_config.renderPMBackend = "_renderPM"
        from reportlab.graphics import renderPM

        renderPM.drawToFile(drawing, str(output_png), fmt="PNG", dpi=dpi)
        return
    except Exception:
        pass

    if cairosvg is not None:
        try:
            cairosvg.svg2png(
                url=str(svg_path),
                write_to=str(output_png),
                output_width=int(drawing.width),
                output_height=int(drawing.height),
            )
            return
        except Exception:
            pass

    try:
        import fitz  # PyMuPDF

        # Keep PNG fallback consistent with PDF geometry: first build a PDF in-memory
        # using the same SVG->PDF converter path, then rasterize that PDF.
        width_cm, height_cm = _read_svg_canvas_cm(svg_path)
        pdf_bytes = _svg_to_pdf_bytes(
            svg_path=svg_path,
            layout=PosterLayout(
                width_cm=width_cm,
                height_cm=height_cm,
                left_margin_cm=0,
                right_margin_cm=0,
                top_margin_cm=0,
                bottom_margin_cm=0,
                map_box=LayoutBox(0, 0, width_cm, height_cm),
                title_box=LayoutBox(0, 0, 0, 0),
                subtitle_box=LayoutBox(0, 0, 0, 0),
                coordinates_box=LayoutBox(0, 0, 0, 0),
                custom_text_box=LayoutBox(0, 0, 0, 0),
            ),
        )
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        pix = page.get_pixmap(dpi=dpi)
        pix.save(str(output_png))
        doc.close()
        return
    except Exception:
        pass

    raise RuntimeError(
        "PNG export backend unavailable. Install reportlab _renderPM backend, Cairo runtime, or PyMuPDF."
    )


def svg_to_pdf(*, svg_path: Path, output_pdf: Path, layout: PosterLayout) -> None:
    """Thin SVG → PDF export. The composed SVG is the single source of truth.
    No layout is recalculated here.
    """
    output_pdf.write_bytes(_svg_to_pdf_bytes(svg_path=svg_path, layout=layout))


def _svg_to_pdf_bytes(*, svg_path: Path, layout: PosterLayout) -> bytes:
    """Convert composed SVG to PDF bytes with optional cairo backend and stable fallback."""
    if cairosvg is not None:
        try:
            return cairosvg.svg2pdf(
                url=str(svg_path),
                output_width=layout.width_cm * cm,
                output_height=layout.height_cm * cm,
            )
        except Exception:
            # Fallback when Cairo runtime libraries are unavailable.
            pass

    drawing = svg2rlg(str(svg_path))
    page_width_pt = layout.width_cm * cm
    page_height_pt = layout.height_cm * cm
    scale_x = page_width_pt / drawing.width
    scale_y = page_height_pt / drawing.height
    scale = min(scale_x, scale_y)
    drawing.scale(scale, scale)
    buffer = BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=(page_width_pt, page_height_pt))
    renderPDF.draw(drawing, pdf_canvas, 0, 0)
    pdf_canvas.showPage()
    pdf_canvas.save()
    return buffer.getvalue()


def _read_svg_canvas_cm(svg_path: Path) -> tuple[float, float]:
    root = ET.parse(svg_path).getroot()
    width_raw = root.get("width", "0").strip().lower().replace("cm", "")
    height_raw = root.get("height", "0").strip().lower().replace("cm", "")
    return float(width_raw), float(height_raw)


def compose_poster_outputs(
    *,
    layout: PosterLayout,
    map_svg_path: Path,
    output_dir: Path,
    filename_prefix: str,
    title: str,
    subtitle: str,
    coordinates: Optional[str],
    custom_text: Optional[str],
    theme: PosterTheme,
    export_pdf: bool = True,
) -> PosterCompositionResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    output_svg = output_dir / f"{filename_prefix}.svg"
    output_svg.write_text(
        _compose_svg_document(
            layout=layout,
            map_svg_path=map_svg_path,
            title=title,
            subtitle=subtitle,
            coordinates=coordinates,
            custom_text=custom_text,
            theme=theme,
        ),
        encoding="utf-8",
    )

    output_png = output_dir / f"{filename_prefix}.png"
    svg_to_png(svg_path=output_svg, output_png=output_png)

    output_pdf: Optional[Path] = None
    if export_pdf:
        output_pdf = output_dir / f"{filename_prefix}.pdf"
        svg_to_pdf(svg_path=output_svg, output_pdf=output_pdf, layout=layout)

    return PosterCompositionResult(output_svg=output_svg, output_png=output_png, output_pdf=output_pdf)