from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import csv
import math

from reportlab.pdfgen import canvas
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


def render_star_map_stub(
    spec,
    output_dir: Path,
    seed: int = 42,
    filename_prefix: str = "star_map",
    preview_dpi: int = 350,
    cutoff_mag: float = 5.8,
    enable_glow: bool = True,
) -> StarsRenderResult:

    output_dir.mkdir(parents=True, exist_ok=True)

    w_in, h_in = spec.fig_size_inches
    w_pt, h_pt = w_in * 72.0, h_in * 72.0

    pdf_path = output_dir / f"{filename_prefix}.pdf"
    png_path = output_dir / f"{filename_prefix}_preview.png"

    rng = random.Random(seed)
    c = canvas.Canvas(str(pdf_path), pagesize=(w_pt, h_pt))

    # -----------------------------
    # Layout parameters (DESIGN)
    # -----------------------------
    edge_margin = min(w_pt, h_pt) * 0.07

    # Visual layout tuning:
    #  - circle scaled to ~90%
    #  - positioned towards top for gallery-style composition
    top_margin = edge_margin * 3.1  # több hely felül

    max_diameter = min(
        w_pt - 2 * edge_margin,
        h_pt - top_margin - edge_margin,
    )

    radius = (max_diameter / 2.0) * 0.9
    cx = w_pt / 2.0
    cy = h_pt - top_margin - radius  # kör felülre igazítva

    # -----------------------------
    # Load catalog
    # -----------------------------
    project_root = Path(__file__).resolve().parents[1]
    catalog_path = project_root / "data" / "stars_sample.csv"
    stars = _load_star_catalog_csv(catalog_path) if catalog_path.exists() else []

    # -----------------------------
    # Circle outline only
    # -----------------------------
    c.setLineWidth(0.8)
    c.setStrokeColorRGB(0.75, 0.75, 0.75)
    c.circle(cx, cy, radius, stroke=1, fill=0)

    # -----------------------------
    # Background stars (Milky Way band)
    # -----------------------------
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

    # -----------------------------
    # Catalog stars (foreground)
    # -----------------------------
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

    c.showPage()
    c.save()

    _pdf_to_preview_png(pdf_path, png_path, dpi=preview_dpi)

    return StarsRenderResult(
        output_pdf=pdf_path,
        output_preview_png=png_path,
    )
