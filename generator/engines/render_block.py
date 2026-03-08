from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import random
import math
import hashlib

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox

from shapely.geometry import Point, box
from shapely.ops import polygonize, unary_union

from generator.specs import ProductSpec
from generator.styles import get_style_config
from generator.core.cache import load_or_build_geometry


@dataclass(frozen=True)
class MapLayerResult:
    output_svg: Optional[Path]


def _classify_road(hw: str) -> str:

    hw = str(hw)

    if hw in {"motorway", "trunk"}:
        return "highway"

    if hw in {"primary", "secondary", "tertiary"}:
        return "arterial"

    if hw in {"residential", "unclassified", "living_street"}:
        return "local"

    return "minor"

def _deterministic_color(geom, palette):
    key = geom.wkb
    h = hashlib.md5(key).hexdigest()
    idx = int(h, 16) % len(palette)
    return palette[idx]

def render_map_block(
    *,
    center_lat: float,
    center_lon: float,
    spec: ProductSpec,
    output_dir: Optional[Path] = None,
    palette_name: str,
    seed: int = 42,
    filename_prefix: str = "map_layer",
    preview_mode: bool = False,
) -> MapLayerResult:

    random.seed(seed)
    np.random.seed(seed)

    style_cfg = get_style_config(palette_name)

    inner_width_cm = spec.width_cm - 2
    inner_height_cm = spec.height_cm - 5

    fig_w_in = inner_width_cm / 2.54
    fig_h_in = inner_height_cm / 2.54

    inner_ratio = inner_width_cm / inner_height_cm

    half_height_m = spec.extent_m
    half_width_m = half_height_m * inner_ratio

    dist_m = int(math.ceil(math.sqrt(half_width_m**2 + half_height_m**2))) + 300

    def _build_geometry():

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

        # ROADS

        G = ox.graph_from_point(
            (center_lat, center_lon),
            dist=dist_m,
            network_type="all",
            simplify=True,
        )

        edges = ox.graph_to_gdfs(G, nodes=False, edges=True)

        edges_p = ox.projection.project_gdf(edges)

        edges_p = gpd.clip(
            edges_p,
            gpd.GeoSeries([clip_rect], crs=edges_p.crs)
        )

        edges_p["road_class"] = edges_p["highway"].apply(_classify_road)

        # WATER (natural only)

        clip_gdf = gpd.GeoDataFrame(
            geometry=[clip_rect],
            crs=edges_p.crs
        )

        clip_wgs = clip_gdf.to_crs("EPSG:4326").geometry.iloc[0]

        water = ox.features_from_polygon(
            clip_wgs,
            tags={
                "natural": "water",
                "waterway": "riverbank"
            }
        )

        if water is None or len(water) == 0:
            water_p = gpd.GeoDataFrame(geometry=[], crs=edges_p.crs)

        else:

            water = water[water.geometry.notnull()]
            water_p = water.to_crs(edges_p.crs)

            water_p = water_p[
                water_p.geom_type.isin(["Polygon", "MultiPolygon"])
            ]

            water_p = gpd.clip(
                water_p,
                gpd.GeoSeries([clip_rect], crs=edges_p.crs)
            )

        # COASTLINE

        try:

            coast = ox.features_from_polygon(
                clip_wgs,
                tags={"natural": "coastline"}
            )

        except:

            coast = None

        sea_poly = None

        if coast is not None and len(coast) > 0:

            coast = coast[coast.geometry.notnull()]
            coast_p = coast.to_crs(edges_p.crs)

            coast_lines = coast_p[
                coast_p.geom_type.isin(["LineString", "MultiLineString"])
            ]

            merged = unary_union(
                list(coast_lines.geometry.values) +
                [clip_rect.boundary]
            )

            polys = list(polygonize(merged))

            for p in polys:

                if p.contains(center_p):

                    land_poly = p
                    sea_poly = clip_rect.difference(land_poly)
                    break

        if sea_poly is not None:

            water_p = gpd.GeoDataFrame(
                geometry=list(water_p.geometry) + [sea_poly],
                crs=edges_p.crs
            )

        # LARGE WATER ONLY (remove pools)

        large_water = water_p[water_p.area > 2000]

        # POLYGONIZE INPUT

        boundary = clip_rect.boundary

        lines = list(edges_p.geometry.values) + [boundary]

        if len(large_water) > 0:

            water_union = unary_union(large_water.geometry)

            lines += [water_union.boundary]

        merged = unary_union(lines)

        polygons = list(polygonize(merged))

        cells = gpd.GeoDataFrame(
            geometry=polygons,
            crs=edges_p.crs
        )

        cells = gpd.clip(
            cells,
            gpd.GeoSeries([clip_rect], crs=cells.crs)
        )

        # classify water cells

        if len(large_water) > 0:

            water_union = unary_union(large_water.geometry)

            water_union = unary_union (large_water.geometry)

            def is_water_cell (poly):

                inter = poly.intersection (water_union)

                if inter.is_empty:
                    return False

                ratio = inter.area / poly.area

                return ratio > 0.5

            cells ["is_water"] = cells.geometry.apply (is_water_cell)

        else:

            cells["is_water"] = False

        return {
            "cells": cells,
            "roads": edges_p,
            "bounds": (minx, maxx, miny, maxy),
        }

    geometry_data = load_or_build_geometry(
        cache_prefix="block",
        center_lat=center_lat,
        center_lon=center_lon,
        extent_m=spec.extent_m,
        builder_func=_build_geometry,
    )

    cells = geometry_data["cells"]
    edges_p = geometry_data["roads"]

    minx, maxx, miny, maxy = geometry_data["bounds"]

    fig, ax = plt.subplots(
        figsize=(fig_w_in, fig_h_in),
        dpi=300
    )

    water_cells = cells[cells["is_water"]]
    land_cells = cells[~cells["is_water"]]

    if len(water_cells) > 0:

        water_cells.plot(
            ax=ax,
            color=style_cfg.water,
            edgecolor="none",
            zorder=1
        )

    land_cells ["color"] = [
        _deterministic_color (geom, style_cfg.block_colors)
        for geom in land_cells.geometry
    ]

    land_cells.plot(
        ax=ax,
        color=land_cells["color"],
        edgecolor="none",
        zorder=2
    )

    base_width = style_cfg.road_style.base_width
    multipliers = style_cfg.road_style.multipliers

    for road_class, m in multipliers.items():

        subset = edges_p[edges_p["road_class"] == road_class]

        if len(subset) == 0:
            continue

        subset.plot(
            ax=ax,
            linewidth=base_width * m,
            color=style_cfg.road,
            zorder=3
        )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    plt.tight_layout()

    output_svg = None

    if output_dir:

        output_dir.mkdir(parents=True, exist_ok=True)

        output_svg = output_dir / f"{filename_prefix}.svg"

        fig.savefig(
            output_svg,
            format="svg",
            bbox_inches="tight",
            pad_inches=0,
        )

    plt.close(fig)

    return MapLayerResult(output_svg=output_svg)