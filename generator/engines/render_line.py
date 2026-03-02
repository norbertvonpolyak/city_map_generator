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
    if hw in {"residential", "living_street"}:
        return "local"
    return "minor"


# ---------------------------------------------------------------------------
# MAIN LINE ENGINE
# ---------------------------------------------------------------------------

def render_map_line(
    *,
    center_lat: float,
    center_lon: float,
    spec: ProductSpec,
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

    fig_w_in, fig_h_in = spec.fig_size_inches
    half_width_m, half_height_m = spec.frame_half_sizes_m
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

    road_width_base = style_cfg.road_style.base_width
    multipliers = style_cfg.road_style.multipliers

    if extent_m > 2000:
        road_width_base *= (2000 / extent_m)

    for cls, mult in multipliers.items():
        subset = edges_p[edges_p["road_class"] == cls]
        if len(subset) > 0:
            subset.plot(
                ax=ax,
                color=style_cfg.road,
                linewidth=road_width_base * mult,
                zorder=10,
            )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    # -----------------------------------------------------------------------
    # SAVE
    # -----------------------------------------------------------------------

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
        )

    plt.close(fig)

    return MapLayerResult(output_svg=output_path)