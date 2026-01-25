from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import csv
import math

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import fitz  # PyMuPDF


@dataclass(frozen=True)
class StarsRenderResult:
    output_pdf: Path
    output_preview_png: Path


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


def _inside_unit_disk(x: float, y: float) -> bool:
    return (x * x + y * y) <= 1.0


def _mag_to_radius_pt(mag: float, twinkle: float) -> float:
    mag = max(-1.5, min(6.0, mag))
    b = 10 ** (-0.4 * mag)
    b_min = 10 ** (-0.4 * 6.0)
    b_max = 10 ** (-0.4 * (-1.5))
    t = (b - b_min) / (b_max - b_min)
    t = t ** 0.55
    return (0.55 + t * 2.6) * twinkle


def _draw_centered_tracked(c, text: str, cx: float, y: float, font_name: str, font_size: float, tracking_pt: float):
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

    # ============================================================
    # CIRCLE LAYOUT (fix): top gap == side gap (circle fully visible)
    # ============================================================
    side_clear = min(w_pt, h_pt) * 0.07

    # Circle diameter from width constraint (side margins), then 90% scale
    max_diameter = (w_pt - 2 * side_clear)
    radius = (max_diameter / 2.0) * 0.9

    cx = w_pt / 2.0
    # Top of circle is side_clear => cy = h - side_clear - radius
    cy = h_pt - side_clear - radius

    # Circle outline
    c.setLineWidth(0.8)
    c.setStrokeColorRGB(0.75, 0.75, 0.75)
    c.circle(cx, cy, radius, stroke=1, fill=0)

    # Load stars
    catalog_path = project_root / "data" / "stars_sample.csv"
    stars = _load_star_catalog_csv(catalog_path) if catalog_path.exists() else []

    # Background (Milky Way band)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.setStrokeColorRGB(0.35, 0.35, 0.35)

    bg_count = 2000
    band_angle = rng.random() * math.pi
    band_sigma = 0.18
    band_strength = 0.65

    for _ in range(bg_count):
        while True:
            xu = rng.uniform(-1.0, 1.0)
            yu = rng.uniform(-1.0, 1.0)
            if not _inside_unit_disk(xu, yu):
                continue

            d = abs(xu * math.sin(band_angle) - yu * math.cos(band_angle))
            p_band = math.exp(-(d / band_sigma) ** 2)
            p_accept = (1.0 - band_strength) + band_strength * p_band
            if rng.random() < p_accept:
                break

        x = cx + xu * radius
        y = cy + yu * radius

        d = abs(xu * math.sin(band_angle) - yu * math.cos(band_angle))
        p_band = math.exp(-(d / band_sigma) ** 2)

        r = 0.28 + 0.35 * rng.random() + 0.20 * p_band * rng.random()
        c.circle(x, y, r, stroke=0, fill=1)

    # Catalog stars
    c.setFillColorRGB(0, 0, 0)
    c.setStrokeColorRGB(0, 0, 0)

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
        star_r = _mag_to_radius_pt(mag, tw)

        if enable_glow and mag <= 0.8:
            halo_r = star_r * (1.9 + 0.4 * rng.random())
            c.setFillColorRGB(0.88, 0.88, 0.88)
            c.circle(x, y, halo_r, stroke=0, fill=1)

            halo2_r = star_r * (1.35 + 0.2 * rng.random())
            c.setFillColorRGB(0.75, 0.75, 0.75)
            c.circle(x, y, halo2_r, stroke=0, fill=1)

            c.setFillColorRGB(0, 0, 0)

        c.circle(x, y, star_r, stroke=0, fill=1)

    # ============================================================
    # TYPOGRAPHY (fix): push block closer to bottom + scale
    # ============================================================
    # Scaling per your request:
    # title x1.5, motto x2, the rest x1.5
    TITLE_SIZE = 66 * 1.5
    MOTTO_SIZE = 13 * 2.0
    LINE2_SIZE = 11 * 1.5
    LINE3_SIZE = 10.5 * 1.5

    # Tracking (a bit stronger with size)
    TRACK1 = 1.6 * 1.25
    TRACK2 = 1.4 * 1.20
    TRACK3 = 1.2 * 1.20

    # Bottom anchoring: coordinates baseline near bottom margin
    bottom_margin = side_clear * 1.45
    y3 = bottom_margin
    y2 = y3 + (LINE3_SIZE * 1.30)
    y1 = y2 + (LINE2_SIZE * 2.30)
    y_title = y1 + (MOTTO_SIZE * 2.30)

    # If the title would collide with the circle, push the whole block down a bit
    circle_bottom = cy - radius
    min_gap = side_clear * 0.55  # safety gap between circle and typography
    if y_title + (TITLE_SIZE * 0.2) > (circle_bottom - min_gap):
        shift = (y_title + (TITLE_SIZE * 0.2)) - (circle_bottom - min_gap)
        # Move everything DOWN by shift (i.e., subtract)
        y_title -= shift
        y1 -= shift
        y2 -= shift
        y3 -= shift

    # Color: slightly softer than pure black
    c.setFillColorRGB(0.15, 0.15, 0.15)

    title_text = title.strip()
    c.setFont(fonts["title"], TITLE_SIZE)
    tw = pdfmetrics.stringWidth(title_text, fonts["title"], TITLE_SIZE)
    c.drawString(cx - tw / 2.0, y_title, title_text)

    _draw_centered_tracked(c, motto.upper(), cx, y1, fonts["meta"], MOTTO_SIZE, TRACK1)

    loc_date = f"{location_name.upper()}  |  {date_text.upper()}"
    _draw_centered_tracked(c, loc_date, cx, y2, fonts["meta"], LINE2_SIZE, TRACK2)

    coord = f"{lat:.6f}°N, {lon:.6f}°E"
    _draw_centered_tracked(c, coord, cx, y3, fonts["meta"], LINE3_SIZE, TRACK3)

    c.showPage()
    c.save()

    _pdf_to_preview_png(pdf_path, png_path, dpi=preview_dpi)

    return StarsRenderResult(output_pdf=pdf_path, output_preview_png=png_path)
