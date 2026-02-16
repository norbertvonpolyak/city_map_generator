from __future__ import annotations

import argparse
import time
from pathlib import Path

from generator.specs import (
    ProductLine,
    spec_from_size_key,
    validate_size_key_for_product_line,
)

from generator.render import render_city_map
from generator.layout_composer import compose_print_pdf


# =============================================================================
# ARG PARSER
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="City Map Renderer – B Architecture (SVG pipeline)"
    )

    p.add_argument("--size-key", default="70x50")
    p.add_argument("--extent-m", type=int, default=2000)
    p.add_argument("--dpi", type=int, default=300)

    p.add_argument("--center-lat", type=float,
                   default=52.37025557713184)
    p.add_argument("--center-lon", type=float,
                   default=4.8982369032362545)

    p.add_argument("--palette", default="urban_modern")
    p.add_argument("--seed", type=int, default=42)

    p.add_argument("--title", type=str,
                   default="WASHINGTON D.C.")

    p.add_argument("--subtitle", type=str,
                   default=None)

    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
    )

    p.add_argument(
        "--font-path",
        type=str,
        default=None,
    )

    return p


# =============================================================================
# HELPERS
# =============================================================================

def format_short_coords(lat: float, lon: float) -> str:
    return f"{lat:.4f}° N {lon:.4f}° E"


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    total_start = time.perf_counter()

    args = build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # SPEC
    # -------------------------------------------------------------------------

    product_line = ProductLine.CITYMAP
    validate_size_key_for_product_line(args.size_key, product_line)

    spec = spec_from_size_key(
        args.size_key,
        extent_m=args.extent_m,
        dpi=args.dpi,
    )

    print("--------------------------------------------------")
    print("B Architecture Active")
    print("Step 1: Rendering map layer (SVG)")
    print("--------------------------------------------------")

    # -------------------------------------------------------------------------
    # STEP 1 – MAP LAYER (SVG)
    # -------------------------------------------------------------------------

    map_layer_result = render_city_map(
        center_lat=args.center_lat,
        center_lon=args.center_lon,
        spec=spec,
        output_dir=args.output_dir,
        palette_name=args.palette,
        seed=args.seed,
    )

    map_svg_path = map_layer_result.output_svg
    print("Map layer SVG:", map_svg_path)

    # -------------------------------------------------------------------------
    # STEP 2 – FINAL PRINT PDF
    # -------------------------------------------------------------------------

    print("--------------------------------------------------")
    print("Step 2: Composing final print PDF")
    print("--------------------------------------------------")

    subtitle_text = (
        args.subtitle
        if args.subtitle
        else format_short_coords(args.center_lat, args.center_lon)
    )

    layout_result = compose_print_pdf(
        spec=spec,
        map_svg_path=map_svg_path,
        output_dir=args.output_dir,
        size_key=args.size_key,
        title=args.title,
        subtitle=subtitle_text,
        font_path=args.font_path,
    )

    print("Final PDF:", layout_result.output_pdf)

    total_end = time.perf_counter()
    print(f"Total time : {total_end - total_start:.2f} seconds")


if __name__ == "__main__":
    main()
