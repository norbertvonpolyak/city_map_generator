from __future__ import annotations

import json
import os
from pathlib import Path
import time
from time import perf_counter
from typing import Iterable

import osmnx as ox
from PIL import Image

from generator.core.render_dispatcher import render_product
from generator.core.style_registry import STYLE_REGISTRY
from generator.specs import ProductLine, spec_from_size_key, validate_size_key_for_product_line


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
CITY_DATA_PATH = BASE_DIR.parent / "woocommerce_helpers" / "data" / "cities_with_coords.json"
SIZE_KEY = "50x70"
MAX_WEBP_BYTES = 150 * 1024
MAX_WEBP_LONG_SIDE = 1500
RETRY_ATTEMPTS = max(int(os.getenv("BATCH_RETRY_ATTEMPTS", "3")), 1)
RETRY_DELAY_SECONDS = max(float(os.getenv("BATCH_RETRY_DELAY_SECONDS", "5")), 0.0)
OSMNX_REQUEST_TIMEOUT_SECONDS = max(int(os.getenv("BATCH_OSMNX_TIMEOUT_SECONDS", "60")), 5)
CITY_START_FROM = os.getenv("BATCH_CITY_START_FROM", "").strip()
CITY_ONLY = os.getenv("BATCH_CITY_ONLY", "").strip()

CITY_EXTENTS = {
    "Budapest": 5000,
    "Debrecen": 4500,
    "Szeged": 4000,
    "Miskolc": 4000,
    "Pécs": 4000,
    "Győr": 3500,
    "Nyíregyháza": 3500,
    "Kecskemét": 3500,
    "Székesfehérvár": 3000,
    "Érd": 3000,
    "Szombathely": 3000,
    "Tatabánya": 2500,
    "Sopron": 2500,
    "Eger": 2500,
    "Veszprém": 2500,
    "Szentendre": 2000,
    "Balatonfüred": 2000,
    "Tihany": 2000,
}

DEFAULT_EXTENT_M = 2500


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
    quality_steps = [90, 84, 78, 72, 66, 60, 54, 48, 42, 36, 30, 24, 18, 12, 8, 6]
    methods = [6, 4]

    with Image.open(source_png) as raw:
        image = _resize_to_max_long_side(raw, MAX_WEBP_LONG_SIDE)

        while True:
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

            if saved:
                return

            current_w, current_h = image.size
            if max(current_w, current_h) <= 600:
                return

            reduced_long_side = max(int(round(max(current_w, current_h) * 0.9)), 600)
            image = _resize_to_max_long_side(image, reduced_long_side)


def _to_float(value: object, field_name: str, city_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid {field_name} for city '{city_name}': {value!r}") from error


def _to_int(value: object, field_name: str, city_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid {field_name} for city '{city_name}': {value!r}") from error


def _city_name_from_record(city: dict[str, object]) -> str:
    value = city.get("city") or city.get("name")
    if not value:
        raise ValueError(f"City record is missing city/name field: {city!r}")
    return str(value)


def _country_from_record(city: dict[str, object]) -> str:
    value = city.get("country")
    return str(value) if value is not None else ""


def _lat_from_record(city: dict[str, object], city_name: str) -> float:
    return _to_float(city.get("lat"), "lat", city_name)


def _lon_from_record(city: dict[str, object], city_name: str) -> float:
    return _to_float(city.get("lon"), "lon", city_name)


def _extent_from_record(city: dict[str, object], city_name: str) -> int:
    return _to_int(city.get("extent"), "extent", city_name)


def _slugify_city_name(city_name: str) -> str:
    return "_".join(city_name.strip().lower().split())


def _subtitle_from_coords(latitude: float, longitude: float) -> str:
    lat_suffix = "N" if latitude >= 0 else "S"
    lon_suffix = "E" if longitude >= 0 else "W"
    return f"{abs(latitude):.4f} {lat_suffix} {abs(longitude):.4f} {lon_suffix}"


def load_cities() -> list[dict[str, object]]:
    with CITY_DATA_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError(f"Expected a list of city records in {CITY_DATA_PATH}, got {type(data).__name__}")

    return data


def assign_missing_extents(cities: list[dict[str, object]]) -> bool:
    modified = False

    for city in cities:
        city_name = _city_name_from_record(city)
        if "city" not in city and "name" in city:
            city["city"] = city["name"]
            modified = True

        if "extent" not in city or city.get("extent") in (None, ""):
            city["extent"] = CITY_EXTENTS.get(city_name, DEFAULT_EXTENT_M)
            modified = True

    return modified


def save_cities_if_modified(cities: list[dict[str, object]], modified: bool) -> None:
    if not modified:
        return

    with CITY_DATA_PATH.open("w", encoding="utf-8") as handle:
        json.dump(cities, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def render_city(
    *,
    city_name: str,
    country: str,
    latitude: float,
    longitude: float,
    extent: int,
    style_names: list[str],
) -> tuple[list[tuple[str, float]], list[str], list[tuple[str, str]]]:
    city_started = perf_counter()
    title = city_name.upper()
    subtitle = _subtitle_from_coords(latitude, longitude)
    city_slug = _slugify_city_name(city_name)
    results: list[tuple[str, float]] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []

    for style_name in style_names:
        final_webp = OUTPUT_DIR / f"{city_slug}_{style_name}_extent{extent}_{SIZE_KEY}.webp"

        if final_webp.exists() and final_webp.stat().st_size > 0:
            skipped.append(style_name)
            print(f"SKIP {city_name}, {country}, {style_name}: existing {final_webp.name}")
            continue

        for attempt in range(1, RETRY_ATTEMPTS + 1):
            style_started = perf_counter()
            try:
                spec = spec_from_size_key(SIZE_KEY, extent_m=extent, dpi=300)
                rendered = render_product(
                    style_name=style_name,
                    center_lat=latitude,
                    center_lon=longitude,
                    spec=spec,
                    output_dir=OUTPUT_DIR,
                    title=title,
                    subtitle=subtitle,
                    preview_mode=False,
                    order_id="DESIGN_TEST",
                    use_cache=True,
                )

                prefix = rendered.output_svg.stem
                generated_webp = OUTPUT_DIR / f"{prefix}.webp"

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
                style_elapsed = perf_counter() - style_started
                results.append((style_name, kb))
                print(
                    f"DONE {city_name}, {country}, {style_name}: "
                    f"{final_webp.name} ({kb} KB, {style_elapsed:.2f}s)"
                )
                break
            except Exception as error:
                if attempt < RETRY_ATTEMPTS:
                    print(
                        f"RETRY {city_name}, {country}, {style_name}: "
                        f"attempt {attempt}/{RETRY_ATTEMPTS} failed ({error})"
                    )
                    if RETRY_DELAY_SECONDS > 0:
                        time.sleep(RETRY_DELAY_SECONDS)
                else:
                    failed.append((style_name, str(error)))
                    print(
                        f"FAIL {city_name}, {country}, {style_name}: "
                        f"{error} (after {RETRY_ATTEMPTS} attempts)"
                    )

    city_elapsed = perf_counter() - city_started
    print(
        f"CITY_TIMING {city_name}: total={city_elapsed:.2f}s "
        f"rendered={len(results)} skipped={len(skipped)} failed={len(failed)}"
    )

    return results, skipped, failed


def _safe_unlink(paths: Iterable[Path]) -> None:
    for path in paths:
        try:
            if path and path.exists():
                path.unlink()
        except Exception:
            pass


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ox.settings.use_cache = True
    ox.settings.timeout = OSMNX_REQUEST_TIMEOUT_SECONDS

    cities = load_cities()
    modified = assign_missing_extents(cities)
    save_cities_if_modified(cities, modified)

    if CITY_ONLY:
        cities = [city for city in cities if _city_name_from_record(city).casefold() == CITY_ONLY.casefold()]
    elif CITY_START_FROM:
        start_index = 0
        found = False
        for index, city in enumerate(cities):
            if _city_name_from_record(city).casefold() == CITY_START_FROM.casefold():
                start_index = index
                found = True
                break
        if found:
            cities = cities[start_index:]

    validate_size_key_for_product_line(SIZE_KEY, ProductLine.CITYMAP)
    style_names = list(STYLE_REGISTRY.keys())
    results: list[tuple[str, str, float]] = []
    skipped_results: list[tuple[str, str]] = []
    failed_results: list[tuple[str, str, str]] = []

    for city in cities:
        city_name = _city_name_from_record(city)
        country = _country_from_record(city)
        latitude = _lat_from_record(city, city_name)
        longitude = _lon_from_record(city, city_name)
        extent = _extent_from_record(city, city_name)

        city_results, city_skipped, city_failed = render_city(
            city_name=city_name,
            country=country,
            latitude=latitude,
            longitude=longitude,
            extent=extent,
            style_names=style_names,
        )

        for style_name, kb in city_results:
            results.append((city_name, style_name, kb))

        for style_name in city_skipped:
            skipped_results.append((city_name, style_name))

        for style_name, error in city_failed:
            failed_results.append((city_name, style_name, error))

    print("\nSUMMARY")
    for city_name, style_name, kb in results:
        print(f"- {city_name} / {style_name}: {kb} KB")

    print("\nSKIPPED (already existed)")
    if skipped_results:
        for city_name, style_name in skipped_results:
            print(f"- {city_name} / {style_name}")
    else:
        print("- none")

    print("\nFAILED")
    if failed_results:
        for city_name, style_name, error in failed_results:
            print(f"- {city_name} / {style_name}: {error}")
    else:
        print("- none")


if __name__ == "__main__":
    main()
