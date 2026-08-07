# -*- coding: utf-8 -*-
"""
render_manual.py
================
Manuális, paraméterez­hető várostérkép-renderelő.

HASZNÁLAT:
  1. Állítsd be a paramétereket az alábbi blokkban.
  2. Futtasd: python render_manual.py

KIMENET:
  output/<varos>_<stilus>_<extent>m_<meret>.webp
  (max 150 KB, hosszabb oldal max 1500 px)

ELÉRHETŐ STÍLUSOK:
  Block engine   : urban_modern, midnight_ember
  Building engine: midnight_blue, architect_sage, warm_terracotta,
                   mono_black, royal_purple, sandstone_beige, luxury_gold
  Line engine    : vintage_atlas

ELÉRHETŐ MÉRETEK (cm):
  40x50, 50x40, 50x70, 70x50, 50x50, 60x90, 90x60
"""

from __future__ import annotations

# =============================================================================
#  PARAMETEREK - IDE IRD AT
# =============================================================================

# - "overpass": online Overpass API or "local": helyi .osm / .osm.xml fajl hasznalata
DATA_SOURCE = "local"

# --------------------------------------------------------------------------- #
# KÖZÖS PARAMÉTEREK
# --------------------------------------------------------------------------- #

CITY_NAME = "HELSINKI"            # Cim a poszteren (es a fajlnevben)
SIZE_KEY = "50x70"                # Plakatmeret kulcs (cm)
STYLE = "vintage_atlas"           # Stilus neve (lasd fent)
SUBTITLE = None                    # None -> automatikus koordinata felirat
OUTPUT_DIR_BASE = "output"        # Kimeneti mappa (a project gyokerehez kepest)
USE_CACHE = True                   # OSM gyorsitotar hasznalata

# --------------------------------------------------------------------------- #
# OVERPASS / API MÓD PARAMÉTEREI
# Csak akkor számítanak, ha DATA_SOURCE = "overpass"
# --------------------------------------------------------------------------- #

API_LAT = 44.8378                  # Szelessegi fok
API_LON = -0.5792                  # Hosszusagi fok
API_EXTENT_M = 5000                # Fel-extent meterben

# --------------------------------------------------------------------------- #
# LOCAL OSM/XML MÓD PARAMÉTEREI
# Csak akkor számítanak, ha DATA_SOURCE = "local"
# --------------------------------------------------------------------------- #

# Ha None, akkor az input/osm mappabol a legfrissebb *.osm vagy *.osm.xml lesz hasznalva.
# Ha megadod, lehet relativ (projecthez kepest) vagy abszolut utvonal.
LOCAL_OSM_FILE = "input/osm/Helsinki.osm"

# Ide mentsd a kezzel letoltott XML fajlokat:
#   city_map_generator/input/osm/
LOCAL_OSM_INPUT_DIR = "input/osm"

# Ha True, a helyi OSM fajl bbox-abol automatikusan szamol center/extentet.
# Ha False, akkor a lenti LOCAL_* center/extent ertekek lesznek hasznalva.
LOCAL_AUTO_FIT_TO_FILE = True
LOCAL_FIT_MARGIN = 0.90  # 0..1, kisebb = biztosabb peremhagyás

# Kezi local center/extent csak akkor szamit, ha LOCAL_AUTO_FIT_TO_FILE = False
LOCAL_LAT = 60.1710 
LOCAL_LON = 24.9375
LOCAL_EXTENT_M = 5000
LOCAL_USE_CACHE = True             # Local mod cache: True=ON, False=OFF

# Local extra render opciok
LOCAL_RENDER_ALL_OBJECTS = False    # Local XML-bol minel tobb objektum betoltese/rajzolasa
LOCAL_EXACT_WATER = True            # Local XML + Overpass pontos vizfelulet-egyesites
LOCAL_HIDE_LABELS = False           # Local modban cim es koordinata elrejtese
LOCAL_HIDE_VEGETATION = False       # Zoldteruletek elrejtese
LOCAL_HIDE_TREES = True             # Fa-pontok elrejtese
LOCAL_HIDE_WATER_LINES = True       # Vizfelszinen ne rajzoljon vonalakat






from manual_render_common import ManualRenderConfig, render_style


def main() -> None:
    result = render_style(
        ManualRenderConfig(
            data_source=DATA_SOURCE,
            city_name=CITY_NAME,
            size_key=SIZE_KEY,
            subtitle=SUBTITLE,
            output_dir_base=OUTPUT_DIR_BASE,
            use_cache=USE_CACHE,
            api_lat=API_LAT,
            api_lon=API_LON,
            api_extent_m=API_EXTENT_M,
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
        ),
        style_name=STYLE,
    )
    print(f"\nKesz! ({result.elapsed_seconds:.1f} s)")


if __name__ == "__main__":
    main()
