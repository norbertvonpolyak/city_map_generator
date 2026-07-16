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


def _plot_dotted_texture(
    ax,
    gdf: gpd.GeoDataFrame,
    *,
    spacing_m: float,
    dot_size: float,
    color: str,
    alpha: float,
    zorder: float,
    rng: np.random.Generator,
) -> None:
    if gdf is None or len(gdf) == 0:
        return

    xs: list[float] = []
    ys: list[float] = []

    jitter = spacing_m * 0.22

    for geom in gdf.geometry:
        if geom is None or geom.is_empty:
            continue

        polygons = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]

        for poly in polygons:
            minx, miny, maxx, maxy = poly.bounds
            x_coords = np.arange(minx, maxx, spacing_m)
            y_coords = np.arange(miny, maxy, spacing_m)

            if len(x_coords) == 0 or len(y_coords) == 0:
                continue

            for x in x_coords:
                for y in y_coords:
                    px = x + rng.uniform(-jitter, jitter)
                    py = y + rng.uniform(-jitter, jitter)
                    if poly.contains(Point(px, py)):
                        xs.append(px)
                        ys.append(py)

    if xs:
        ax.scatter(xs, ys, s=dot_size, c=color, alpha=alpha, linewidths=0, zorder=zorder)


# =============================================================================
# BUILDING ENGINE
# =============================================================================

def render_map_building(
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

    # No palette is forced to building-only mode.
    render_only_buildings = False

    # Keep surface treatment style-specific so other building palettes stay unchanged.
    use_surface_texture = palette_name == "pretty_buildings"
    texture_rng = np.random.default_rng(seed if seed is not None else 42)

    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fig_w_in = map_width_cm / 2.54
    fig_h_in = map_height_cm / 2.54
    half_width_m, half_height_m = viewport_half_width_m, viewport_half_height_m

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

    if render_only_buildings:
        tags = {
            "building": True,
            "building:part": True,
        }
    else:
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
                "heath","fell","beach","sand"
            ],

            "amenity": [
                "parking","grave_yard","school","college","university"
            ],

            "place": ["square"],

            "highway": ["pedestrian"],
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

    trees_p = None
    draw_green_layers = (not render_only_buildings) and (palette_name != "mono_black")
    draw_tree_layers = draw_green_layers and (
        palette_name not in {"arctic_blue", "luxury_gold", "midnight_blue"}
    )

    if not render_only_buildings:
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

    waterway_p = gpd.GeoDataFrame(geometry=[], crs=gdf_all_p.crs)
    if not render_only_buildings:
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

    railway_p = gpd.GeoDataFrame(geometry=[], crs=gdf_all_p.crs)
    if not render_only_buildings:
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

    paths_p = gpd.GeoDataFrame(geometry=[], crs=gdf_all_p.crs)
    if not render_only_buildings:
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
    place = col(gdf_all_p, "place")
    highway = col(gdf_all_p, "highway")

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

    beach_p = gdf_all_p[
        (natural.isin(["beach", "sand"])) if natural is not None else False
    ]

    squares_p = gdf_all_p[
        ((place == "square") if place is not None else False)
        |
        ((highway == "pedestrian") if highway is not None else False)
    ]
    railway_p = railway_p[
        railway_p.geom_type.isin(["LineString", "MultiLineString"])
    ]

    # =============================================================================
    # COASTLINE (Balaton fix)
    # =============================================================================

    # =============================================================================
    # COASTLINE (Balaton fix)
    # =============================================================================

    coast_water = None
    if not render_only_buildings:
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

        except InsufficientResponseError:

            print (">>> No coastline found in this area")

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

    if len(waterway_p) > 0 and not use_surface_texture:

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

    if not render_only_buildings:
        if palette_name == "arctic_blue":
            beach_color = "#E8EEF4"
            beach_edge = "#AFBECF"
            parking_color = "#DCE6F0"
            industrial_color = "#C7D6E6"
        elif palette_name == "midnight_blue":
            beach_color = "#2A374A"
            beach_edge = "#3E526E"
            parking_color = "#1E2A3A"
            industrial_color = "#2B3E56"
        elif palette_name == "luxury_gold":
            beach_color = "#6A5D3E"
            beach_edge = "#8E7A4A"
            parking_color = "#5C5136"
            industrial_color = "#73643E"
        else:
            beach_color = "#EEE4D2"
            beach_edge = "none"
            parking_color = "#E6E6E6"
            industrial_color = "#DADADA"

        # water
        if len(water_p) > 0:
            water_p.plot(
                ax=ax,
                color=style_cfg.water,
                edgecolor=style_cfg.water_edge,
                linewidth=style_cfg.water_edge_width,
                zorder=1,
            )
            if use_surface_texture:
                _plot_dotted_texture(
                    ax,
                    water_p,
                    spacing_m=10,
                    dot_size=17.0,
                    color="#3F6F8B",
                    alpha=0.72,
                    zorder=1.08,
                    rng=texture_rng,
                )

        skip_waterway_overlay = use_surface_texture and len(water_p) > 0

        if len(waterway_p) > 0 and not skip_waterway_overlay:
            waterway_p.plot(
                ax=ax,
                color=style_cfg.water,
                edgecolor=style_cfg.water_edge,
                linewidth=style_cfg.water_edge_width,
                zorder=1,
            )
            if use_surface_texture:
                _plot_dotted_texture(
                    ax,
                    waterway_p,
                    spacing_m=10,
                    dot_size=17.0,
                    color="#3F6F8B",
                    alpha=0.72,
                    zorder=1.08,
                    rng=texture_rng,
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
            if use_surface_texture:
                _plot_dotted_texture(
                    ax,
                    coast_water,
                    spacing_m=10,
                    dot_size=17.0,
                    color="#3F6F8B",
                    alpha=0.72,
                    zorder=0.08,
                    rng=texture_rng,
                )

        if len(beach_p) > 0:
            beach_p.plot(
                ax=ax,
                color=beach_color,
                edgecolor=beach_edge,
                linewidth=0.06 if palette_name == "arctic_blue" else 0,
                zorder=1.7,
            )

        if len(squares_p) > 0:
            squares_p.plot(
                ax=ax,
                color="#D9CDB2" if use_surface_texture else style_cfg.background,
                edgecolor="none",
                zorder=1.9,
            )
            if use_surface_texture:
                _plot_dotted_texture(
                    ax,
                    squares_p,
                    spacing_m=9,
                    dot_size=16.0,
                    color="#8F7959",
                    alpha=0.74,
                    zorder=1.95,
                    rng=texture_rng,
                )

        # greens
        if draw_green_layers and len (greens_p) > 0:
            greens_p.plot (
                ax=ax,
                color=style_cfg.green,
                edgecolor=style_cfg.green_edge,
                linewidth=style_cfg.green_edge_width,
                zorder=2,
            )
            if use_surface_texture:
                _plot_dotted_texture(
                    ax,
                    greens_p,
                    spacing_m=9,
                    dot_size=16.4,
                    color="#2F603B",
                    alpha=0.74,
                    zorder=2.08,
                    rng=texture_rng,
                )

        # trees
        if draw_tree_layers and len (trees_p) > 0:
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
            paths_to_plot = paths_p
            if palette_name == "midnight_blue":
                green_masks = []
                if len(greens_p) > 0:
                    green_masks.append(unary_union(greens_p.geometry))
                if len(cemetery_p) > 0:
                    green_masks.append(unary_union(cemetery_p.geometry))
                if len(green_masks) > 0:
                    combined_green_mask = unary_union(green_masks)
                    paths_to_plot = gpd.clip(
                        paths_p,
                        gpd.GeoSeries([combined_green_mask], crs=paths_p.crs),
                    )

            path_color = "#6F6F6F"
            path_width = 0.9
            path_alpha = 0.8
            path_zorder = 3
            if palette_name == "pretty_buildings":
                path_color = "#3F5258"
                path_width = 2.4
                path_alpha = 0.72
            elif palette_name == "midnight_blue":
                path_color = style_cfg.background
                path_width = 1.45
                path_alpha = 0.96
                path_zorder = 4
            elif palette_name == "luxury_gold":
                path_color = style_cfg.background
                path_width = 1.6
                path_alpha = 0.96
                path_zorder = 4

            if len(paths_to_plot) > 0:
                paths_to_plot.plot (
                    ax=ax,
                    color=path_color,
                    linewidth=path_width,
                    alpha=path_alpha,
                    zorder=path_zorder,
                )

        if draw_green_layers and river_green is not None:
            river_green.plot(
                ax=ax,
                color=style_cfg.green,
                edgecolor="none",
                alpha=0.6,
                zorder=2,
            )

        # extra
        # cemetery
        if draw_green_layers and len (cemetery_p) > 0:
            cemetery_p.plot (
                ax=ax,
                color=style_cfg.green,
                edgecolor=style_cfg.green_edge,
                linewidth=style_cfg.green_edge_width,
                zorder=2,
            )

        if len(parking_p) > 0:
            parking_p.plot(ax=ax, color=parking_color, edgecolor="none", zorder=3)

        if len(industrial_p) > 0:
            industrial_p.plot(ax=ax, color=industrial_color, edgecolor="none", zorder=3)

    # buildings
    if len(buildings_p) > 0:

        palette = style_cfg.building_colors

        base_weights = [0.34, 0.28, 0.15, 0.12, 0.08, 0.03]
        if len(palette) == len(base_weights):
            weights = base_weights
        elif len(palette) < len(base_weights):
            # Keep the intended front-loaded distribution and renormalize.
            sliced = base_weights[: len(palette)]
            total = sum(sliced)
            weights = [w / total for w in sliced]
        else:
            # Fallback for longer custom palettes.
            weights = None

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

    draw_transport_layers = (not render_only_buildings) and (
        palette_name not in {
            "architect_sage", "warm_terracotta", "mono_black", "luxury_gold", "midnight_blue"
        }
    )

    if draw_transport_layers:
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
    ax.set_position([0, 0, 1, 1])

    # =============================================================================
    # SAVE
    # =============================================================================

    if preview_mode:

        output_path = output_dir / f"{filename_prefix}.png"

        fig.savefig(
            output_path,
            dpi=140,
            pad_inches=0,
        )

    else:

        output_path = output_dir / f"{filename_prefix}.svg"

        fig.savefig(
            output_path,
            format="svg",
            dpi=spec.dpi,
            pad_inches=0,
        )

    plt.close(fig)

    print(">>> Render complete")

    return MapLayerResult(output_svg=output_path)