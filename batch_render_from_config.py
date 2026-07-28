#!/usr/bin/env python3
"""
Batch render cities from config JSON file.
- Reads cities_with_coords.json
- Generates WebP for each city x style
- Skips existing files
- Optimizes for 150KB max, 1500px max dimension, 50x70 format
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from PIL import Image

sys.path.insert(0, ".")

from generator.core.style_registry import STYLE_REGISTRY
from generator.core.render_dispatcher import get_viewport_for_style
from generator.core.osm_bundle_cache import load_or_build_shared_osm_bundle
from generator.specs import spec_from_size_key

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

CONFIG_FILE = Path("../woocommerce_helpers/data/cities_with_coords.json")

MAX_BYTES = 150 * 1024
MAX_LONG = 1500
SIZE_KEY = "50x70"


def _resize(img, max_long):
    w, h = img.size
    longest = max(w, h)
    if longest <= max_long:
        return img
    scale = max_long / longest
    return img.resize(
        (round(w * scale), round(h * scale)),
        Image.Resampling.LANCZOS,
    )


def save_webp(src_png, dst_webp):
    """Convert PNG to WebP with compression to meet size constraint."""
    with Image.open(src_png) as raw:
        img = _resize(raw, MAX_LONG)
        for quality in [90, 84, 78, 72, 66, 60, 54, 48, 42, 36, 30, 24, 18, 12, 8, 6]:
            img.save(
                dst_webp,
                format="WEBP",
                quality=quality,
                method=6,
                optimize=True,
            )
            if dst_webp.stat().st_size <= MAX_BYTES:
                return dst_webp.stat().st_size / 1024
    return dst_webp.stat().st_size / 1024


def load_config():
    """Load cities config from JSON."""
    with open(CONFIG_FILE) as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("cities", [])


def main():
    cities = load_config()
    styles = sorted(STYLE_REGISTRY.keys())
    
    total_cities = len(cities)
    
    print(f"Loaded {total_cities} cities, {len(styles)} styles")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Size: {SIZE_KEY}, Max: {MAX_LONG}px / {MAX_BYTES//1024}KB")
    print("-" * 70)
    
    skipped_count = 0
    rendered_count = 0
    error_count = 0
    
    for city_idx, city in enumerate(cities, 1):
        name = city.get("name", "Unknown")
        lat = float(city.get("lat") or city.get("latitude") or 0)
        lon = float(city.get("lon") or city.get("longitude") or 0)
        extent = int(city.get("extent") or city.get("extent_m") or 0)
        
        if lat == 0 or lon == 0 or extent == 0:
            print(f"[{city_idx}/{total_cities}] {name}: SKIP (missing coords/extent)")
            skipped_count += 1
            continue
        
        # Check if all styles exist for this city
        existing = []
        missing = []
        for style in styles:
            webp = OUTPUT_DIR / f"{name.lower().replace(' ', '_')}_{style}_{extent}_50x70.webp"
            if webp.exists():
                existing.append(style)
            else:
                missing.append(style)
        
        if not missing:
            print(f"[{city_idx}/{total_cities}] {name}: SKIP (all {len(styles)} styles exist)")
            skipped_count += 1
            continue
        
        print(f"[{city_idx}/{total_cities}] {name}: rendering {len(missing)}/{len(styles)} styles (extent={extent}m)")
        
        # Compute max viewport for single cache fetch
        spec = spec_from_size_key(SIZE_KEY, extent_m=extent)
        max_hw = 0.0
        max_hh = 0.0
        for style in styles:
            hw, hh = get_viewport_for_style(style, spec)
            max_hw = max(max_hw, hw)
            max_hh = max(max_hh, hh)
        
        # Fetch OSM bundle once
        try:
            load_or_build_shared_osm_bundle(
                center_lat=lat,
                center_lon=lon,
                extent_m=extent,
                half_width_m=max_hw,
                half_height_m=max_hh,
                use_cache=True,
            )
        except KeyboardInterrupt:
            print(f"    ERROR: Overpass API timeout/interrupted")
            error_count += 1
            continue
        except Exception as e:
            print(f"    ERROR: OSM fetch failed: {str(e)[:100]}")
            error_count += 1
            continue
        
        # Render each style
        for style_idx, style in enumerate(missing, 1):
            webp = OUTPUT_DIR / f"{name.lower().replace(' ', '_')}_{style}_{extent}_50x70.webp"
            
            result = subprocess.run(
                [
                    sys.executable,
                    "main.py",
                    "--size-key", SIZE_KEY,
                    "--center-lat", str(lat),
                    "--center-lon", str(lon),
                    "--title", name.upper(),
                    "--palette", style,
                    "--extent-m", str(extent),
                ],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=Path("."),
                env=os.environ.copy(),
            )
            
            if result.returncode != 0:
                print(f"    [{style_idx}/{len(missing)}] {style}: ERROR")
                error_count += 1
                continue
            
            match = re.search(r"PNG output: output[/\\]+(.+?\.png)", result.stdout)
            if not match:
                print(f"    [{style_idx}/{len(missing)}] {style}: no PNG in stdout")
                error_count += 1
                continue
            
            png = OUTPUT_DIR / match.group(1)
            
            try:
                kb = save_webp(png, webp)
                
                # Cleanup temp files
                for suffix in (".png", ".svg", ".pdf"):
                    (OUTPUT_DIR / (png.stem + suffix)).unlink(missing_ok=True)
                
                print(f"    [{style_idx}/{len(missing)}] {style}: OK ({kb:.0f}KB)")
                rendered_count += 1
            except Exception as e:
                print(f"    [{style_idx}/{len(missing)}] {style}: WebP save failed: {e}")
                error_count += 1
    
    print("-" * 70)
    print(f"Results: {rendered_count} rendered, {skipped_count} skipped, {error_count} errors")


if __name__ == "__main__":
    main()
