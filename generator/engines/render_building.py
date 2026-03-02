from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import osmnx as ox
import random

from shapely.geometry import Point, box
from osmnx._errors import InsufficientResponseError

from generator.specs import ProductSpec
from generator.styles import get_style_config, BuildingStyleConfig


# =============================================================================
# RESULT TYPE
# =============================================================================

@dataclass(frozen=True)
class MapLayerResult:
    output_svg: Path


# =============================================================================
# HELPERS
# =============================================================================

def _normalize_highway_value(v):
    return v[0] if isinstance(v, (list, tuple)) and v else v


def _classify_road(hw: str) -> str:
    hw = str(hw)

    if hw in {"motorway", "trunk"}:
        return "highway"
    if hw in {"primary", "secondary", "tertiary"}:
        return "arterial"
    if hw in {"residential", "unclassified", "living_street"}:
        return "local"
    if hw in {"service"}:
        return "minor"
    return "local"


# =============================================================================
# BUILDING ENGINE
# =============================================================================

def render_map_building(
    *,
    center_lat: float,
    center_lon: float,
    spec: ProductSpec,
    output_dir: Path,
    palette_name: str,
    seed: Optional[int] = 42,
    filename_prefix: str = "map_layer_building",
    preview_mode: bool = False,
    network_type_draw: str = "drive",
    zoom: float = 0.6,
    road_width: float = 1.1,
    min_building_area: float = 15.0,
) -> MapLayerResult:

    style_cfg = get_style_config(palette_name)

    if not isinstance(style_cfg, BuildingStyleConfig):
        raise TypeError(f"Style '{palette_name}' is not building-based.")

    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fig_w_in, fig_h_in = spec.fig_size_inches
    half_width_m, half_height_m = spec.frame_half_sizes_m

    half_width_m *= zoom
    half_height_m *= zoom

    dist_m = int(np.ceil((half_width_m**2 + half_height_m**2) ** 0.5)) + 300

    # -------------------------------------------------------------------------
    # CENTER + CLIP
    # -------------------------------------------------------------------------

    center = gpd.GeoDataFrame(
        geometry=[Point(center_lon, center_lat)],
        crs="EPSG:4326",
    )

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
        gdf_bld = ox.features_from_point(
            (center_lat, center_lon),
            tags={"building": True},
            dist=dist_m,
        )
    except InsufficientResponseError:
        gdf_bld = None

    gdf_bld_p = None

    if gdf_bld is not None and len(gdf_bld) > 0:
        gdf_bld = gdf_bld[gdf_bld.geometry.notnull()]
        gdf_bld_p = ox.projection.project_gdf(gdf_bld)
        gdf_bld_p = gdf_bld_p[
            gdf_bld_p.geom_type.isin(["Polygon", "MultiPolygon"])
        ]
        gdf_bld_p = gpd.clip(
            gdf_bld_p,
            gpd.GeoSeries([clip_rect], crs=gdf_bld_p.crs),
        )
        gdf_bld_p = gdf_bld_p[
            gdf_bld_p.geometry.area > min_building_area
        ]

    # -------------------------------------------------------------------------
    # PLOT
    # -------------------------------------------------------------------------

    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
    fig.patch.set_facecolor(style_cfg.background)
    ax.set_facecolor(style_cfg.background)

    # Buildings
    if gdf_bld_p is not None and len(gdf_bld_p) > 0:

        if not style_cfg.building_colors:
            raise ValueError(
                f"Style '{palette_name}' must define building_colors."
            )

        building_colors = np.random.choice(
            style_cfg.building_colors,
            size=len(gdf_bld_p),
        )

        gdf_bld_p.plot(
            ax=ax,
            color=building_colors,
            linewidth=0,
            zorder=5,
        )

    # Roads
    road_width_base = style_cfg.road_style.base_width
    multipliers = style_cfg.road_style.multipliers

    for cls, mult in multipliers.items():
        subset = edges_p[edges_p["road_class"] == cls]
        if len(subset) > 0:
            subset.plot(
                ax=ax,
                color=style_cfg.road,
                linewidth=road_width_base * mult,
                capstyle="round",
                joinstyle="round",
                zorder=10,
            )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    # -------------------------------------------------------------------------
    # SAVE
    # -------------------------------------------------------------------------

    if preview_mode:
        output_path = output_dir / f"{filename_prefix}.png"
        fig.savefig(
            output_path,
            format="png",
            dpi=140,
            bbox_inches="tight",
            pad_inches=0,
        )
    else:
        output_path = output_dir / f"{filename_prefix}.svg"
        fig.savefig(
            output_path,
            format="svg",
            bbox_inches="tight",
            dpi=spec.dpi,
        )

    plt.close(fig)

    return MapLayerResult(output_svg=output_path)