#!/usr/bin/env python3
"""
Batch render all cities with all styles.
- Loads cities from JSON (lat, lon, extent defined)
- For each city: pre-warms OSM bundle caches in-process (one Overpass fetch
  per unique viewport geometry, shared across all styles of the same size)
- Renders 50x70 for each city × style combination
- Converts to WebP (max 1500px longest side, max 150KB)
- Naming: {cityname}_{stylename}_{extent}_50x70.webp
- Skips existing files, uses cache
"""

import json
import subprocess
import sys
import re
import os
from pathlib import Path
from PIL import Image

# Bypass any system/corporate proxy for Overpass API requests
for _var in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
    os.environ.pop(_var, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

CITIES_JSON = Path(__file__).parent.parent / "woocommerce_helpers" / "data" / "cities_with_coords.json"
OUTPUT_DIR = Path(__file__).parent / "output"
MAX_WEBP_BYTES = 150 * 1024
MAX_WEBP_LONG_SIDE = 1500

# Import all styles
sys.path.insert(0, str(Path(__file__).parent))
from generator.core.style_registry import STYLE_REGISTRY
from generator.core.render_dispatcher import get_viewport_for_style
from generator.core.osm_bundle_cache import load_or_build_shared_osm_bundle
from generator.specs import spec_from_size_key

SIZE_KEY = "50x70"


def _resize_to_max_long_side(image: Image.Image, max_long_side: int) -> Image.Image:
    width, height = image.size
    long_side = max(width, height)
    if long_side <= max_long_side:
        return image

    scale = max_long_side / long_side
    return image.resize(
        (round(width * scale), round(height * scale)),
        Image.Resampling.LANCZOS,
    )


def _save_webp_under_cap(source_png: Path, target_webp: Path, max_size_bytes: int) -> float:
    quality_steps = [90, 84, 78, 72, 66, 60, 54, 48, 42, 36, 30, 24, 18, 12, 8, 6]
    methods = [6, 4]

    with Image.open(source_png) as raw:
        image = _resize_to_max_long_side(raw, MAX_WEBP_LONG_SIDE)

        while True:
            for method in methods:
                for quality in quality_steps:
                    image.save(
                        target_webp,
                        format="WEBP",
                        quality=quality,
                        method=method,
                        optimize=True,
                    )
                    if target_webp.stat().st_size <= max_size_bytes:
                        return target_webp.stat().st_size / 1024

            current_w, current_h = image.size
            if max(current_w, current_h) <= 600:
                return target_webp.stat().st_size / 1024

            reduced_long_side = max(int(round(max(current_w, current_h) * 0.9)), 600)
            image = _resize_to_max_long_side(image, reduced_long_side)

def load_cities():
    with open(CITIES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def get_all_styles():
    """Get all styles sorted by engine type"""
    from collections import defaultdict
    by_engine = defaultdict(list)
    for name in sorted(STYLE_REGISTRY.keys()):
        engine = STYLE_REGISTRY[name].engine
        by_engine[engine].append(name)
    
    # Flatten: BLOCK, BUILDING, LINE
    result = []
    for engine_type in ["block", "building", "line"]:
        result.extend(by_engine[engine_type])
    return result


def prime_city_caches(city_name: str, lat: float, lon: float, extent: int, styles: list):
    """Pre-warm a single OSM bundle cache covering all styles for the given city.

    Computes the maximum viewport across all styles and fetches once.  All styles
    with smaller viewports will automatically reuse this superset cache via the
    _find_superset_bundle_cache lookup in load_or_build_shared_osm_bundle.
    """
    spec = spec_from_size_key(SIZE_KEY, extent_m=extent)

    max_hw = max_hh = 0.0
    for style in styles:
        hw, hh = get_viewport_for_style(style, spec)
        if hw > max_hw:
            max_hw = hw
        if hh > max_hh:
            max_hh = hh

    print(f"  [CACHE] 1 fetch for {city_name}: hw={int(round(max_hw))}×hh={int(round(max_hh))} (covers all {len(styles)} styles)")

    load_or_build_shared_osm_bundle(
        center_lat=lat,
        center_lon=lon,
        extent_m=extent,
        half_width_m=max_hw,
        half_height_m=max_hh,
        use_cache=True,
    )

def get_webp_filename(city_name, style, extent):
    """Generate WebP filename: cityname_stylename_extentXXXX_50x70.webp"""
    return f"{city_name.lower()}_{style}_{extent}_50x70.webp"

def render_city(city_name, lat, lon, extent, style):
    """Render city and convert to WebP."""
    webp_name = get_webp_filename(city_name, style, extent)
    webp_path = OUTPUT_DIR / webp_name
    
    if webp_path.exists():
        size_kb = webp_path.stat().st_size / 1024
        if webp_path.stat().st_size <= MAX_WEBP_BYTES:
            return ("SKIP", size_kb)

        print(f"      Existing file exceeds 150KB target, rerendering: {webp_name} ({size_kb:.0f}KB)")
    
    # Render
    cmd = [
        sys.executable, "main.py",
        "--size-key", "50x70",
        "--center-lat", str(lat),
        "--center-lon", str(lon),
        "--title", city_name.upper(),
        "--palette", style,
        "--extent-m", str(extent),
    ]
    
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
            cwd=Path(__file__).parent
        )
        
        if result.returncode != 0:
            return ("ERROR", None)
        
        # Find PNG from stdout
        match = re.search(r"PNG output: output\\(.+?\.png)", result.stdout)
        if not match:
            return ("ERROR", None)
        
        png_name = match.group(1)
        png_path = OUTPUT_DIR / png_name
        
        if not png_path.exists():
            return ("ERROR", None)
        
        size_kb = _save_webp_under_cap(png_path, webp_path, MAX_WEBP_BYTES)
        
        # Cleanup all temp files (PNG, SVG, PDF)
        stem = png_path.stem
        for suffix in [".png", ".svg", ".pdf"]:
            tmp = OUTPUT_DIR / (stem + suffix)
            try:
                tmp.unlink(missing_ok=True)
            except:
                pass

        if webp_path.stat().st_size > MAX_WEBP_BYTES:
            return ("OVERSIZE", size_kb)

        return ("OK", size_kb)
        
    except Exception as e:
        return ("ERROR", None)

def main():
    cities = load_cities()
    styles = get_all_styles()
    
    print(f"[BATCH RENDER] {len(cities)} cities × {len(styles)} styles = {len(cities) * len(styles)} renders")
    print(f"Styles: {', '.join(styles)}")
    print(f"\nOutput format: {{cityname}}_{{stylename}}_{{extent}}_50x70.webp (max 150KB, max 1500px)\n")
    
    stats = {"OK": 0, "SKIP": 0, "OVERSIZE": 0, "ERROR": 0}
    total_kb = 0
    
    for city_idx, city_data in enumerate(cities, 1):
        name = city_data["name"]
        lat = float(city_data["lat"])
        lon = float(city_data["lon"])
        extent = int(city_data["extent"])
        
        print(f"[{city_idx}/{len(cities)}] {name} ({lat}, {lon}, extent={extent}m)")
        
        # Pre-warm OSM bundle cache for all unique viewports (in-process)
        prime_city_caches(name, lat, lon, extent, styles)

        for style_idx, style in enumerate(styles, 1):
            status, size_kb = render_city(name, lat, lon, extent, style)
            
            if status == "OK":
                stats["OK"] += 1
                total_kb += size_kb
                print(f"    [{style_idx}/{len(styles)}] {style}: OK ({size_kb:.0f}KB)")
            elif status == "SKIP":
                stats["SKIP"] += 1
                total_kb += size_kb
                print(f"    [{style_idx}/{len(styles)}] {style}: SKIP ({size_kb:.0f}KB)")
            elif status == "OVERSIZE":
                stats["OVERSIZE"] += 1
                total_kb += size_kb
                print(f"    [{style_idx}/{len(styles)}] {style}: OVERSIZE ({size_kb:.0f}KB)")
            else:
                stats["ERROR"] += 1
                print(f"    [{style_idx}/{len(styles)}] {style}: ERROR")
    
    total_renders = len(cities) * len(styles)
    avg_kb = total_kb / (stats["OK"] + stats["SKIP"]) if (stats["OK"] + stats["SKIP"]) > 0 else 0
    
    print(f"\n{'='*70}")
    print(f"SUMMARY:")
    print(f"  Total renders: {total_renders}")
    print(f"  Success:      {stats['OK']}")
    print(f"  Skipped:      {stats['SKIP']}")
    print(f"  Oversize:     {stats['OVERSIZE']}")
    print(f"  Errors:       {stats['ERROR']}")
    print(f"  Total size:   {total_kb:.0f}KB")
    print(f"  Average:      {avg_kb:.0f}KB per file")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
