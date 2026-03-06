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

from osmnx._errors import InsufficientResponseError

from shapely.geometry import Point, box
from shapely.ops import unary_union, polygonize

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

def col(gdf, name):
    return gdf[name] if name in gdf.columns else None


def _normalize_highway_value(v):
    return v[0] if isinstance(v, (list, tuple)) and v else v


def _classify_road(hw: str):

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
    min_building_area: float = 15.0,
) -> MapLayerResult:

    print(">>> ENTER render_map_building")

    ox.settings.use_cache = True
    ox.settings.timeout = 60

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

    print(f">>> dist_m = {dist_m}")

    # =============================================================================
    # CENTER + CLIP
    # =============================================================================

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

    # =============================================================================
    # ROADS
    # =============================================================================

    print(">>> Downloading roads...")

    G = ox.graph_from_point(
        (center_lat, center_lon),
        dist=dist_m,
        network_type=network_type_draw,
        simplify=True,
    )

    edges = ox.graph_to_gdfs(G, nodes=False, edges=True)

    edges_p = ox.projection.project_gdf(edges)

    edges_p = gpd.clip(
        edges_p,
        gpd.GeoSeries([clip_rect], crs=edges_p.crs)
    )

    edges_p = edges_p[~edges_p.is_empty]

    if "highway" in edges_p.columns:

        edges_p["highway"] = edges_p["highway"].apply(
            _normalize_highway_value
        )

        edges_p["road_class"] = edges_p["highway"].apply(
            _classify_road
        )

    else:
        edges_p["road_class"] = "local"

    print(">>> Roads ready")

    # =============================================================================
    # FEATURE QUERY – MAXIMAL ZÖLD
    # =============================================================================

    tags = {

        "building": True,
        "building:part": True,

        "landuse": [
            "grass","meadow","farmland","orchard","forest",
            "allotments","garden","recreation_ground",
            "village_green","cemetery",
            "industrial","commercial","retail",
            "education"
        ],

        "leisure": [
            "park","garden","pitch","sports_centre","stadium",
            "nature_reserve","playground","dog_park"
        ],

        "natural": [
            "water","wood","scrub","grassland","wetland",
            "heath","fell"
        ],

        "amenity": [
            "parking","grave_yard","school","college","university"
        ],
    }

    print(">>> Downloading unified features...")

    gdf_all = ox.features_from_point(
        (center_lat, center_lon),
        tags=tags,
        dist=dist_m,
    )

    gdf_all = gdf_all[gdf_all.geometry.notnull()]

    gdf_all_p = ox.projection.project_gdf(gdf_all)

    gdf_all_p = gdf_all_p[
        gdf_all_p.geom_type.isin(["Polygon", "MultiPolygon"])
    ]

    gdf_all_p = gpd.clip(
        gdf_all_p,
        gpd.GeoSeries([clip_rect], crs=gdf_all_p.crs),
    )

    # =============================================================================
    # TREES
    # =============================================================================

    print (">>> Downloading trees...")

    trees = ox.features_from_point (
        (center_lat, center_lon),
        tags={"natural": "tree"},
        dist=dist_m,
    )

    trees = trees [trees.geometry.notnull ()]

    trees_p = ox.projection.project_gdf (trees)

    trees_p = gpd.clip (
        trees_p,
        gpd.GeoSeries ([clip_rect], crs=trees_p.crs),
    )

    # =============================================================================
    # WATERWAYS
    # =============================================================================

    print(">>> Downloading waterways...")

    waterway = ox.features_from_point(
        (center_lat, center_lon),
        tags={"waterway": True},
        dist=dist_m,
    )

    waterway = waterway[waterway.geometry.notnull()]

    waterway_p = ox.projection.project_gdf(waterway)

    waterway_p = gpd.clip(
        waterway_p,
        gpd.GeoSeries([clip_rect], crs=waterway_p.crs),
    )

    waterway_p = waterway_p[~waterway_p.is_empty]

    if len(waterway_p) > 0:

        width_map = {
            "river": 4,
            "stream": 2,
            "ditch": 1,
            "canal": 3,
        }

        if "waterway" in waterway_p.columns:

            waterway_p["width"] = waterway_p["waterway"].map(width_map).fillna(1.5)

            waterway_p["geometry"] = waterway_p.apply(
                lambda r: r.geometry.buffer(r.width),
                axis=1,
            )

    # =============================================================================
    # RAILWAY
    # =============================================================================

    print (">>> Downloading railways...")

    railway = ox.features_from_point (
        (center_lat, center_lon),
        tags={"railway": True},
        dist=dist_m,
    )

    railway = railway [railway.geometry.notnull ()]

    railway_p = ox.projection.project_gdf (railway)

    railway_p = gpd.clip (
        railway_p,
        gpd.GeoSeries ([clip_rect], crs=railway_p.crs),
    )

    railway_p = railway_p [~railway_p.is_empty]

    # =============================================================================
    # PATHS (parks / cemeteries / forests)
    # =============================================================================

    print (">>> Downloading paths...")

    paths = ox.features_from_point (
        (center_lat, center_lon),
        tags={
            "highway": [
                "footway",
                "path",
                "track",
                "steps"
            ]
        },
        dist=dist_m,
    )

    paths = paths [paths.geometry.notnull ()]

    paths_p = ox.projection.project_gdf (paths)

    paths_p = gpd.clip (
        paths_p,
        gpd.GeoSeries ([clip_rect], crs=paths_p.crs),
    )

    paths_p = paths_p [~paths_p.is_empty]

    # =============================================================================
    # SAFE COLUMN ACCESS
    # =============================================================================

    building = col(gdf_all_p, "building")
    building_part = col(gdf_all_p, "building:part")

    landuse = col(gdf_all_p, "landuse")
    leisure = col(gdf_all_p, "leisure")
    natural = col(gdf_all_p, "natural")
    amenity = col(gdf_all_p, "amenity")

    # =============================================================================
    # BUILDINGS
    # =============================================================================

    building_mask = False

    if building is not None:
        building_mask = building.notnull()

    if building_part is not None:
        building_mask = building_mask | building_part.notnull()

    buildings_p = gdf_all_p[building_mask]

    buildings_p = buildings_p[
        buildings_p.geometry.area > min_building_area
    ]

    # =============================================================================
    # GREEN AREAS
    # =============================================================================

    greens_p = gdf_all_p[

        (
            (leisure.isin([
                "park","garden","pitch","nature_reserve",
                "playground","dog_park"
            ]))
            if leisure is not None else False
        )

        |

        (
            (landuse.isin([
                "grass","meadow","farmland","orchard","forest",
                "allotments","garden","recreation_ground",
                "village_green"
            ]))
            if landuse is not None else False
        )

        |

        (
            (natural.isin([
                "wood","scrub","grassland","wetland","heath","fell"
            ]))
            if natural is not None else False
        )
    ]


    # =============================================================================
    # WATER POLYGONS
    # =============================================================================

    water_p = gdf_all_p[
        (natural == "water") if natural is not None else False
    ]

    # =============================================================================
    # COASTLINE (Balaton fix)
    # =============================================================================

    # =============================================================================
    # COASTLINE (Balaton fix)
    # =============================================================================

    print (">>> Downloading coastline...")

    try:

        coast = ox.features_from_point (
            (center_lat, center_lon),
            tags={"natural": "coastline"},
            dist=dist_m,
        )

        coast = coast [coast.geometry.notnull ()]

        if len (coast) > 0:

            coast_p = ox.projection.project_gdf (coast)

            coast_p = gpd.clip (
                coast_p,
                gpd.GeoSeries ([clip_rect], crs=coast_p.crs),
            )

            coast_lines = coast_p.geometry

            water_polygons = list (polygonize (coast_lines))

            if len (water_polygons) > 0:

                coast_water = gpd.GeoDataFrame (
                    geometry=water_polygons,
                    crs=coast_p.crs,
                )

                coast_water = gpd.clip (
                    coast_water,
                    gpd.GeoSeries ([clip_rect], crs=coast_water.crs),
                )

            else:
                coast_water = None

        else:
            coast_water = None

    except InsufficientResponseError:

        print (">>> No coastline found in this area")

        coast_water = None

    # =============================================================================
    # EXTRA AREAS
    # =============================================================================

    cemetery_p = gdf_all_p[
        (
            (landuse == "cemetery") if landuse is not None else False
        )
        |
        (
            (amenity == "grave_yard") if amenity is not None else False
        )
    ]

    parking_p = gdf_all_p[
        (amenity == "parking") if amenity is not None else False
    ]

    industrial_p = gdf_all_p[
        (
            (landuse.isin(["industrial","commercial","retail"]))
            if landuse is not None else False
        )
    ]

    # =============================================================================
    # AUTOMATIC RIVER GREEN BELT
    # =============================================================================

    if len(waterway_p) > 0:

        river_green = gpd.GeoDataFrame(
            geometry=[unary_union(waterway_p.geometry).buffer(25)],
            crs=waterway_p.crs
        )

    else:
        river_green = None

    # =============================================================================
    # PLOT
    # =============================================================================

    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))

    fig.patch.set_facecolor(style_cfg.background)
    ax.set_facecolor(style_cfg.background)

    # water
    if len(water_p) > 0:
        water_p.plot(
            ax=ax,
            color=style_cfg.water,
            edgecolor=style_cfg.water_edge,
            linewidth=style_cfg.water_edge_width,
            zorder=1,
        )

    if len(waterway_p) > 0:
        waterway_p.plot(
            ax=ax,
            color=style_cfg.water,
            edgecolor=style_cfg.water_edge,
            linewidth=style_cfg.water_edge_width,
            zorder=1,
        )

    # coastline water (Balaton)
    if coast_water is not None and len (coast_water) > 0:
        coast_water.plot (
            ax=ax,
            color=style_cfg.water,
            edgecolor=style_cfg.water_edge,
            linewidth=style_cfg.water_edge_width,
            zorder=0,
        )

    # greens
    if len (greens_p) > 0:
        greens_p.plot (
            ax=ax,
            color=style_cfg.green,
            edgecolor=style_cfg.green_edge,
            linewidth=style_cfg.green_edge_width,
            zorder=2,
        )

    # trees
    if len (trees_p) > 0:
        trees_p.plot (
            ax=ax,
            color="#4F6D4F",
            markersize=6,
            marker="o",
            alpha=0.7,
            zorder=4,
        )

    # paths (visible in parks / cemeteries)
    if len (paths_p) > 0:
        paths_p.plot (
            ax=ax,
            color="#B8B8B8",
            linewidth=0.5,
            alpha=0.6,
            zorder=3,
        )

    if river_green is not None:
        river_green.plot(
            ax=ax,
            color=style_cfg.green,
            edgecolor="none",
            alpha=0.6,
            zorder=2,
        )

    # extra
    # cemetery
    if len (cemetery_p) > 0:
        cemetery_p.plot (
            ax=ax,
            color=style_cfg.green,
            edgecolor=style_cfg.green_edge,
            linewidth=style_cfg.green_edge_width,
            zorder=2,
        )

    if len(parking_p) > 0:
        parking_p.plot(ax=ax,color="#E6E6E6",edgecolor="none",zorder=3)

    if len(industrial_p) > 0:
        industrial_p.plot(ax=ax,color="#DADADA",edgecolor="none",zorder=3)

    # buildings
    if len(buildings_p) > 0:

        palette = style_cfg.building_colors

        weights = [0.34,0.28,0.15,0.12,0.08,0.03]

        building_colors = np.random.choice(
            palette,
            size=len(buildings_p),
            p=weights,
        )

        buildings_p.plot(
            ax=ax,
            color=building_colors,
            edgecolor=style_cfg.building_edge,
            linewidth=style_cfg.building_edge_width,
            zorder=5,
        )

    # roads
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

    # railway
    if len (railway_p) > 0:
        railway_p.plot (
            ax=ax,
            color="#555555",
            linewidth=1.2,
            zorder=11,
        )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    # =============================================================================
    # SAVE
    # =============================================================================

    if preview_mode:

        output_path = output_dir / f"{filename_prefix}.png"

        fig.savefig(
            output_path,
            dpi=140,
            bbox_inches="tight",
            pad_inches=0,
        )

    else:

        output_path = output_dir / f"{filename_prefix}.svg"

        fig.savefig(
            output_path,
            format="svg",
            dpi=spec.dpi,
            bbox_inches="tight",
        )

    plt.close(fig)

    print(">>> Render complete")

    return MapLayerResult(output_svg=output_path)