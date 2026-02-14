import argparse
import time
from pathlib import Path

from generator.specs import (
    ProductLine,
    spec_from_size_key,
    validate_size_key_for_product_line,
)
from generator.render import render_city_map
from generator.render_pretty import render_city_map_pretty


# =============================================================================
# ARG PARSER
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="City Map Renderer")

    p.add_argument(
        "--mode",
        choices=["blocks", "pretty"],
        default="blocks",
    )

    p.add_argument("--size-key", default="91x61")
    p.add_argument("--extent-m", type=int, default=2000)
    p.add_argument("--dpi", type=int, default=300)

    # Dev defaults (CLI-ből felülírható)
    p.add_argument("--center-lat", type=float, default=52.37025557713184)
    p.add_argument("--center-lon", type=float, default=4.8982369032362545)

    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path(r"C:\Users\Q642000\OneDrive - BMW Group\Asztal\Sajat\RENDERED IMAGES"),
    )

    p.add_argument("--palette", default="urban_modern")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--zoom", type=float, default=0.6)

    return p


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    total_start = time.perf_counter()

    args = build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    product_line = ProductLine.CITYMAP
    validate_size_key_for_product_line(args.size_key, product_line)

    spec = spec_from_size_key(
        args.size_key,
        extent_m=args.extent_m,
        dpi=args.dpi,
    )

    print("--------------------------------------------------")
    print(f"Mode: {args.mode}")
    print(f"Palette: {args.palette}")
    print("Rendering...")
    print("--------------------------------------------------")

    render_start = time.perf_counter()

    # -------------------------------------------------------------------------
    # BLOCKS
    # -------------------------------------------------------------------------

    if args.mode == "blocks":
        result = render_city_map(
            center_lat=args.center_lat,
            center_lon=args.center_lon,
            spec=spec,
            output_dir=args.output_dir,
            palette_name=args.palette,
            seed=args.seed,
            filename_prefix="city_blocks",
        )

        print("Output:", result.output_pdf)

    # -------------------------------------------------------------------------
    # PRETTY
    # -------------------------------------------------------------------------

    elif args.mode == "pretty":
        result = render_city_map_pretty(
            center_lat=args.center_lat,
            center_lon=args.center_lon,
            spec=spec,
            output_dir=args.output_dir,
            palette_name=args.palette,
            zoom=args.zoom,
        )

        print("Output:", result.output_pdf)

    render_end = time.perf_counter()
    total_end = time.perf_counter()

    print("--------------------------------------------------")
    print(f"Render time: {render_end - render_start:.2f} seconds")
    print(f"Total time : {total_end - total_start:.2f} seconds")
    print("--------------------------------------------------")


if __name__ == "__main__":
    main()
