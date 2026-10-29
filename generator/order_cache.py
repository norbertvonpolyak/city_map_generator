"""Persistent source-identity cache preparation for manually rendered orders."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


CACHE_SCHEMA_VERSION = 1
EXTRACTOR_VERSION = 1
EXTRACTION_MARGIN_M = 2500
CACHE_MANIFEST = "cache_manifest.json"


class OrderCacheError(RuntimeError):
    pass


def _hash_value(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _source_identity(pbf_path: Path, header: dict | None = None) -> dict:
    from generator.core.pbf_store import file_sha256, read_pbf_header

    header = header or read_pbf_header(pbf_path)
    before = pbf_path.stat()
    digest = file_sha256(pbf_path)
    header = read_pbf_header(pbf_path)
    after = pbf_path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise OrderCacheError(f"PBF changed while computing its source identity: {pbf_path}")
    if not header.get("bbox"):
        raise OrderCacheError(f"PBF has no geographic bounds: {pbf_path}")
    return {
        "path": str(pbf_path.resolve()),
        "size_bytes": after.st_size,
        "mtime_ns": after.st_mtime_ns,
        "sha256": digest,
        "header": header,
    }


def build_cache_identity(
    source_identity: dict,
    center_lat: float,
    center_lon: float,
    coverage_bbox_wgs84: tuple[float, float, float, float],
    *,
    schema_version: int,
    preprocess_version: int,
    tag_rules_hash: str,
) -> dict:
    """Identity deliberately excludes order style and size; coverage controls reuse."""
    return {
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "source_identity": source_identity,
        "center": [center_lat, center_lon],
        "coverage_bbox_wgs84": list(coverage_bbox_wgs84),
        "store_schema_version": str(schema_version),
        "store_preprocess_version": str(preprocess_version),
        "tag_rules_hash": tag_rules_hash,
    }


def cache_identity_id(identity: dict) -> str:
    return _hash_value(identity)[:24]


def _max_viewport(extent_m: float, print_dimensions=()) -> tuple[float, float]:
    """Largest renderer viewport over every style for the catalog plus any requested print sizes."""
    from generator.core.render_dispatcher import get_viewport_for_style
    from generator.core.style_registry import STYLE_REGISTRY
    from generator.specs import SIZES_CM, spec_from_dimensions

    max_hw = max_hh = 0.0
    for width_cm, height_cm in list(SIZES_CM.values()) + list(print_dimensions):
        spec = spec_from_dimensions(width_cm, height_cm, extent_m=extent_m)
        for style_name in STYLE_REGISTRY:
            hw, hh = get_viewport_for_style(style_name, spec)
            max_hw = max(max_hw, hw)
            max_hh = max(max_hh, hh)
    return max_hw, max_hh


def _required_cache_bbox(
    center_lat: float, center_lon: float, extent_m: int, print_dimensions=(),
) -> tuple[float, float, float, float]:
    import osmnx as ox

    from generator.core.pbf_source import bundle_dist_m, query_polygon, road_query_polygon
    from generator.specs import DEFAULT_EXTENT_M

    max_bundle_hw, max_bundle_hh = _max_viewport(max(extent_m, DEFAULT_EXTENT_M), print_dimensions)

    dist_m = bundle_dist_m(max_bundle_hw, max_bundle_hh)
    query = query_polygon(center_lat, center_lon, dist_m)
    road_query = road_query_polygon(query)
    projected, projected_crs = ox.projection.project_geometry(road_query)
    expanded = projected.buffer(EXTRACTION_MARGIN_M)
    expanded_wgs84, _ = ox.projection.project_geometry(expanded, crs=projected_crs, to_latlong=True)
    west, south, east, north = expanded_wgs84.bounds
    return west, south, east, north


def _bbox_covers(outer, inner) -> bool:
    if not outer or not inner:
        return False
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]


def _validate_store(store_dir: Path, source_path: Path | None, required_bbox, explicit_coverage) -> dict:
    from generator.core.pbf_store import PbfStoreReader, TagRules

    if not (store_dir / "osm_store.sqlite").is_file():
        raise OrderCacheError(f"Geographic store is missing: {store_dir}")
    with PbfStoreReader(store_dir, pbf_path=source_path, verify_sha256=source_path is not None) as reader:
        coverage = explicit_coverage or reader.header_bbox
        if not _bbox_covers(coverage, required_bbox):
            raise OrderCacheError(f"Cache coverage {coverage} does not contain required bounds {required_bbox}")
        if reader.meta.get("tag_rules_hash") != TagRules.from_production().rules_hash():
            raise OrderCacheError("Store tag rules do not match the active renderer")
        if reader.counts.get("road_ways", 0) <= 0:
            raise OrderCacheError("Store contains no road ways")
        return {
            "path": str(reader.store_path.resolve()),
            "size_bytes": reader.store_path.stat().st_size,
            "header_bbox_wgs84": list(reader.header_bbox or ()),
            "coverage_bbox_wgs84": list(coverage),
            "source": dict(reader.meta),
            "counts": reader.counts,
        }


def _validate_render_features(
    store_dir: Path, center_lat: float, center_lon: float, extent_m: int, required_bbox, print_dimensions=(),
) -> dict:
    from generator.core.pbf_source import PbfBundleSource
    from generator.core.pbf_store import PbfStoreReader

    max_hw, max_hh = _max_viewport(max(extent_m, 5000), print_dimensions)
    with PbfStoreReader(store_dir) as reader:
        provider = PbfBundleSource(reader)
        bundle = provider.load_bundle(
            center_lat=center_lat,
            center_lon=center_lon,
            extent_m=extent_m,
            half_width_m=max_hw,
            half_height_m=max_hh,
            include_building_features=True,
        )
        stats = provider.last_stats
        road_bbox = tuple(stats["road_query_bbox"])
        if not _bbox_covers(required_bbox, road_bbox):
            raise OrderCacheError(f"Requested road query escaped explicit cache coverage: {road_bbox}")
        roads = stats.get("roads", {})
        if roads.get("edges", 0) <= 0 or roads.get("incomplete_ways_dropped", 0):
            raise OrderCacheError(f"Required road features are incomplete: {roads}")
        layers = stats.get("layers", {})
        required_layers = {"buildings", "trees", "waterway", "railway", "paths", "water", "green", "islands"}
        missing = {name: layers.get(name, {}).get("features", 0) for name in required_layers if not layers.get(name, {}).get("features", 0)}
        if missing:
            raise OrderCacheError(f"Required order-render layers are empty: {missing}")
        issues = {
            name: layer for name, layer in layers.items()
            if layer.get("relations_with_missing_members", 0)
            or layer.get("relations_with_nested_members", 0)
            or layer.get("incomplete_ways_dropped", 0)
        }
        if issues:
            raise OrderCacheError(f"Query includes incomplete OSM dependencies: {issues}")
        if bundle.get("edges_raw") is None or len(bundle["edges_raw"]) == 0:
            raise OrderCacheError("PBF adapter returned no road edges")
        if bundle.get("gdf_all_raw") is None or len(bundle["gdf_all_raw"]) == 0:
            raise OrderCacheError("PBF adapter returned no roads or buildings")
        return {
            "query_bbox_wgs84": stats["query_bbox"],
            "road_query_bbox_wgs84": stats["road_query_bbox"],
            "roads": roads,
            "layers": layers,
            "runtime_layer_counts": {key: None if value is None else len(value) for key, value in bundle.items()},
        }


def prepare_order_cache(
    *,
    pbf_path: Path | str,
    center_lat: float,
    center_lon: float,
    extent_m: int,
    cache_root: Path | str,
    preferred_store_dir: Path | str | None = None,
    print_dimensions=(),
) -> dict:
    from generator.core.pbf_store import PbfStoreReader, TagRules, build_store
    from generator.core.regional_extract import extract_region_pbf

    source = Path(pbf_path).expanduser().resolve()
    if not source.is_file() or source.suffix.casefold() != ".pbf":
        raise OrderCacheError(f"PBF_PATH must identify an existing .pbf file: {source}")
    if extent_m <= 0:
        raise OrderCacheError("extent_m must be positive")
    required_bbox = _required_cache_bbox(center_lat, center_lon, extent_m, print_dimensions)
    from generator.core.pbf_store import read_pbf_header

    source_header = read_pbf_header(source)
    if not _bbox_covers(source_header.get("bbox"), required_bbox):
        raise OrderCacheError(f"Source PBF bounds do not contain the required order/cache bounds {required_bbox}")
    source_identity = _source_identity(source, source_header)
    rules_hash = TagRules.from_production().rules_hash()

    candidates = []
    if preferred_store_dir is not None:
        candidates.append((Path(preferred_store_dir).expanduser().resolve(), source, None))
    cache_root = Path(cache_root).expanduser().resolve()
    city_cache_root = cache_root / "budapest"
    if city_cache_root.is_dir():
        for manifest_path in city_cache_root.glob("*/cache_manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if manifest.get("source_identity") == source_identity:
                if _bbox_covers(manifest.get("coverage_bbox_wgs84"), required_bbox):
                    store_path = manifest.get("store_dir")
                    region_path = manifest.get("region_pbf")
                    if store_path and region_path:
                        candidates.append((Path(store_path), Path(region_path), manifest.get("coverage_bbox_wgs84")))

    for candidate, candidate_source, explicit_coverage in candidates:
        try:
            verified = _validate_store(candidate, candidate_source, required_bbox, explicit_coverage=explicit_coverage)
        except Exception:
            continue
        if candidate_source.resolve() == source.resolve():
            recorded_source = Path(verified["source"].get("pbf_path", "")).resolve()
            if recorded_source != source:
                continue
        features = _validate_render_features(candidate, center_lat, center_lon, extent_m, required_bbox, print_dimensions)
        identity = build_cache_identity(
			source_identity,
			center_lat,
			center_lon,
			tuple(verified["coverage_bbox_wgs84"]),
			schema_version=int(verified["source"]["schema_version"]),
			preprocess_version=int(verified["source"]["preprocess_version"]),
			tag_rules_hash=rules_hash,
		)
        cache_id = cache_identity_id(identity)
        view_dir = city_cache_root / cache_id
        manifest_path = view_dir / CACHE_MANIFEST
        existing_manifest = None
        if manifest_path.is_file():
            try:
                existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise OrderCacheError(f"Cannot reuse corrupt cache manifest; preserving files: {manifest_path}: {error}") from error
            if existing_manifest.get("identity") != identity:
                raise OrderCacheError(f"Cache identity mismatch; preserving existing cache: {view_dir}")
        else:
            view_dir.mkdir(parents=True, exist_ok=True)
            _atomic_json(manifest_path, {
                "cache_id": cache_id,
                "identity": identity,
                "source_identity": source_identity,
                "coverage_bbox_wgs84": list(verified["coverage_bbox_wgs84"]),
                "store_dir": str(candidate),
                "region_pbf": str(candidate_source),
                "store_reused_from_existing_path": True,
            })
        return {
            "cache_id": cache_id,
            "store_dir": str(candidate),
            "reused": True,
            "build_duration_s": 0.0,
            "source_identity": source_identity,
            "coverage_bbox_wgs84": verified["coverage_bbox_wgs84"],
            "store": verified,
            "features": features,
            "identity": identity,
            "manifest_path": str(manifest_path),
        }

    cache_bbox = required_bbox
    identity = build_cache_identity(
		source_identity,
		center_lat,
		center_lon,
		cache_bbox,
		schema_version=1,
		preprocess_version=1,
		tag_rules_hash=rules_hash,
	)
    cache_id = cache_identity_id(identity)
    cache_dir = city_cache_root / cache_id
    manifest_path = cache_dir / CACHE_MANIFEST
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest = None
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise OrderCacheError(f"Cannot reuse corrupt cache manifest; preserving files: {manifest_path}: {error}") from error
        if manifest.get("identity") != identity:
            raise OrderCacheError(f"Cache identity mismatch; preserving existing cache: {cache_dir}")

    region_pbf = cache_dir / "region.osm.pbf"
    store_dir = cache_dir / "store"
    build_duration_s = 0.0
    created = False
    if manifest is None:
        if region_pbf.exists() or (store_dir / "osm_store.sqlite").exists():
            raise OrderCacheError(f"Unmanifested cache files exist; preserving them: {cache_dir}")
        extraction_started = time.perf_counter()
        extraction = extract_region_pbf(source, region_pbf, cache_bbox)
        extraction_duration_s = time.perf_counter() - extraction_started
        build_started = time.perf_counter()
        build_result = build_store(region_pbf, store_dir)
        build_duration_s = time.perf_counter() - build_started
        created = True
        manifest = {
            "cache_id": cache_id,
            "identity": identity,
            "source_identity": source_identity,
            "coverage_bbox_wgs84": list(cache_bbox),
            "region_pbf": str(region_pbf),
            "store_dir": str(store_dir),
            "region_pbf_sha256": _source_identity(region_pbf)["sha256"],
            "region_extraction": {
                "duration_s": round(extraction_duration_s, 3),
                "output_size_bytes": extraction.output_size_bytes,
                "output_nodes": extraction.output_nodes,
                "output_ways": extraction.output_ways,
                "output_relations": extraction.output_relations,
                "unresolved_references": extraction.unresolved_references,
                "unresolved_reference_sample": extraction.unresolved_reference_sample,
            },
            "store_build": {"duration_s": round(build_result.duration_s, 3), "store_path": str(build_result.store_path)},
        }
        _atomic_json(manifest_path, manifest)
    elif not region_pbf.is_file():
        raise OrderCacheError(f"Cache manifest exists but regional PBF is missing: {region_pbf}")

    region_identity = _source_identity(region_pbf)
    if manifest.get("region_pbf_sha256") != region_identity["sha256"]:
        raise OrderCacheError(f"Regional cache PBF fingerprint mismatch; preserving cache: {region_pbf}")
    if Path(manifest.get("store_dir", "")).resolve() != store_dir.resolve():
        raise OrderCacheError(f"Cache manifest store path mismatch; preserving cache: {manifest_path}")
    store_info = _validate_store(store_dir, region_pbf, required_bbox, explicit_coverage=cache_bbox)
    features = _validate_render_features(store_dir, center_lat, center_lon, extent_m, required_bbox, print_dimensions)
    return {
        "cache_id": cache_id,
        "store_dir": str(store_dir),
        "reused": not created,
        "build_duration_s": build_duration_s,
        "source_identity": source_identity,
        "region_pbf": str(region_pbf),
        "region_pbf_identity": region_identity,
        "coverage_bbox_wgs84": list(cache_bbox),
        "store": store_info,
        "features": features,
        "identity": identity,
        "manifest_path": str(manifest_path),
    }
