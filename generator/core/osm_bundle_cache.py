from __future__ import annotations

import math
import os
import time
from itertools import count
from pathlib import Path

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

# Mirrors _ROAD_CUSTOM_FILTER for post-filtering edges from graph_from_xml,
# which has no custom_filter argument (unlike graph_from_point).
_ALLOWED_ROAD_HIGHWAYS = {
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
    "secondary", "secondary_link", "tertiary", "tertiary_link", "residential",
    "unclassified", "living_street", "service", "pedestrian", "footway", "path", "steps",
}

# Default Overpass endpoints used for round-robin rotation.
OVERPASS_URLS = [
    "https://overpass-api.de/api",
]

_ENDPOINT_ROTATION_COUNTER = count()


def _highway_tag_matches(value, allowed: set[str] = _ALLOWED_ROAD_HIGHWAYS) -> bool:
    values = value if isinstance(value, (list, tuple, set)) else [value]
    normalized = {str(v).strip().lower() for v in values if v is not None and str(v).strip()}
    return any(v in normalized for v in allowed)


def _local_osm_file_path() -> "Path | None":
    """Return the local OSM XML path when local mode is active, else None.

    Local mode is enabled via OSM_SOURCE=local + OSM_LOCAL_FILE=<path>. When
    active, no Overpass network calls are made — all data is read from disk.
    """
    if os.getenv("OSM_SOURCE", "").strip().lower() != "local":
        return None
    local_file = os.getenv("OSM_LOCAL_FILE", "").strip()
    if not local_file:
        return None
    path = Path(local_file)
    if not path.is_file():
        raise FileNotFoundError(f"OSM_LOCAL_FILE not found: {path}")
    return path


def _fetch_features(
    tags: dict,
    query_label: str,
    *,
    local_file: "Path | None",
    center_lat: float,
    center_lon: float,
    dist_m: int,
):
    """Fetch OSM features either from a local XML file or via Overpass."""
    if local_file is not None:
        return ox.features_from_xml(local_file, tags=tags)
    return _run_with_overpass_fallback(
        lambda: ox.features_from_point((center_lat, center_lon), tags=tags, dist=dist_m),
        query_label,
    )


def _get_overpass_endpoints() -> list[str]:
    endpoints_env = os.getenv("OSM_OVERPASS_ENDPOINTS", "").strip()
    if endpoints_env:
        return [e.strip() for e in endpoints_env.split(",") if e.strip()]
    return OVERPASS_URLS


def _rotated_endpoints(endpoints: list[str]) -> list[str]:
    if not endpoints:
        return []
    start_idx = next(_ENDPOINT_ROTATION_COUNTER) % len(endpoints)
    return endpoints[start_idx:] + endpoints[:start_idx]


def _run_with_overpass_fallback(query_func, query_label: str):
    endpoints = _rotated_endpoints(_get_overpass_endpoints())
    if not endpoints:
        raise RuntimeError("No Overpass endpoints configured. Set OSM_OVERPASS_ENDPOINTS or OVERPASS_URLS.")

    original_overpass_url = ox.settings.overpass_url
    last_error = None

    for endpoint in endpoints:
        try:
            ox.settings.overpass_url = endpoint
            result = query_func()
            ox.settings.overpass_url = original_overpass_url
            return result
        except Exception as error:
            last_error = error
            print(f"[OSM] {query_label} failed via {endpoint}: {error}")
            time.sleep(0.8)
            continue

    ox.settings.overpass_url = original_overpass_url
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"[OSM] {query_label} failed without a captured exception")


def _build_shared_osm_bundle(
    *,
    center_lat: float,
    center_lon: float,
    half_width_m: float,
    half_height_m: float,
    include_building_features: bool = True,
) -> dict[str, object]:
    dist_m = int(math.ceil(math.sqrt(half_width_m**2 + half_height_m**2))) + 300

    local_file = _local_osm_file_path()
    if local_file is not None:
        print(f"[OSM] Local mode: reading {local_file.name} (no Overpass calls)")
        graph = ox.graph_from_xml(local_file, simplify=True)
    else:
        graph = ox.graph_from_point(
            (center_lat, center_lon),
            dist=dist_m,
            custom_filter=_ROAD_CUSTOM_FILTER,
            simplify=True,
        )

    edges_raw = ox.graph_to_gdfs(graph, nodes=False, edges=True)

    if local_file is not None and "highway" in edges_raw.columns:
        # graph_from_xml has no custom_filter; replicate _ROAD_CUSTOM_FILTER here.
        edges_raw = edges_raw[edges_raw["highway"].apply(_highway_tag_matches)]

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
                "construction",
                "brownfield",
                "basin",
                "reservoir",
                "industrial",
                "commercial",
                "retail",
                "port",
                "dock",
                "education",
                "allotments",
                "garden",
                "cemetery",
                "farmland",
                "orchard",
            ],
            "man_made": [
                "pier",
                "quay",
                "breakwater",
                "jetty",
                "groyne",
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
            "sport": ["golf"],
            "water": True,
            "waterway": True,
            "railway": True,
            "amenity": ["parking", "grave_yard", "school", "college", "university"],
            "place": ["square", "island", "islet"],
            "highway": ["pedestrian", "footway", "path", "track", "steps"],
            "tourism": ["hotel", "motel", "resort", "hostel", "guest_house"],
            "aeroway": ["aerodrome", "apron", "terminal", "helipad", "runway", "taxiway"],
        }

        gdf_all_raw = _fetch_features(
            feature_tags,
            "features_from_point:feature_tags",
            local_file=local_file, center_lat=center_lat, center_lon=center_lon, dist_m=dist_m,
        )

        trees_raw = _fetch_features(
            {"natural": "tree"},
            "features_from_point:trees",
            local_file=local_file, center_lat=center_lat, center_lon=center_lon, dist_m=dist_m,
        )

        waterway_raw = _fetch_features(
            {"waterway": True},
            "features_from_point:waterway",
            local_file=local_file, center_lat=center_lat, center_lon=center_lon, dist_m=dist_m,
        )

        railway_raw = _fetch_features(
            {"railway": True},
            "features_from_point:railway",
            local_file=local_file, center_lat=center_lat, center_lon=center_lon, dist_m=dist_m,
        )

        paths_raw = _fetch_features(
            {"highway": ["footway", "path", "track", "steps"]},
            "features_from_point:paths",
            local_file=local_file, center_lat=center_lat, center_lon=center_lon, dist_m=dist_m,
        )

    water_raw = _fetch_features(
        {
            "natural": ["water", "bay", "strait"],
            "water": True,
            "waterway": ["riverbank", "canal"],
            "landuse": ["basin", "reservoir"],
        },
        "features_from_point:water",
        local_file=local_file, center_lat=center_lat, center_lon=center_lon, dist_m=dist_m,
    )

    green_raw = _fetch_features(
        {
            "leisure": ["park", "garden", "nature_reserve", "recreation_ground", "village_green"],
            "landuse": ["forest", "grass", "meadow", "recreation_ground", "village_green"],
            "natural": ["wood", "grassland", "scrub", "heath"],
        },
        "features_from_point:green",
        local_file=local_file, center_lat=center_lat, center_lon=center_lon, dist_m=dist_m,
    )

    try:
        coast_raw = _fetch_features(
            {"natural": "coastline"},
            "features_from_point:coast",
            local_file=local_file, center_lat=center_lat, center_lon=center_lon, dist_m=dist_m,
        )
    except InsufficientResponseError:
        print("[OSM] Nincs tengerpart ezen a területen – coast_raw kihagyva.")
        coast_raw = None

    try:
        islands_raw = _fetch_features(
            {
                "place": ["island", "islet"],
                "natural": "island",
            },
            "features_from_point:islands",
            local_file=local_file, center_lat=center_lat, center_lon=center_lon, dist_m=dist_m,
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
    # Local-file and Overpass data can differ; keep their caches separate.
    local_suffix = "_local" if _local_osm_file_path() is not None else ""
    cache_variant = f"bundle_v2_hw{int(round(half_width_m))}_hh{int(round(half_height_m))}{bld_suffix}{local_suffix}"

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
