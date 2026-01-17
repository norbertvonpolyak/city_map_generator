import argparse
from pathlib import Path

from generator.specs import spec_from_size_key
from generator.render import render_city_map
from generator.render_pretty import render_city_map_pretty


def main() -> None:
    parser = argparse.ArgumentParser(description="City map renderer")
    parser.add_argument(
        "--mode",
        choices=["blocks", "pretty"],
        default="pretty",
        help="Render mode: blocks (abstract) or pretty (buildings)",
    )
    parser.add_argument(
        "--zoom",
        type=float,
        default=0.6,
        help="Zoom factor for pretty mode (e.g. 0.6 or 0.4)",
    )

    args = parser.parse_args()

    # Teszt paraméterek (később WooCommerce-ből jönnek)
    size_key = "50x50"
    extent_m = 2000
    palette_name = "warm"

    # Róma – teszt
    center_lat = 44.86797010403383
    center_lon = 13.84773563745901

    # Kimeneti mappa
    output_dir = Path(r"C:\Users\T470\OneDrive\Asztali gép\WEBSHOP")

    spec = spec_from_size_key(size_key, extent_m=extent_m, dpi=300)

    if args.mode == "blocks":
        result = render_city_map(
            center_lat=center_lat,
            center_lon=center_lon,
            spec=spec,
            output_dir=output_dir,
            palette_name=palette_name,
            seed=42,
            filename_prefix="city_blocks",
        )
        print("Blocks output:", result.output_pdf)

    else:
        result = render_city_map_pretty(
            center_lat=center_lat,
            center_lon=center_lon,
            spec=spec,
            output_dir=output_dir,
            palette_name=palette_name,
            zoom=args.zoom,
        )
        print("Pretty output:", result.output_pdf)


if __name__ == "__main__":
    main()
