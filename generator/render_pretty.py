from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import osmnx as ox
import random

from shapely.geometry import Point, box, LineString
from shapely.ops import unary_union, polygonize
from osmnx._errors import InsufficientResponseError

from generator.specs import ProductSpec
from generator.styles import get_palette_config


@dataclass(frozen=True)
class RenderResult:
    output_pdf: Path


# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------

EXCLUDE_NON_VEHICULAR_HIGHWAYS: set[str] = {
    "pedestrian", "cycleway", "footway", "path", "steps", "bridleway",
}

HIGHWAY_HIGHWAY = {"motorway", "trunk"}
HIGHWAY_ARTERIAL = {"primary", "secondary", "tertiary"}
HIGHWAY_LOCAL = {"residential", "unclassified", "living_street"}
HIGHWAY_MINOR = {"service"}


def _safe_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _scaled_linewidth(
    *,
    half_height_m: float,
    base_linewidth: float,
    reference_half_height_m: float = 2000.0,
    min_lw: float = 0.20,
    max_lw: float = 4.0,
) -> float:
    if half_height_m <= 0:
        return base_linewidth

    scale = reference_half_height_m / float(half_height_m)
    lw = base_linewidth * scale
    return float(max(min_lw, min(lw, max_lw)))


def _normalize_highway_value(v):
    return v[0] if isinstance(v, (list, tuple)) and v else v


def _highway_has_any(v, banned: set[str]) -> bool:
    if isinstance(v, (list, tuple, set)):
        return any(str(x) in banned for x in v)
    return str(v) in banned


def _classify_road(hw: str) -> str:
    hw = str(hw)
    if hw in HIGHWAY_HIGHWAY:
        return "highway"
    if hw in HIGHWAY_ARTERIAL:
        return "arterial"
    if hw in HIGHWAY_LOCAL:
        return "local"
    if hw in HIGHWAY_MINOR:
        return "minor"
    return "local"


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

def render_city_map_pretty(
    *,
    center_lat: float,
    center_lon: float,
    spec: ProductSpec,
    output_dir: Path,
    palette_name: str = "warm",
    seed: Optional[int] = 42,
    filename_prefix: str = "city_pretty",
    network_type_draw: str = "all",
    zoom: float = 0.6,
    road_width: float = 1.15,
    road_boost: float = 1.1,
    lw_highway_mult: float = 3.8,
    lw_arterial_mult: float = 2.8,
    lw_local_mult: float = 1.8,
    lw_minor_mult: float = 1.2,
    min_building_area: float = 12.0,
    draw_non_vehicular: bool = False,
) -> RenderResult:

    palette_cfg = get_palette_config(palette_name)

    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fig_w_in, fig_h_in = spec.fig_size_inches
    half_width_m, half_height_m = spec.frame_half_sizes_m
    half_width_m *= zoom
    half_height_m *= zoom

    base_lw = _scaled_linewidth(
        half_height_m=half_height_m,
        base_linewidth=road_width,
    ) * road_boost

    dist_m = int(np.ceil((half_width_m**2 + half_height_m**2) ** 0.5)) + 300

    ts = _safe_timestamp()
    output_pdf = output_dir / f"{filename_prefix}_{spec.width_cm}x{spec.height_cm}cm_z{zoom:.2f}_{ts}.pdf"

    # -------------------------------------------------------------------------
    # CENTER + CLIP
    # -------------------------------------------------------------------------

    center = gpd.GeoDataFrame(geometry=[Point(center_lon, center_lat)], crs="EPSG:4326")
    center_p = ox.projection.project_gdf(center).geometry.iloc[0]

    minx = center_p.x - half_width_m
    maxx = center_p.x + half_width_m
    miny = center_p.y - half_height_m
    maxy = center_p.y + half_height_m
    clip_rect = box(minx, miny, maxx, maxy)

    # -------------------------------------------------------------------------
    # ROADS
    # -------------------------------------------------------------------------

    G = ox.graph_from_point(
        (center_lat, center_lon),
        dist=dist_m,
        network_type=network_type_draw,
        simplify=True,
    )

    edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
    edges_p = ox.projection.project_gdf(edges)
    edges_p = gpd.clip(edges_p, gpd.GeoSeries([clip_rect], crs=edges_p.crs))
    edges_p = edges_p[~edges_p.is_empty]

    if "highway" in edges_p.columns:
        edges_p["highway"] = edges_p["highway"].apply(_normalize_highway_value)
        edges_p["road_class"] = edges_p["highway"].apply(_classify_road)
    else:
        edges_p["road_class"] = "local"

    # -------------------------------------------------------------------------
    # BUILDINGS
    # -------------------------------------------------------------------------

    try:
        gdf_bld = ox.features_from_point((center_lat, center_lon), tags={"building": True}, dist=dist_m)
    except InsufficientResponseError:
        gdf_bld = None

    gdf_bld_p = None
    if gdf_bld is not None and len(gdf_bld) > 0:
        gdf_bld = gdf_bld[gdf_bld.geometry.notnull()]
        gdf_bld_p = ox.projection.project_gdf(gdf_bld)
        gdf_bld_p = gdf_bld_p[gdf_bld_p.geom_type.isin(["Polygon", "MultiPolygon"])]
        gdf_bld_p = gpd.clip(gdf_bld_p, gpd.GeoSeries([clip_rect], crs=gdf_bld_p.crs))
        gdf_bld_p = gdf_bld_p[gdf_bld_p.geometry.area > min_building_area]

    # -------------------------------------------------------------------------
    # PLOT
    # -------------------------------------------------------------------------

    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
    fig.patch.set_facecolor(palette_cfg.background)
    ax.set_facecolor(palette_cfg.background)

    # buildings
    if gdf_bld_p is not None and len(gdf_bld_p) > 0:
        building_colors = np.random.choice(palette_cfg.blocks, size=len(gdf_bld_p))
        gdf_bld_p.plot(ax=ax, color=building_colors, linewidth=0, zorder=5)

    # water
    try:
        water = ox.features_from_point(
            (center_lat, center_lon),
            tags={"natural": ["water"], "waterway": True},
            dist=dist_m,
        )

        if len(water) > 0:
            water = water[water.geometry.notnull()]
            water_p = ox.projection.project_gdf(water)
            water_p = gpd.clip(water_p, gpd.GeoSeries([clip_rect], crs=water_p.crs))

            water_p.plot(
                ax=ax,
                color=palette_cfg.water_fill,
                edgecolor=palette_cfg.water_edge,
                linewidth=0.8,
                zorder=6,
            )
    except Exception:
        pass

    # roads
    class_order = [
        ("minor", lw_minor_mult, 10),
        ("local", lw_local_mult, 20),
        ("arterial", lw_arterial_mult, 30),
        ("highway", lw_highway_mult, 40),
    ]

    for cls, mult, z in class_order:
        subset = edges_p[edges_p["road_class"] == cls]
        if len(subset) > 0:
            subset.plot(
                ax=ax,
                color=palette_cfg.road,
                linewidth=base_lw * mult,
                capstyle="round",
                joinstyle="round",
                zorder=z,
            )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    fig.savefig(output_pdf, format="pdf", dpi=spec.dpi, bbox_inches="tight")
    plt.close(fig)

    return RenderResult(output_pdf=output_pdf)
