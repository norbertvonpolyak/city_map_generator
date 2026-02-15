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
# HELPERS
# =============================================================================

def format_coordinate(value: float, is_lat: bool) -> str:
    """
    4 tizedesre vágott koordináta formázás
    Égtáj jelöléssel
    """
    direction = ""
    if is_lat:
        direction = "N" if value >= 0 else "S"
    else:
        direction = "E" if value >= 0 else "W"

    return f"{abs(value):.4f}° {direction}"


# =============================================================================
# ARG PARSER
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="City Map Renderer – B Architecture"
    )

    p.add_argument("--size-key", default="50x50")
    p.add_argument("--extent-m", type=int, default=2000)
    p.add_argument("--dpi", type=int, default=300)

    p.add_argument("--center-lat", type=float,
                   default=52.37025557713184)
    p.add_argument("--center-lon", type=float,
                   default=4.8982369032362545)

    p.add_argument("--palette", default="urban_modern")
    p.add_argument("--seed", type=int, default=42)

    p.add_argument("--title", type=str,
                   default="Washington D.C.")

    # Ha None → automatikusan generáljuk
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
        default=r"C:\Users\Q642000\PycharmProjects\city_map_generator\Fonts\Monoton-Regular.ttf",
    )

    return p


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
    print("Step 1: Rendering map layer")
    print("--------------------------------------------------")

    # -------------------------------------------------------------------------
    # STEP 1 – MAP LAYER
    # -------------------------------------------------------------------------

    map_layer_result = render_city_map(
        center_lat=args.center_lat,
        center_lon=args.center_lon,
        spec=spec,
        output_dir=args.output_dir,
        palette_name=args.palette,
        seed=args.seed,
    )

    map_png_path = map_layer_result.output_png
    print("Map layer PNG:", map_png_path)

    # -------------------------------------------------------------------------
    # SUBTITLE AUTO GENERATION
    # -------------------------------------------------------------------------

    if args.subtitle is None:
        lat_str = format_coordinate(args.center_lat, is_lat=True)
        lon_str = format_coordinate(args.center_lon, is_lat=False)
        subtitle = f"{lat_str} {lon_str}"
    else:
        subtitle = args.subtitle

    print("Subtitle:", subtitle)

    print("--------------------------------------------------")
    print("Step 2: Composing final print PDF")
    print("--------------------------------------------------")

    # -------------------------------------------------------------------------
    # STEP 2 – FINAL PDF
    # -------------------------------------------------------------------------

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")

    layout_result = compose_print_pdf(
        spec=spec,
        map_image_path=map_png_path,
        output_dir=args.output_dir,
        size_key=args.size_key,
        title=args.title,
        subtitle=subtitle,
        font_path=args.font_path,
    )

    print("Final PDF:", layout_result.output_pdf)

    total_end = time.perf_counter()

    print("--------------------------------------------------")
    print(f"Total time : {total_end - total_start:.2f} seconds")
    print("--------------------------------------------------")


if __name__ == "__main__":
    main()
