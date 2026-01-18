import streamlit as st
from pathlib import Path


from generator.render_monochrome import render_city_map_monochrome
from generator.specs import spec_from_size_key
from generator.relief import ReliefConfig
from generator.styles import MonoStyle  # ezt megírjuk

st.set_page_config(layout="wide")
st.title("Monochrome map style tuner")

# --- Sidebar ---
st.sidebar.header("Roads")

road_width = st.sidebar.slider("Road base width", 0.5, 3.0, 1.5, 0.05)
road_boost = st.sidebar.slider("Road boost", 0.5, 2.0, 1.2, 0.05)

highway_fill = st.sidebar.color_picker("Highway color", "#000000")
local_fill = st.sidebar.color_picker("Local road color", "#808080")

collapse = st.sidebar.checkbox("Collapse parallel roads", False)
tol = st.sidebar.slider("Parallel tolerance (m)", 3, 15, 7)

# --- Style object ---
style = MonoStyle(
    highway_fill=highway_fill,
    arterial_fill=highway_fill,
    local_fill=local_fill,
    water_fill="#000000",
    road_width=road_width,
    road_boost=road_boost,
)

# --- Render ---
spec = spec_from_size_key("30x30", extent_m=2000, dpi=120)

out = render_city_map_monochrome(
    center_lat=47.5317,
    center_lon=21.6252,
    spec=spec,
    output_dir=Path("tmp"),
    zoom=0.6,
    relief=ReliefConfig(enabled=False),
    style=style,
    collapse_parallels=collapse,
    parallel_tol_m=tol,
    preview=True,   # PNG
)

st.image(str(out.output_png))
