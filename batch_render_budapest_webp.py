from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image

from generator.core.render_dispatcher import render_product
from generator.core.style_registry import STYLE_REGISTRY
from generator.specs import ProductLine, spec_from_size_key, validate_size_key_for_product_line


OUTPUT_DIR = Path("output")
CITY = "budapest"
SIZE_KEY = "50x70"
EXTENT_M = 5000
CENTER_LAT = 47.4978789
CENTER_LON = 19.0402383
TITLE = "BUDAPEST"
SUBTITLE = "47.4979 N 19.0402 E"
MAX_WEBP_BYTES = 150 * 1024
MAX_WEBP_LONG_SIDE = 1500


def _resize_to_max_long_side(image: Image.Image, max_long_side: int) -> Image.Image:
    w, h = image.size
    long_side = max(w, h)
    if long_side <= max_long_side:
        return image
    scale = max_long_side / long_side
    new_w = round(w * scale)
    new_h = round(h * scale)
    return image.resize((new_w, new_h), Image.LANCZOS)


def _save_webp_under_cap(source_png: Path, target_webp: Path, max_size: int) -> None:
    quality_steps = [90, 84, 78, 72, 66, 60, 54, 48, 42, 36, 30]
    methods = [6, 4]

    with Image.open(source_png) as raw:
        image = _resize_to_max_long_side(raw, MAX_WEBP_LONG_SIDE)
        saved = False
        for method in methods:
            for quality in quality_steps:
                image.save(
                    target_webp,
                    format="WEBP",
                    quality=quality,
                    method=method,
                    optimize=True,
                )
                if target_webp.stat().st_size <= max_size:
                    saved = True
                    break
            if saved:
                break

        if not saved:
            image.save(
                target_webp,
                format="WEBP",
                quality=24,
                method=6,
                optimize=True,
            )


def _safe_unlink(paths: Iterable[Path]) -> None:
    for path in paths:
        try:
            if path and path.exists():
                path.unlink()
        except Exception:
            pass


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    validate_size_key_for_product_line(SIZE_KEY, ProductLine.CITYMAP)
    spec = spec_from_size_key(SIZE_KEY, extent_m=EXTENT_M, dpi=300)

    style_names = list(STYLE_REGISTRY.keys())
    results: list[tuple[str, float]] = []

    for style_name in style_names:
        rendered = render_product(
            style_name=style_name,
            center_lat=CENTER_LAT,
            center_lon=CENTER_LON,
            spec=spec,
            output_dir=OUTPUT_DIR,
            title=TITLE,
            subtitle=SUBTITLE,
            preview_mode=False,
            order_id="DESIGN_TEST",
            use_cache=True,
        )

        prefix = rendered.output_svg.stem
        generated_webp = OUTPUT_DIR / f"{prefix}.webp"
        final_webp = OUTPUT_DIR / f"{CITY}_{style_name}_extent{EXTENT_M}_{SIZE_KEY}.webp"

        if generated_webp.exists():
            _save_webp_under_cap(generated_webp, final_webp, MAX_WEBP_BYTES)
        else:
            _save_webp_under_cap(rendered.output_png, final_webp, MAX_WEBP_BYTES)

        _safe_unlink([
            rendered.output_svg,
            rendered.output_png,
            rendered.output_pdf if rendered.output_pdf else Path(""),
            generated_webp if generated_webp.exists() else Path(""),
        ])

        kb = round(final_webp.stat().st_size / 1024.0, 2)
        results.append((style_name, kb))
        print(f"DONE {style_name}: {final_webp.name} ({kb} KB)")

    print("\nSUMMARY")
    for style_name, kb in results:
        print(f"- {style_name}: {kb} KB")


if __name__ == "__main__":
    main()
