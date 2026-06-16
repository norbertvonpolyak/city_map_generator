from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
import re

import osmnx as ox

from generator.core.render_dispatcher import render_product
from generator.specs import ProductLine, spec_from_size_key, validate_size_key_for_product_line

PREVIEW_OUTPUT_DIR = Path("cache") / "umc_preview_city"
PREVIEW_SIZE_KEY = "50x50"
PREVIEW_EXTENT_M = 1800
PREVIEW_DPI = 96

logger = logging.getLogger(__name__)


def _normalize_style(style: str) -> str:
    normalized = style.strip().lower()

    if normalized in {"minimal", "minimal_sand"}:
        return "minimal_sand"

    raise ValueError("Unsupported city preview style. Only 'minimal' is available.")


@lru_cache(maxsize=256)
def _geocode_city(city: str) -> tuple[float, float]:
    query = city.strip()
    if not query:
        raise ValueError("City name is required.")

    logger.info("City preview geocoding start: city=%s", query)
    latitude, longitude = ox.geocode(query)
    logger.info("City preview geocoding success: city=%s lat=%s lon=%s", query, latitude, longitude)
    return float(latitude), float(longitude)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-") or "city"


def generate_city_preview_svg(
    *,
    city: str,
    style: str = "minimal",
    size_key: str = PREVIEW_SIZE_KEY,
    extent_m: int = PREVIEW_EXTENT_M,
) -> str:
    logger.info(
        "City preview request start: city=%s style=%s size_key=%s extent_m=%s",
        city,
        style,
        size_key,
        extent_m,
    )

    try:
        validate_size_key_for_product_line(size_key, ProductLine.CITYMAP)
        palette_name = _normalize_style(style)
        latitude, longitude = _geocode_city(city)

        spec = spec_from_size_key(size_key=size_key, extent_m=extent_m, dpi=PREVIEW_DPI)
        logger.info(
            "City preview render_product start: style=%s lat=%s lon=%s spec=%s output_dir=%s preview_mode=%s use_cache=%s",
            palette_name,
            latitude,
            longitude,
            spec,
            PREVIEW_OUTPUT_DIR,
            True,
            True,
        )

        output_path = render_product(
            style_name=palette_name,
            center_lat=latitude,
            center_lon=longitude,
            spec=spec,
            output_dir=PREVIEW_OUTPUT_DIR,
            title=city.strip(),
            subtitle=f"{latitude:.4f}, {longitude:.4f}",
            preview_mode=True,
            use_cache=True,
        )

        logger.info("City preview render_product output_path=%s", output_path)

        if output_path is None:
            raise RuntimeError("Preview generation failed: render_product returned no output path.")

        logger.info("City preview output exists check: path=%s exists=%s", output_path, output_path.exists())

        if not output_path.exists():
            raise RuntimeError(f"Preview generation failed: SVG file not found at {output_path}")

        svg_text = output_path.read_text(encoding="utf-8")
        logger.info("City preview SVG read success: bytes=%s", len(svg_text.encode('utf-8')))
        return svg_text
    except Exception:
        logger.exception("City preview generation failed")
        raise


# Backward-compatible thin wrapper for the older preview route.
def generate_preview(
    *,
    lat: float,
    lon: float,
    size_key: str,
    palette: str,
    extent_m: int | None = None,
) -> bytes:
    spec = spec_from_size_key(
        size_key=size_key,
        extent_m=extent_m if extent_m is not None else PREVIEW_EXTENT_M,
        dpi=PREVIEW_DPI,
    )

    logger.info(
        "Legacy preview render_product start: lat=%s lon=%s size_key=%s extent_m=%s palette=%s output_dir=%s preview_mode=%s use_cache=%s",
        lat,
        lon,
        size_key,
        extent_m,
        palette,
        PREVIEW_OUTPUT_DIR,
        True,
        True,
    )

    try:
        output_path = render_product(
            style_name=_normalize_style(palette),
            center_lat=lat,
            center_lon=lon,
            spec=spec,
            output_dir=PREVIEW_OUTPUT_DIR,
            title="Preview",
            subtitle=f"{lat:.4f}, {lon:.4f}",
            preview_mode=True,
            use_cache=True,
        )

        logger.info("Legacy preview render_product output_path=%s", output_path)

        if output_path is None:
            raise RuntimeError("Preview generation failed: render_product returned no output path.")

        logger.info("Legacy preview output exists check: path=%s exists=%s", output_path, output_path.exists())

        if not output_path.exists():
            raise RuntimeError(f"Preview generation failed: SVG file not found at {output_path}")

        return output_path.read_text(encoding="utf-8").encode("utf-8")
    except Exception:
        logger.exception("Legacy preview generation failed")
        raise
