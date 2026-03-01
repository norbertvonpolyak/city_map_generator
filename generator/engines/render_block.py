from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

from dataclasses import dataclass
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
from generator.styles import get_style_config, BlockStyleConfig


# =============================================================================
# RESULT TYPE
# =============================================================================

@dataclass(frozen=True)
class MapLayerResult:
    output_svg: Optional[Path]


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
# BLOCK-BASED ENGINE
# =============================================================================

def render_map_block(
    *,
    center_lat: float,
    center_lon: float,
    spec: ProductSpec,
    output_dir: Optional[Path] = None,
    palette_name: str,
    seed: int = 42,
    filename_prefix: str = "map_layer",
) -> MapLayerResult:

    random.seed(seed)
    np.random.seed(seed)

    style_cfg = get_style_config(palette_name)

    if not isinstance(style_cfg, BlockStyleConfig):
        raise TypeError(
            f"Style '{palette_name}' is not block-based."
        )

    # -------------------------------------------------------------------------
    # INNER MAP AREA (layout-reserved margins)
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # CENTER + CLIP
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # ROADS
    # -------------------------------------------------------------------------

    G = ox.graph_from_point(
        (center_lat, center_lon),
        dist=dist_m,
        network_type="all",
        simplify=True,
    )
    ox.settings.timeout = 30

    edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
    edges_p = ox.projection.project_gdf(edges)
    edges_p = gpd.clip(edges_p, gpd.GeoSeries([clip_rect], crs=edges_p.crs))
    edges_p = edges_p[~edges_p.is_empty]

    edges_p["road_class"] = edges_p["highway"].apply(_classify_road)

    # -------------------------------------------------------------------------
    # WATER
    # -------------------------------------------------------------------------

    water = ox.features_from_point(
        (center_lat, center_lon),
        tags={"natural": "water"},
        dist=dist_m,
    )

    if len(water) > 0:
        water_p = ox.projection.project_gdf(water)
        water_p = gpd.clip(
            water_p,
            gpd.GeoSeries([clip_rect], crs=water_p.crs)
        )
    else:
        water_p = None

    # -------------------------------------------------------------------------
    # BLOCKS (POLYGONIZE)
    # -------------------------------------------------------------------------

    boundary = clip_rect.boundary
    merged = unary_union(list(edges_p.geometry) + [boundary])
    polygons = list(polygonize(merged))

    blocks_gdf = gpd.GeoDataFrame(
        geometry=polygons,
        crs=edges_p.crs
    )

    blocks_gdf = gpd.clip(
        blocks_gdf,
        gpd.GeoSeries([clip_rect], crs=blocks_gdf.crs)
    )

    if water_p is not None and len(water_p) > 0:
        water_union = water_p.unary_union
        blocks_gdf["geometry"] = blocks_gdf.geometry.difference(water_union)

    if len(blocks_gdf) > 0:
        blocks_gdf["color"] = np.random.choice(
            style_cfg.block_colors,
            size=len(blocks_gdf)
        )

    # -------------------------------------------------------------------------
    # PLOT
    # -------------------------------------------------------------------------

    fig = plt.figure(figsize=(fig_w_in, fig_h_in))
    ax = fig.add_axes([0, 0, 1, 1])

    fig.patch.set_facecolor(style_cfg.background)
    ax.set_facecolor(style_cfg.background)

    # Water
    if water_p is not None and len(water_p) > 0:
        water_p.plot(
            ax=ax,
            color=style_cfg.water,
            linewidth=0,
            zorder=1,
        )

    # Blocks
    if len(blocks_gdf) > 0:
        blocks_gdf.plot(
            ax=ax,
            color=blocks_gdf["color"],
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
                zorder=20,
            )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    # -------------------------------------------------------------------------
    # SAVE SVG
    # -------------------------------------------------------------------------

    output_svg_path = None

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_svg_path = output_dir / f"{filename_prefix}.svg"
        fig.savefig(
            output_svg_path,
            format="svg",
            bbox_inches=None
        )

    plt.close(fig)

    return MapLayerResult(output_svg=output_svg_path)