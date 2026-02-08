import argparse
from pathlib import Path

from generator.specs import (
    ProductLine,
    spec_from_size_key,
    validate_size_key_for_product_line,
)
from generator.render import render_city_map
from generator.render_pretty import render_city_map_pretty
from generator.render_monochrome import render_city_map_monochrome
from generator.relief import ReliefConfig
from generator.render_stars import render_star_map_stub


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Renderer")

    # Mode
    p.add_argument(
        "--mode",
        choices=["blocks", "pretty", "monochrome", "stars"],
        default="blocks",
        help="Render mode: blocks / pretty / monochrome / stars",
    )

    # CORE INPUTS
    p.add_argument("--size-key", default="50x50", help="Product size key (e.g. 30x40, 50x50)")
    p.add_argument("--extent-m", type=int, default=2000, help="Extent in meters (e.g. 2000, 5000)")
    p.add_argument("--dpi", type=int, default=300, help="Export DPI")
    p.add_argument("--center-lat", type=float, default=52.37025557713184, help="Center latitude")
    p.add_argument("--center-lon", type=float, default=4.8982369032362545, help="Center longitude")
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path(r"C:\Users\Q642000\OneDrive - BMW Group\Asztal\Sajat\RENDERED IMAGES"),
        help="Output directory",
    )

    # ---------------
    # BLOCKS / PRETTY
    # ---------------

    p.add_argument("--palette", default="grayscale", help="Palette name (blocks/pretty). Ignored in monochrome.")
    p.add_argument("--seed", type=int, default=42, help="Seed (blocks; also used in monochrome)")
    p.add_argument("--zoom", type=float, default=0.6, help="Zoom factor for pretty/monochrome (e.g. 0.6 or 0.4)")

    # ----------
    # MONOCHROME
    # ----------

    # toggles
    p.add_argument("--no-relief", action="store_true", help="Disable hillshade relief in monochrome")
    p.add_argument("--dem-dir", type=Path, default=Path("data/dem"), help="DEM GeoTIFF cache directory")
    p.add_argument("--no-buildings", action="store_true", help="Disable buildings in monochrome")
    # controls
    p.add_argument("--mono-road-width", type=float, default=1.15, help="Monochrome base road width")
    p.add_argument("--mono-road-boost", type=float, default=1.0, help="Extra multiplier for all monochrome roads")
    p.add_argument(
        "--mono-parallel-tol-m",
        type=float,
        default=7.0,
        help="Collapse parallel roads: distance tolerance in meters (bigger = more aggressive)",
    )
    p.add_argument(
        "--mono-parallel-angle-deg",
        type=float,
        default=12.0,
        help="Collapse parallel roads: angle tolerance in degrees (bigger = more aggressive)",
    )
    p.add_argument("--mono-min-building-area", type=float, default=12.0, help="Min building area (m^2-ish in proj CRS)")
    # switch network detail in monochrome
    p.add_argument(
        "--mono-network",
        default="all",
        choices=["all", "all_private", "drive", "drive_service", "walk", "bike"],
        help="OSMnx network_type for monochrome roads",
    )

    # -------
    # STARMAP
    # -------

    p.add_argument("--stars-cutoff-mag", type=float, default=5.8, help="Magnitude cutoff for stars (higher = denser). Typical: 5.0-6.0")
    p.add_argument("--stars-glow", action="store_true", default=True, help="Enable simple halo/glow effect for bright stars")

    p.add_argument("--stars-title", type=str, default="Tamara & Norbert")
    p.add_argument("--stars-motto", type=str, default="THE NIGHT OUR LOVE WAS BORN")
    p.add_argument("--stars-location", type=str, default="KIRÁLYRÉT")
    p.add_argument("--stars-date", type=str, default="MAY 8, 2022")
    p.add_argument("--stars-lat", type=float, default=47.894722)
    p.add_argument("--stars-lon", type=float, default=18.977778)

    return p


def main() -> None:
    args = build_parser().parse_args()

    # Ensure output dir exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # TERMÉKVONAL meghatározása + méret validálás
    # ------------------------------------------------------------
    product_line = ProductLine.STARMAP if args.mode == "stars" else ProductLine.CITYMAP

    # Csak STARMAP-nál aktív a korlátozás (fekvő OFF, négyzetből csak 50x50)
    validate_size_key_for_product_line(args.size_key, product_line)

    # Build spec
    spec = spec_from_size_key(args.size_key, extent_m=args.extent_m, dpi=args.dpi)

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
        print("Blocks output:", result.output_pdf)
        return

    if args.mode == "pretty":
        result = render_city_map_pretty(
            center_lat=args.center_lat,
            center_lon=args.center_lon,
            spec=spec,
            output_dir=args.output_dir,
            palette_name=args.palette,
            zoom=args.zoom,
        )
        print("Pretty output:", result.output_pdf)
        return

    if args.mode == "stars":
        result = render_star_map_stub(
            spec=spec,
            output_dir=args.output_dir,
            seed=args.seed,
            filename_prefix="star_map",
            cutoff_mag=args.stars_cutoff_mag,
            enable_glow=args.stars_glow,
            title=args.stars_title,
            motto=args.stars_motto,
            location_name=args.stars_location,
            date_text=args.stars_date,
            lat=args.stars_lat,
            lon=args.stars_lon,
        )

        print("Stars output:", result.output_pdf)
        print("Stars preview:", result.output_preview_png)
        return

    # Monochrome
    relief_cfg = ReliefConfig(
        enabled=(not args.no_relief),
        cache_dir=str(args.dem_dir),
    )

    result = render_city_map_monochrome(
        center_lat=args.center_lat,
        center_lon=args.center_lon,
        spec=spec,
        output_dir=args.output_dir,
        zoom=args.zoom,
        preset_name="snazzy_bw_blackwater",
        relief=relief_cfg,
        draw_non_vehicular=False,  # FALSE -> gyalog/bicikli/path NEM rajzolódik
        # collapse_parallels=False, # opcionális, default is False
    )

    print("Monochrome output:", result.output_pdf)


if __name__ == "__main__":
    main()
