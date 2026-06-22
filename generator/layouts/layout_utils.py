from __future__ import annotations

from io import BytesIO
import base64
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from matplotlib.font_manager import FontProperties
from matplotlib.path import Path as MplPath
from matplotlib.textpath import TextPath
import numpy as np
from PIL import Image
from reportlab.graphics import renderPDF
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
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
    bottom_fade_color: Optional[str] = None
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
    bottom_fade: bool = False
    center_title: bool = False
    block_engine_layout: bool = False


@dataclass(frozen=True)
class PosterCompositionResult:
    output_svg: Path
    output_png: Path
    output_pdf: Optional[Path] = None


def build_poster_layout(width_cm: float, height_cm: float, uniform_margins: bool = False) -> PosterLayout:
    short_side_cm = min(width_cm, height_cm)
    side_margin_cm = short_side_cm * 0.04
    top_margin_cm = side_margin_cm
    bottom_margin_cm = side_margin_cm if uniform_margins else height_cm * 0.10

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


def _append_passepartout(svg_root: ET.Element, layout: PosterLayout, color: str, bottom_fade: bool = False, fade_color: Optional[str] = None) -> None:
    overlay = ET.SubElement(svg_root, f"{{{SVG_NS}}}g", {"id": "passepartout-layer"})
    resolved_fade_color = fade_color or color

    # Top strip
    ET.SubElement(overlay, f"{{{SVG_NS}}}rect", {
        "x": "0",
        "y": "0",
        "width": f"{layout.width_cm:.4f}",
        "height": f"{layout.top_margin_cm:.4f}",
        "fill": color,
        "stroke": "none",
    })

    # Bottom: use an embedded raster alpha gradient to avoid visible banding
    # while staying compatible with svglib/reportlab image rendering.
    if bottom_fade:
        fade_height = layout.height_cm * 0.40
        fade_y = layout.height_cm - layout.bottom_margin_cm - fade_height
        img_w = 32
        img_h = 1200
        rgb = tuple(int(resolved_fade_color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        gradient = np.zeros((img_h, img_w, 4), dtype=np.uint8)
        gradient[:, :, 0] = rgb[0]
        gradient[:, :, 1] = rgb[1]
        gradient[:, :, 2] = rgb[2]
        for y in range(img_h):
            t = y / max(1, img_h - 1)
            alpha = int(min(1.0, t ** 2.2) * 255)
            gradient[y, :, 3] = alpha

        image = Image.fromarray(gradient, mode="RGBA")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

        ET.SubElement(overlay, f"{{{SVG_NS}}}image", {
            "x": f"{layout.map_box.x_cm:.4f}",
            "y": f"{fade_y:.4f}",
            "width": f"{layout.map_box.width_cm:.4f}",
            "height": f"{fade_height:.4f}",
            "preserveAspectRatio": "none",
            "href": data_uri,
        })
    else:
        ET.SubElement(overlay, f"{{{SVG_NS}}}rect", {
            "x": "0",
            "y": f"{layout.height_cm - layout.bottom_margin_cm:.4f}",
            "width": f"{layout.width_cm:.4f}",
            "height": f"{layout.bottom_margin_cm:.4f}",
            "fill": color,
            "stroke": "none",
        })

    # Side strips stop at the map area's bottom edge so the lower passepartout stays open for the fade zone.
    side_bottom_y = layout.height_cm - layout.bottom_margin_cm if bottom_fade else layout.height_cm - layout.bottom_margin_cm
    side_height = side_bottom_y - layout.top_margin_cm
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


def _resolve_montserrat_font_path(weight: str = "Bold") -> Optional[Path]:
    current = Path(__file__).resolve()
    candidates = [
        current.parents[1] / "Fonts" / f"Montserrat-{weight}.ttf",
        current.parents[2] / "Fonts" / f"Montserrat-{weight}.ttf",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _resolve_mathilde_font_path() -> Optional[Path]:
    current = Path(__file__).resolve()
    candidates = [
        current.parents[2] / "Fonts" / "Mathilde.ttf",
        current.parents[2] / "Fonts" / "Mathilde.otf",
        current.parents[2] / "Fonts" / "Mathilde-Regular.ttf",
        current.parents[2] / "Fonts" / "Mathilde-Regular.otf",
        current.parents[3] / "Fonts" / "Mathilde.ttf",
        current.parents[3] / "Fonts" / "Mathilde.otf",
        current.parents[3] / "Fonts" / "Mathilde-Regular.ttf",
        current.parents[3] / "Fonts" / "Mathilde-Regular.otf",
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

    def _pt(x: float, y: float) -> tuple[float, float]:
        x_cm = (x * scale) + offset_x_cm
        y_bottom_cm = (y * scale) + offset_y_cm
        return x_cm, _svg_y_from_bottom(layout, y_bottom_cm)

    for verts, code in path.iter_segments(curves=True, simplify=False):
        if code == MplPath.MOVETO:
            x, y = _pt(verts[0], verts[1])
            d_parts.append(f"M {x:.4f} {y:.4f}")
        elif code == MplPath.LINETO:
            x, y = _pt(verts[0], verts[1])
            d_parts.append(f"L {x:.4f} {y:.4f}")
        elif code == MplPath.CURVE3:
            x1, y1 = _pt(verts[0], verts[1])
            x2, y2 = _pt(verts[2], verts[3])
            d_parts.append(f"Q {x1:.4f} {y1:.4f} {x2:.4f} {y2:.4f}")
        elif code == MplPath.CURVE4:
            x1, y1 = _pt(verts[0], verts[1])
            x2, y2 = _pt(verts[2], verts[3])
            x3, y3 = _pt(verts[4], verts[5])
            d_parts.append(f"C {x1:.4f} {y1:.4f} {x2:.4f} {y2:.4f} {x3:.4f} {y3:.4f}")
        elif code == MplPath.CLOSEPOLY:
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


def _append_block_engine_typography(
    svg_root: ET.Element,
    *,
    layout: PosterLayout,
    title: str,
    subtitle: str,
    coordinates: Optional[str],
    theme: PosterTheme,
) -> None:
    """Append typography for block and building engines (bottom-right aligned).
    
    Args:
        svg_root: SVG root element to append to
        layout: Poster layout with dimensions
        title: Main title (city name)
        subtitle: Unused for block engine typography
        coordinates: Optional coordinates string rendered below the city name
        theme: Theme with colors and font settings
    """
    if not title and not coordinates:
        return

    typo = ET.SubElement(svg_root, f"{{{SVG_NS}}}g", {"id": "block-engine-typography"})
    
    # Positioning in the bottom band (right-aligned)
    band_height_cm = layout.bottom_margin_cm
    right_edge_cm = layout.width_cm - layout.right_margin_cm
    right_padding_cm = 0.3
    
    if theme.title_font_family.lower() == "mathilde":
        title_font_path = _resolve_mathilde_font_path() or _resolve_monoton_font_path()
    else:
        title_font_path = _resolve_monoton_font_path()
    subtitle_font_path = None
    montserrat_medium_path = None
    try:
        centaurea_path = Path(__file__).resolve().parents[2] / "Fonts" / "CentaureaDemo.ttf"
        if centaurea_path.exists():
            subtitle_font_path = centaurea_path
        mm_path = Path(__file__).resolve().parents[2] / "Fonts" / "Montserrat-Medium.ttf"
        if mm_path.exists():
            montserrat_medium_path = mm_path
    except:
        pass
    
    # Scale the two-line typography block to the upper 50% of the bottom band.
    # Keep only the title/coordinates size ratio fixed; derive actual sizes from the
    # available vertical space so the layout stays consistent across all block sizes.
    base_title_ratio = 0.2925
    base_coord_ratio = 0.1265 * 0.70 * 0.80
    base_gap_ratio = base_coord_ratio * 0.40
    upper_half_height_cm = band_height_cm * 0.50
    top_inset_cm = band_height_cm * 0.07

    if coordinates:
        total_ratio = base_title_ratio + base_gap_ratio + base_coord_ratio
        scale_factor = upper_half_height_cm / (band_height_cm * total_ratio)
        title_height_cm = band_height_cm * base_title_ratio * scale_factor
        coord_height_cm = band_height_cm * base_coord_ratio * scale_factor
        edge_gap_title_coord_cm = band_height_cm * base_gap_ratio * scale_factor

        stack_top_cm = band_height_cm - top_inset_cm
        title_cy_from_bottom = stack_top_cm - (title_height_cm / 2)
        coord_cy_from_bottom = (
            title_cy_from_bottom
            - (title_height_cm / 2)
            - edge_gap_title_coord_cm
            - (coord_height_cm / 2)
        )
    else:
        title_height_cm = upper_half_height_cm
        coord_height_cm = 0.0
        title_cy_from_bottom = (band_height_cm - top_inset_cm) - (title_height_cm / 2)
        coord_cy_from_bottom = 0.0
    
    # Draw title
    if title and title_font_path:
        title_path = TextPath((0, 0), title, prop=FontProperties(fname=str(title_font_path)), size=1)
        bbox = title_path.get_extents()
        if bbox.height > 0:
            scale = title_height_cm / bbox.height
            title_width_cm = bbox.width * scale
            offset_x_cm = (right_edge_cm - right_padding_cm) - title_width_cm - (bbox.x0 * scale)
            bottom_y_cm = title_cy_from_bottom - (bbox.height * scale / 2) - (bbox.y0 * scale)
            path_d = _text_path_to_svg_d(title_path, scale=scale, offset_x_cm=offset_x_cm, offset_y_cm=bottom_y_cm, layout=layout)
            ET.SubElement(typo, f"{{{SVG_NS}}}path", {
                "d": path_d,
                "fill": theme.title_color,
                "stroke": "none",
                "id": "block-title-text",
            })
    
    # Draw coordinates directly below the title (Montserrat-Medium, subtitle-sized)
    coord_font_path = montserrat_medium_path or subtitle_font_path
    if coordinates and coord_font_path:
        coord_path = TextPath((0, 0), coordinates, prop=FontProperties(fname=str(coord_font_path)), size=1)
        c_bbox = coord_path.get_extents()
        if c_bbox.height > 0:
            c_scale = coord_height_cm / c_bbox.height
            coord_width_cm = c_bbox.width * c_scale
            c_offset_x = (right_edge_cm - right_padding_cm) - coord_width_cm - (c_bbox.x0 * c_scale)
            c_bottom_y = coord_cy_from_bottom - (c_bbox.height * c_scale / 2) - (c_bbox.y0 * c_scale)
            path_d = _text_path_to_svg_d(coord_path, scale=c_scale, offset_x_cm=c_offset_x, offset_y_cm=c_bottom_y, layout=layout)
            ET.SubElement(typo, f"{{{SVG_NS}}}path", {
                "d": path_d,
                "fill": theme.coordinates_color,
                "stroke": "none",
                "id": "block-coordinates-text",
            })


def _append_line_engine_typography(
    svg_root: ET.Element,
    *,
    layout: PosterLayout,
    title: str,
    subtitle: str,
    theme: PosterTheme,
) -> None:
    typo = ET.SubElement(svg_root, f"{{{SVG_NS}}}g", {"id": "line-engine-typography"})

    title_font_path = _resolve_montserrat_font_path("Bold") or _resolve_monoton_font_path()
    fade_zone_cm = layout.height_cm * 0.40 + layout.bottom_margin_cm
    map_cx = layout.map_box.x_cm + layout.map_box.width_cm / 2
    title_height_cm = layout.height_cm * 0.050
    sub_height_cm = layout.height_cm * 0.018
    line_gap_cm = layout.height_cm * 0.004
    title_cy = fade_zone_cm * 0.25
    subtitle_cy = title_cy - ((title_height_cm + sub_height_cm) / 2) - line_gap_cm

    # ---- TITLE: Montserrat Bold, centered ----
    if title_font_path and title:
        title_text = title.upper()
        cx = map_cx
        cy = title_cy

        tp = TextPath((0, 0), title_text, prop=FontProperties(fname=str(title_font_path)), size=1)
        bbox = tp.get_extents()
        if bbox.height > 0:
            scale = title_height_cm / bbox.height
            w = bbox.width * scale
            offset_x_cm = cx - (w / 2) - (bbox.x0 * scale)
            bottom_y_cm = cy - (bbox.height * scale / 2) - (bbox.y0 * scale)
            path_d = _text_path_to_svg_d(tp, scale=scale, offset_x_cm=offset_x_cm, offset_y_cm=bottom_y_cm, layout=layout)
            ET.SubElement(typo, f"{{{SVG_NS}}}path", {
                "d": path_d,
                "fill": theme.title_color,
                "stroke": "none",
                "id": "title-text",
            })

    # ---- SUBTITLE: Montserrat Medium, centered, with flanking lines ----
    sub_font_path = _resolve_montserrat_font_path("Medium") or title_font_path
    if sub_font_path and subtitle:
        sub_text = subtitle.upper()
        cx = map_cx
        cy = subtitle_cy

        sp = TextPath((0, 0), sub_text, prop=FontProperties(fname=str(sub_font_path)), size=1)
        s_bbox = sp.get_extents()
        if s_bbox.height > 0:
            s_scale = sub_height_cm / s_bbox.height
            sw = s_bbox.width * s_scale
            s_offset_x = cx - (sw / 2) - (s_bbox.x0 * s_scale)
            s_bottom_y = cy - (s_bbox.height * s_scale / 2) - (s_bbox.y0 * s_scale)
            path_d = _text_path_to_svg_d(sp, scale=s_scale, offset_x_cm=s_offset_x, offset_y_cm=s_bottom_y, layout=layout)
            ET.SubElement(typo, f"{{{SVG_NS}}}path", {
                "d": path_d,
                "fill": theme.subtitle_color,
                "stroke": "none",
                "id": "subtitle-text",
            })

            # Horizontal lines flanking the subtitle
            spacer_path = TextPath((0, 0), "MMM", prop=FontProperties(fname=str(sub_font_path)), size=1)
            spacer_bbox = spacer_path.get_extents()
            gap_cm = max(sw * 0.06, spacer_bbox.width * s_scale)
            edge_margin_cm = layout.width_cm * 0.06
            sub_svg_y = _svg_y_from_bottom(layout, cy)
            stroke_w = layout.height_cm * 0.0018

            lx1 = layout.left_margin_cm + edge_margin_cm
            lx2 = cx - sw / 2 - gap_cm
            rx1 = cx + sw / 2 + gap_cm
            rx2 = layout.width_cm - layout.right_margin_cm - edge_margin_cm

            if lx2 > lx1:
                ET.SubElement(typo, f"{{{SVG_NS}}}line", {
                    "x1": f"{lx1:.4f}", "y1": f"{sub_svg_y:.4f}",
                    "x2": f"{lx2:.4f}", "y2": f"{sub_svg_y:.4f}",
                    "stroke": theme.subtitle_color,
                    "stroke-width": f"{stroke_w:.4f}",
                })
            if rx2 > rx1:
                ET.SubElement(typo, f"{{{SVG_NS}}}line", {
                    "x1": f"{rx1:.4f}", "y1": f"{sub_svg_y:.4f}",
                    "x2": f"{rx2:.4f}", "y2": f"{sub_svg_y:.4f}",
                    "stroke": theme.subtitle_color,
                    "stroke-width": f"{stroke_w:.4f}",
                })


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

    _append_passepartout(
        svg_root,
        layout,
        theme.passepartout_color,
        bottom_fade=theme.bottom_fade,
        fade_color=theme.bottom_fade_color,
    )
    if theme.center_title:
        _append_line_engine_typography(svg_root, layout=layout, title=title, subtitle=subtitle, theme=theme)
    elif theme.block_engine_layout:
        _append_block_engine_typography(svg_root, layout=layout, title=title, subtitle=subtitle, coordinates=coordinates, theme=theme)
    else:
        _append_title_typography(svg_root, layout=layout, title=title, theme=theme)

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


def _register_font_if_available(font_name: str, font_path: Optional[Path]) -> str:
    if font_path is None or not font_path.exists():
        return "Helvetica"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    return font_name


def _build_fade_image(color_hex: str, img_w: int = 64, img_h: int = 1600) -> ImageReader:
    rgb = tuple(int(color_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    gradient = np.zeros((img_h, img_w, 4), dtype=np.uint8)
    gradient[:, :, 0] = rgb[0]
    gradient[:, :, 1] = rgb[1]
    gradient[:, :, 2] = rgb[2]
    for y in range(img_h):
        t = y / max(1, img_h - 1)
        alpha = int(min(1.0, t ** 2.2) * 255)
        gradient[y, :, 3] = alpha
    image = Image.fromarray(gradient, mode="RGBA")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return ImageReader(buffer)


def _compose_line_engine_pdf_bytes(
    *,
    layout: PosterLayout,
    map_svg_path: Path,
    title: str,
    subtitle: str,
    theme: PosterTheme,
) -> bytes:
    page_width_pt = layout.width_cm * cm
    page_height_pt = layout.height_cm * cm
    buffer = BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=(page_width_pt, page_height_pt))

    pdf_canvas.setFillColor(colors.HexColor(theme.passepartout_color))
    pdf_canvas.rect(0, 0, page_width_pt, page_height_pt, fill=1, stroke=0)

    drawing = svg2rlg(str(map_svg_path))
    map_width_pt = layout.map_box.width_cm * cm
    map_height_pt = layout.map_box.height_cm * cm
    scale_x = map_width_pt / drawing.width
    scale_y = map_height_pt / drawing.height
    drawing.scale(scale_x, scale_y)
    renderPDF.draw(
        drawing,
        pdf_canvas,
        layout.map_box.x_cm * cm,
        layout.map_box.y_cm * cm,
    )

    fade_height_pt = layout.height_cm * 0.40 * cm
    fade_overlay = _build_fade_image(theme.bottom_fade_color or theme.passepartout_color)
    pdf_canvas.drawImage(
        fade_overlay,
        layout.map_box.x_cm * cm,
        layout.bottom_margin_cm * cm,
        width=map_width_pt,
        height=fade_height_pt,
        mask="auto",
    )

    montserrat_bold = _register_font_if_available("MontserratBoldPoster", _resolve_montserrat_font_path("Bold"))
    montserrat_medium = _register_font_if_available("MontserratMediumPoster", _resolve_montserrat_font_path("Medium"))

    text_color = colors.HexColor(theme.title_color)
    pdf_canvas.setFillColor(text_color)
    pdf_canvas.setStrokeColor(text_color)

    fade_zone_cm = layout.height_cm * 0.40 + layout.bottom_margin_cm
    title_size_pt = layout.height_cm * 0.050 * cm
    subtitle_size_pt = layout.height_cm * 0.018 * cm
    center_x_pt = (layout.map_box.x_cm + layout.map_box.width_cm / 2) * cm
    line_gap_pt = layout.height_cm * 0.004 * cm
    title_cy_pt = fade_zone_cm * 0.25 * cm
    subtitle_cy_pt = title_cy_pt - ((title_size_pt + subtitle_size_pt) / 2) - line_gap_pt
    title_y_pt = title_cy_pt - (title_size_pt * 0.28)
    subtitle_y_pt = subtitle_cy_pt - (subtitle_size_pt * 0.22)

    title_text = title.upper()
    pdf_canvas.setFont(montserrat_bold, title_size_pt)
    title_width_pt = pdfmetrics.stringWidth(title_text, montserrat_bold, title_size_pt)
    pdf_canvas.drawString(center_x_pt - (title_width_pt / 2), title_y_pt, title_text)

    subtitle_text = subtitle.upper()
    pdf_canvas.setFont(montserrat_medium, subtitle_size_pt)
    subtitle_width_pt = pdfmetrics.stringWidth(subtitle_text, montserrat_medium, subtitle_size_pt)
    pdf_canvas.drawString(center_x_pt - (subtitle_width_pt / 2), subtitle_y_pt, subtitle_text)

    gap_pt = max(subtitle_width_pt * 0.06, pdfmetrics.stringWidth("MMM", montserrat_medium, subtitle_size_pt))
    edge_margin_pt = layout.width_cm * 0.06 * cm
    line_y_pt = subtitle_y_pt + (subtitle_size_pt * 0.45)
    stroke_w_pt = layout.height_cm * 0.0018 * cm
    left_margin_pt = layout.left_margin_cm * cm
    right_margin_pt = page_width_pt - (layout.right_margin_cm * cm)
    left_line_x1 = left_margin_pt + edge_margin_pt
    left_line_x2 = center_x_pt - (subtitle_width_pt / 2) - gap_pt
    right_line_x1 = center_x_pt + (subtitle_width_pt / 2) + gap_pt
    right_line_x2 = right_margin_pt - edge_margin_pt
    pdf_canvas.setLineWidth(stroke_w_pt)
    if left_line_x2 > left_line_x1:
        pdf_canvas.line(left_line_x1, line_y_pt, left_line_x2, line_y_pt)
    if right_line_x2 > right_line_x1:
        pdf_canvas.line(right_line_x1, line_y_pt, right_line_x2, line_y_pt)

    pdf_canvas.showPage()
    pdf_canvas.save()
    return buffer.getvalue()


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
    output_pdf: Optional[Path] = None

    if theme.center_title and theme.bottom_fade:
        pdf_bytes = _compose_line_engine_pdf_bytes(
            layout=layout,
            map_svg_path=map_svg_path,
            title=title,
            subtitle=subtitle,
            theme=theme,
        )
        if export_pdf:
            output_pdf = output_dir / f"{filename_prefix}.pdf"
            output_pdf.write_bytes(pdf_bytes)

        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        pix = page.get_pixmap(dpi=96)
        pix.save(str(output_png))
        doc.close()
    else:
        svg_to_png(svg_path=output_svg, output_png=output_png)
        if export_pdf:
            output_pdf = output_dir / f"{filename_prefix}.pdf"
            svg_to_pdf(svg_path=output_svg, output_pdf=output_pdf, layout=layout)

    return PosterCompositionResult(output_svg=output_svg, output_png=output_png, output_pdf=output_pdf)