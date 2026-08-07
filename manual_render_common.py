from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

import geopandas as gpd
import osmnx as ox
from PIL import Image
from shapely.geometry import box


_SCRIPT_DIR = Path(__file__).parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from generator.core.render_dispatcher import get_viewport_for_style, render_product
from generator.core.style_registry import EngineType, STYLE_REGISTRY
from generator.specs import ProductLine, spec_from_size_key, validate_size_key_for_product_line


MAX_WEBP_BYTES = 150 * 1024
MAX_LONG_SIDE = 1500
QUALITY_STEPS = [88, 82, 76, 70, 64, 58, 52, 46, 40, 34, 28]


@dataclass(frozen=True)
class ManualRenderConfig:
    data_source: str = "local"
    city_name: str = "HELSINKI"
    size_key: str = "50x70"
    subtitle: str | None = None
    output_dir_base: str = "output"
    use_cache: bool = True
    api_lat: float = 44.8378
    api_lon: float = -0.5792
    api_extent_m: int = 5000
    local_osm_file: str | None = None
    local_osm_input_dir: str = "input/osm"
    local_auto_fit_to_file: bool = True
    local_fit_margin: float = 0.90
    local_lat: float = 60.1710
    local_lon: float = 24.9375
    local_extent_m: int = 5000
    local_use_cache: bool = True
    local_render_all_objects: bool = False
    local_exact_water: bool = True
    local_hide_labels: bool = False
    local_hide_vegetation: bool = False
    local_hide_trees: bool = True
    local_hide_water_lines: bool = True


@dataclass(frozen=True)
class ResolvedRenderContext:
    source: str
    effective_lat: float
    effective_lon: float
    effective_extent_m: int
    effective_use_cache: bool
    output_dir: Path
    hide_labels: bool
    subtitle_text: str
    local_osm_display: str


@dataclass(frozen=True)
class RenderExecutionResult:
    status: str
    output_path: Path
    size_bytes: int
    extent_m: int
    elapsed_seconds: float


def get_all_styles() -> list[str]:
    by_engine: dict[EngineType, list[str]] = {
        EngineType.BLOCK: [],
        EngineType.BUILDING: [],
        EngineType.LINE: [],
    }
    for name in sorted(STYLE_REGISTRY.keys()):
        by_engine[STYLE_REGISTRY[name].engine].append(name)
    return [
        *by_engine[EngineType.BLOCK],
        *by_engine[EngineType.BUILDING],
        *by_engine[EngineType.LINE],
    ]


def _safe_name(text: str) -> str:
    text = text.strip().upper()
    replacements = {
        "A": "A", "E": "E", "I": "I", "O": "O", "U": "U",
        "a": "A", "e": "E", "i": "I", "o": "O", "u": "U",
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ö": "O", "Ő": "O",
        "Ú": "U", "Ü": "U", "Ű": "U",
        "á": "A", "é": "E", "í": "I", "ó": "O", "ö": "O", "ő": "O",
        "ú": "U", "ü": "U", "ű": "U",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


def build_output_name(city: str, style: str, extent: int, size_key: str) -> str:
    city_slug = _safe_name(city)
    style_slug = style.lower().replace(" ", "_")
    return f"{city_slug}_{style_slug}_{extent}m_{size_key}.webp"


def _resize_if_needed(img: Image.Image) -> Image.Image:
    width, height = img.size
    long_side = max(width, height)
    if long_side <= MAX_LONG_SIDE:
        return img
    scale = MAX_LONG_SIDE / long_side
    new_width = int(round(width * scale))
    new_height = int(round(height * scale))
    print(f"  -> Atmeretezes: {width}x{height} -> {new_width}x{new_height} px")
    return img.resize((new_width, new_height), Image.LANCZOS)


def _save_webp(img: Image.Image, dest: Path) -> int:
    for quality in QUALITY_STEPS:
        img.save(dest, format="WEBP", quality=quality, method=6, optimize=True)
        size = dest.stat().st_size
        print(f"  -> quality={quality} -> {size / 1024:.1f} KB", end="")
        if size <= MAX_WEBP_BYTES:
            print(" OK")
            return size
        print()

    img.save(dest, format="WEBP", quality=20, method=6, optimize=True)
    size = dest.stat().st_size
    print(f"  -> quality=20 (minimum) -> {size / 1024:.1f} KB  WARN meretkorlat nem teljesitheto")
    return size


def _delete_files(*paths: Path | None) -> None:
    for path in paths:
        if path and path.exists():
            path.unlink()
            print(f"  torolve: {path.name}")


def _resolve_local_osm_file_path(config: ManualRenderConfig) -> Path:
    if config.local_osm_file:
        candidate = Path(config.local_osm_file)
        if not candidate.is_absolute():
            candidate = (_SCRIPT_DIR / candidate).resolve()
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError(f"Local OSM file not found: {candidate}")
        return candidate

    osm_dir = _SCRIPT_DIR / config.local_osm_input_dir
    candidates: list[Path] = []
    for pattern in ("*.osm", "*.osm.xml"):
        candidates.extend(osm_dir.glob(pattern))

    files = [path for path in candidates if path.is_file()]
    if not files:
        raise FileNotFoundError(f"No .osm/.osm.xml file found in: {osm_dir}")

    return max(files, key=lambda path: path.stat().st_mtime)


def _read_osm_bounds(local_osm_file: Path) -> tuple[float, float, float, float]:
    for _, elem in ET.iterparse(str(local_osm_file), events=("start",)):
        if elem.tag.endswith("bounds"):
            minlat = float(elem.attrib["minlat"])
            minlon = float(elem.attrib["minlon"])
            maxlat = float(elem.attrib["maxlat"])
            maxlon = float(elem.attrib["maxlon"])
            return minlat, minlon, maxlat, maxlon
    raise ValueError(f"OSM bounds not found in XML: {local_osm_file}")


def _auto_fit_center_extent_from_osm(config: ManualRenderConfig, style_name: str, local_osm_file: Path) -> tuple[float, float, int]:
    minlat, minlon, maxlat, maxlon = _read_osm_bounds(local_osm_file)
    center_lat = (minlat + maxlat) / 2.0
    center_lon = (minlon + maxlon) / 2.0

    bbox = gpd.GeoDataFrame(geometry=[box(minlon, minlat, maxlon, maxlat)], crs="EPSG:4326")
    bbox_projected = ox.projection.project_gdf(bbox)
    minx, miny, maxx, maxy = bbox_projected.total_bounds

    half_width_avail = max((maxx - minx) / 2.0, 1.0)
    half_height_avail = max((maxy - miny) / 2.0, 1.0)

    probe_spec = spec_from_size_key(config.size_key, extent_m=1000, dpi=150)
    probe_half_width, probe_half_height = get_viewport_for_style(style_name, probe_spec)
    viewport_ratio = max(probe_half_width / max(probe_half_height, 1e-9), 1e-9)

    margin = max(0.5, min(float(config.local_fit_margin), 0.999))
    max_half_height = min(half_height_avail, half_width_avail / viewport_ratio) * margin
    fitted_extent_m = max(int(round(max_half_height)), 200)

    return center_lat, center_lon, fitted_extent_m


def _configure_data_source_env(config: ManualRenderConfig) -> str:
    source = (config.data_source or "overpass").strip().lower()
    if source not in {"overpass", "local"}:
        raise ValueError("DATA_SOURCE must be 'overpass' or 'local'.")

    if source == "local":
        os.environ["OSM_SOURCE"] = "local"
        if config.local_render_all_objects:
            os.environ["OSM_LOCAL_ALL_TAGS"] = "1"
            os.environ["BUILDING_RENDER_ALL_OBJECTS"] = "1"
        else:
            os.environ.pop("OSM_LOCAL_ALL_TAGS", None)
            os.environ.pop("BUILDING_RENDER_ALL_OBJECTS", None)

        if config.local_exact_water:
            os.environ["OSM_LOCAL_EXACT_WATER"] = "1"
        else:
            os.environ.pop("OSM_LOCAL_EXACT_WATER", None)

        if config.local_hide_vegetation:
            os.environ["BUILDING_HIDE_VEGETATION"] = "1"
        else:
            os.environ.pop("BUILDING_HIDE_VEGETATION", None)

        if config.local_hide_trees:
            os.environ["BUILDING_HIDE_TREES"] = "1"
        else:
            os.environ.pop("BUILDING_HIDE_TREES", None)

        if config.local_hide_water_lines:
            os.environ["BUILDING_HIDE_WATER_LINES"] = "1"
        else:
            os.environ.pop("BUILDING_HIDE_WATER_LINES", None)

        local_dir = _SCRIPT_DIR / config.local_osm_input_dir
        local_dir.mkdir(parents=True, exist_ok=True)

        if config.local_osm_file:
            local_path = Path(config.local_osm_file)
            if not local_path.is_absolute():
                local_path = (_SCRIPT_DIR / local_path).resolve()
            os.environ["OSM_LOCAL_FILE"] = str(local_path)
        else:
            os.environ.pop("OSM_LOCAL_FILE", None)
    else:
        os.environ.pop("OSM_SOURCE", None)
        os.environ.pop("OSM_LOCAL_FILE", None)
        os.environ.pop("OSM_LOCAL_ALL_TAGS", None)
        os.environ.pop("OSM_LOCAL_EXACT_WATER", None)
        os.environ.pop("BUILDING_RENDER_ALL_OBJECTS", None)
        os.environ.pop("BUILDING_HIDE_VEGETATION", None)
        os.environ.pop("BUILDING_HIDE_TREES", None)
        os.environ.pop("BUILDING_HIDE_WATER_LINES", None)

    return source


def resolve_render_context(config: ManualRenderConfig, style_name: str) -> ResolvedRenderContext:
    product_line = ProductLine.CITYMAP
    validate_size_key_for_product_line(config.size_key, product_line)
    source = _configure_data_source_env(config)

    if source == "overpass":
        effective_lat = config.api_lat
        effective_lon = config.api_lon
        effective_extent_m = config.api_extent_m
    else:
        effective_lat = config.local_lat
        effective_lon = config.local_lon
        effective_extent_m = config.local_extent_m

    local_osm_display = "n/a"
    if source == "local" and config.local_auto_fit_to_file:
        local_osm_file = _resolve_local_osm_file_path(config)
        auto_lat, auto_lon, auto_extent = _auto_fit_center_extent_from_osm(config, style_name, local_osm_file)
        effective_lat = auto_lat
        effective_lon = auto_lon
        effective_extent_m = auto_extent
        local_osm_display = str(local_osm_file)
    elif source == "local":
        local_osm_display = config.local_osm_file or "(latest from OSM dir)"

    effective_use_cache = config.use_cache if source == "overpass" else config.local_use_cache
    output_dir = _SCRIPT_DIR / config.output_dir_base
    output_dir.mkdir(parents=True, exist_ok=True)

    hide_labels = bool(source == "local" and config.local_hide_labels)
    subtitle_text = "" if hide_labels else (
        config.subtitle if config.subtitle else f"{effective_lat:.4f}° N  {effective_lon:.4f}° E"
    )

    return ResolvedRenderContext(
        source=source,
        effective_lat=effective_lat,
        effective_lon=effective_lon,
        effective_extent_m=effective_extent_m,
        effective_use_cache=effective_use_cache,
        output_dir=output_dir,
        hide_labels=hide_labels,
        subtitle_text=subtitle_text,
        local_osm_display=local_osm_display,
    )


def render_style(config: ManualRenderConfig, style_name: str, skip_existing: bool = False) -> RenderExecutionResult:
    t0 = time.perf_counter()
    context = resolve_render_context(config, style_name)
    webp_name = build_output_name(config.city_name, style_name, context.effective_extent_m, config.size_key)
    webp_path = context.output_dir / webp_name

    if skip_existing and webp_path.exists() and webp_path.stat().st_size > 0:
        return RenderExecutionResult(
            status="SKIP",
            output_path=webp_path,
            size_bytes=webp_path.stat().st_size,
            extent_m=context.effective_extent_m,
            elapsed_seconds=time.perf_counter() - t0,
        )

    print("=" * 60)
    print(f"  Varos   : {config.city_name}")
    print(f"  Stilus  : {style_name}")
    print(f"  Meret   : {config.size_key} cm  |  extent: {context.effective_extent_m} m")
    print(f"  Koord.  : {context.effective_lat}, {context.effective_lon}")
    print(f"  OSM src : {context.source}")
    print(f"  Cache   : {'ON' if context.effective_use_cache else 'OFF'}")
    print(f"  Labels  : {'OFF' if context.hide_labels else 'ON'}")
    if context.source == "local":
        print(f"  OSM dir : {_SCRIPT_DIR / config.local_osm_input_dir}")
        if config.local_auto_fit_to_file:
            print("  OSM fit : auto (bbox-based)")
        print(f"  OSM file: {context.local_osm_display}")
        print(f"  All obj : {'ON' if config.local_render_all_objects else 'OFF'}")
        print(f"  Exact H2O: {'ON' if config.local_exact_water else 'OFF'}")
    print(f"  Kimenet : {webp_path}")
    print("=" * 60)

    spec = spec_from_size_key(config.size_key, extent_m=context.effective_extent_m, dpi=150)
    result = render_product(
        style_name=style_name,
        center_lat=context.effective_lat,
        center_lon=context.effective_lon,
        spec=spec,
        output_dir=context.output_dir,
        title="" if context.hide_labels else config.city_name,
        subtitle=context.subtitle_text,
        preview_mode=False,
        order_id="MANUAL",
        use_cache=context.effective_use_cache,
    )

    print("\n[WebP konverzio]")
    with Image.open(result.output_png) as png_img:
        img = _resize_if_needed(png_img.convert("RGB"))
        final_size = _save_webp(img, webp_path)

    print(f"\n  Vegso fajl : {webp_path.name}  ({final_size / 1024:.1f} KB)")

    print("\n[Takaritas]")
    _delete_files(result.output_png, result.output_svg, result.output_pdf)

    possible_pdf = output_dir_pdf_path(result.output_png, context.output_dir)
    _delete_files(possible_pdf)

    pipeline_webp = output_dir_webp_path(result.output_png, context.output_dir)
    if pipeline_webp != webp_path and pipeline_webp.exists():
        _delete_files(pipeline_webp)

    return RenderExecutionResult(
        status="OK",
        output_path=webp_path,
        size_bytes=final_size,
        extent_m=context.effective_extent_m,
        elapsed_seconds=time.perf_counter() - t0,
    )


def output_dir_pdf_path(output_png: Path | None, output_dir: Path) -> Path | None:
    if not output_png:
        return None
    return output_dir / f"{output_png.stem}.pdf"


def output_dir_webp_path(output_png: Path | None, output_dir: Path) -> Path | None:
    if not output_png:
        return None
    return output_dir / f"{output_png.stem}.webp"