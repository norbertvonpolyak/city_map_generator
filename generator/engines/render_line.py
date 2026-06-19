from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

from dataclasses import dataclass
from typing import Optional
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
import random

from shapely.geometry import Point, box

from generator.specs import ProductSpec
from generator.styles import get_style_config, LineStyleConfig


# ---------------------------------------------------------------------------
# RESULT
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MapLayerResult:
    output_svg: Path


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _classify_road(hw: str) -> str:
    hw = str(hw)

    if hw in {"motorway", "trunk"}:
        return "highway"
    if hw in {"primary", "secondary", "tertiary"}:
        return "arterial"
    if hw in {"residential", "unclassified", "living_street"}:
        return "local"
    return "minor"


def _prepare_polygon_layer(raw_layer: gpd.GeoDataFrame | None, target_crs, clip_rect) -> gpd.GeoDataFrame:
    if raw_layer is None or len(raw_layer) == 0:
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    layer = raw_layer[(~raw_layer.geometry.isna()) & (~raw_layer.geometry.is_empty)]
    if len(layer) == 0:
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    layer_p = layer.to_crs(target_crs)
    layer_p = layer_p[layer_p.geom_type.isin(["Polygon", "MultiPolygon"])]
    if len(layer_p) == 0:
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    return gpd.clip(layer_p, gpd.GeoSeries([clip_rect], crs=target_crs))


# ---------------------------------------------------------------------------
# MAIN LINE ENGINE
# ---------------------------------------------------------------------------

def render_map_line(
    *,
    center_lat: float,
    center_lon: float,
    spec: ProductSpec,
    map_width_cm: float,
    map_height_cm: float,
    viewport_half_width_m: float,
    viewport_half_height_m: float,
    output_dir: Path,
    palette_name: str,
    seed: Optional[int] = 42,
    filename_prefix: str = "map_layer_line",
    preview_mode: bool = False,
) -> MapLayerResult:

    style_cfg = get_style_config(palette_name)

    if not isinstance(style_cfg, LineStyleConfig):
        raise TypeError(f"Style '{palette_name}' is not line-based.")

    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fig_w_in = map_width_cm / 2.54
    fig_h_in = map_height_cm / 2.54
    half_width_m, half_height_m = viewport_half_width_m, viewport_half_height_m
    extent_m = spec.extent_m

    dist_m = int(np.ceil((half_width_m**2 + half_height_m**2) ** 0.5)) + 300

    # -----------------------------------------------------------------------
    # CENTER + CLIP
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # ADAPTIVE DETAIL FILTER
    # -----------------------------------------------------------------------

    if extent_m <= 1500:
        custom_filter = (
            '["highway"~"motorway|trunk|primary|secondary|tertiary|'
            'residential|living_street|service|pedestrian|cycleway|footway"]'
        )
    elif extent_m <= 3000:
        custom_filter = (
            '["highway"~"motorway|trunk|primary|secondary|tertiary|'
            'residential|living_street|service|cycleway"]'
        )
    else:
        custom_filter = (
            '["highway"~"motorway|trunk|primary|secondary|tertiary"]'
        )

    # -----------------------------------------------------------------------
    # GRAPH DOWNLOAD
    # -----------------------------------------------------------------------

    G = ox.graph_from_point(
        (center_lat, center_lon),
        dist=dist_m,
        custom_filter=custom_filter,
        simplify=True,
    )

    edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
    edges_p = ox.projection.project_gdf(edges)
    edges_p = gpd.clip(edges_p, gpd.GeoSeries([clip_rect], crs=edges_p.crs))
    edges_p = edges_p[~edges_p.is_empty]

    clip_gdf = gpd.GeoDataFrame(geometry=[clip_rect], crs=edges_p.crs)
    clip_wgs = clip_gdf.to_crs("EPSG:4326").geometry.iloc[0]

    try:
        water_raw = ox.features_from_polygon(
            clip_wgs,
            tags={
                "natural": ["water", "bay", "strait"],
                "water": True,
                "waterway": ["riverbank", "canal"],
                "landuse": ["basin", "reservoir"],
            },
        )
    except Exception:
        water_raw = ox.features_from_polygon(
            clip_wgs,
            tags={
                "natural": "water",
                "waterway": "riverbank",
            },
        )

    try:
        green_raw = ox.features_from_polygon(
            clip_wgs,
            tags={
                "leisure": ["park", "garden", "nature_reserve", "recreation_ground", "village_green"],
                "landuse": ["forest", "grass", "meadow", "recreation_ground", "village_green"],
                "natural": ["wood", "grassland", "scrub", "heath"],
            },
        )
    except Exception:
        green_raw = ox.features_from_polygon(
            clip_wgs,
            tags={"leisure": "park"},
        )

    water_p = _prepare_polygon_layer(water_raw, edges_p.crs, clip_rect)
    green_p = _prepare_polygon_layer(green_raw, edges_p.crs, clip_rect)

    if "highway" in edges_p.columns:
        edges_p["road_class"] = edges_p["highway"].apply(_classify_road)
    else:
        edges_p["road_class"] = "local"

    # -----------------------------------------------------------------------
    # PLOT
    # -----------------------------------------------------------------------

    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
    fig.patch.set_facecolor(style_cfg.background)
    ax.set_facecolor(style_cfg.background)

    if len(water_p) > 0:
        water_p.plot(
            ax=ax,
            color=style_cfg.water,
            edgecolor="none",
            zorder=1,
        )

    if len(green_p) > 0:
        green_p.plot(
            ax=ax,
            color=style_cfg.green,
            edgecolor="none",
            zorder=2,
        )

    road_width_base = style_cfg.road_style.base_width
    multipliers = style_cfg.road_style.multipliers

    for cls, mult in multipliers.items():
        subset = edges_p[edges_p["road_class"] == cls]
        if len(subset) > 0:
            subset.plot(
                ax=ax,
                color=style_cfg.road,
                linewidth=road_width_base * mult,
                zorder=12,
            )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()
    ax.set_position([0, 0, 1, 1])

    # -----------------------------------------------------------------------
    # SAVE
    # -----------------------------------------------------------------------

    if preview_mode:
        output_path = output_dir / f"{filename_prefix}.png"
        fig.savefig(
            output_path,
            format="png",
            dpi=140,
            pad_inches=0,
        )
    else:
        output_path = output_dir / f"{filename_prefix}.svg"
        fig.savefig(
            output_path,
            format="svg",
            pad_inches=0,
        )

    plt.close(fig)

    return MapLayerResult(output_svg=output_path)