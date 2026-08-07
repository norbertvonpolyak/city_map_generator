from __future__ import annotations

import os
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
from matplotlib import colors as mcolors

from osmnx._errors import InsufficientResponseError

from shapely.geometry import Point, Polygon, MultiPolygon, box
from shapely.ops import unary_union, polygonize

from generator.core.osm_bundle_cache import load_or_build_shared_osm_bundle
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


def _is_bridge_value(v) -> bool:
    if isinstance(v, (list, tuple, set)):
        return any(_is_bridge_value(item) for item in v)
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s not in {"", "0", "false", "no", "none", "nan"}


def _relative_luminance(color: str) -> float:
    r, g, b = mcolors.to_rgb(color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _rgb_distance(c1: str, c2: str) -> float:
    r1, g1, b1 = mcolors.to_rgb(c1)
    r2, g2, b2 = mcolors.to_rgb(c2)
    return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5


def _blend_towards(color: str, target: str, amount: float) -> str:
    r, g, b = mcolors.to_rgb(color)
    tr, tg, tb = mcolors.to_rgb(target)
    a = max(0.0, min(1.0, amount))
    return mcolors.to_hex((r + (tr - r) * a, g + (tg - g) * a, b + (tb - b) * a))


def _bridge_color_for_style(palette_name: str, road_color: str, water_color: str) -> str:
    style_overrides = {
        "architect_sage": "#bfd4cf",
        "warm_terracotta": "#f5e8d6",
        "sandstone_beige": None,
        "luxury_gold": "#111111",
        "midnight_blue": "#183940",
        "mono_black": "#e0e0e0",
        "royal_purple": "#4b4779",
    }

    if palette_name in style_overrides:
        override = style_overrides[palette_name]
        return road_color if override is None else override

    # Keep bridge close to style road color, but force stronger contrast vs water.
    if _rgb_distance(road_color, water_color) >= 0.30:
        return road_color
    water_l = _relative_luminance(water_color)
    target = "#FFFFFF" if water_l < 0.52 else "#111111"
    return _blend_towards(road_color, target, 0.38)


def _fill_polygon_holes(geom, min_hole_area_m2: float = 10_000):
    """Fill interior rings smaller than threshold (data noise); preserve larger ones (islands)."""
    if geom is None or geom.is_empty:
        return geom
    if isinstance(geom, Polygon):
        kept = [r for r in geom.interiors if Polygon(r).area >= min_hole_area_m2]
        return Polygon(geom.exterior, kept)
    if isinstance(geom, MultiPolygon):
        result = []
        for poly in geom.geoms:
            kept = [r for r in poly.interiors if Polygon(r).area >= min_hole_area_m2]
            result.append(Polygon(poly.exterior, kept))
        return MultiPolygon(result)
    return geom


def _mask_out_water(gdf: gpd.GeoDataFrame, water_geom):
    if gdf is None or len(gdf) == 0 or water_geom is None or water_geom.is_empty:
        return gdf
    clipped = gdf.copy()
    try:
        clipped["geometry"] = clipped.geometry.apply(lambda geom: geom.difference(water_geom))
        return clipped[~clipped.is_empty]
    except Exception as e:
        # Topology error: skip masking and return original
        print(f"[WARNING] Water masking failed ({type(e).__name__}): {str(e)[:80]}. Skipping masking.")
        return gdf


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


def _filter_man_made(gdf: gpd.GeoDataFrame | None, values: set[str]) -> gpd.GeoDataFrame:
    if gdf is None or len(gdf) == 0 or "man_made" not in gdf.columns:
        return gpd.GeoDataFrame(geometry=[], crs=getattr(gdf, "crs", None))
    man_made = gdf["man_made"].fillna("").astype(str).str.lower()
    return gdf[man_made.isin(values)].copy()


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
    zoom: float = 1.0,
    min_building_area: float = 15.0,
    use_cache: bool = True,
) -> MapLayerResult:

    print(">>> ENTER render_map_building")

    ox.settings.use_cache = True
    ox.settings.timeout = 60

    style_cfg = get_style_config(palette_name)

    if not isinstance(style_cfg, BuildingStyleConfig):
        raise TypeError(f"Style '{palette_name}' is not building-based.")

    # No palette is forced to building-only mode.
    render_only_buildings = False
    all_objects_mode = os.getenv("BUILDING_RENDER_ALL_OBJECTS", "").strip().lower() in {"1", "true", "yes", "on"}
    hide_vegetation = os.getenv("BUILDING_HIDE_VEGETATION", "").strip().lower() in {"1", "true", "yes", "on"}
    hide_lines_on_water = os.getenv("BUILDING_HIDE_WATER_LINES", "").strip().lower() in {"1", "true", "yes", "on"}
    if all_objects_mode:
        print(">>> Building engine all-objects overlay: ON")

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

    def _build_geometry() -> dict[str, object]:
        edges = shared_bundle["edges_raw"]

        edges_p = ox.projection.project_gdf(edges)
        # All layers must share one CRS; ox.projection.project_gdf picks UTM zone
        # per-dataset and can assign different zones near zone boundaries.
        ref_crs = edges_p.crs

        # Recompute clip_rect in the edges_p CRS to ensure consistency.
        center_in_ref = gpd.GeoDataFrame(
            geometry=[Point(center_lon, center_lat)],
            crs="EPSG:4326"
        ).to_crs(ref_crs).geometry.iloc[0]
        clip_rect_local = box(
            center_in_ref.x - half_width_m,
            center_in_ref.y - half_height_m,
            center_in_ref.x + half_width_m,
            center_in_ref.y + half_height_m
        )

        edges_p = gpd.clip(
            edges_p,
            gpd.GeoSeries([clip_rect_local], crs=ref_crs)
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

        gdf_all = shared_bundle["gdf_all_raw"]

        gdf_all = gdf_all[gdf_all.geometry.notnull()]

        gdf_all_p = gdf_all.to_crs(ref_crs)

        if not all_objects_mode:
            gdf_all_p = gdf_all_p[
                gdf_all_p.geom_type.isin(["Polygon", "MultiPolygon"])
            ]

        gdf_all_p = gpd.clip(
            gdf_all_p,
            gpd.GeoSeries([clip_rect_local], crs=ref_crs),
        )

        trees_p = gpd.GeoDataFrame(geometry=[], crs=gdf_all_p.crs)
        if not render_only_buildings:
            trees = shared_bundle["trees_raw"]

            trees = trees[trees.geometry.notnull()]

            trees_p = trees.to_crs(ref_crs)

            trees_p = gpd.clip(
                trees_p,
                gpd.GeoSeries([clip_rect_local], crs=ref_crs),
            )

        green_p = gpd.GeoDataFrame(geometry=[], crs=gdf_all_p.crs)
        if not render_only_buildings:
            green_raw = shared_bundle.get("green_raw")
            if green_raw is not None and len(green_raw) > 0:
                green_raw = green_raw[green_raw.geometry.notnull()]
                if len(green_raw) > 0:
                    green_p = green_raw.to_crs(ref_crs)
                    green_p = gpd.clip(
                        green_p,
                        gpd.GeoSeries([clip_rect_local], crs=ref_crs),
                    )
                    green_p = green_p[~green_p.is_empty]
                    green_p = green_p[
                        green_p.geom_type.isin(["Polygon", "MultiPolygon"])
                    ]

        waterway_p = gpd.GeoDataFrame(geometry=[], crs=gdf_all_p.crs)
        if not render_only_buildings:
            waterway = shared_bundle["waterway_raw"]

            waterway = waterway[waterway.geometry.notnull()]

            waterway_p = waterway.to_crs(ref_crs)

            waterway_p = gpd.clip(
                waterway_p,
                gpd.GeoSeries([clip_rect_local], crs=ref_crs),
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

        railway_p = gpd.GeoDataFrame(geometry=[], crs=gdf_all_p.crs)
        if not render_only_buildings:
            railway = shared_bundle["railway_raw"]

            railway = railway[railway.geometry.notnull()]

            railway_p = railway.to_crs(ref_crs)

            railway_p = gpd.clip(
                railway_p,
                gpd.GeoSeries([clip_rect_local], crs=ref_crs),
            )

            railway_p = railway_p[~railway_p.is_empty]

        paths_p = gpd.GeoDataFrame(geometry=[], crs=gdf_all_p.crs)
        if not render_only_buildings:
            paths = shared_bundle["paths_raw"]

            paths = paths[paths.geometry.notnull()]

            paths_p = paths.to_crs(ref_crs)

            paths_p = gpd.clip(
                paths_p,
                gpd.GeoSeries([clip_rect_local], crs=ref_crs),
            )

            paths_p = paths_p[~paths_p.is_empty]

        water_structures_p = gpd.GeoDataFrame(geometry=[], crs=gdf_all_p.crs)
        pier_areas_p = gpd.GeoDataFrame(geometry=[], crs=gdf_all_p.crs)
        if not render_only_buildings:
            water_structures = shared_bundle.get(
                "water_structures_raw",
                gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"),
            )

            water_structures = water_structures[water_structures.geometry.notnull()]

            if len(water_structures) > 0:
                water_structures_p = water_structures.to_crs(ref_crs)

                water_structures_p = gpd.clip(
                    water_structures_p,
                    gpd.GeoSeries([clip_rect_local], crs=ref_crs),
                )

                water_structures_p = water_structures_p[~water_structures_p.is_empty]

                pier_areas_p = _filter_man_made(water_structures_p, {"pier"})
                pier_areas_p = pier_areas_p[
                    pier_areas_p.geom_type.isin(["Polygon", "MultiPolygon"])
                ]

        railway_p = railway_p[
            railway_p.geom_type.isin(["LineString", "MultiLineString"])
        ]

        coast_water = None
        if not render_only_buildings:
            coast = shared_bundle["coast_raw"]

            if coast is None:
                coast = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

            coast = coast[coast.geometry.notnull()]

            if len(coast) > 0:

                coast_p = coast.to_crs(ref_crs)

                coast_p = gpd.clip(
                    coast_p,
                    gpd.GeoSeries([clip_rect_local], crs=ref_crs),
                )

                coast_lines = coast_p[coast_p.geom_type.isin(["LineString", "MultiLineString"])]

                if len(coast_lines) > 0:
                    # Add clip boundary so polygonize can close open coastline segments
                    merged = unary_union(list(coast_lines.geometry.values) + [clip_rect_local.boundary])
                    water_polygons = [p for p in polygonize(merged) if not p.is_empty and p.area > 0]

                    if water_polygons:
                        # Keep only low-road-density regions (open water, not built-up land)
                        roads_union = unary_union(list(edges_p.geometry.values)) if len(edges_p) > 0 else None
                        sea_threshold = 1e-2
                        sea_regions = []
                        for poly in water_polygons:
                            if poly.contains(center_in_ref):
                                continue
                            density = 0.0
                            if roads_union is not None and poly.area > 0:
                                road_inside = poly.intersection(roads_union)
                                if not road_inside.is_empty:
                                    density = road_inside.length / poly.area
                            if density < sea_threshold:
                                sea_regions.append(poly)

                        if sea_regions:
                            sea_poly = unary_union(sea_regions)
                            coast_water = gpd.GeoDataFrame(
                                geometry=[sea_poly],
                                crs=ref_crs,
                            )
                            coast_water = gpd.clip(
                                coast_water,
                                gpd.GeoSeries([clip_rect_local], crs=ref_crs),
                            )
                else:
                    # Polygon-type coastline features (e.g. lakes already as polygons)
                    water_polygons = list(polygonize(coast_p.geometry))
                    if water_polygons:
                        coast_water = gpd.GeoDataFrame(geometry=water_polygons, crs=coast_p.crs)
                        coast_water = gpd.clip(
                            coast_water,
                            gpd.GeoSeries([clip_rect_local], crs=coast_water.crs),
                        )

        islands_p = gpd.GeoDataFrame(geometry=[], crs=gdf_all_p.crs)
        if not render_only_buildings:
            islands = shared_bundle.get("islands_raw")

            if islands is not None:
                islands = islands[islands.geometry.notnull()]

                if len(islands) > 0:
                    islands_p = islands.to_crs(ref_crs)

                    islands_p = gpd.clip(
                        islands_p,
                        gpd.GeoSeries([clip_rect_local], crs=ref_crs),
                    )

                    islands_p = islands_p[~islands_p.is_empty]
                    islands_p = islands_p[
                        islands_p.geom_type.isin(["Polygon", "MultiPolygon"])
                    ]

        # The coastline-derived sea polygon is built from road density alone, so
        # low-traffic islands (parks, pedestrian-only islets) can end up fully
        # inside it instead of forming their own hole. Punch known islands out
        # explicitly so buildings/greens on them survive the water mask below.
        if coast_water is not None and len(coast_water) > 0 and len(islands_p) > 0:
            island_union = unary_union(islands_p.geometry)
            coast_water = coast_water.copy()
            coast_water["geometry"] = coast_water.geometry.apply(
                lambda g: g.difference(island_union) if g is not None else g
            )
            coast_water = coast_water[
                (~coast_water.is_empty) & coast_water.geometry.notnull()
            ]

        return {
            "edges_p": edges_p,
            "gdf_all_p": gdf_all_p,
            "trees_p": trees_p,
            "green_p": green_p,
            "waterway_p": waterway_p,
            "railway_p": railway_p,
            "paths_p": paths_p,
            "water_structures_p": water_structures_p,
            "pier_areas_p": pier_areas_p,
            "coast_water": coast_water,
            "islands_p": islands_p,
            "bounds": (minx, maxx, miny, maxy),
            "ref_crs": ref_crs,
            "clip_rect_local": clip_rect_local,
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

    edges_p = geometry_data["edges_p"]
    gdf_all_p = geometry_data["gdf_all_p"]
    trees_p = geometry_data["trees_p"]
    green_p = geometry_data["green_p"]
    waterway_p = geometry_data["waterway_p"]
    railway_p = geometry_data["railway_p"]
    paths_p = geometry_data["paths_p"]
    water_structures_p = geometry_data["water_structures_p"]
    pier_areas_p = geometry_data["pier_areas_p"]
    coast_water = geometry_data["coast_water"]
    islands_p = geometry_data["islands_p"]
    minx, maxx, miny, maxy = geometry_data["bounds"]
    ref_crs = geometry_data["ref_crs"]
    clip_rect_local = geometry_data["clip_rect_local"]

    draw_green_layers = (not render_only_buildings) and (palette_name != "mono_black") and (not hide_vegetation)
    draw_tree_layers = False

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
    tourism = col(gdf_all_p, "tourism")
    aeroway = col(gdf_all_p, "aeroway")
    sport = col(gdf_all_p, "sport")

    # =============================================================================
    # BUILDINGS
    # =============================================================================

    building_mask = False

    if building is not None:
        building_mask = building.notnull()

    if building_part is not None:
        building_mask = building_mask | building_part.notnull()

    if tourism is not None:
        building_mask = building_mask | tourism.isin(["hotel", "motel", "resort", "hostel", "guest_house"])

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
                "park","garden","pitch","sports_centre","stadium","golf_course","nature_reserve",
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
                "wood","scrub","grassland","wetland","heath","fell","beach","sand"
            ]))
            if natural is not None else False
        )

        |

        (
            (sport.isin(["golf"]))
            if sport is not None else False
        )
    ]
    greens_p = greens_p[
        greens_p.geom_type.isin(["Polygon", "MultiPolygon"])
    ]
    if len(green_p) > 0:
        greens_p = gpd.GeoDataFrame(
            geometry=list(greens_p.geometry) + list(green_p.geometry),
            crs=greens_p.crs,
        )
        greens_p = greens_p[~greens_p.is_empty]


    # =============================================================================
    # WATER POLYGONS
    # =============================================================================

    water_col = col(gdf_all_p, "water")
    water_p = gdf_all_p[
        ((natural == "water") if natural is not None else False)
        | (water_col.notnull() if water_col is not None else False)
    ]

    # Merge water_raw for broader coverage (bay, strait, reservoir, canal…).
    _water_raw = shared_bundle.get("water_raw")
    if _water_raw is not None and len(_water_raw) > 0:
        _wr = _water_raw[_water_raw.geometry.notnull()].to_crs(ref_crs)
        _wr = gpd.clip(_wr, gpd.GeoSeries([clip_rect_local], crs=ref_crs))
        _wr = _wr[_wr.geom_type.isin(["Polygon", "MultiPolygon"])]
        if len(_wr) > 0:
            water_p = gpd.GeoDataFrame(
                geometry=list(water_p.geometry) + list(_wr.geometry),
                crs=water_p.crs,
            )

    beach_p = gdf_all_p[
        (natural.isin(["beach", "sand"])) if natural is not None else False
    ]

    squares_p = gdf_all_p[
        ((place == "square") if place is not None else False)
        |
        ((highway == "pedestrian") if highway is not None else False)
    ]
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

    residential_p = gdf_all_p[
        (landuse == "residential") if landuse is not None else False
    ]

    construction_p = gdf_all_p[
        (landuse == "construction") if landuse is not None else False
    ]

    airport_p = gdf_all_p[
        (
            (aeroway.isin(["aerodrome", "apron", "terminal", "helipad"]))
            if aeroway is not None else False
        )
    ]

    runway_p = gdf_all_p[
        (
            (aeroway.isin(["runway", "taxiway"]))
            if aeroway is not None else False
        )
    ]

    # =============================================================================
    # AUTOMATIC RIVER GREEN BELT
    # =============================================================================

    # Disabled: this overlay can create a visible mid-river band artifact.
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

        residential_color = "#314557" if palette_name == "midnight_blue" else "#E2DED5"
        construction_color = style_cfg.construction
        airport_color = "#5A667A" if palette_name == "midnight_blue" else "#D3D6DB"
        runway_color = "#74839B" if palette_name == "midnight_blue" else "#B7BCC4"

        # water
        dissolved_water = None
        water_mask_geom = None
        if len(water_p) > 0:
            water_union = unary_union(water_p.geometry)
            water_union = _fill_polygon_holes(water_union)
            dissolved_water = gpd.GeoDataFrame(
                geometry=[water_union],
                crs=water_p.crs,
            )
            water_mask_geom = water_union
            dissolved_water.plot(
                ax=ax,
                color=style_cfg.water,
                edgecolor="none",
                linewidth=0,
                zorder=1,
            )
            if use_surface_texture:
                _plot_dotted_texture(
                    ax,
                    dissolved_water,
                    spacing_m=10,
                    dot_size=17.0,
                    color="#3F6F8B",
                    alpha=0.72,
                    zorder=1.08,
                    rng=texture_rng,
                )

        # Waterway is used only as a fallback when no water polygons are present.
        # Dissolving avoids inner seams from overlapping buffered centerlines.
        if len(waterway_p) > 0 and dissolved_water is None:
            waterway_union = unary_union(waterway_p.geometry)
            waterway_union = _fill_polygon_holes(waterway_union)
            waterway_fill = gpd.GeoDataFrame(
                geometry=[waterway_union],
                crs=waterway_p.crs,
            )
            waterway_fill = waterway_fill[~waterway_fill.is_empty]
            water_mask_geom = waterway_union
            waterway_fill.plot(
                ax=ax,
                color=style_cfg.water,
                edgecolor="none",
                linewidth=0,
                zorder=1,
            )
            if use_surface_texture:
                _plot_dotted_texture(
                    ax,
                    waterway_fill,
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
                edgecolor="none",
                linewidth=0,
                zorder=0,
            )
            coast_union = unary_union(coast_water.geometry)
            water_mask_geom = coast_union if water_mask_geom is None else unary_union([water_mask_geom, coast_union])
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

        # islands in rivers/water
        if len(islands_p) > 0:
            islands_p.plot(
                ax=ax,
                color=style_cfg.background,
                edgecolor="none",
                linewidth=0,
                zorder=1.5,
            )

        if len(beach_p) > 0:
            beach_p = _mask_out_water(beach_p, water_mask_geom)
            beach_p.plot(
                ax=ax,
                color=beach_color,
                edgecolor=beach_edge,
                linewidth=0.06 if palette_name == "arctic_blue" else 0,
                zorder=1.7,
            )

        if len(squares_p) > 0:
            squares_p = _mask_out_water(squares_p, water_mask_geom)
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

        if len(pier_areas_p) > 0 and not hide_lines_on_water:
            pier_color = _bridge_color_for_style(
                palette_name,
                style_cfg.road,
                style_cfg.water,
            )
            pier_areas_p.plot(
                ax=ax,
                color=pier_color,
                edgecolor="none",
                alpha=0.94,
                zorder=1.96,
            )

        # greens
        if draw_green_layers and len (greens_p) > 0:
            greens_p = _mask_out_water(greens_p, water_mask_geom)
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
                if hide_lines_on_water:
                    paths_to_plot = _mask_out_water(paths_to_plot, water_mask_geom)
                paths_to_plot.plot (
                    ax=ax,
                    color=path_color,
                    linewidth=path_width,
                    alpha=path_alpha,
                    zorder=path_zorder,
                )

        # Water-edge structures: pier / quay / groyne
        if len(water_structures_p) > 0 and not hide_lines_on_water:
            structure_color = _bridge_color_for_style(
                palette_name,
                style_cfg.road,
                style_cfg.water,
            )
            structure_width = 1.1
            structure_alpha = 0.88
            structure_zorder = 9

            structure_lines = water_structures_p[
                water_structures_p.geom_type.isin(["LineString", "MultiLineString"])
            ]
            structure_polys = water_structures_p[
                water_structures_p.geom_type.isin(["Polygon", "MultiPolygon"])
            ]
            structure_polys = structure_polys[
                ~structure_polys.index.isin(pier_areas_p.index)
            ]

            if "man_made" in structure_lines.columns:
                structure_lines = structure_lines.copy()
                breakwater_lines = structure_lines[
                    structure_lines["man_made"].fillna("").astype(str).str.lower().eq("breakwater")
                ]
                other_structure_lines = structure_lines[
                    ~structure_lines.index.isin(breakwater_lines.index)
                ]
            else:
                breakwater_lines = structure_lines.iloc[0:0]
                other_structure_lines = structure_lines

            if len(structure_polys) > 0:
                structure_polys.plot(
                    ax=ax,
                    color=structure_color,
                    edgecolor="none",
                    alpha=min(structure_alpha + 0.06, 1.0),
                    zorder=structure_zorder,
                )

            if len(other_structure_lines) > 0:
                other_structure_lines.plot(
                    ax=ax,
                    color=structure_color,
                    linewidth=structure_width,
                    alpha=structure_alpha,
                    zorder=structure_zorder,
                )

            if len(breakwater_lines) > 0:
                breakwater_lines.plot(
                    ax=ax,
                    color=structure_color,
                    linewidth=max(structure_width * 1.6, 1.8),
                    alpha=min(structure_alpha + 0.08, 1.0),
                    zorder=structure_zorder + 0.1,
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
            cemetery_p = _mask_out_water(cemetery_p, water_mask_geom)
            cemetery_p.plot (
                ax=ax,
                color=style_cfg.green,
                edgecolor=style_cfg.green_edge,
                linewidth=style_cfg.green_edge_width,
                zorder=2,
            )

        if len(parking_p) > 0:
            parking_p = _mask_out_water(parking_p, water_mask_geom)
            parking_p.plot(ax=ax, color=parking_color, edgecolor="none", zorder=3)

        if len(industrial_p) > 0:
            industrial_p = _mask_out_water(industrial_p, water_mask_geom)
            industrial_p.plot(ax=ax, color=industrial_color, edgecolor="none", zorder=3)

        if len(residential_p) > 0:
            residential_p = _mask_out_water(residential_p, water_mask_geom)
            residential_p.plot(ax=ax, color=residential_color, edgecolor="none", alpha=0.42, zorder=1.85)

        if len(construction_p) > 0:
            construction_p = _mask_out_water(construction_p, water_mask_geom)
            construction_p.plot(ax=ax, color=construction_color, edgecolor="none", alpha=0.75, zorder=3.05)

        if len(airport_p) > 0:
            airport_p = _mask_out_water(airport_p, water_mask_geom)
            airport_p.plot(ax=ax, color=airport_color, edgecolor="none", alpha=0.72, zorder=3.1)

        if len(runway_p) > 0:
            runway_p = _mask_out_water(runway_p, water_mask_geom)
            runway_p.plot(ax=ax, color=runway_color, edgecolor="none", alpha=0.8, zorder=3.15)

    # buildings
    if len(buildings_p) > 0:
        buildings_p = _mask_out_water(buildings_p, water_mask_geom if 'water_mask_geom' in locals() else None)

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

    if all_objects_mode:
        fallback_poly = gdf_all_p[gdf_all_p.geom_type.isin(["Polygon", "MultiPolygon"])]
        fallback_line = gdf_all_p[gdf_all_p.geom_type.isin(["LineString", "MultiLineString"])]
        fallback_point = gdf_all_p[gdf_all_p.geom_type.isin(["Point", "MultiPoint"])]

        if len(fallback_poly) > 0:
            fallback_poly.plot(
                ax=ax,
                color="#2F4359" if palette_name == "midnight_blue" else style_cfg.building_colors[0],
                edgecolor="none",
                linewidth=0,
                alpha=0.28,
                zorder=4.6,
            )

        if len(fallback_line) > 0:
            if hide_lines_on_water:
                fallback_line = _mask_out_water(fallback_line, water_mask_geom if 'water_mask_geom' in locals() else None)
            fallback_line.plot(
                ax=ax,
                color="#AFC4DA" if palette_name == "midnight_blue" else style_cfg.road,
                linewidth=0.75,
                alpha=0.85,
                zorder=11.8,
            )

        if len(fallback_point) > 0:
            fallback_point.plot(
                ax=ax,
                color="#D0DEEC" if palette_name == "midnight_blue" else style_cfg.road,
                markersize=2.8,
                marker="o",
                alpha=0.8,
                zorder=12.2,
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

    # railway (always visible for building renders when available)
    if (not render_only_buildings) and len(railway_p) > 0:
        if hide_lines_on_water:
            railway_p = _mask_out_water(railway_p, water_mask_geom if 'water_mask_geom' in locals() else None)
        rail_color = "#555555"
        rail_width = 1.2
        rail_alpha = 0.9

        railway_p.plot(
            ax=ax,
            color=rail_color,
            linewidth=rail_width,
            alpha=rail_alpha,
            zorder=11,
        )

    # Draw bridges on top of water/buildings with style-specific contrast colors.
    if "bridge" in edges_p.columns:
        bridges = edges_p[edges_p["bridge"].apply(_is_bridge_value)]
    else:
        bridges = edges_p.iloc[0:0]

    if len(bridges) > 0:
        road_width_base = style_cfg.road_style.base_width
        multipliers = style_cfg.road_style.multipliers
        bridge_color = _bridge_color_for_style(palette_name, style_cfg.road, style_cfg.water)

        for cls, mult in multipliers.items():
            bridge_subset = bridges[bridges["road_class"] == cls]
            if len(bridge_subset) == 0:
                continue
            bridge_subset.plot(
                ax=ax,
                color=bridge_color,
                linewidth=(road_width_base * mult) * 1.15,
                capstyle="round",
                joinstyle="round",
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