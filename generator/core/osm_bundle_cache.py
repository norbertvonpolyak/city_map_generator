from __future__ import annotations

import math
import os
import pickle
import hashlib
import json
import time
from itertools import count
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import osmnx as ox
from osmnx._errors import InsufficientResponseError
from shapely.geometry import Point

try:
    from requests.exceptions import (
        ConnectTimeout as RequestsConnectTimeout,
        ConnectionError as RequestsConnectionError,
        HTTPError as RequestsHTTPError,
        ProxyError as RequestsProxyError,
        ReadTimeout as RequestsReadTimeout,
        Timeout as RequestsTimeout,
    )

    _REQUESTS_NETWORK_EXCEPTIONS: tuple[type[BaseException], ...] = (
        RequestsConnectTimeout,
        RequestsReadTimeout,
        RequestsTimeout,
        RequestsConnectionError,
        RequestsProxyError,
    )
    _REQUESTS_HTTP_ERROR = RequestsHTTPError
except Exception:
    _REQUESTS_NETWORK_EXCEPTIONS = ()
    _REQUESTS_HTTP_ERROR = ()

from generator.core.cache import load_or_build_geometry


_ROAD_CUSTOM_FILTER = (
    '["highway"~"motorway|motorway_link|trunk|trunk_link|primary|primary_link|'
    'secondary|secondary_link|tertiary|tertiary_link|residential|unclassified|living_street|service|'
    'pedestrian|footway|path|steps"]'
)

# Default Overpass endpoints used for round-robin rotation.
OVERPASS_URLS = [
    "https://overpass-api.de/api",
]

_ENDPOINT_ROTATION_COUNTER = count()

_ROAD_CACHE_VERSION = "v1"
_LAYER_CACHE_VERSION = "v1"


_FEATURE_TAGS_BUILDINGS = {
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


_FEATURE_LAYER_SPECS: dict[str, dict[str, object]] = {
    "buildings": {
        "query_label": "features_from_point:feature_tags",
        "tags": _FEATURE_TAGS_BUILDINGS,
        "missing_message": None,
    },
    "trees": {
        "query_label": "features_from_point:trees",
        "tags": {"natural": "tree"},
        "missing_message": None,
    },
    "waterway": {
        "query_label": "features_from_point:waterway",
        "tags": {"waterway": True},
        "missing_message": None,
    },
    "railway": {
        "query_label": "features_from_point:railway",
        "tags": {"railway": True},
        "missing_message": None,
    },
    "paths": {
        "query_label": "features_from_point:paths",
        "tags": {"highway": ["footway", "path", "track", "steps"]},
        "missing_message": None,
    },
    "water": {
        "query_label": "features_from_point:water",
        "tags": {
            "natural": ["water", "bay", "strait"],
            "water": True,
            "waterway": ["riverbank", "canal"],
            "landuse": ["basin", "reservoir"],
        },
        "missing_message": None,
    },
    "green": {
        "query_label": "features_from_point:green",
        "tags": {
            "leisure": ["park", "garden", "nature_reserve", "recreation_ground", "village_green"],
            "landuse": ["forest", "grass", "meadow", "recreation_ground", "village_green"],
            "natural": ["wood", "grassland", "scrub", "heath"],
        },
        "missing_message": None,
    },
    "coast": {
        "query_label": "features_from_point:coast",
        "tags": {"natural": "coastline"},
        "missing_message": "[OSM] Nincs tengerpart ezen a területen – coast_raw kihagyva.",
    },
    "islands": {
        "query_label": "features_from_point:islands",
        "tags": {
            "place": ["island", "islet"],
            "natural": "island",
        },
        "missing_message": "[OSM] Nincsenek szigetek ezen a területen – islands_raw kihagyva.",
    },
}


def _overpass_debug_enabled() -> bool:
    return os.getenv("OVERPASS_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _fmt_ts(epoch_s: float) -> str:
    return datetime.fromtimestamp(epoch_s).strftime("%Y-%m-%d %H:%M:%S")


def _fmt_bytes(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "n/a"
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def _estimate_memory_bytes(result) -> int | None:
    try:
        if hasattr(result, "memory_usage"):
            usage = result.memory_usage(deep=True)
            if hasattr(usage, "sum"):
                return int(usage.sum())
    except Exception:
        return None
    return None


def _estimate_pickle_bytes(result) -> int | None:
    try:
        payload = pickle.dumps(result)
        return int(len(payload))
    except Exception:
        return None


def _estimate_object_count(result) -> int | None:
    try:
        return int(len(result))
    except Exception:
        return None


def _extract_result_metrics(result) -> dict[str, int | None]:
    metrics: dict[str, int | None] = {}

    if isinstance(result, gpd.GeoDataFrame):
        metrics["object_count"] = int(len(result))
        metrics["features"] = int(len(result))
        metrics["memory_bytes"] = _estimate_memory_bytes(result)
        metrics["pickle_bytes"] = _estimate_pickle_bytes(result)
        return metrics

    if hasattr(result, "number_of_nodes") and hasattr(result, "number_of_edges"):
        try:
            metrics["nodes"] = int(result.number_of_nodes())
            metrics["edges"] = int(result.number_of_edges())
            metrics["object_count"] = int(metrics["nodes"] + metrics["edges"])
        except Exception:
            metrics["nodes"] = None
            metrics["edges"] = None
            metrics["object_count"] = None
        metrics["memory_bytes"] = _estimate_memory_bytes(result)
        metrics["pickle_bytes"] = _estimate_pickle_bytes(result)
        return metrics

    metrics["object_count"] = _estimate_object_count(result)
    metrics["memory_bytes"] = _estimate_memory_bytes(result)
    metrics["pickle_bytes"] = _estimate_pickle_bytes(result)
    return metrics


def _format_metrics_inline(metrics: dict[str, int | None]) -> str:
    parts: list[str] = []

    if "object_count" in metrics and metrics["object_count"] is not None:
        parts.append(f"objects={metrics['object_count']}")

    if "features" in metrics and metrics["features"] is not None:
        parts.append(f"features={metrics['features']}")
    elif "nodes" in metrics and "edges" in metrics:
        if metrics.get("nodes") is not None:
            parts.append(f"nodes={metrics['nodes']}")
        if metrics.get("edges") is not None:
            parts.append(f"edges={metrics['edges']}")

    if "memory_bytes" in metrics:
        parts.append(f"mem={_fmt_bytes(metrics['memory_bytes'])}")

    if "pickle_bytes" in metrics:
        parts.append(f"pickle={_fmt_bytes(metrics['pickle_bytes'])}")

    return " ".join(parts)


def _summary_label(query_label: str) -> str:
    if query_label.startswith("features_from_point:"):
        return query_label.split(":", 1)[1]
    return query_label


def _metric_for_sort(metrics: dict[str, int | None], key: str) -> int:
    value = metrics.get(key)
    if isinstance(value, int):
        return value
    return -1


def _print_overpass_summary(summary_rows: dict[str, dict[str, object]]) -> None:
    print("========== OVERPASS SUMMARY ==========")

    if not summary_rows:
        print("(no overpass diagnostics captured)")
        print("======================================")
        return

    rows = sorted(
        summary_rows.values(),
        key=lambda row: float(row.get("elapsed_s", 0.0)),
        reverse=True,
    )

    for row in rows:
        query_label = str(row.get("query_label", "unknown"))
        display_label = _summary_label(query_label)
        elapsed_s = float(row.get("elapsed_s", 0.0))
        status = str(row.get("status", "UNKNOWN"))
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        exception_name = row.get("exception_name")

        if status == "FAILED":
            detail = "FAILED"
            if exception_name:
                detail = f"FAILED ({exception_name})"
        else:
            detail = _format_metrics_inline(metrics) if isinstance(metrics, dict) else ""

        print(f"{display_label:<18} {elapsed_s:>7.1f}s   {detail}".rstrip())

    print("======================================")


def _print_osm_cache_profile(summary_rows: dict[str, dict[str, object]]) -> None:
    print("========== OSM CACHE PROFILE ==========")

    rows = []
    for row in summary_rows.values():
        if str(row.get("status", "")) != "DONE":
            continue
        metrics = row.get("metrics")
        if not isinstance(metrics, dict):
            continue
        rows.append({
            "query_label": str(row.get("query_label", "unknown")),
            "metrics": metrics,
        })

    if not rows:
        print("(no successful measurable layers)")
        print("=======================================")
        return

    rows.sort(
        key=lambda row: (
            _metric_for_sort(row["metrics"], "pickle_bytes"),
            _metric_for_sort(row["metrics"], "memory_bytes"),
        ),
        reverse=True,
    )

    total_pickle = 0
    total_memory = 0

    for row in rows:
        label = _summary_label(row["query_label"])
        metrics = row["metrics"]
        print("")
        print(f"{label}")

        if metrics.get("features") is not None:
            print(f"  features={metrics['features']}")
        elif metrics.get("nodes") is not None or metrics.get("edges") is not None:
            nodes = metrics.get("nodes")
            edges = metrics.get("edges")
            print(f"  nodes={nodes if nodes is not None else 'n/a'}")
            print(f"  edges={edges if edges is not None else 'n/a'}")
        elif metrics.get("object_count") is not None:
            print(f"  objects={metrics['object_count']}")
        else:
            print("  objects=n/a")

        memory_bytes = metrics.get("memory_bytes")
        pickle_bytes = metrics.get("pickle_bytes")

        print(f"  mem={_fmt_bytes(memory_bytes)}")
        print(f"  pickle={_fmt_bytes(pickle_bytes)}")

        if isinstance(memory_bytes, int):
            total_memory += memory_bytes
        if isinstance(pickle_bytes, int):
            total_pickle += pickle_bytes

    print("")
    print("=======================================")
    print("")
    print(f"TOTAL pickle size: {_fmt_bytes(total_pickle)}")
    print(f"TOTAL memory:      {_fmt_bytes(total_memory)}")
    print("")
    print("Top 5 cache contributors")

    top_rows = rows[:5]
    for idx, row in enumerate(top_rows, start=1):
        label = _summary_label(row["query_label"])
        pickle_bytes = row["metrics"].get("pickle_bytes")
        print(f"{idx}. {label:<14} {_fmt_bytes(pickle_bytes)}")


def _bundle_usage_sets() -> dict[str, set[str]]:
    # Current engine-level shared bundle consumption map.
    return {
        "Block": {"edges_raw", "water_raw", "coast_raw", "islands_raw"},
        "Building": {
            "edges_raw",
            "gdf_all_raw",
            "trees_raw",
            "waterway_raw",
            "railway_raw",
            "paths_raw",
            "coast_raw",
        },
        "Line": {"edges_raw", "water_raw", "green_raw"},
    }


def _print_bundle_profile(bundle: dict[str, object]) -> None:
    print("========== BUNDLE PROFILE ==========")

    entries: list[dict[str, object]] = []
    measured_sum = 0

    for key, value in bundle.items():
        size_bytes = _estimate_pickle_bytes(value)
        if isinstance(size_bytes, int):
            measured_sum += size_bytes
        entries.append({
            "key": key,
            "value": value,
            "pickle_bytes": size_bytes,
        })

    entries.sort(
        key=lambda e: (e["pickle_bytes"] if isinstance(e["pickle_bytes"], int) else -1),
        reverse=True,
    )

    for entry in entries:
        key = str(entry["key"])
        size_bytes = entry["pickle_bytes"]

        if isinstance(size_bytes, int):
            percent = ""
            if measured_sum > 0:
                percent = f" ({(100.0 * size_bytes / measured_sum):.0f}%)"
            print(f"{key:<15} {_fmt_bytes(size_bytes):>10}{percent}")
        else:
            print(f"{key:<15} {'n/a':>10}")

    total_bundle_bytes = _estimate_pickle_bytes(bundle)
    print("-----------------------------------")
    print(f"TOTAL bundle: {_fmt_bytes(total_bundle_bytes)}")
    print("===================================")

    print("========== OPTIMIZATION HINTS ==========")

    key_to_entry = {str(e["key"]): e for e in entries}
    usage_sets = _bundle_usage_sets()

    for engine_name, used_keys in usage_sets.items():
        print("")
        print(f"Unused in {engine_name}:")

        unused: list[tuple[str, int]] = []
        for key, entry in key_to_entry.items():
            if key in used_keys:
                continue
            value = entry["value"]
            size_bytes = entry["pickle_bytes"]
            if value is None:
                continue
            if isinstance(size_bytes, int) and size_bytes > 0:
                unused.append((key, size_bytes))

        unused.sort(key=lambda item: item[1], reverse=True)

        if not unused:
            print("  (none)")
            continue

        for key, size_bytes in unused:
            print(f"  {key} ({_fmt_bytes(size_bytes)})")

    print("")
    print("Largest contributors:")

    top_entries = [
        e for e in entries
        if isinstance(e["pickle_bytes"], int) and e["value"] is not None
    ][:5]

    if not top_entries:
        print("  (none)")
    else:
        for idx, entry in enumerate(top_entries, start=1):
            print(f"  {idx}. {entry['key']:<15} {_fmt_bytes(entry['pickle_bytes'])}")

    print("=======================================")


def _stable_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()[:12]


def _road_filter_hash() -> str:
    return hashlib.sha1(_ROAD_CUSTOM_FILTER.encode("utf-8")).hexdigest()[:12]


def _bool_to_flag(value: bool) -> str:
    return "1" if value else "0"


def _cache_dir() -> Path:
    from generator.core.cache import CACHE_DIR

    return CACHE_DIR


def _build_road_graph_cache_filename(
    *,
    center_lat: float,
    center_lon: float,
    dist_m: int,
    simplify: bool,
    cache_version: str = _ROAD_CACHE_VERSION,
) -> str:
    return (
        f"osm_road_graph_"
        f"{center_lat:.6f}_"
        f"{center_lon:.6f}_"
        f"rf{_road_filter_hash()}_"
        f"s{_bool_to_flag(simplify)}_"
        f"{cache_version}_"
        f"d{int(dist_m)}.pkl"
    )


def _build_feature_layer_cache_filename(
    *,
    layer_name: str,
    center_lat: float,
    center_lon: float,
    dist_m: int,
    tags: dict[str, object],
    cache_version: str = _LAYER_CACHE_VERSION,
) -> str:
    return (
        f"osm_feature_layer_"
        f"{layer_name}_"
        f"{center_lat:.6f}_"
        f"{center_lon:.6f}_"
        f"d{int(dist_m)}_"
        f"qh{_stable_hash(tags)}_"
        f"{cache_version}.pkl"
    )


def _road_graph_group_prefix(
    *,
    center_lat: float,
    center_lon: float,
    simplify: bool,
    cache_version: str = _ROAD_CACHE_VERSION,
) -> str:
    return (
        f"osm_road_graph_"
        f"{center_lat:.6f}_"
        f"{center_lon:.6f}_"
        f"rf{_road_filter_hash()}_"
        f"s{_bool_to_flag(simplify)}_"
        f"{cache_version}_"
    )


def _read_pickle(path: Path):
    with open(path, "rb") as f:
        return pickle.load(f)


def _write_pickle(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(payload, f)


def _find_best_road_graph_superset(
    *,
    center_lat: float,
    center_lon: float,
    requested_dist_m: int,
    simplify: bool,
    cache_version: str = _ROAD_CACHE_VERSION,
) -> "Path | None":
    import re

    prefix = _road_graph_group_prefix(
        center_lat=center_lat,
        center_lon=center_lon,
        simplify=simplify,
        cache_version=cache_version,
    )

    pattern = re.compile(r"_d(\d+)\.pkl$")
    best_path: "Path | None" = None
    best_dist = None

    for candidate in _cache_dir().glob(f"{prefix}d*.pkl"):
        match = pattern.search(candidate.name)
        if not match:
            continue
        candidate_dist = int(match.group(1))
        if candidate_dist < requested_dist_m:
            continue
        if best_path is None or candidate_dist < best_dist:
            best_path = candidate
            best_dist = candidate_dist

    return best_path


def _select_required_feature_layers(include_building_features: bool) -> list[str]:
    shared_layers = ["water", "green", "coast", "islands"]
    if include_building_features:
        return ["buildings", "trees", "waterway", "railway", "paths", *shared_layers]
    return shared_layers


def _init_cache_stats() -> dict[str, object]:
    return {
        "road": {"hit": 0, "miss": 0, "build": 0},
        "layers": {},
        "bundle_assemble_s": 0.0,
    }


def _bump_cache_stat(cache_stats: dict[str, object], cache_scope: str, cache_name: str, stat_name: str) -> None:
    if cache_scope == "road":
        road = cache_stats["road"]
        if isinstance(road, dict):
            road[stat_name] = int(road.get(stat_name, 0)) + 1
        return

    layers = cache_stats.get("layers")
    if not isinstance(layers, dict):
        return

    layer_stats = layers.setdefault(cache_name, {"hit": 0, "miss": 0, "build": 0})
    if isinstance(layer_stats, dict):
        layer_stats[stat_name] = int(layer_stats.get(stat_name, 0)) + 1


def _print_cache_runtime_stats(cache_stats: dict[str, object], overpass_calls: int) -> None:
    print("========== CACHE RUNTIME STATS ==========")

    road = cache_stats.get("road", {})
    if isinstance(road, dict):
        print(
            "Road Graph Cache "
            f"HIT={int(road.get('hit', 0))} "
            f"MISS={int(road.get('miss', 0))} "
            f"BUILD={int(road.get('build', 0))}"
        )

    layers = cache_stats.get("layers", {})
    if isinstance(layers, dict):
        for layer_name in sorted(layers.keys()):
            layer_stats = layers[layer_name]
            if not isinstance(layer_stats, dict):
                continue
            print(
                f"Layer Cache [{layer_name}] "
                f"HIT={int(layer_stats.get('hit', 0))} "
                f"MISS={int(layer_stats.get('miss', 0))} "
                f"BUILD={int(layer_stats.get('build', 0))}"
            )

    assemble_s = float(cache_stats.get("bundle_assemble_s", 0.0))
    print(f"Bundle assemble elapsed: {assemble_s:.3f}s")
    print(f"Overpass calls this render: {int(overpass_calls)}")
    print("=========================================")


def _empty_layer_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")


def _iter_exception_chain(error: Exception):
    seen: set[int] = set()
    current: Exception | None = error
    while current is not None and id(current) not in seen:
        yield current
        seen.add(id(current))
        next_error = current.__cause__ or current.__context__
        current = next_error if isinstance(next_error, Exception) else None


def _http_status_code(error: Exception) -> int | None:
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    return None


def _is_transient_network_error(error: Exception) -> bool:
    for candidate in _iter_exception_chain(error):
        if _REQUESTS_NETWORK_EXCEPTIONS and isinstance(candidate, _REQUESTS_NETWORK_EXCEPTIONS):
            return True

        if _REQUESTS_HTTP_ERROR and isinstance(candidate, _REQUESTS_HTTP_ERROR):
            status = _http_status_code(candidate)
            if isinstance(status, int) and 500 <= status <= 599:
                return True

        status = _http_status_code(candidate)
        if isinstance(status, int) and 500 <= status <= 599:
            return True

        cls_name = type(candidate).__name__.lower()
        msg = str(candidate).lower()

        if any(
            token in cls_name
            for token in (
                "connecttimeout",
                "readtimeout",
                "timeout",
                "proxyerror",
                "connectionerror",
                "connectionreset",
                "temporaryfailure",
            )
        ):
            return True

        if any(
            token in msg
            for token in (
                "timed out",
                "temporarily unavailable",
                "temporary failure",
                "name or service not known",
                "connection reset",
                "connection aborted",
                "connection refused",
                "proxy error",
                "bad gateway",
                "service unavailable",
                "gateway timeout",
            )
        ):
            return True

    return False


def _load_or_build_road_graph(
    *,
    center_lat: float,
    center_lon: float,
    dist_m: int,
    debug_enabled: bool,
    debug_summary: dict[str, dict[str, object]] | None,
    overpass_call_counter: dict[str, int],
    cache_stats: dict[str, object],
    use_cache: bool,
):
    simplify = True
    exact_name = _build_road_graph_cache_filename(
        center_lat=center_lat,
        center_lon=center_lon,
        dist_m=dist_m,
        simplify=simplify,
    )
    exact_path = _cache_dir() / exact_name

    if use_cache and exact_path.exists():
        _bump_cache_stat(cache_stats, "road", "road", "hit")
        if debug_enabled:
            print(f"[CACHE] Road graph HIT: {exact_path.name}")
        return _read_pickle(exact_path)

    if use_cache:
        superset_path = _find_best_road_graph_superset(
            center_lat=center_lat,
            center_lon=center_lon,
            requested_dist_m=dist_m,
            simplify=simplify,
        )
        if superset_path is not None:
            _bump_cache_stat(cache_stats, "road", "road", "hit")
            if debug_enabled:
                print(f"[CACHE] Road graph HIT (superset): {superset_path.name}")
            return _read_pickle(superset_path)

    _bump_cache_stat(cache_stats, "road", "road", "miss")
    _bump_cache_stat(cache_stats, "road", "road", "build")
    if debug_enabled:
        print(f"[CACHE] Road graph MISS: {exact_path.name}")

    graph = _run_with_overpass_fallback(
        lambda: ox.graph_from_point(
            (center_lat, center_lon),
            dist=dist_m,
            custom_filter=_ROAD_CUSTOM_FILTER,
            simplify=simplify,
        ),
        "graph_from_point",
        debug_enabled=debug_enabled,
        debug_summary=debug_summary,
        overpass_call_counter=overpass_call_counter,
    )
    if use_cache:
        _write_pickle(exact_path, graph)
    return graph


def _load_or_build_feature_layer(
    *,
    layer_name: str,
    center_lat: float,
    center_lon: float,
    dist_m: int,
    debug_enabled: bool,
    debug_summary: dict[str, dict[str, object]] | None,
    overpass_call_counter: dict[str, int],
    cache_stats: dict[str, object],
    use_cache: bool,
):
    layer_spec = _FEATURE_LAYER_SPECS[layer_name]
    tags = layer_spec["tags"]
    query_label = str(layer_spec["query_label"])
    missing_message = layer_spec["missing_message"]

    filename = _build_feature_layer_cache_filename(
        layer_name=layer_name,
        center_lat=center_lat,
        center_lon=center_lon,
        dist_m=dist_m,
        tags=tags,
    )
    cache_path = _cache_dir() / filename

    if use_cache and cache_path.exists():
        _bump_cache_stat(cache_stats, "layer", layer_name, "hit")
        if debug_enabled:
            print(f"[CACHE] Layer HIT [{layer_name}]: {cache_path.name}")
        return _read_pickle(cache_path)

    _bump_cache_stat(cache_stats, "layer", layer_name, "miss")
    _bump_cache_stat(cache_stats, "layer", layer_name, "build")
    if debug_enabled:
        print(f"[CACHE] Layer MISS [{layer_name}]: {cache_path.name}")

    try:
        result = _run_with_overpass_fallback(
            lambda: ox.features_from_point(
                (center_lat, center_lon),
                tags=tags,
                dist=dist_m,
            ),
            query_label,
            debug_enabled=debug_enabled,
            debug_summary=debug_summary,
            overpass_call_counter=overpass_call_counter,
        )
    except InsufficientResponseError:
        if layer_name == "islands":
            result = _empty_layer_gdf()
            print("[CACHE] Layer EMPTY [islands]")
            print("reason=No matching features")
            print("cached=yes")
            if use_cache:
                _write_pickle(cache_path, result)
            return result

        if missing_message:
            print(missing_message)
            result = None
        else:
            raise
    except Exception as error:
        if layer_name == "islands" and _is_transient_network_error(error):
            print("[CACHE] Layer FALLBACK [islands]: temporary empty layer")
            print(f"reason={type(error).__name__}")
            print("not cached")
            return _empty_layer_gdf()
        raise

    if use_cache:
        _write_pickle(cache_path, result)
    return result


def _load_or_build_feature_layers(
    *,
    center_lat: float,
    center_lon: float,
    dist_m: int,
    include_building_features: bool,
    debug_enabled: bool,
    debug_summary: dict[str, dict[str, object]] | None,
    overpass_call_counter: dict[str, int],
    cache_stats: dict[str, object],
    use_cache: bool,
) -> dict[str, object]:
    required_layers = _select_required_feature_layers(include_building_features)
    loaded_layers: dict[str, object] = {}

    for layer_name in required_layers:
        loaded_layers[layer_name] = _load_or_build_feature_layer(
            layer_name=layer_name,
            center_lat=center_lat,
            center_lon=center_lon,
            dist_m=dist_m,
            debug_enabled=debug_enabled,
            debug_summary=debug_summary,
            overpass_call_counter=overpass_call_counter,
            cache_stats=cache_stats,
            use_cache=use_cache,
        )

    return loaded_layers


def _assemble_runtime_bundle(
    *,
    edges_raw,
    feature_layers: dict[str, object],
    include_building_features: bool,
) -> dict[str, object]:
    gdf_all_raw = feature_layers.get("buildings") if include_building_features else None
    trees_raw = feature_layers.get("trees") if include_building_features else None
    waterway_raw = feature_layers.get("waterway") if include_building_features else None
    railway_raw = feature_layers.get("railway") if include_building_features else None
    paths_raw = feature_layers.get("paths") if include_building_features else None

    return {
        "edges_raw": edges_raw,
        "gdf_all_raw": gdf_all_raw,
        "trees_raw": trees_raw,
        "waterway_raw": waterway_raw,
        "railway_raw": railway_raw,
        "paths_raw": paths_raw,
        "water_raw": feature_layers.get("water"),
        "green_raw": feature_layers.get("green"),
        "coast_raw": feature_layers.get("coast"),
        "islands_raw": feature_layers.get("islands"),
    }


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


def _run_with_overpass_fallback(
    query_func,
    query_label: str,
    *,
    debug_enabled: bool = False,
    debug_summary: dict[str, dict[str, object]] | None = None,
    overpass_call_counter: dict[str, int] | None = None,
):
    endpoints = _rotated_endpoints(_get_overpass_endpoints())
    if not endpoints:
        raise RuntimeError("No Overpass endpoints configured. Set OSM_OVERPASS_ENDPOINTS or OVERPASS_URLS.")

    original_overpass_url = ox.settings.overpass_url
    last_error = None

    for endpoint in endpoints:
        started_monotonic = time.perf_counter()
        started_wall = time.time()
        if debug_enabled:
            print(f"[START] {query_label}")
            print(f"        start={_fmt_ts(started_wall)} endpoint={endpoint}")

        try:
            ox.settings.overpass_url = endpoint
            if overpass_call_counter is not None:
                overpass_call_counter["count"] = int(overpass_call_counter.get("count", 0)) + 1
            result = query_func()

            finished_wall = time.time()
            elapsed_s = time.perf_counter() - started_monotonic
            metrics: dict[str, int | None] = {}
            if debug_enabled or debug_summary is not None:
                metrics = _extract_result_metrics(result)

            if debug_enabled:
                print(f"[DONE ] {query_label}")
                print(f"        end={_fmt_ts(finished_wall)}")
                print(f"        elapsed={elapsed_s:.1f}s")
                metrics_line = _format_metrics_inline(metrics)
                if metrics_line:
                    print(f"        {metrics_line}")

            if debug_summary is not None:
                debug_summary[query_label] = {
                    "query_label": query_label,
                    "status": "DONE",
                    "elapsed_s": elapsed_s,
                    "metrics": metrics,
                    "exception_name": None,
                }

            ox.settings.overpass_url = original_overpass_url
            return result
        except Exception as error:
            finished_wall = time.time()
            elapsed_s = time.perf_counter() - started_monotonic

            if debug_enabled:
                print(f"[FAIL ] {query_label}")
                print(f"        end={_fmt_ts(finished_wall)}")
                print(f"        elapsed={elapsed_s:.1f}s")
                print(f"        error={type(error).__name__}")

            if debug_summary is not None:
                debug_summary[query_label] = {
                    "query_label": query_label,
                    "status": "FAILED",
                    "elapsed_s": elapsed_s,
                    "metrics": {},
                    "exception_name": type(error).__name__,
                }

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
    use_cache: bool = True,
) -> dict[str, object]:
    debug_enabled = _overpass_debug_enabled()
    debug_summary: dict[str, dict[str, object]] = {}
    overpass_call_counter: dict[str, int] = {"count": 0}
    cache_stats = _init_cache_stats()

    dist_m = int(math.ceil(math.sqrt(half_width_m**2 + half_height_m**2))) + 300

    try:
        graph = _load_or_build_road_graph(
            center_lat=center_lat,
            center_lon=center_lon,
            dist_m=dist_m,
            debug_enabled=debug_enabled,
            debug_summary=debug_summary if debug_enabled else None,
            overpass_call_counter=overpass_call_counter,
            cache_stats=cache_stats,
            use_cache=use_cache,
        )

        assemble_started = time.perf_counter()
        edges_raw = ox.graph_to_gdfs(graph, nodes=False, edges=True)
        feature_layers = _load_or_build_feature_layers(
            center_lat=center_lat,
            center_lon=center_lon,
            dist_m=dist_m,
            include_building_features=include_building_features,
            debug_enabled=debug_enabled,
            debug_summary=debug_summary if debug_enabled else None,
            overpass_call_counter=overpass_call_counter,
            cache_stats=cache_stats,
            use_cache=use_cache,
        )

        bundle = _assemble_runtime_bundle(
            edges_raw=edges_raw,
            feature_layers=feature_layers,
            include_building_features=include_building_features,
        )
        cache_stats["bundle_assemble_s"] = float(time.perf_counter() - assemble_started)

        if debug_enabled:
            _print_bundle_profile(bundle)

        return bundle
    finally:
        if debug_enabled:
            _print_overpass_summary(debug_summary)
            _print_osm_cache_profile(debug_summary)
            _print_cache_runtime_stats(cache_stats, int(overpass_call_counter.get("count", 0)))


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
    _ = extent_m  # Maintained for API compatibility; graph identity is dist-based.

    return _build_shared_osm_bundle(
        center_lat=center_lat,
        center_lon=center_lon,
        half_width_m=half_width_m,
        half_height_m=half_height_m,
        include_building_features=include_building_features,
        use_cache=use_cache,
    )
