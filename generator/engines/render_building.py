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


def _is_mainline_railway(v) -> bool:
    if v is None:
        return False

    if isinstance(v, (list, tuple, set)):
        values = [str(item).strip().lower() for item in v if item is not None]
    else:
        values = [str(v).strip().lower()]

    excluded = {"subway", "metro", "light_rail", "tram", "monorail", "funicular"}

    has_mainline = any(val == "rail" for val in values)
    has_excluded = any(val in excluded for val in values)
    return has_mainline and (not has_excluded)


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


def _is_truthy_bridge(value) -> bool:
    if value is None:
        return False

    if isinstance(value, (list, tuple)):
        return any(_is_truthy_bridge(v) for v in value)

    text = str(value).strip().lower()
    return text in {"yes", "true", "1", "viaduct", "aqueduct", "movable"}


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.strip().lstrip("#")

    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)

    if len(value) != 6:
        return (0, 0, 0)

    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    )


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02X}{g:02X}{b:02X}"


def _blend_hex(a: str, b: str, ratio_to_b: float) -> str:
    ratio = max(0.0, min(1.0, ratio_to_b))
    ar, ag, ab = _hex_to_rgb(a)
    br, bg, bb = _hex_to_rgb(b)

    blended = (
        int(round(ar * (1.0 - ratio) + br * ratio)),
        int(round(ag * (1.0 - ratio) + bg * ratio)),
        int(round(ab * (1.0 - ratio) + bb * ratio)),
    )
    return _rgb_to_hex(blended)


def _color_distance(a: str, b: str) -> float:
    ar, ag, ab = _hex_to_rgb(a)
    br, bg, bb = _hex_to_rgb(b)
    return ((ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2) ** 0.5


def _relative_luminance(color: str) -> float:
    rgb = [c / 255.0 for c in _hex_to_rgb(color)]

    linear = []
    for channel in rgb:
        if channel <= 0.04045:
            linear.append(channel / 12.92)
        else:
            linear.append(((channel + 0.055) / 1.055) ** 2.4)

    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(a: str, b: str) -> float:
    la = _relative_luminance(a)
    lb = _relative_luminance(b)
    lighter = max(la, lb)
    darker = min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def _pick_bridge_color(
    style_cfg: BuildingStyleConfig,
    *,
    palette_name: str,
    road_water_merged: bool,
    draw_transport_layers: bool,
) -> str:
    if palette_name == "architect_sage":
        return "#A3A5A0"
    if palette_name == "warm_terracotta":
        return style_cfg.background

    # Keep bridge tones in-palette while ensuring they stay visible over water.
    if road_water_merged or (not draw_transport_layers):
        preferred = [
            style_cfg.building_edge,
            style_cfg.building_colors[2] if len(style_cfg.building_colors) > 2 else None,
            style_cfg.building_colors[0] if len(style_cfg.building_colors) > 0 else None,
            style_cfg.building_colors[1] if len(style_cfg.building_colors) > 1 else None,
        ]
    else:
        preferred = [
            style_cfg.road,
            style_cfg.building_edge,
            style_cfg.building_colors[0] if len(style_cfg.building_colors) > 0 else None,
        ]

    fallback = "#2D3640" if _relative_luminance(style_cfg.background) >= 0.45 else "#D7D7D7"

    viable: list[str] = []
    for candidate in preferred:
        if candidate is None:
            continue

        contrast = _contrast_ratio(candidate, style_cfg.water)
        distance = _color_distance(candidate, style_cfg.water)

        # Avoid both muddy (too low contrast) and overly harsh highlights.
        if contrast >= 1.55 and distance >= 26:
            if contrast <= 6.8:
                return candidate
            viable.append(candidate)

    if len(viable) > 0:
        best_color = viable[0]
    else:
        best_color = fallback
        best_score = -1.0

        for candidate in preferred:
            if candidate is None:
                continue

            contrast = _contrast_ratio(candidate, style_cfg.water)
            distance = _color_distance(candidate, style_cfg.water)
            score = contrast * 9.0 + distance
            if score > best_score:
                best_score = score
                best_color = candidate

    # Harmonize slightly toward the active water color without losing legibility.
    bridge_color = _blend_hex(best_color, style_cfg.water, 0.22)

    if _contrast_ratio(bridge_color, style_cfg.water) < 1.35:
        bridge_color = _blend_hex(best_color, style_cfg.water, 0.10)

    if _contrast_ratio(bridge_color, style_cfg.water) > 5.8:
        bridge_color = _blend_hex(best_color, style_cfg.water, 0.32)

    return bridge_color


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
    use_surface_texture = False
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

    bridges_p = gpd.GeoDataFrame(geometry=[], crs=edges_p.crs)
    if "bridge" in edges_p.columns:
        bridge_mask = edges_p["bridge"].apply(_is_truthy_bridge)
        if bridge_mask.any():
            bridges_p = edges_p[bridge_mask].copy()
            bridges_p = bridges_p[
                bridges_p.geom_type.isin(["LineString", "MultiLineString"])
            ]

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
        palette_name not in {"luxury_gold", "midnight_blue"}
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

    if len(railway_p) > 0 and "railway" in railway_p.columns:
        railway_p = railway_p[railway_p["railway"].apply(_is_mainline_railway)]

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
    # PLOT
    # =============================================================================

    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))

    fig.patch.set_facecolor(style_cfg.background)
    ax.set_facecolor(style_cfg.background)

    if not render_only_buildings:
        if palette_name == "midnight_blue":
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

        # Waterway overlay is intentionally disabled to avoid centerline artifacts
        # inside wide rivers across all building styles.

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
                linewidth=0,
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
            if palette_name == "midnight_blue":
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

    road_water_merged = _color_distance(style_cfg.road, style_cfg.water) < 24
    draw_bridge_highlight = (
        (not render_only_buildings)
        and len(bridges_p) > 0
        and (road_water_merged or (not draw_transport_layers))
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

    # railway: keep visible in all building styles, even when roads are hidden.
    if (not render_only_buildings) and len(railway_p) > 0:
        railway_p.plot(
            ax=ax,
            color="#B8B8B8",
            linewidth=1.2,
            alpha=0.75,
            zorder=11,
        )

    if draw_bridge_highlight:
        bridge_color = _pick_bridge_color(
            style_cfg,
            palette_name=palette_name,
            road_water_merged=road_water_merged,
            draw_transport_layers=draw_transport_layers,
        )
        road_width_base = style_cfg.road_style.base_width
        multipliers = style_cfg.road_style.multipliers

        if "road_class" in bridges_p.columns:
            for cls, mult in multipliers.items():
                subset = bridges_p[bridges_p["road_class"] == cls]
                if len(subset) == 0:
                    continue

                subset.plot(
                    ax=ax,
                    color=bridge_color,
                    linewidth=max(0.85, road_width_base * mult * 1.22 * 0.60),
                    capstyle="round",
                    joinstyle="round",
                    alpha=0.96,
                    zorder=12,
                )
        else:
            bridges_p.plot(
                ax=ax,
                color=bridge_color,
                linewidth=max(0.85, road_width_base * 1.8 * 0.60),
                capstyle="round",
                joinstyle="round",
                alpha=0.96,
                zorder=12,
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