from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import csv
import math
from io import BytesIO

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

import fitz  # PyMuPDF

from generator.styles import DEFAULT_STARMAP_STYLE
from generator.nebula_background import make_nebula_background, NebulaParams


@dataclass(frozen=True)
class StarsRenderResult:
    output_pdf: Path
    output_preview_png: Path


# =============================================================================
# IO / Preview
# =============================================================================

def _pdf_to_preview_png(pdf_path: Path, png_path: Path, dpi: int = 350) -> None:
    doc = fitz.open(str(pdf_path))
    page = doc.load_page(0)
    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    pix.save(str(png_path))
    doc.close()


def _load_star_catalog_csv(csv_path: Path):
    stars = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                stars.append(
                    {
                        "ra_deg": float(row["ra_deg"]),
                        "dec_deg": float(row["dec_deg"]),
                        "mag": float(row["mag"]),
                        "name": (row.get("name") or "").strip(),
                    }
                )
            except (KeyError, ValueError):
                continue
    return stars


# =============================================================================
# Helpers
# =============================================================================

def _safe_set_alpha(c, fill: float | None = None, stroke: float | None = None) -> None:
    if fill is not None:
        try:
            c.setFillAlpha(fill)
        except Exception:
            pass
    if stroke is not None:
        try:
            c.setStrokeAlpha(stroke)
        except Exception:
            pass


def _paint_page_white(c, w_pt: float, h_pt: float) -> None:
    st = DEFAULT_STARMAP_STYLE
    c.saveState()
    _safe_set_alpha(c, fill=1.0, stroke=1.0)
    c.setFillColorRGB(*st.page_rgb)
    c.setStrokeColorRGB(*st.page_rgb)
    c.rect(0, 0, w_pt, h_pt, stroke=0, fill=1)
    c.restoreState()


def _clip_to_circle(c, cx: float, cy: float, r: float) -> None:
    p = c.beginPath()
    p.circle(cx, cy, r)
    c.clipPath(p, stroke=0, fill=0)


def _inside_unit_disk(x: float, y: float) -> bool:
    return (x * x + y * y) <= 1.0


def _mag_to_radius_pt(mag: float, twinkle: float) -> float:
    """
    Halvány csillagok láthatóság:
    - enyhe gamma (t**0.45)
    - baseline emelve
    - minimum sugár a styles-ból
    """
    st = DEFAULT_STARMAP_STYLE

    mag = max(-1.5, min(6.0, mag))
    b = 10 ** (-0.4 * mag)
    b_min = 10 ** (-0.4 * 6.0)
    b_max = 10 ** (-0.4 * (-1.5))
    t = (b - b_min) / (b_max - b_min)
    t = max(0.0, min(1.0, t))

    t = t ** 0.45
    r = (1.05 + t * 3.10) * twinkle
    return max(st.star_min_radius_pt, r)


def draw_star_glow(c, x: float, y: float, r: float, rng: random.Random) -> None:
    st = DEFAULT_STARMAP_STYLE
    r1 = r * (2.2 + 0.4 * rng.random())
    r2 = r * (1.6 + 0.2 * rng.random())

    c.saveState()
    c.setFillColorRGB(*st.glow_rgb)
    _safe_set_alpha(c, fill=st.glow_alpha_1)
    c.circle(x, y, r1, stroke=0, fill=1)
    _safe_set_alpha(c, fill=st.glow_alpha_2)
    c.circle(x, y, r2, stroke=0, fill=1)
    c.restoreState()


def draw_star_core(c, x: float, y: float, r: float) -> None:
    """
    Core: alpha nélkül.
    A nagyon kicsiket négyzettel rajzoljuk, hogy biztosan látszódjanak raster preview-ban is.
    """
    st = DEFAULT_STARMAP_STYLE
    c.saveState()
    _safe_set_alpha(c, fill=1.0, stroke=1.0)
    c.setFillColorRGB(*st.star_rgb)

    if r < 1.10:
        s = max(1.25, r * 1.70)
        c.rect(x - s / 2.0, y - s / 2.0, s, s, stroke=0, fill=1)
    else:
        c.circle(x, y, r, stroke=0, fill=1)

    c.restoreState()


def draw_star_dust(
    *,
    c,
    rng: random.Random,
    count: int,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    band_angle: float,
) -> None:
    """
    Procedurális "dust": kerek, kevésbé fényes pontok.
    """
    st = DEFAULT_STARMAP_STYLE

    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    hw = (x1 - x0) / 2.0
    hh = (y1 - y0) / 2.0

    def to_unit(px: float, py: float) -> tuple[float, float]:
        return (px - cx) / hw, (py - cy) / hh

    c.saveState()
    c.setFillColorRGB(*st.star_rgb)
    _safe_set_alpha(c, fill=st.dust_alpha, stroke=1.0)

    for _ in range(count):
        while True:
            x = rng.uniform(x0, x1)
            y = rng.uniform(y0, y1)
            xu, yu = to_unit(x, y)
            d = abs(xu * math.sin(band_angle) - yu * math.cos(band_angle))
            p_band = math.exp(-(d / st.band_sigma) ** 2)
            if rng.random() < ((1.0 - st.dust_band_bias) + st.dust_band_bias * p_band):
                break

        s = rng.uniform(st.dust_min_size_pt, st.dust_max_size_pt)
        r = s * 0.55
        c.circle(x, y, r, stroke=0, fill=1)

    c.restoreState()


def draw_circle_shadow(c, cx: float, cy: float, r: float) -> None:
    """
    Very subtle fake "blurred" drop shadow with a few soft circles.
    """
    st = DEFAULT_STARMAP_STYLE
    steps = max(1, int(st.shadow_steps))

    c.saveState()
    c.setFillColorRGB(0.0, 0.0, 0.0)

    for i in range(steps):
        t = i / max(1, (steps - 1))
        alpha = st.shadow_alpha_max * (1.0 - t) * 0.65
        spread = st.shadow_spread_pt * (0.35 + 0.65 * t)

        _safe_set_alpha(c, fill=alpha)
        c.circle(
            cx + st.shadow_dx_pt,
            cy + st.shadow_dy_pt,
            r + spread,
            stroke=0,
            fill=1,
        )

    c.restoreState()


def _draw_centered_tracked(c, text: str, cx: float, y: float, font_name: str, font_size: float, tracking_pt: float) -> None:
    text = text or ""
    w = 0.0
    for ch in text:
        w += pdfmetrics.stringWidth(ch, font_name, font_size)
    if len(text) > 1:
        w += tracking_pt * (len(text) - 1)

    x = cx - w / 2.0
    c.setFont(font_name, font_size)
    for i, ch in enumerate(text):
        c.drawString(x, y, ch)
        x += pdfmetrics.stringWidth(ch, font_name, font_size)
        if i != len(text) - 1:
            x += tracking_pt


def _register_fonts(project_root: Path) -> dict:
    fonts_dir = project_root / "data" / "fonts"
    fonts = {"title": "Helvetica", "meta": "Helvetica"}

    love_path = fonts_dir / "LoveLight-Regular.ttf"
    if love_path.exists():
        try:
            pdfmetrics.registerFont(TTFont("LoveLight", str(love_path)))
            fonts["title"] = "LoveLight"
        except Exception:
            pass

    candidates = [
        ("Cormorant", "CormorantGaramond-Regular.ttf"),
        ("EBGaramond", "EBGaramond-Regular.ttf"),
        ("BarlowCondensed", "BarlowCondensed-Regular.ttf"),
        ("NotoSans", "NotoSans-Regular.ttf"),
        ("Inter", "Inter-Regular.ttf"),
    ]
    for name, fname in candidates:
        p = fonts_dir / fname
        if p.exists():
            try:
                pdfmetrics.registerFont(TTFont(name, str(p)))
                fonts["meta"] = name
                break
            except Exception:
                continue

    return fonts


def _portrait_type_scale(h_pt: float) -> float:
    """
    Tipó skála: 30x40 a baseline.
    Így a 21x30 automatikusan kisebb lesz, és az arány helyreáll.
    """
    base_h_pt_30x40 = (40.0 / 2.54) * 72.0
    s = h_pt / base_h_pt_30x40
    return max(0.72, min(1.08, s))


def _pil_to_imagereader_rgb(pil_img) -> ImageReader:
    """
    PIL -> ReportLab ImageReader (memóriában, fájl nélkül)
    """
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    buf = BytesIO()
    pil_img.save(buf, format="PNG", optimize=False)
    buf.seek(0)
    return ImageReader(buf)


def _make_nebula_reader_for_page(*, w_in: float, h_in: float, dpi: int, seed: int) -> ImageReader:
    w_px = max(32, int(round(w_in * dpi)))
    h_px = max(32, int(round(h_in * dpi)))

    # paramok már “referencia-közeli” alapértelmezéssel
    pil_bg = make_nebula_background(
        width_px=w_px,
        height_px=h_px,
        seed=seed,
        params=NebulaParams(
            base_darkness=0.58,  # sötétebb dominancia
            fog_strength=1.35,
            blotch_strength=0.80,
            lane_strength=0.38,
            grain_strength=0.24,
            vignette=0.48,
            final_blur=0.55,
        ),

    )

    return _pil_to_imagereader_rgb(pil_bg)


# =============================================================================
# Layouts
# =============================================================================

def _render_portrait_circle(
    *,
    c,
    w_pt: float,
    h_pt: float,
    w_in: float,
    h_in: float,
    dpi: int,
    rng: random.Random,
    fonts: dict,
    stars: list,
    cutoff_mag: float,
    enable_glow: bool,
    title: str,
    motto: str,
    location_name: str,
    date_text: str,
    lat: float,
    lon: float,
    nebula_reader: ImageReader,
) -> None:
    st = DEFAULT_STARMAP_STYLE

    _paint_page_white(c, w_pt, h_pt)

    side_clear = min(w_pt, h_pt) * st.portrait_side_clear_frac
    max_diameter = (w_pt - 2 * side_clear)
    radius = (max_diameter / 2.0) * st.portrait_radius_scale

    cx = w_pt / 2.0
    cy = h_pt - side_clear - radius

    # subtle shadow behind circle (on white page)
    draw_circle_shadow(c, cx, cy, radius)

    # --- NEBULA BACKGROUND (clipped to circle) ---
    c.saveState()
    _clip_to_circle(c, cx, cy, radius)
    # full page image, de a clip miatt csak a körben látszik
    c.drawImage(nebula_reader, 0, 0, width=w_pt, height=h_pt, mask=None)
    c.restoreState()

    # circle outline
    c.saveState()
    c.setLineWidth(st.circle_stroke_width)
    c.setStrokeColorRGB(*st.circle_stroke_rgb)
    _safe_set_alpha(c, stroke=st.circle_stroke_alpha)
    c.circle(cx, cy, radius, stroke=1, fill=0)
    c.restoreState()

    # dust + catalog stars inside clip (nebula fölé)
    c.saveState()
    _clip_to_circle(c, cx, cy, radius)

    band_angle = rng.random() * math.pi

    # dust texture (nebula fölé finom csillagpor)
    draw_star_dust(
        c=c,
        rng=rng,
        count=st.dust_count_portrait,
        x0=cx - radius,
        y0=cy - radius,
        x1=cx + radius,
        y1=cy + radius,
        band_angle=band_angle,
    )

    # catalog stars
    for s in stars:
        mag = s["mag"]
        if mag > cutoff_mag:
            continue

        xu = ((s["ra_deg"] % 360.0) / 180.0) - 1.0
        yu = max(-90.0, min(90.0, s["dec_deg"])) / 90.0
        if not _inside_unit_disk(xu, yu):
            continue

        x = cx + xu * radius
        y = cy + yu * radius

        tw = 0.85 + 0.35 * rng.random()
        sr = _mag_to_radius_pt(mag, tw)
        if enable_glow and mag <= 0.8:
            draw_star_glow(c, x, y, sr, rng)
        draw_star_core(c, x, y, sr)

    c.restoreState()

    # typography on white (dynamic scaling)
    s = _portrait_type_scale(h_pt)

    TITLE_SIZE = st.portrait_title_size * s
    MOTTO_SIZE = st.portrait_motto_size * s
    LINE2_SIZE = st.portrait_line2_size * s
    LINE3_SIZE = st.portrait_line3_size * s

    TRACK1 = st.portrait_track1 * s
    TRACK2 = st.portrait_track2 * s
    TRACK3 = st.portrait_track3 * s

    bottom_margin = side_clear * 1.45
    y3 = bottom_margin
    y2 = y3 + (LINE3_SIZE * 1.30)
    y1 = y2 + (LINE2_SIZE * 2.30)
    y_title = y1 + (MOTTO_SIZE * 2.30)

    circle_bottom = cy - radius
    min_gap = min(w_pt, h_pt) * st.portrait_min_gap_frac
    if y_title + (TITLE_SIZE * 0.2) > (circle_bottom - min_gap):
        shift = (y_title + (TITLE_SIZE * 0.2)) - (circle_bottom - min_gap)
        y_title -= shift
        y1 -= shift
        y2 -= shift
        y3 -= shift

    c.setFillColorRGB(*st.text_rgb)

    title_text = (title or "").strip()
    c.setFont(fonts["title"], TITLE_SIZE)
    tw = pdfmetrics.stringWidth(title_text, fonts["title"], TITLE_SIZE)
    c.drawString(cx - tw / 2.0, y_title, title_text)

    _draw_centered_tracked(c, (motto or "").upper(), cx, y1, fonts["meta"], MOTTO_SIZE, TRACK1)
    loc_date = f"{(location_name or '').upper()}  |  {(date_text or '').upper()}"
    _draw_centered_tracked(c, loc_date, cx, y2, fonts["meta"], LINE2_SIZE, TRACK2)
    coord = f"{lat:.6f}°N, {lon:.6f}°E"
    _draw_centered_tracked(c, coord, cx, y3, fonts["meta"], LINE3_SIZE, TRACK3)


def _render_square50_banded(
    *,
    c,
    w_pt: float,
    h_pt: float,
    w_in: float,
    h_in: float,
    dpi: int,
    rng: random.Random,
    fonts: dict,
    stars: list,
    cutoff_mag: float,
    enable_glow: bool,
    title: str,
    motto: str,
    location_name: str,
    date_text: str,
    lat: float,
    lon: float,
    nebula_reader: ImageReader,
) -> None:
    st = DEFAULT_STARMAP_STYLE

    _paint_page_white(c, w_pt, h_pt)

    band_h = h_pt * st.square50_band_height_frac

    # --- NEBULA BACKGROUND full page ---
    c.saveState()
    c.drawImage(nebula_reader, 0, 0, width=w_pt, height=h_pt, mask=None)
    c.restoreState()

    band_angle = rng.random() * math.pi

    # dust across full page (nebula fölé)
    draw_star_dust(
        c=c,
        rng=rng,
        count=st.dust_count_square50,
        x0=0.0,
        y0=0.0,
        x1=w_pt,
        y1=h_pt,
        band_angle=band_angle,
    )

    # catalog stars across full page
    for s in stars:
        mag = s["mag"]
        if mag > cutoff_mag:
            continue

        xu = ((s["ra_deg"] % 360.0) / 180.0) - 1.0
        yu = max(-90.0, min(90.0, s["dec_deg"])) / 90.0

        x = (w_pt / 2.0) + xu * (w_pt / 2.0)
        y = (h_pt / 2.0) + yu * (h_pt / 2.0)

        tw = 0.85 + 0.35 * rng.random()
        sr = _mag_to_radius_pt(mag, tw)
        if enable_glow and mag <= 0.8:
            draw_star_glow(c, x, y, sr, rng)
        draw_star_core(c, x, y, sr)

    # bottom band overlay
    c.saveState()
    c.setFillColorRGB(*st.square50_band_fill_rgb)
    _safe_set_alpha(c, fill=st.square50_band_alpha)
    c.rect(0, 0, w_pt, band_h, stroke=0, fill=1)
    c.restoreState()

    # typography on band (black)
    c.setFillColorRGB(*st.square50_text_rgb)
    cx = w_pt / 2.0
    pad = max(14.0, band_h * 0.12)
    band_top = band_h

    TITLE_SIZE = max(28.0, min(56.0, band_h * 0.36))
    MOTTO_SIZE = max(10.0, min(20.0, band_h * 0.12))
    LINE2_SIZE = max(9.0, min(16.0, band_h * 0.10))
    LINE3_SIZE = max(8.0, min(14.0, band_h * 0.09))

    TRACK1 = st.square50_track1
    TRACK2 = st.square50_track2
    TRACK3 = st.square50_track3

    y_title = band_top - pad - TITLE_SIZE
    y1 = y_title - (MOTTO_SIZE * 1.55)
    y2 = y1 - (LINE2_SIZE * 1.35)
    y3 = y2 - (LINE3_SIZE * 1.25)

    title_text = (title or "").strip()
    c.setFont(fonts["title"], TITLE_SIZE)
    tw = pdfmetrics.stringWidth(title_text, fonts["title"], TITLE_SIZE)
    c.drawString(cx - tw / 2.0, y_title, title_text)

    _draw_centered_tracked(c, (motto or "").upper(), cx, y1, fonts["meta"], MOTTO_SIZE, TRACK1)
    loc_date = f"{(location_name or '').upper()}  |  {(date_text or '').upper()}"
    _draw_centered_tracked(c, loc_date, cx, y2, fonts["meta"], LINE2_SIZE, TRACK2)
    coord = f"{lat:.6f}°N, {lon:.6f}°E"
    _draw_centered_tracked(c, coord, cx, y3, fonts["meta"], LINE3_SIZE, TRACK3)


# =============================================================================
# Public entry
# =============================================================================

def render_star_map_stub(
    spec,
    output_dir: Path,
    seed: int = 42,
    filename_prefix: str = "star_map",
    preview_dpi: int = 350,
    cutoff_mag: float = 5.8,
    enable_glow: bool = True,
    title: str = "Tamara & Norbert",
    motto: str = "THE NIGHT OUR LOVE WAS BORN",
    location_name: str = "KIRÁLYRÉT",
    date_text: str = "MAY 8, 2022",
    lat: float = 47.894722,
    lon: float = 18.977778,
) -> StarsRenderResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    w_in, h_in = spec.fig_size_inches
    w_pt, h_pt = w_in * 72.0, h_in * 72.0

    pdf_path = output_dir / f"{filename_prefix}.pdf"
    png_path = output_dir / f"{filename_prefix}_preview.png"

    rng = random.Random(seed)
    c = canvas.Canvas(str(pdf_path), pagesize=(w_pt, h_pt))

    project_root = Path(__file__).resolve().parents[1]
    fonts = _register_fonts(project_root)

    catalog_path = project_root / "data" / "stars_sample.csv"
    stars = _load_star_catalog_csv(catalog_path) if catalog_path.exists() else []

    # A starmap háttér DPI-je: spec.dpi (mainből jön), fallback 300
    bg_dpi = int((getattr(spec, "dpi", None) or 300) * 1.4)

    # Nebula háttér generálás egyszer oldalanként (magas felbontás, print-friendly)
    nebula_reader = _make_nebula_reader_for_page(
        w_in=w_in,
        h_in=h_in,
        dpi=bg_dpi,
        seed=seed,
    )

    is_square_50 = (getattr(spec, "width_cm", None) == 50 and getattr(spec, "height_cm", None) == 50)

    if is_square_50:
        _render_square50_banded(
            c=c,
            w_pt=w_pt,
            h_pt=h_pt,
            w_in=w_in,
            h_in=h_in,
            dpi=bg_dpi,
            rng=rng,
            fonts=fonts,
            stars=stars,
            cutoff_mag=cutoff_mag,
            enable_glow=enable_glow,
            title=title,
            motto=motto,
            location_name=location_name,
            date_text=date_text,
            lat=lat,
            lon=lon,
            nebula_reader=nebula_reader,
        )
    else:
        _render_portrait_circle(
            c=c,
            w_pt=w_pt,
            h_pt=h_pt,
            w_in=w_in,
            h_in=h_in,
            dpi=bg_dpi,
            rng=rng,
            fonts=fonts,
            stars=stars,
            cutoff_mag=cutoff_mag,
            enable_glow=enable_glow,
            title=title,
            motto=motto,
            location_name=location_name,
            date_text=date_text,
            lat=lat,
            lon=lon,
            nebula_reader=nebula_reader,
        )

    c.showPage()
    c.save()

    _pdf_to_preview_png(pdf_path, png_path, dpi=preview_dpi)
    return StarsRenderResult(output_pdf=pdf_path, output_preview_png=png_path)
