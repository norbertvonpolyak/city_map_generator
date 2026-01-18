from __future__ import annotations

# ---------- bootstrap PYTHONPATH ----------
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# -----------------------------------------

import json
from pathlib import Path
from datetime import datetime
from dataclasses import asdict
from typing import Dict, Any

import numpy as np
import pandas as pd
import streamlit as st
import geopandas as gpd
import osmnx as ox

from shapely.geometry import Point

from generator.specs import spec_from_size_key, SIZES_CM
from generator.styles import MonoStyle, MONO_PRESETS
from generator.render_monochrome import render_city_map_monochrome
from generator.relief import ReliefConfig


# =========================================================
# ---------------------- CACHES ---------------------------
# =========================================================

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_roads(center_lat, center_lon, dist_m, network_type):
    G = ox.graph_from_point(
        (center_lat, center_lon),
        dist=dist_m,
        network_type=network_type,
        simplify=True,
    )
    try:
        G = ox.convert.to_undirected(G)
    except Exception:
        pass
    edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
    return edges


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_features(center_lat, center_lon, dist_m, tags):
    try:
        gdf = ox.features_from_point(
            (center_lat, center_lon),
            dist=dist_m,
            tags=tags,
        )
        return gdf
    except Exception:
        return None


# =========================================================
# ---------------------- UI SETUP -------------------------
# =========================================================

st.set_page_config(layout="wide")
st.title("Monochrome Map Style Tuner (FAST MODE)")

left, right = st.columns([0.38, 0.62], gap="large")

# =========================================================
# ---------------------- LEFT PANEL -----------------------
# =========================================================

with left:
    st.subheader("Viewport")

    center_lat = st.number_input("Latitude", value=47.5316754, format="%.8f")
    center_lon = st.number_input("Longitude", value=21.6252263, format="%.8f")

    size_keys = list(SIZES_CM.keys())
    default_ix = size_keys.index("30x40") if "30x40" in size_keys else 0
    size_key = st.selectbox("Size", size_keys, index=default_ix)

    extent_m = st.slider("Extent (m)", 1000, 10000, 2000, 250)
    zoom = st.slider("Zoom", 0.3, 1.2, 0.6, 0.05)

    preview_dpi = st.slider("Preview DPI", 50, 120, 70, 10)

    st.divider()

    st.subheader("OSM scope")
    network_type = st.selectbox(
        "Network type",
        ["drive"],
        index=0,
    )

    show_buildings = st.checkbox("Buildings", value=False)
    show_landuse = st.checkbox("Landuse", value=False)
    show_parks = st.checkbox("Parks", value=False)
    show_rail = st.checkbox("Rail", value=False)

    st.divider()

    st.subheader("Performance")
    collapse_parallels = st.checkbox("Collapse parallel roads", value=False)
    render_relief = st.checkbox("Render relief (slow)", value=False)

    st.divider()

    st.subheader("Style preset")
    preset_name = st.selectbox("Base preset", list(MONO_PRESETS.keys()))
    base = MONO_PRESETS[preset_name]

    background = st.color_picker("Background", base.background)
    water = st.color_picker("Water", base.water_fill)
    buildings = st.color_picker("Buildings", base.buildings_fill)

    st.subheader("Road colors")
    highway = st.color_picker("Highway", base.highway_fill)
    arterial = st.color_picker("Arterial", base.arterial_fill)
    local = st.color_picker("Local", base.local_fill)
    minor = st.color_picker("Minor", base.minor_fill)

    st.subheader("Road widths")
    road_width = st.slider("Base width", 0.4, 3.0, base.road_width, 0.05)
    road_boost = st.slider("Global boost", 0.6, 2.0, base.road_boost, 0.05)

    lw_highway = st.slider("Highway mult", 0.8, 2.0, base.lw_highway_mult, 0.05)
    lw_arterial = st.slider("Arterial mult", 0.8, 1.6, base.lw_arterial_mult, 0.05)
    lw_local = st.slider("Local mult", 0.5, 1.2, base.lw_local_mult, 0.05)
    lw_minor = st.slider("Minor mult", 0.3, 1.0, base.lw_minor_mult, 0.05)

    st.divider()
    apply = st.button("Apply changes", type="primary")

# =========================================================
# ---------------------- RIGHT PANEL ----------------------
# =========================================================

with right:
    if not apply:
        st.info("Adjust sliders, then click **Apply changes**")
        st.stop()

    # 1) build style
    style = MonoStyle(
        background=background,
        water_fill=water,
        water_edge=water,
        buildings_fill=buildings,

        highway_fill=highway,
        arterial_fill=arterial,
        local_fill=local,
        minor_fill=minor,

        road_width=road_width,
        road_boost=road_boost,

        lw_highway_mult=lw_highway,
        lw_arterial_mult=lw_arterial,
        lw_local_mult=lw_local,
        lw_minor_mult=lw_minor,
    )

    # 2) JSON preview (copy-paste)
    st.subheader("MonoStyle JSON (copy-paste)")
    st.code(
        json.dumps({"mono_style": asdict(style)}, ensure_ascii=False, indent=2),
        language="json",
    )

    # 3) render
    with st.spinner("Rendering preview…"):
        spec = spec_from_size_key(size_key, extent_m=int(extent_m), dpi=int(preview_dpi))
        relief_cfg = ReliefConfig(enabled=render_relief)

        result = render_city_map_monochrome(
            center_lat=center_lat,
            center_lon=center_lon,
            spec=spec,
            output_dir=Path("tmp"),
            zoom=zoom,
            network_type_draw=network_type,

            show_buildings=show_buildings,
            show_landuse=show_landuse,
            show_parks=show_parks,
            show_rail=show_rail,

            collapse_parallels=collapse_parallels,
            relief=relief_cfg,

            style=style,
            preview=True,
        )

    if result.output_png:
        st.image(str(result.output_png), use_container_width=True)

    st.divider()
    st.subheader("Export default preset (writes JSON into repo)")

    DEFAULT_MONO_JSON_PATH = Path("generator") / "presets" / "monochrome_default.json"

    if st.button("Export default MONO JSON"):
        DEFAULT_MONO_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "version": "mono-default-v1",
            "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "mono_style": asdict(style),
            "defaults": {
                "zoom": float(zoom),
                "extent_m": int(extent_m),
                "network_type": str(network_type),
            },
        }

        DEFAULT_MONO_JSON_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        st.success("Saved monochrome default JSON")
        st.write(str(DEFAULT_MONO_JSON_PATH.resolve()))
