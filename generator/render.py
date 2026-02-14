from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import random

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
from shapely.geometry import Point, box
from shapely.ops import polygonize, unary_union
from matplotlib.patches import Rectangle

from generator.specs import ProductSpec
from generator.styles import get_palette_config


# =============================================================================
# RESULT
# =============================================================================

@dataclass(frozen=True)
class RenderResult:
    output_pdf: Optional[Path] = None


# =============================================================================
# HELPERS
# =============================================================================

def _safe_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


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
# MAIN
# =============================================================================

def render_city_map(
    *,
    center_lat: float,
    center_lon: float,
    spec: ProductSpec,
    output_dir: Path,
    palette_name: str,
    seed: int = 42,
    filename_prefix: str = "city_blocks",
) -> RenderResult:

    random.seed(seed)
    np.random.seed(seed)

    palette_cfg = get_palette_config(palette_name)

    fig_w_in, fig_h_in = spec.fig_size_inches
    half_width_m, half_height_m = spec.frame_half_sizes_m

    dist_m = int(np.ceil((half_width_m ** 2 + half_height_m ** 2) ** 0.5)) + 200

    ts = _safe_timestamp()
    output_dir.mkdir(parents=True, exist_ok=True)

    out_pdf = output_dir / f"{filename_prefix}_{spec.width_cm}x{spec.height_cm}cm_{ts}.pdf"

    # -------------------------------------------------------------------------
    # CENTER + BBOX
    # -------------------------------------------------------------------------

    center = gpd.GeoDataFrame(
        geometry=[Point(center_lon, center_lat)], crs="EPSG:4326"
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

    edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
    edges_p = ox.projection.project_gdf(edges)
    edges_p = gpd.clip(edges_p, gpd.GeoSeries([clip_rect], crs=edges_p.crs))

    edges_p["road_class"] = edges_p["highway"].apply(_classify_road)

    # -------------------------------------------------------------------------
    # POLYGONIZE WITH BOUNDARY (CRITICAL FIX)
    # -------------------------------------------------------------------------

    boundary = clip_rect.boundary
    merged = unary_union(list(edges_p.geometry) + [boundary])
    polygons = list(polygonize(merged))

    blocks_gdf = gpd.GeoDataFrame(geometry=polygons, crs=edges_p.crs)
    blocks_gdf = gpd.clip(blocks_gdf, gpd.GeoSeries([clip_rect], crs=blocks_gdf.crs))

    if len(blocks_gdf) > 0:
        blocks_gdf["color"] = np.random.choice(
            palette_cfg.blocks, size=len(blocks_gdf)
        )

    # -------------------------------------------------------------------------
    # WATER
    # -------------------------------------------------------------------------

    water_p = None

    try:
        water = ox.features_from_point(
            (center_lat, center_lon),
            tags={"natural": ["water"], "waterway": True},
            dist=dist_m,
        )

        if len(water) > 0:
            water = water[water.geometry.notnull()]
            water_p = ox.projection.project_gdf(water)
            water_p = gpd.clip(
                water_p,
                gpd.GeoSeries([clip_rect], crs=water_p.crs),
            )

    except Exception:
        pass

    # -------------------------------------------------------------------------
    # FIGURE
    # -------------------------------------------------------------------------

    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
    fig.patch.set_facecolor(palette_cfg.background)
    ax.set_facecolor(palette_cfg.background)

    # ---- CM based margins (STABLE!) ----

    margin_cm = 1.0
    margin_in = margin_cm / 2.54

    left = margin_in / fig_w_in
    right = 1 - (margin_in / fig_w_in)
    top = 1 - (margin_in / fig_h_in)
    bottom = margin_in / fig_h_in

    fig.subplots_adjust(left=left, right=right, top=top, bottom=bottom)

    # -------------------------------------------------------------------------
    # DRAW ORDER
    # -------------------------------------------------------------------------

    # Blocks
    if len(blocks_gdf) > 0:
        blocks_gdf.plot(
            ax=ax,
            color=blocks_gdf["color"],
            linewidth=0,
            zorder=5,
        )

    # Water
    if water_p is not None and len(water_p) > 0:
        water_p.plot(
            ax=ax,
            color=palette_cfg.water_fill,
            edgecolor="none",
            zorder=10,
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
                alpha=1.0,
                zorder=20,
            )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    # -------------------------------------------------------------------------
    # VERY THIN BORDER
    # -------------------------------------------------------------------------

    border = Rectangle(
        (0, 0),
        1,
        1,
        transform=fig.transFigure,
        fill=False,
        linewidth=0.8,
        edgecolor="#222222",
    )
    fig.patches.append(border)

    fig.savefig(out_pdf, format="pdf", dpi=spec.dpi)
    plt.close(fig)

    return RenderResult(output_pdf=out_pdf)
