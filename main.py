from pathlib import Path

from generator.specs import spec_from_size_key
from generator.render import render_city_map


def main() -> None:
    # Teszt paraméterek (később WooCommerce-ből jönnek)
    size_key = "50x50"
    extent_m = 6000  # default, de itt most direkt megadjuk
    palette_name = "warm"

    # Budapest középpont (teszt)
    center_lat = 41.385812657647385
    center_lon = 2.154530264356313

    # Kimeneti mappa (a tiéd)
    output_dir = Path(r"C:\Users\T470\OneDrive\Asztali gép\WEBSHOP")

    spec = spec_from_size_key(size_key, extent_m=extent_m, dpi=300)

    result = render_city_map(
        center_lat=center_lat,
        center_lon=center_lon,
        spec=spec,
        output_dir=output_dir,
        palette_name=palette_name,
        seed=42,
        filename_prefix="bp_blocks",
    )

    print("RENDER RESULT (placeholder):", result.output_pdf)


if __name__ == "__main__":
    main()
