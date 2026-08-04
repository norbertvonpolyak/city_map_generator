from __future__ import annotations

import math

import geopandas as gpd
import osmnx as ox
from osmnx._errors import InsufficientResponseError
from shapely.geometry import Point

from generator.core.cache import load_or_build_geometry


_ROAD_CUSTOM_FILTER = (
    '["highway"~"motorway|motorway_link|trunk|trunk_link|primary|primary_link|'
    'secondary|secondary_link|tertiary|tertiary_link|residential|unclassified|living_street|service|'
    'pedestrian|footway|path|steps"]'
)

ox.settings.requests_timeout = 300


def _build_shared_osm_bundle(
    *,
    center_lat: float,
    center_lon: float,
    half_width_m: float,
    half_height_m: float,
    include_building_features: bool = True,
) -> dict[str, object]:
    dist_m = int(math.ceil(math.sqrt(half_width_m**2 + half_height_m**2))) + 300

    graph = ox.graph_from_point(
        (center_lat, center_lon),
        dist=dist_m,
        custom_filter=_ROAD_CUSTOM_FILTER,
        simplify=True,
    )

    edges_raw = ox.graph_to_gdfs(graph, nodes=False, edges=True)

    # Building engine-specific features (only if needed)
    if not include_building_features:
        gdf_all_raw = None
        trees_raw = None
        waterway_raw = None
        railway_raw = None
        paths_raw = None
    else:
        feature_tags = {
            "building": True,
            "building:part": True,
            "landuse": [
                "forest",
                "grass",
                "meadow",
                "recreation_ground",
                "village_green",
                "basin",
                "reservoir",
                "industrial",
                "commercial",
                "retail",
                "education",
                "allotments",
                "garden",
                "cemetery",
                "farmland",
                "orchard",
            ],
            "leisure": [
                "park",
                "garden",
                "pitch",
                "sports_centre",
                "stadium",
                "nature_reserve",
                "playground",
                "dog_park",
                "recreation_ground",
                "village_green",
            ],
            "natural": [
                "water",
                "wood",
                "scrub",
                "grassland",
                "wetland",
                "heath",
                "fell",
                "bay",
                "strait",
                "beach",
                "sand",
                "tree",
                "coastline",
                "island",
            ],
            "water": True,
            "waterway": True,
            "railway": True,
            "amenity": ["parking", "grave_yard", "school", "college", "university"],
            "place": ["square", "island", "islet"],
            "highway": ["pedestrian", "footway", "path", "track", "steps"],
        }

        gdf_all_raw = ox.features_from_point(
            (center_lat, center_lon),
            tags=feature_tags,
            dist=dist_m,
        )

        trees_raw = ox.features_from_point(
            (center_lat, center_lon),
            tags={"natural": "tree"},
            dist=dist_m,
        )

        waterway_raw = ox.features_from_point(
            (center_lat, center_lon),
            tags={"waterway": True},
            dist=dist_m,
        )

        railway_raw = ox.features_from_point(
            (center_lat, center_lon),
            tags={"railway": True},
            dist=dist_m,
        )

        paths_raw = ox.features_from_point(
            (center_lat, center_lon),
            tags={"highway": ["footway", "path", "track", "steps"]},
            dist=dist_m,
        )

    water_raw = ox.features_from_point(
        (center_lat, center_lon),
        tags={
            "natural": ["water", "bay", "strait"],
            "water": True,
            "waterway": ["riverbank", "canal"],
            "landuse": ["basin", "reservoir"],
        },
        dist=dist_m,
    )

    green_raw = ox.features_from_point(
        (center_lat, center_lon),
        tags={
            "leisure": ["park", "garden", "nature_reserve", "recreation_ground", "village_green"],
            "landuse": ["forest", "grass", "meadow", "recreation_ground", "village_green"],
            "natural": ["wood", "grassland", "scrub", "heath"],
        },
        dist=dist_m,
    )

    try:
        coast_raw = ox.features_from_point(
            (center_lat, center_lon),
            tags={"natural": "coastline"},
            dist=dist_m,
        )
    except InsufficientResponseError:
        print("[OSM] Nincs tengerpart ezen a területen – coast_raw kihagyva.")
        coast_raw = None

    try:
        islands_raw = ox.features_from_point(
            (center_lat, center_lon),
            tags={
                "place": ["island", "islet"],
                "natural": "island",
            },
            dist=dist_m,
        )
    except InsufficientResponseError:
        print("[OSM] Nincsenek szigetek ezen a területen – islands_raw kihagyva.")
        islands_raw = None

    return {
        "edges_raw": edges_raw,
        "gdf_all_raw": gdf_all_raw,
        "trees_raw": trees_raw,
        "waterway_raw": waterway_raw,
        "railway_raw": railway_raw,
        "paths_raw": paths_raw,
        "water_raw": water_raw,
        "green_raw": green_raw,
        "coast_raw": coast_raw,
        "islands_raw": islands_raw,
    }


def _find_superset_bundle_cache(
    *,
    center_lat: float,
    center_lon: float,
    extent_m: int,
    half_width_m: float,
    half_height_m: float,
    include_building_features: bool = False,
) -> "Path | None":
    """Return an existing cache file whose viewport fully contains the requested one.

    Any cache built with hw_existing >= half_width_m AND hh_existing >= half_height_m
    covers a superset of the requested area and is safe to reuse.
    """
    import re
    from generator.core.cache import CACHE_DIR

    req_hw = int(round(half_width_m))
    req_hh = int(round(half_height_m))
    bld_suffix = "_bld" if include_building_features else ""
    prefix = (
        f"osm_shared_bundle_"
        f"{center_lat:.6f}_"
        f"{center_lon:.6f}_"
        f"{extent_m}_bundle_v1_hw"
    )
    pattern = re.compile(rf"bundle_v1_hw(\d+)_hh(\d+){re.escape(bld_suffix)}\.pkl$")

    best: "Path | None" = None
    best_area = -1
    for path in CACHE_DIR.glob(f"{prefix}*.pkl"):
        m = pattern.search(path.name)
        if not m:
            continue
        ex_hw, ex_hh = int(m.group(1)), int(m.group(2))
        if ex_hw >= req_hw and ex_hh >= req_hh:
            area = ex_hw * ex_hh
            if best is None or area < best_area:  # prefer smallest superset
                best, best_area = path, area
    return best


def load_or_build_shared_osm_bundle(
    *,
    center_lat: float,
    center_lon: float,
    extent_m: int,
    half_width_m: float,
    half_height_m: float,
    use_cache: bool = True,
    include_building_features: bool = False,
) -> dict[str, object]:
    bld_suffix = "_bld" if include_building_features else ""
    cache_variant = f"bundle_v1_hw{int(round(half_width_m))}_hh{int(round(half_height_m))}{bld_suffix}"

    if not use_cache:
        return _build_shared_osm_bundle(
            center_lat=center_lat,
            center_lon=center_lon,
            half_width_m=half_width_m,
            half_height_m=half_height_m,
            include_building_features=include_building_features,
        )

    # Before building a new cache, check if an existing larger cache can be reused.
    from generator.core.cache import CACHE_DIR
    import pickle
    exact_path = CACHE_DIR / (
        f"osm_shared_bundle_"
        f"{center_lat:.6f}_"
        f"{center_lon:.6f}_"
        f"{extent_m}_"
        f"{cache_variant}.pkl"
    )
    if not exact_path.exists():
        superset = _find_superset_bundle_cache(
            center_lat=center_lat,
            center_lon=center_lon,
            extent_m=extent_m,
            half_width_m=half_width_m,
            half_height_m=half_height_m,
            include_building_features=include_building_features,
        )
        if superset is not None:
            from time import perf_counter
            started = perf_counter()
            with open(superset, "rb") as f:
                data = pickle.load(f)
            elapsed = perf_counter() - started
            print(f"[CACHE] Reusing superset bundle: {superset.name} ({elapsed:.2f}s)")
            return data

    return load_or_build_geometry(
        cache_prefix="osm_shared_bundle",
        center_lat=center_lat,
        center_lon=center_lon,
        extent_m=extent_m,
        cache_variant=cache_variant,
        builder_func=lambda: _build_shared_osm_bundle(
            center_lat=center_lat,
            center_lon=center_lon,
            half_width_m=half_width_m,
            half_height_m=half_height_m,
            include_building_features=include_building_features,
        ),
    )
