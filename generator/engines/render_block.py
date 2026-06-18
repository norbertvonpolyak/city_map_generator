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
    output_png: Optional[Path] = None


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
    map_width_cm: float,
    map_height_cm: float,
    viewport_half_width_m: float,
    viewport_half_height_m: float,
    output_dir: Optional[Path] = None,
    palette_name: str,
    seed: int = 42,
    filename_prefix: str = "map_layer",
    preview_mode: bool = False,
    use_cache: bool = True,
    output_png_path: Optional[Path] = None,
) -> MapLayerResult:

    random.seed(seed)
    np.random.seed(seed)

    style_cfg = get_style_config(palette_name)

    inner_width_cm = map_width_cm
    inner_height_cm = map_height_cm

    fig_w_in = inner_width_cm / 2.54
    fig_h_in = inner_height_cm / 2.54

    half_height_m = viewport_half_height_m
    half_width_m = viewport_half_width_m

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

        # WATER (broader OSM tags for sea/harbor/basin coverage)

        clip_gdf = gpd.GeoDataFrame(
            geometry=[clip_rect],
            crs=edges_p.crs
        )

        clip_wgs = clip_gdf.to_crs("EPSG:4326").geometry.iloc[0]

        try:
            water = ox.features_from_polygon(
                clip_wgs,
                tags={
                    "natural": ["water", "bay", "strait"],
                    "water": True,
                    "waterway": ["riverbank", "canal"],
                    "landuse": ["basin", "reservoir"],
                }
            )
        except Exception:
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

            water = water[(~water.geometry.isna()) & (~water.geometry.is_empty)]
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

            coast = coast[(~coast.geometry.isna()) & (~coast.geometry.is_empty)]
            coast_p = coast.to_crs(edges_p.crs)

            coast_lines = coast_p[
                coast_p.geom_type.isin(["LineString", "MultiLineString"])
            ]

            merged = unary_union(
                list(coast_lines.geometry.values) +
                [clip_rect.boundary]
            )

            polys = [
                p for p in polygonize(merged)
                if (not p.is_empty) and p.area > 0
            ]

            if polys:

                # Classify EACH coastline-bounded region as land or sea.
                #
                # The previous logic kept ONLY the region containing the map
                # center as land and flooded every other region as sea. That
                # breaks any city whose frame contains more than one landmass:
                # the opposite bank of a strait/river (e.g. Istanbul's Asian
                # side) or the separate islands of an archipelago
                # (e.g. Stockholm, Helsinki) were drawn as water with streets
                # sitting on top.
                #
                # A region is LAND when its road-length density (metres of road
                # per m^2 of region) is high. Measured values:
                #   * dense built-up land  ~3e-2 .. 9e-2 m/m^2
                #   * map-center landmass  ~6e-2 m/m^2
                #   * open sea (gulf) with piers / breakwaters / shore paths
                #                          ~2.5e-3 m/m^2 or lower
                # Islands sit in their OWN coastline regions (polygonize gives
                # the sea face a hole where each island is), so flagging a sea
                # region never affects island land. A threshold of 1e-2 sits in
                # the wide gap between sea (<=~2.5e-3) and land (>=~3e-2) and is
                # robust without any expensive buffering (buffering the whole
                # road network is far too slow and froze the render).

                roads_union = (
                    unary_union(list(edges_p.geometry.values))
                    if len(edges_p) > 0 else None
                )

                sea_regions = []

                for p in polys:

                    if p.contains(center_p):
                        # Region with the map center is always land.
                        continue

                    density = 0.0
                    if roads_union is not None and p.area > 0:
                        road_inside = p.intersection(roads_union)
                        if not road_inside.is_empty:
                            density = road_inside.length / p.area

                    # Built-up land: dense road network.
                    # Open sea: only sparse pier/shore coverage -> below thresh.
                    if density < 1e-2:
                        sea_regions.append(p)

                if sea_regions:
                    sea_poly = unary_union(sea_regions)

        if sea_poly is not None:

            water_p = gpd.GeoDataFrame(
                geometry=list(water_p.geometry) + [sea_poly],
                crs=edges_p.crs
            )

        island_union = None

        # ISLAND OVERRIDE
        # Remove explicit island polygons from water surfaces so they are
        # always rendered as land parcels.
        try:
            islands = ox.features_from_polygon(
                clip_wgs,
                tags={
                    "place": ["island", "islet"],
                    "natural": "island",
                },
            )
        except Exception:
            islands = None

        if islands is not None and len(islands) > 0 and len(water_p) > 0:
            islands = islands[(~islands.geometry.isna()) & (~islands.geometry.is_empty)]
            islands_p = islands.to_crs(edges_p.crs)
            islands_p = islands_p[
                islands_p.geom_type.isin(["Polygon", "MultiPolygon"])
            ]

            if len(islands_p) > 0:
                islands_p = gpd.clip(
                    islands_p,
                    gpd.GeoSeries([clip_rect], crs=edges_p.crs)
                )

            if len(islands_p) > 0:
                island_union = unary_union(islands_p.geometry)
                water_p = water_p.copy()
                water_p["geometry"] = water_p.geometry.apply(
                    lambda geom: geom.difference(island_union)
                )
                water_p = water_p[
                    (~water_p.geometry.isna()) & (~water_p.geometry.is_empty)
                ]
                water_p = water_p[
                    water_p.geom_type.isin(["Polygon", "MultiPolygon"])
                ]

        # Remove tiny artifacts but keep medium harbor fragments.

        large_water = water_p[water_p.area > 300]

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
            # Small expansion helps fragmented shore segments, but only when
            # there is already true (unbuffered) water overlap.
            water_mask = water_union.buffer(5)

            def is_water_cell(poly):

                raw_inter = poly.intersection(water_union)
                if raw_inter.is_empty:
                    # Never classify as water from buffered overlap only.
                    return False

                poly_area = poly.area
                if poly_area <= 0:
                    return False

                raw_ratio = raw_inter.area / poly_area
                if raw_ratio > 0.5:
                    return True

                buffered_inter = poly.intersection(water_mask)
                if buffered_inter.is_empty:
                    return False

                buffered_ratio = buffered_inter.area / poly_area
                return raw_ratio > 0.03 and buffered_ratio > 0.2

            cells["is_water"] = cells.geometry.apply(is_water_cell)

        else:

            cells["is_water"] = False

        if island_union is not None:

            def is_island_cell(poly):
                inter = poly.intersection(island_union)
                if inter.is_empty or poly.area <= 0:
                    return False
                return (inter.area / poly.area) > 0.15

            island_cells = cells.geometry.apply(is_island_cell)
            cells.loc[island_cells, "is_water"] = False

        return {
            "cells": cells,
            "roads": edges_p,
            "bounds": (minx, maxx, miny, maxy),
        }

    if use_cache:
        geometry_data = load_or_build_geometry(
            # Bump cache key so previous misclassified geometry is not reused.
            cache_prefix="block_v10_density",
            center_lat=center_lat,
            center_lon=center_lon,
            extent_m=spec.extent_m,
            cache_variant=f"{half_width_m:.2f}x{half_height_m:.2f}",
            builder_func=_build_geometry,
        )
    else:
        print("[CACHE] Disabled: rebuilding geometry")
        geometry_data = _build_geometry()

    cells = geometry_data["cells"]
    edges_p = geometry_data["roads"]

    minx, maxx, miny, maxy = geometry_data["bounds"]

    fig, ax = plt.subplots(
        figsize=(fig_w_in, fig_h_in),
        dpi=300
    )

    water_cells = cells[cells["is_water"]]
    land_cells = cells[~cells["is_water"]].copy()

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
    ax.set_position([0, 0, 1, 1])

    output_svg = None
    output_png = None

    if output_dir:

        output_dir.mkdir(parents=True, exist_ok=True)

        output_svg = output_dir / f"{filename_prefix}.svg"

        fig.savefig(
            output_svg,
            format="svg",
            pad_inches=0,
        )

    if output_png_path is not None:
        output_png_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(
            output_png_path,
            format="png",
            dpi=spec.dpi,
            pad_inches=0,
        )
        output_png = output_png_path

    plt.close(fig)

    return MapLayerResult(output_svg=output_svg, output_png=output_png)