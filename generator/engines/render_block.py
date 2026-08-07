from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import random
import math
import hashlib
import os

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox

from shapely.geometry import Point, box
from shapely.ops import polygonize, unary_union

from generator.specs import ProductSpec
from generator.styles import get_style_config
from generator.core.osm_bundle_cache import load_or_build_shared_osm_bundle


@dataclass(frozen=True)
class MapLayerResult:
    output_svg: Optional[Path]
    output_png: Optional[Path] = None


def _road_width_scale_for_extent(extent_m: float) -> float:
    """Linear block-road width scaling between webshop extent bounds.

    - 2000m extent -> 100% width
    - 5000m extent -> 70% width
    """
    min_extent = 2000.0
    max_extent = 5000.0
    max_reduction = 0.30

    clamped = max(min_extent, min(max_extent, float(extent_m)))
    t = (clamped - min_extent) / (max_extent - min_extent)
    return 1.0 - (max_reduction * t)


def _classify_road(hw: str) -> str:

    hw = str(hw)

    if hw in {"motorway", "trunk"}:
        return "highway"

    if hw in {"primary", "secondary", "tertiary"}:
        return "arterial"

    if hw in {"residential", "unclassified", "living_street"}:
        return "local"

    if hw in {"pedestrian", "footway", "path", "steps"}:
        return "pedestrian"

    return "minor"

def _deterministic_color(geom, palette):
    key = geom.wkb
    h = hashlib.md5(key).hexdigest()
    idx = int(h, 16) % len(palette)
    return palette[idx]


def _filter_pier_areas(gdf: gpd.GeoDataFrame | None) -> gpd.GeoDataFrame:
    if gdf is None or len(gdf) == 0 or "man_made" not in gdf.columns:
        return gpd.GeoDataFrame(geometry=[], crs=getattr(gdf, "crs", None))
    man_made = gdf["man_made"].fillna("").astype(str).str.lower()
    return gdf[man_made.eq("pier")].copy()


def _buffer_waterways_to_polygons(waterway_gdf: gpd.GeoDataFrame, target_crs) -> gpd.GeoDataFrame:
    if waterway_gdf is None or len(waterway_gdf) == 0:
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    width_map = {
        "river": 85.0,
        "canal": 24.0,
        "stream": 6.0,
        "ditch": 3.0,
        "drain": 2.5,
        "dock": 22.0,
    }

    def _parse_width_m(value) -> float | None:
        if value is None:
            return None
        text = str(value).strip().lower()
        if not text or text in {"nan", "none"}:
            return None
        text = text.replace(",", ".")
        for suffix in ("meters", "meter", "metres", "metre", "m"):
            if text.endswith(suffix):
                text = text[: -len(suffix)].strip()
                break
        try:
            parsed = float(text)
        except ValueError:
            return None
        if parsed <= 0:
            return None
        return parsed / 2.0

    waterways = waterway_gdf[(~waterway_gdf.geometry.isna()) & (~waterway_gdf.geometry.is_empty)].to_crs(target_crs).copy()
    waterways = waterways[waterways.geom_type.isin(["LineString", "MultiLineString", "Polygon", "MultiPolygon"])]
    if len(waterways) == 0:
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    line_mask = waterways.geom_type.isin(["LineString", "MultiLineString"])
    polygons = []

    if line_mask.any():
        line_waterways = waterways[line_mask].copy()
        line_waterways["_water_width"] = 10.0
        if "waterway" in line_waterways.columns:
            line_waterways["_water_width"] = line_waterways["waterway"].fillna("").astype(str).str.lower().map(width_map).fillna(line_waterways["_water_width"])
        if "width" in line_waterways.columns:
            parsed_widths = line_waterways["width"].apply(_parse_width_m)
            line_waterways["_water_width"] = parsed_widths.combine_first(line_waterways["_water_width"])
        polygons.extend(line_waterways.apply(lambda row: row.geometry.buffer(float(row["_water_width"])), axis=1).tolist())

    if (~line_mask).any():
        polygons.extend(waterways[~line_mask].geometry.tolist())

    polygons = [geom for geom in polygons if geom is not None and not geom.is_empty]
    if not polygons:
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    return gpd.GeoDataFrame(geometry=polygons, crs=target_crs)

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

        edges = shared_bundle["edges_raw"]

        edges_p = ox.projection.project_gdf(edges)

        edges_p = gpd.clip(
            edges_p,
            gpd.GeoSeries([clip_rect], crs=edges_p.crs)
        )

        edges_p["road_class"] = edges_p["highway"].apply(_classify_road)

        # WATER (broader OSM tags for sea/harbor/basin coverage)

        water = shared_bundle["water_raw"]

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

        exact_water_mode = os.getenv("OSM_LOCAL_EXACT_WATER", "").strip().lower() in {"1", "true", "yes", "on"}
        use_waterway_fallback = (not exact_water_mode) or len(water_p) == 0
        if use_waterway_fallback:
            waterway = shared_bundle.get("waterway_raw")
            waterway_p = _buffer_waterways_to_polygons(waterway, edges_p.crs)
            if len(waterway_p) > 0:
                waterway_p = gpd.clip(
                    waterway_p,
                    gpd.GeoSeries([clip_rect], crs=edges_p.crs)
                )
                if len(water_p) > 0:
                    water_p = gpd.GeoDataFrame(
                        geometry=list(water_p.geometry) + list(waterway_p.geometry),
                        crs=edges_p.crs,
                    )
                else:
                    water_p = waterway_p

        # COASTLINE

        coast = shared_bundle["coast_raw"]

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
        islands = shared_bundle["islands_raw"]

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

        water_union = unary_union(large_water.geometry) if len(large_water) > 0 else None
        water_surface = gpd.GeoDataFrame(geometry=[], crs=edges_p.crs)
        if water_union is not None and not water_union.is_empty:
            water_surface = gpd.GeoDataFrame(
                geometry=[water_union],
                crs=edges_p.crs,
            )

        water_structures = shared_bundle.get("water_structures_raw")
        pier_areas = _filter_pier_areas(water_structures)
        pier_p = gpd.GeoDataFrame(geometry=[], crs=edges_p.crs)
        if len(pier_areas) > 0:
            pier_p = pier_areas.to_crs(edges_p.crs)
            pier_p = pier_p[pier_p.geom_type.isin(["Polygon", "MultiPolygon"])]
            if len(pier_p) > 0:
                pier_p = gpd.clip(
                    pier_p,
                    gpd.GeoSeries([clip_rect], crs=edges_p.crs)
                )

        return {
            "cells": cells,
            "roads": edges_p,
            "water_surface": water_surface,
            "pier_p": pier_p,
            "bounds": (minx, maxx, miny, maxy),
        }

    shared_bundle = load_or_build_shared_osm_bundle(
        center_lat=center_lat,
        center_lon=center_lon,
        extent_m=spec.extent_m,
        half_width_m=half_width_m,
        half_height_m=half_height_m,
        use_cache=use_cache,
        include_building_features=True,
    )

    geometry_data = _build_geometry()

    cells = geometry_data["cells"]
    edges_p = geometry_data["roads"]
    water_surface = geometry_data["water_surface"]
    pier_p = geometry_data["pier_p"]

    minx, maxx, miny, maxy = geometry_data["bounds"]

    fig, ax = plt.subplots(
        figsize=(fig_w_in, fig_h_in),
        dpi=300
    )

    land_cells = cells.copy()
    if len(water_surface) > 0:
        water_union = water_surface.geometry.iloc[0]
        land_cells["geometry"] = land_cells.geometry.apply(lambda geom: geom.difference(water_union))
        land_cells = land_cells[(~land_cells.geometry.isna()) & (~land_cells.geometry.is_empty)]
        land_cells = land_cells[land_cells.geom_type.isin(["Polygon", "MultiPolygon"])]

        water_surface.plot(
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

    if len(pier_p) > 0:
        pier_p.plot(
            ax=ax,
            color=style_cfg.road,
            edgecolor="none",
            alpha=0.92,
            zorder=2.4,
        )

    base_width = style_cfg.road_style.base_width
    extent_scale = _road_width_scale_for_extent(spec.extent_m)
    multipliers = style_cfg.road_style.multipliers

    for road_class, m in multipliers.items():

        subset = edges_p[edges_p["road_class"] == road_class]

        if len(subset) == 0:
            continue

        subset.plot(
            ax=ax,
            linewidth=base_width * m * extent_scale,
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