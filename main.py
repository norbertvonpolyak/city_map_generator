# main.py
import argparse
from pathlib import Path
from generator.specs import spec_from_size_key
from generator.render import render_city_map
from generator.render_pretty import render_city_map_pretty
from generator.render_monochrome import render_city_map_monochrome
from generator.relief import ReliefConfig


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="City map renderer")

    # Mode
    p.add_argument(
        "--mode",
        choices=["blocks", "pretty", "monochrome"],
        default="monochrome",
        help="Render mode: blocks / pretty / monochrome",
    )

    # Core inputs
    p.add_argument("--size-key", default="50x50", help="Product size key (e.g. 30x40, 50x50)")
    p.add_argument("--extent-m", type=int, default=4000, help="Extent in meters (e.g. 2000, 5000)")
    p.add_argument("--dpi", type=int, default=300, help="Export DPI")
    p.add_argument("--center-lat", type=float, default=47.53167540125413, help="Center latitude")
    p.add_argument("--center-lon", type=float, default=21.62522630640404, help="Center longitude")

    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path(r"C:\Users\T470\OneDrive\Asztali gép\WEBSHOP"),
        help="Output directory",
    )

    # Blocks / pretty
    p.add_argument("--palette", default="warm", help="Palette name (blocks/pretty). Ignored in monochrome.")
    p.add_argument("--seed", type=int, default=42, help="Seed (blocks; also used in monochrome)")

    # Pretty / monochrome shared
    p.add_argument("--zoom", type=float, default=0.6, help="Zoom factor for pretty/monochrome (e.g. 0.6 or 0.4)")

    # Monochrome toggles
    p.add_argument("--no-relief", action="store_true", help="Disable hillshade relief in monochrome")
    p.add_argument("--dem-dir", type=Path, default=Path("data/dem"), help="DEM GeoTIFF cache directory")
    p.add_argument("--no-buildings", action="store_true", help="Disable buildings in monochrome")

    # Monochrome controls (your requested “from main I can tweak it” knobs)
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

    # Optional: switch network detail in monochrome
    p.add_argument(
        "--mono-network",
        default="all",
        choices=["all", "all_private", "drive", "drive_service", "walk", "bike"],
        help="OSMnx network_type for monochrome roads",
    )

    return p


def main() -> None:
    args = build_parser().parse_args()

    # Ensure output dir exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

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
        seed=args.seed,
        network_type_draw=args.mono_network,
        show_buildings=(not args.no_buildings),
        min_building_area=args.mono_min_building_area,
        relief=relief_cfg,
        road_width=args.mono_road_width,
        road_boost=args.mono_road_boost,
        parallel_tol_m=args.mono_parallel_tol_m,
        parallel_angle_tol_deg=args.mono_parallel_angle_deg,
    )
    print("Monochrome output:", result.output_pdf)


if __name__ == "__main__":
    main()
