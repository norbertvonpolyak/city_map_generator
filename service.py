from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re

import osmnx as ox

from generator.core.style_registry import STYLE_REGISTRY
from generator.core.render_dispatcher import render_product
from generator.specs import ProductLine, spec_from_size_key, validate_size_key_for_product_line

PREVIEW_OUTPUT_DIR = Path("cache") / "umc_preview_city"
PREVIEW_SIZE_KEY = "50x50"
PREVIEW_EXTENT_M = 1800
PREVIEW_DPI = 96

logger = logging.getLogger(__name__)


def _normalize_style(style: str) -> str:
    normalized = style.strip().lower()
    aliases = {
        "minimal": "nordic_teal",
        "minimal_night": "bw_minimal",
    }

    mapped = aliases.get(normalized, normalized)
    if mapped in STYLE_REGISTRY:
        return mapped

    supported = ", ".join(sorted(STYLE_REGISTRY.keys()))
    raise ValueError(f"Unsupported city preview style '{style}'. Supported styles: {supported}")


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


@dataclass
class CityPreviewResult:
    svg: str
    png_base64: str


def generate_city_preview_svg(
    *,
    city: str,
    style: str = "nordic_teal",
    size_key: str = PREVIEW_SIZE_KEY,
    extent_m: int = PREVIEW_EXTENT_M,
) -> CityPreviewResult:
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

        result = render_product(
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

        logger.info("City preview render_product result=%s", result)

        if not result.output_svg.exists():
            raise RuntimeError(f"Preview generation failed: SVG not found at {result.output_svg}")
        if not result.output_png.exists():
            raise RuntimeError(f"Preview generation failed: PNG not found at {result.output_png}")

        svg_text = result.output_svg.read_text(encoding="utf-8")
        png_base64 = base64.b64encode(result.output_png.read_bytes()).decode("ascii")
        logger.info("City preview success: svg_bytes=%s png_bytes=%s", len(svg_text.encode('utf-8')), len(result.output_png.read_bytes()))
        return CityPreviewResult(svg=svg_text, png_base64=png_base64)
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
        result = render_product(
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

        logger.info("Legacy preview result=%s", result)

        if not result.output_svg.exists():
            raise RuntimeError(f"Preview generation failed: SVG not found at {result.output_svg}")

        return result.output_svg.read_text(encoding="utf-8").encode("utf-8")
    except Exception:
        logger.exception("Legacy preview generation failed")
        raise
