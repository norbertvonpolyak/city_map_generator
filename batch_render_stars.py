from __future__ import annotations

from pathlib import Path
from datetime import datetime

from generator.specs import (
    ProductLine,
    get_allowed_size_keys,
    spec_from_size_key,
)
from generator.render_stars import render_star_map_stub


def main() -> None:
    # Timestampelt mappa, hogy ne írjuk felül a korábbi futásokat
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("out") / "stars_samples" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    # Egységes demo szövegek (összehasonlíthatóság miatt)
    demo = dict(
        seed=42,
        cutoff_mag=5.8,
        enable_glow=True,
        title="Tamara & Norbert",
        motto="THE NIGHT OUR LOVE WAS BORN",
        location_name="KIRÁLYRÉT",
        date_text="MAY 8, 2022",
        lat=47.894722,
        lon=18.977778,
    )

    # Csak a STARMAP-hoz engedélyezett méretek: nincs fekvő, négyzetből csak 50x50
    size_keys = get_allowed_size_keys(ProductLine.STARMAP)

    for size_key in sorted(size_keys):
        spec = spec_from_size_key(size_key=size_key, extent_m=2000, dpi=300)

        # fájlnév prefix: mindegyik méret külön fájl legyen
        prefix = f"stars_{size_key}"

        result = render_star_map_stub(
            spec=spec,

            output_dir=out_dir,
            filename_prefix=prefix,
            preview_dpi=350,
            **demo,
        )

        print(f"[OK] {size_key} -> {result.output_pdf.name} | {result.output_preview_png.name}")

    print(f"\nDONE. Output dir: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
