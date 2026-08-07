from __future__ import annotations

"""
batch_render_manual.py
======================
Parameterezheto batch renderer ugyanazzal a logikaval, mint a render_manual.py.

HASZNALAT:
  1. Allitsd be a parametereket az alabi blokkban.
  2. Futtasd: python batch_render_manual.py

KIMENET:
  output/<varos>_<stilus>_<extent>m_<meret>.webp

MEGJEGYZES:
  Ha BATCH_STYLES = None, az osszes stilus lefut.
  Ha listat adsz meg, csak azok a stilusok renderelodnek.
"""

from manual_render_common import ManualRenderConfig, get_all_styles, render_style


# =============================================================================
#  PARAMETEREK - IDE IRD AT
# =============================================================================

DATA_SOURCE = "local"

CITY_NAME = "BUDAPEST"
SIZE_KEY = "50x70"
SUBTITLE = None
OUTPUT_DIR_BASE = "output"
USE_CACHE = True

LOCAL_OSM_FILE = "input/osm/Budapest.osm"
LOCAL_OSM_INPUT_DIR = "input/osm"
LOCAL_AUTO_FIT_TO_FILE = True
LOCAL_FIT_MARGIN = 0.90
LOCAL_LAT = 47.4979
LOCAL_LON = 19.0402     
LOCAL_EXTENT_M = 5000
LOCAL_USE_CACHE = True
LOCAL_RENDER_ALL_OBJECTS = False
LOCAL_EXACT_WATER = True
LOCAL_HIDE_LABELS = False
LOCAL_HIDE_VEGETATION = False
LOCAL_HIDE_TREES = True
LOCAL_HIDE_WATER_LINES = True

# None -> az osszes elerheto stilus.
# Pelda: ["midnight_blue", "architect_sage", "vintage_atlas"]
BATCH_STYLES = None

# True eseten a mar letezo webp-ket atugorja.
SKIP_EXISTING = True


def main() -> None:
    config = ManualRenderConfig(
        data_source=DATA_SOURCE,
        city_name=CITY_NAME,
        size_key=SIZE_KEY,
        subtitle=SUBTITLE,
        output_dir_base=OUTPUT_DIR_BASE,
        use_cache=USE_CACHE,
        api_lat=None,
        api_lon=None,
        api_extent_m=None,
        local_osm_file=LOCAL_OSM_FILE,
        local_osm_input_dir=LOCAL_OSM_INPUT_DIR,
        local_auto_fit_to_file=LOCAL_AUTO_FIT_TO_FILE,
        local_fit_margin=LOCAL_FIT_MARGIN,
        local_lat=LOCAL_LAT,
        local_lon=LOCAL_LON,
        local_extent_m=LOCAL_EXTENT_M,
        local_use_cache=LOCAL_USE_CACHE,
        local_render_all_objects=LOCAL_RENDER_ALL_OBJECTS,
        local_exact_water=LOCAL_EXACT_WATER,
        local_hide_labels=LOCAL_HIDE_LABELS,
        local_hide_vegetation=LOCAL_HIDE_VEGETATION,
        local_hide_trees=LOCAL_HIDE_TREES,
        local_hide_water_lines=LOCAL_HIDE_WATER_LINES,
    )

    styles = BATCH_STYLES or get_all_styles()
    if not styles:
        raise ValueError("Nincs egyetlen renderelendo stilus sem.")

    print(f"[BATCH MANUAL] {len(styles)} stilus")
    print(f"Varos: {CITY_NAME} | Meret: {SIZE_KEY} | Forras: {DATA_SOURCE}")
    print(f"Stilusok: {', '.join(styles)}")

    stats = {"OK": 0, "SKIP": 0, "ERROR": 0}

    for index, style_name in enumerate(styles, start=1):
        print(f"\n[{index}/{len(styles)}] {style_name}")
        try:
            result = render_style(config, style_name=style_name, skip_existing=SKIP_EXISTING)
            stats[result.status] = stats.get(result.status, 0) + 1
            size_kb = result.size_bytes / 1024 if result.size_bytes else 0
            print(f"[{result.status}] {result.output_path.name} ({size_kb:.1f} KB)")
        except Exception as exc:
            stats["ERROR"] += 1
            print(f"[ERROR] {style_name}: {exc}")

    print("\n" + "=" * 60)
    print("Osszegzes")
    print(f"  OK    : {stats['OK']}")
    print(f"  SKIP  : {stats['SKIP']}")
    print(f"  ERROR : {stats['ERROR']}")
    print("=" * 60)


if __name__ == "__main__":
    main()