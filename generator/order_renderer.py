"""Manual, local-PBF order rendering through the existing dispatcher and PBF store."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

import fitz

from generator.batch_pipeline import (
    _atomic_json,
    _cache_only_environment,
    _publish_pair,
    _render_pdf_to_webp,
    _validate_webp,
)
from generator.core.render_dispatcher import render_product
from generator.core.style_registry import STYLE_REGISTRY
from generator.order_cache import OrderCacheError, prepare_order_cache
from generator.specs import DEFAULT_EXTENT_M, resolve_size_request, spec_from_dimensions


class OrderRenderError(RuntimeError):
    pass


WEB_PREVIEW_MAX_BYTES = 150_000
WEB_PREVIEW_MAX_LONG_SIDE = 1400
WEB_PREVIEW_LONG_SIDES = (1400, 1120, 960, 800)


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().casefold()).strip("-")
    if not normalized:
        raise ValueError("CITY_NAME must contain at least one letter or number")
    return normalized


def _validate_order_config(
    *,
    pbf_path: Path,
    city_name: str,
    center_lat: float,
    center_lon: float,
    style: str,
    sizes: tuple,
    extent_m: int,
) -> None:
    if not pbf_path.is_file() or pbf_path.suffix.casefold() != ".pbf":
        raise ValueError(f"PBF_PATH must identify an existing local .pbf file: {pbf_path}")
    if not city_name.strip():
        raise ValueError("CITY_NAME must not be empty")
    if not math.isfinite(center_lat) or not -90 <= center_lat <= 90:
        raise ValueError(f"CENTER_LAT must be finite and between -90 and 90: {center_lat}")
    if not math.isfinite(center_lon) or not -180 <= center_lon <= 180:
        raise ValueError(f"CENTER_LON must be finite and between -180 and 180: {center_lon}")
    if style not in STYLE_REGISTRY:
        raise ValueError(f"STYLE {style!r} is not registered. Registered styles: {', '.join(STYLE_REGISTRY)}")
    if not sizes:
        raise ValueError("At least one size must be selected")
    for size in sizes:
        resolve_size_request(size)
    if extent_m <= 0:
        raise ValueError("EXTENT_M must be a positive radius in metres")


def _validate_pdf(path: Path, width_cm: int, height_cm: int) -> dict:
    if not path.is_file() or path.stat().st_size == 0:
        raise OrderRenderError(f"Renderer did not produce a non-empty PDF: {path}")
    with fitz.open(path) as document:
        if len(document) != 1:
            raise OrderRenderError(f"Expected a single-page PDF, got {len(document)} pages")
        page = document[0]
        width_mm = page.rect.width * 25.4 / 72
        height_mm = page.rect.height * 25.4 / 72
        expected_width_mm, expected_height_mm = width_cm * 10, height_cm * 10
        if abs(width_mm - expected_width_mm) > 0.05 or abs(height_mm - expected_height_mm) > 0.05:
            raise OrderRenderError(
                f"PDF page is {width_mm:.4f}x{height_mm:.4f} mm; expected {expected_width_mm}x{expected_height_mm} mm"
            )
        vector_drawings = len(page.get_drawings())
        if vector_drawings <= 0 and not page.get_text().strip():
            raise OrderRenderError("PDF has no vector paths or text")
        return {
            "width_mm": width_mm,
            "height_mm": height_mm,
            "vector_drawings": vector_drawings,
            "embedded_images": len(page.get_images(full=True)),
        }


def _safe_order_manifest(path: Path, *, city_name: str, pbf_path: Path, cache: dict) -> dict:
    if path.is_file():
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise OrderRenderError(f"Cannot read existing order manifest; preserving it: {path}: {error}") from error
        if manifest.get("city_name") != city_name:
            raise OrderRenderError(f"Existing order manifest belongs to a different city; preserving it: {path}")
    else:
        manifest = {
            "schema_version": 1,
            "city_name": city_name,
            "jobs": {},
        }
    manifest["source_pbf"] = str(pbf_path)
    manifest["source_identity"] = cache["source_identity"]
    manifest["cache_id"] = cache["cache_id"]
    manifest["cache_dir"] = cache["store_dir"]
    manifest["cache_coverage_wgs84"] = cache["coverage_bbox_wgs84"]
    manifest["cache_reused"] = cache["reused"]
    manifest["extent_m"] = cache["extent_m"]
    manifest.setdefault("source_runs", {})
    manifest["source_runs"].setdefault(cache["source_identity"]["sha256"], {"source_pbf": str(pbf_path), "jobs": {}})
    return manifest


def render_order(
    *,
    pbf_path: Path | str,
    city_name: str,
    center_lat: float,
    center_lon: float,
    style: str,
    sizes: tuple,
    extent_m: int | None,
    output_dir: Path | str,
    cache_root: Path | str,
    preferred_store_dir: Path | str | None = None,
    dpi: int = 300,
) -> dict:
    from generator.core.pbf_store import read_pbf_header

    pbf_path = Path(pbf_path).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    cache_root = Path(cache_root).expanduser().resolve()
    resolved_extent_m = DEFAULT_EXTENT_M if extent_m is None else extent_m
    sizes = tuple(sizes)
    _validate_order_config(
        pbf_path=pbf_path,
        city_name=city_name,
        center_lat=center_lat,
        center_lon=center_lon,
        style=style,
        sizes=sizes,
        extent_m=resolved_extent_m,
    )
    resolved_sizes = [resolve_size_request(size) for size in sizes]
    size_labels = [label for label, _, _ in resolved_sizes]
    header = read_pbf_header(pbf_path)
    cache = prepare_order_cache(
        pbf_path=pbf_path,
        center_lat=center_lat,
        center_lon=center_lon,
        extent_m=resolved_extent_m,
        cache_root=cache_root,
        preferred_store_dir=preferred_store_dir,
        print_dimensions=[(width_cm, height_cm) for _, width_cm, height_cm in resolved_sizes],
    )
    cache["extent_m"] = resolved_extent_m
    output_slug = _slug(city_name)
    order_root = output_dir / output_slug
    manifest_path = order_root / "order_manifest.json"
    manifest = _safe_order_manifest(manifest_path, city_name=city_name, pbf_path=pbf_path, cache=cache)
    manifest.update({
        "center": {"lat": center_lat, "lon": center_lon},
        "style": style,
        "sizes_requested": size_labels,
        "extent_m": resolved_extent_m,
        "pbf_header": header,
        "remote_osm_api_used": False,
    })
    order_root.mkdir(parents=True, exist_ok=True)
    _atomic_json(manifest_path, manifest)
    print(f"PBF: {pbf_path}")
    print(f"CACHE: {cache['store_dir']} id={cache['cache_id']} reused={cache['reused']}")
    print(f"CACHE COVERAGE: {cache['coverage_bbox_wgs84']}")
    print(f"STYLE: {style}; SIZES: {', '.join(size_labels)}; EXTENT_M: {resolved_extent_m} (radius/half-height)")

    success = failed = 0
    for size_key, width_cm, height_cm in resolved_sizes:
        spec = spec_from_dimensions(width_cm, height_cm, extent_m=resolved_extent_m, dpi=dpi)
        key = f"{cache['source_identity']['sha256'][:12]}/{style}/{size_key}"
        final_dir = order_root / style / size_key
        started = time.perf_counter()
        try:
            final_dir.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=f"order-{output_slug}-{style}-{size_key}-", dir=final_dir.parent) as temp:
                temp_path = Path(temp)
                render_dir = temp_path / "render"
                stage_dir = temp_path / "stage"
                render_dir.mkdir()
                stage_dir.mkdir()
                with _cache_only_environment(Path(cache["store_dir"])):
                    rendered = render_product(
                        style_name=style,
                        center_lat=center_lat,
                        center_lon=center_lon,
                        spec=spec,
                        output_dir=render_dir,
                        title=city_name,
                        subtitle=f"{center_lat:.4f} N  {center_lon:.4f} E",
                        preview_mode=False,
                        order_id=f"ORDER_{output_slug}_{style}_{size_key}_{time.time_ns()}",
                        use_cache=True,
                    )
                if rendered.output_pdf is None or not rendered.output_pdf.is_file():
                    raise OrderRenderError("Existing renderer did not produce a PDF")
                staged_pdf = stage_dir / "map.pdf"
                staged_preview = stage_dir / "preview.webp"
                shutil.copy2(rendered.output_pdf, staged_pdf)
                pdf_info = _validate_pdf(staged_pdf, spec.width_cm, spec.height_cm)
                preview_info = _render_pdf_to_webp(
                    staged_pdf,
                    staged_preview,
                    spec.width_cm,
                    spec.height_cm,
                    WEB_PREVIEW_MAX_BYTES,
                    max_long_side=WEB_PREVIEW_MAX_LONG_SIDE,
                    long_sides=WEB_PREVIEW_LONG_SIDES,
                )
                _validate_webp(staged_preview, tuple(preview_info["dimensions_px"]), WEB_PREVIEW_MAX_BYTES)
                output_names = frozenset({"map.pdf", "preview.webp"})
                if {item.name for item in stage_dir.iterdir()} != output_names:
                    raise OrderRenderError("Temporary staging directory contains unexpected files")
                _publish_pair(stage_dir, final_dir, expected_names=output_names, retired_names=frozenset({"map.webp"}))

            record = {
                "status": "success",
                "pbf_source": str(pbf_path),
                "cache_id": cache["cache_id"],
                "cache_store": cache["store_dir"],
                "style": style,
                "size": size_key,
                "print_width_cm": spec.width_cm,
                "print_height_cm": spec.height_cm,
                "extent_m": resolved_extent_m,
                "pdf_path": str(final_dir / "map.pdf"),
                "pdf_bytes": (final_dir / "map.pdf").stat().st_size,
                "pdf_validation": pdf_info,
                "web_preview_path": str(final_dir / "preview.webp"),
                "web_preview": {
                    **preview_info,
                    "max_long_side_px": WEB_PREVIEW_MAX_LONG_SIDE,
                    "lossless": False,
                },
                "render_duration_s": round(time.perf_counter() - started, 3),
                "remote_osm_api_used": False,
                "temporary_cleanup": "completed",
            }
            manifest["jobs"][key] = record
            manifest["source_runs"].setdefault(cache["source_identity"]["sha256"], {"source_pbf": str(pbf_path), "jobs": {}})["jobs"][f"{style}/{size_key}"] = record
            success += 1
            print(f"[{key}] OK pdf={pdf_info['width_mm']:.2f}x{pdf_info['height_mm']:.2f}mm preview={preview_info['width_px']}x{preview_info['height_px']} {preview_info['bytes']} bytes duration={record['render_duration_s']}s")
        except Exception as error:
            failure = {"status": "failed", "error": f"{type(error).__name__}: {error}", "cache_id": cache["cache_id"]}
            manifest["jobs"][key] = failure
            manifest["source_runs"].setdefault(cache["source_identity"]["sha256"], {"source_pbf": str(pbf_path), "jobs": {}})["jobs"][f"{style}/{size_key}"] = failure
            failed += 1
            print(f"[{key}] FAIL {type(error).__name__}: {error}")
        _atomic_json(manifest_path, manifest)

    return {
        "expected": len(sizes),
        "success": success,
        "failed": failed,
        "manifest": str(manifest_path),
        "cache": cache,
    }