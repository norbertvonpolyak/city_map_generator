from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # Backend safe for FastAPI

from typing import Optional
from pathlib import Path
import random
import math

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox

from shapely.geometry import Point, box
from shapely.ops import polygonize, unary_union

from generator.specs import ProductSpec
from generator.styles import get_palette_config


# =============================================================================
# HELPERS
# =============================================================================

def _classify_road(hw: str) -> str:
    hw = str(hw)

    if hw in {"motorway", "trunk"}:
        return "highway"
    if hw in {"primary", "secondary", "tertiary"}:
        return "arterial"
    if hw in {"residential", "unclassified", "living_street"}:
        return "local"
    return "minor"


# =============================================================================
# MAIN RENDER
# =============================================================================

def render_city_map(
    *,
    center_lat: float,
    center_lon: float,
    spec: ProductSpec,
    output_dir: Optional[Path] = None,   # optional!
    palette_name: str,
    seed: int = 42,
    filename_prefix: str = "map_layer",
) -> plt.Figure:
    """
    Always returns a matplotlib Figure.
    If output_dir is provided, also saves SVG.
    """

    random.seed(seed)
    np.random.seed(seed)

    palette_cfg = get_palette_config(palette_name)

    # ------------------------------------------------------------
    # INNER MAP AREA (1cm sides + 1cm top + 4cm bottom reserved)
    # ------------------------------------------------------------

    inner_width_cm = spec.width_cm - 2
    inner_height_cm = spec.height_cm - 5

    fig_w_in = inner_width_cm / 2.54
    fig_h_in = inner_height_cm / 2.54

    inner_ratio = inner_width_cm / inner_height_cm

    half_height_m = spec.extent_m
    half_width_m = half_height_m * inner_ratio

    dist_m = int(
        math.ceil(math.sqrt(half_width_m**2 + half_height_m**2))
    ) + 300

    # ------------------------------------------------------------
    # CENTER + CLIP BBOX
    # ------------------------------------------------------------

    center = gpd.GeoDataFrame(
        geometry=[Point(center_lon, center_lat)],
        crs="EPSG:4326"
    )

    center_p = ox.projection.project_gdf(center).geometry.iloc[0]

    minx = center_p.x - half_width_m
    maxx = center_p.x + half_width_m
    miny = center_p.y - half_height_m
    maxy = center_p.y + half_height_m

    clip_rect = box(minx, miny, maxx, maxy)

    # ------------------------------------------------------------
    # ROAD GRAPH
    # ------------------------------------------------------------

    G = ox.graph_from_point(
        (center_lat, center_lon),
        dist=dist_m,
        network_type="all",
        simplify=True,
    )

    edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
    edges_p = ox.projection.project_gdf(edges)
    edges_p = gpd.clip(edges_p, gpd.GeoSeries([clip_rect], crs=edges_p.crs))

    edges_p["road_class"] = edges_p["highway"].apply(_classify_road)

    # ------------------------------------------------------------
    # WATER
    # ------------------------------------------------------------

    water = ox.features_from_point(
        (center_lat, center_lon),
        tags={"natural": "water"},
        dist=dist_m,
    )

    if len(water) > 0:
        water_p = ox.projection.project_gdf(water)
        water_p = gpd.clip(water_p, gpd.GeoSeries([clip_rect], crs=water_p.crs))
    else:
        water_p = None

    # ------------------------------------------------------------
    # BLOCKS (POLYGONIZE)
    # ------------------------------------------------------------

    boundary = clip_rect.boundary
    merged = unary_union(list(edges_p.geometry) + [boundary])
    polygons = list(polygonize(merged))

    blocks_gdf = gpd.GeoDataFrame(geometry=polygons, crs=edges_p.crs)
    blocks_gdf = gpd.clip(
        blocks_gdf,
        gpd.GeoSeries([clip_rect], crs=blocks_gdf.crs)
    )

    if water_p is not None and len(water_p) > 0:
        water_union = water_p.unary_union
        blocks_gdf["geometry"] = blocks_gdf.geometry.difference(water_union)

    if palette_cfg.blocks and len(blocks_gdf) > 0:
        blocks_gdf["color"] = np.random.choice(
            palette_cfg.blocks,
            size=len(blocks_gdf)
        )

    # ------------------------------------------------------------
    # PLOT
    # ------------------------------------------------------------

    fig = plt.figure(figsize=(fig_w_in, fig_h_in))
    ax = fig.add_axes([0, 0, 1, 1])

    fig.patch.set_facecolor(palette_cfg.background)
    ax.set_facecolor(palette_cfg.background)

    # Water
    if water_p is not None and len(water_p) > 0:
        water_p.plot(
            ax=ax,
            color=palette_cfg.water,
            linewidth=0,
            zorder=1,
        )

    # Blocks
    if palette_cfg.blocks and len(blocks_gdf) > 0:
        blocks_gdf.plot(
            ax=ax,
            color=blocks_gdf["color"],
            linewidth=0,
            zorder=5,
        )

    # Roads
    road_width_base = palette_cfg.road_style.base_width
    multipliers = palette_cfg.road_style.multipliers

    for cls, mult in multipliers.items():
        subset = edges_p[edges_p["road_class"] == cls]
        if len(subset) > 0:
            subset.plot(
                ax=ax,
                color=palette_cfg.road,
                linewidth=road_width_base * mult,
                zorder=20,
            )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    # Optional SVG save (CLI use-case)
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        svg_path = output_dir / f"{filename_prefix}.svg"
        fig.savefig(svg_path, format="svg")

    return fig