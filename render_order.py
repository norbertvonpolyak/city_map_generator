"""Manually render one city order from a local OSM source through the existing map pipeline.

Edit the configuration block below and run this file with the project's Python interpreter.

- ``SOURCE_PATH`` ending in ``.osm``/``.xml``: raw OSM XML order. The XML is streamed into a temporary
  per-order store that is removed afterwards; no persistent cache is created by default.
- ``SOURCE_PATH`` ending in ``.pbf``: PBF order through the validated persistent PBF store.

``SIZES`` accepts webshop catalog keys (``generator.specs.SIZES_CM``) and, for internal requests,
explicit ``(print_width_cm, print_height_cm)`` pairs such as ``(45, 65)``. ``None`` renders the catalog.
"""

from __future__ import annotations

import os
from pathlib import Path

from generator.specs import DEFAULT_EXTENT_M, SIZES_CM


# Order configuration: update these values for each manually processed order.
SOURCE_PATH = Path(__file__).resolve().parents[1] / "raw_osm" / "minszk.osm"
CITY_NAME = "Minsk"
CENTER_LAT: float | None = None  # XML: None uses the verified source-bounds midpoint. PBF: required.
CENTER_LON: float | None = None
STYLE = "luxury_gold"
SIZES: list | None = ["50x50"]  # Catalog keys and/or (width_cm, height_cm) pairs; None selects SIZES_CM.
EXTENT_M: float | None = 2500  # Projected viewport half-height in metres; None uses specs.DEFAULT_EXTENT_M.
OUTPUT_DIR = Path(__file__).resolve().parent / "output" / "orders"
DPI = 300

# XML only: opt-in persistent store directory (None keeps the default temporary per-order store).
XML_PERSISTENT_STORE_DIR: Path | None = None

LOCAL_APP_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
PREFERRED_STORE_DIR = LOCAL_APP_DATA / "MapCanvas" / "pbf_store"
CACHE_ROOT = LOCAL_APP_DATA / "MapCanvas" / "order_renderer" / "cache"


def main() -> int:
    selected_sizes = list(SIZES_CM) if SIZES is None else list(SIZES)
    resolved_extent = DEFAULT_EXTENT_M if EXTENT_M is None else EXTENT_M
    center = None if CENTER_LAT is None or CENTER_LON is None else (CENTER_LAT, CENTER_LON)

    if SOURCE_PATH.suffix.casefold() in {".osm", ".xml"}:
        from generator.xml_order import render_xml_order

        result = render_xml_order(
            xml_path=SOURCE_PATH,
            city_name=CITY_NAME,
            style=STYLE,
            sizes=selected_sizes,
            extent_m=resolved_extent,
            output_dir=OUTPUT_DIR,
            center=center,
            dpi=DPI,
            persistent_store_dir=XML_PERSISTENT_STORE_DIR,
        )
        for label, record in result["results"].items():
            print(f"[{label}] {record['status']} {record.get('output_dir') or record.get('error')}")
        print(f"CLEANUP: {result['cleanup']}")
        print(f"PHASE PEAK RSS (bytes): {result['phase_peak_rss_bytes']}")
        print(
            f"ORDER SUMMARY expected={result['expected']} success={result['success']} failed={result['failed']} "
            f"total_s={result['total_s']} peak_rss_bytes={result['process_peak_rss_bytes']} "
            f"temp_disk_peak_bytes={result['temporary_disk_peak_bytes']}"
        )
        return 0 if result["failed"] == 0 else 1

    if center is None:
        raise SystemExit("PBF orders require CENTER_LAT and CENTER_LON")
    from generator.order_renderer import render_order

    result = render_order(
        pbf_path=SOURCE_PATH,
        city_name=CITY_NAME,
        center_lat=center[0],
        center_lon=center[1],
        style=STYLE,
        sizes=tuple(selected_sizes),
        extent_m=resolved_extent,
        output_dir=OUTPUT_DIR,
        cache_root=CACHE_ROOT,
        preferred_store_dir=PREFERRED_STORE_DIR,
        dpi=DPI,
    )
    print(
        f"ORDER SUMMARY expected={result['expected']} success={result['success']} "
        f"failed={result['failed']} manifest={result['manifest']}"
    )
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
