# -*- coding: utf-8 -*-
"""
render_manual.py
================
Manuális, paraméterez­hető várostérkép-renderelő.

HASZNÁLAT:
  1. Állítsd be a paramétereket az alábbi blokkban.
  2. Futtasd: python render_manual.py

KIMENET:
  output/<varos>_<stilus>_<extent>m_<meret>.webp
  (max 150 KB, hosszabb oldal max 1500 px)

ELÉRHETŐ STÍLUSOK:
  Block engine   : urban_modern, midnight_ember
  Building engine: midnight_blue, architect_sage, warm_terracotta,
                   mono_black, royal_purple, sandstone_beige, luxury_gold
  Line engine    : vintage_atlas

ELÉRHETŐ MÉRETEK (cm):
  40x50, 50x40, 50x70, 70x50, 50x50, 60x90, 90x60
"""

from __future__ import annotations

# =============================================================================
#  PARAMÉTEREK – IDE ÍRD ÁT!
# =============================================================================

CITY_NAME   = "MOSCOV"          # Cím a poszteren (és a fájlnévben)
LAT         = 55.7526      # Szélességi fok
LON         = 37.6226             # Hosszúsági fok
EXTENT_M    = 3000                # Fél-extent méterben (pl. 2000 = ~4 km átmérő)
SIZE_KEY    = "50x70"             # Plakátméret kulcs (cm)
STYLE       = "vintage_atlas"    # Stílus neve (lásd fent)
SUBTITLE    = None                # None → automatikus koordináta felirat
OUTPUT_DIR_BASE = "output"        # Kimeneti mappa (a project gyökéréhez képest)
USE_CACHE   = True                # OSM gyorsítótár használata
OVERPASS_DEBUG = True            # True -> részletes Overpass diagnosztikai log

# =============================================================================
# (Alatta nem kell módosítani, hacsak nem tudod, mit csinálsz.)
# =============================================================================

import re
import os
import sys
import time
from pathlib import Path

from PIL import Image

# Biztosítjuk, hogy a generator csomag importálható legyen
_script_dir = Path(__file__).parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from generator.specs import ProductLine, spec_from_size_key, validate_size_key_for_product_line
from generator.core.render_dispatcher import render_product


# --------------------------------------------------------------------------- #
# KONSTANSOK
# --------------------------------------------------------------------------- #

MAX_WEBP_BYTES  = 150 * 1024   # 150 KB
MAX_LONG_SIDE   = 1500          # px
QUALITY_STEPS   = [88, 82, 76, 70, 64, 58, 52, 46, 40, 34, 28]


# --------------------------------------------------------------------------- #
# SEGÉDFÜGGVÉNYEK
# --------------------------------------------------------------------------- #

def _safe_name(text: str) -> str:
    """Fájlnévbe biztonságos string (ékezetek, szóközök eltávolítása)."""
    text = text.strip().upper()
    # Ékezetes karakterek -> ASCII közelítés
    replacements = {
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ö": "O", "Ő": "O",
        "Ú": "U", "Ü": "U", "Ű": "U",
        "á": "A", "é": "E", "í": "I", "ó": "O", "ö": "O", "ő": "O",
        "ú": "U", "ü": "U", "ű": "U",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    # Maradék nem-alfanumerikus karakterek -> _
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


def _build_output_name(city: str, style: str, extent: int, size_key: str) -> str:
    city_slug  = _safe_name(city)
    style_slug = style.lower().replace(" ", "_")
    size_slug  = size_key.replace("x", "x")
    return f"{city_slug}_{style_slug}_{extent}m_{size_slug}.webp"


def _resize_if_needed(img: Image.Image) -> Image.Image:
    """Hosszabb oldal legfeljebb MAX_LONG_SIDE px."""
    w, h = img.size
    long_side = max(w, h)
    if long_side <= MAX_LONG_SIDE:
        return img
    scale = MAX_LONG_SIDE / long_side
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    print(f"  → Átméretezés: {w}×{h} → {new_w}×{new_h} px")
    return img.resize((new_w, new_h), Image.LANCZOS)


def _save_webp(img: Image.Image, dest: Path) -> int:
    """WebP mentés quality-léptetéssel, max MAX_WEBP_BYTES."""
    for quality in QUALITY_STEPS:
        img.save(dest, format="WEBP", quality=quality, method=6, optimize=True)
        size = dest.stat().st_size
        print(f"  → quality={quality}  →  {size / 1024:.1f} KB", end="")
        if size <= MAX_WEBP_BYTES:
            print("  ✓")
            return size
        print()

    # Ha egyik sem elég: utolsó erőfeszítés (lossless=False, min quality)
    img.save(dest, format="WEBP", quality=20, method=6, optimize=True)
    size = dest.stat().st_size
    print(f"  → quality=20 (minimum)  →  {size / 1024:.1f} KB  ⚠ méretkorlát nem teljesíthető")
    return size


def _delete_files(*paths: Path | None) -> None:
    """Közbülső fájlok törlése."""
    for p in paths:
        if p and p.exists():
            p.unlink()
            print(f"  törölve: {p.name}")


# --------------------------------------------------------------------------- #
# MAIN
# --------------------------------------------------------------------------- #

def main() -> None:
    t0 = time.perf_counter()

    prev_overpass_debug = os.environ.get("OVERPASS_DEBUG")
    if OVERPASS_DEBUG:
        os.environ["OVERPASS_DEBUG"] = "1"
    else:
        os.environ.pop("OVERPASS_DEBUG", None)

    # --- validáció ---
    product_line = ProductLine.CITYMAP
    validate_size_key_for_product_line(SIZE_KEY, product_line)

    spec = spec_from_size_key(SIZE_KEY, extent_m=EXTENT_M, dpi=150)

    output_dir = _script_dir / OUTPUT_DIR_BASE
    output_dir.mkdir(parents=True, exist_ok=True)

    subtitle_text = (
        SUBTITLE
        if SUBTITLE
        else f"{LAT:.4f}° N  {LON:.4f}° E"
    )

    webp_name = _build_output_name(CITY_NAME, STYLE, EXTENT_M, SIZE_KEY)
    webp_path = output_dir / webp_name

    print("=" * 60)
    print(f"  Város   : {CITY_NAME}")
    print(f"  Stílus  : {STYLE}")
    print(f"  Méret   : {SIZE_KEY} cm  |  extent: {EXTENT_M} m")
    print(f"  Koord.  : {LAT}, {LON}")
    print(f"  Overpass debug: {'ON' if OVERPASS_DEBUG else 'OFF'}")
    print(f"  Kimenet : {webp_path}")
    print("=" * 60)

    # --- render (ideiglenes fájlok az output_dir-be kerülnek) ---
    try:
        result = render_product(
            style_name=STYLE,
            center_lat=LAT,
            center_lon=LON,
            spec=spec,
            output_dir=output_dir,
            title=CITY_NAME,
            subtitle=subtitle_text,
            preview_mode=False,
            order_id="MANUAL",
            use_cache=USE_CACHE,
        )
    finally:
        if prev_overpass_debug is None:
            os.environ.pop("OVERPASS_DEBUG", None)
        else:
            os.environ["OVERPASS_DEBUG"] = prev_overpass_debug

    # --- PNG → WebP konverzió ---
    print("\n[WebP konverzió]")
    with Image.open(result.output_png) as png_img:
        img = _resize_if_needed(png_img.convert("RGB"))
        final_size = _save_webp(img, webp_path)

    print(f"\n  Végső fájl : {webp_path.name}  ({final_size / 1024:.1f} KB)")

    # --- köztes fájlok törlése ---
    print("\n[Takarítás]")
    _delete_files(result.output_png, result.output_svg, result.output_pdf)

    # Ha maradt ugyanolyan nevű PDF a pipeline-tól (line engine generálja)
    possible_pdf = output_dir / (result.output_png.stem + ".pdf") if result.output_png else None
    _delete_files(possible_pdf)

    # Az esetleg generált pipeline-WebP törlése (ha nem a mi fájlunk)
    pipeline_webp = output_dir / (result.output_png.stem.replace(".png", "") + ".webp") if result.output_png else None
    if pipeline_webp and pipeline_webp != webp_path and pipeline_webp.exists():
        _delete_files(pipeline_webp)

    t1 = time.perf_counter()
    print(f"\nKész! ({t1 - t0:.1f} s)")


if __name__ == "__main__":
    main()
