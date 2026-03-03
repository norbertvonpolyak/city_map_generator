from __future__ import annotations

import argparse
import time
from pathlib import Path

from generator.specs import (
    ProductLine,
    spec_from_size_key,
    validate_size_key_for_product_line,
)

from generator.core.render_dispatcher import render_product


# =============================================================================
# ARG PARSER
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="City Map Renderer – B Architecture (SVG pipeline)"
    )

    p.add_argument("--size-key", default="50x50")
    p.add_argument("--extent-m", type=int, default=2000) #48.13654710283969, 11.576770383227576
    p.add_argument("--dpi", type=int, default=300)

    p.add_argument("--center-lat", type=float,
                   default=48.13654710283969)
    p.add_argument("--center-lon", type=float,
                   default=11.576770383227576)

    p.add_argument("--palette", default="pretty_buildings")
    p.add_argument("--seed", type=int, default=42)

    p.add_argument("--title", type=str,
                   default="MÜNCHEN")

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
    print("Rendering product via style dispatcher")
    print("--------------------------------------------------")

    subtitle_text = (
        args.subtitle
        if args.subtitle
        else format_short_coords(args.center_lat, args.center_lon)
    )

    # -------------------------------------------------------------------------
    # PREVIEW RENDER
    # -------------------------------------------------------------------------

    output_path = render_product (
        style_name=args.palette,
        center_lat=args.center_lat,
        center_lon=args.center_lon,
        spec=spec,
        output_dir=args.output_dir,
        title=args.title,
        subtitle=subtitle_text,
        preview_mode=False,
        order_id="DESIGN_TEST",  # ← EZ KELL
    )

    print("Preview output:", output_path)

    total_end = time.perf_counter()
    print(f"Total time : {total_end - total_start:.2f} seconds")


if __name__ == "__main__":
    main()
