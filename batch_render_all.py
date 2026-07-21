#!/usr/bin/env python3
"""
Batch render all cities with all styles.
- Loads cities from JSON (lat, lon, extent defined)
- Renders 50x70 for each city × style combination
- Converts to WebP (max 1500px longest side, max 150KB)
- Naming: {cityname}_{stylename}_{extent}_50x70.webp
- Skips existing files, uses cache
"""

import json
import subprocess
import sys
import re
from pathlib import Path
from PIL import Image

CITIES_JSON = Path(__file__).parent.parent / "woocommerce_helpers" / "data" / "cities_with_coords.json"
OUTPUT_DIR = Path(__file__).parent / "output"

# Import all styles
sys.path.insert(0, str(Path(__file__).parent))
from generator.core.style_registry import STYLE_REGISTRY

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

def get_webp_filename(city_name, style, extent):
    """Generate WebP filename: cityname_stylename_extentXXXX_50x70.webp"""
    return f"{city_name.lower()}_{style}_{extent}_50x70.webp"

def render_city(city_name, lat, lon, extent, style):
    """Render city and convert to WebP."""
    webp_name = get_webp_filename(city_name, style, extent)
    webp_path = OUTPUT_DIR / webp_name
    
    if webp_path.exists():
        size_kb = webp_path.stat().st_size / 1024
        return ("SKIP", size_kb)
    
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
        
        # Convert to WebP (1500px max, optimize to <=150KB)
        img = Image.open(png_path)
        orig_size = img.size
        
        # Scale if needed
        max_side = max(img.size)
        if max_side > 1500:
            scale = 1500 / max_side
            img = img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.Resampling.LANCZOS
            )
        
        # Find best quality to stay under 150KB
        quality = 85
        for q in [85, 75, 65, 55, 45]:
            img.save(webp_path, format="WEBP", quality=q, method=6)
            size = webp_path.stat().st_size / 1024
            if size <= 150:
                quality = q
                break
        
        # Final save with best quality found
        img.save(webp_path, format="WEBP", quality=quality, method=6)
        size_kb = webp_path.stat().st_size / 1024
        
        # Cleanup temp PNG
        try:
            png_path.unlink()
        except:
            pass
        
        return ("OK", size_kb)
        
    except Exception as e:
        return ("ERROR", None)

def main():
    cities = load_cities()
    styles = get_all_styles()
    
    print(f"[BATCH RENDER] {len(cities)} cities × {len(styles)} styles = {len(cities) * len(styles)} renders")
    print(f"Styles: {', '.join(styles)}")
    print(f"\nOutput format: {{cityname}}_{{stylename}}_{{extent}}_50x70.webp (max 150KB, max 1500px)\n")
    
    stats = {"OK": 0, "SKIP": 0, "ERROR": 0}
    total_kb = 0
    
    for city_idx, city_data in enumerate(cities, 1):
        name = city_data["name"]
        lat = float(city_data["lat"])
        lon = float(city_data["lon"])
        extent = int(city_data["extent"])
        
        print(f"[{city_idx}/{len(cities)}] {name} ({lat}, {lon}, extent={extent}m)")
        
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
    print(f"  Errors:       {stats['ERROR']}")
    print(f"  Total size:   {total_kb:.0f}KB")
    print(f"  Average:      {avg_kb:.0f}KB per file")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
