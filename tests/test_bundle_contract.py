"""T1: offline data-source contract of the current Overpass bundle loader.

Runs the real ``load_or_build_shared_osm_bundle`` and real OSMnx processing against FakeOverpass.
Tests marked ``working_tree`` characterize uncommitted working-tree behavior (``buildings_only_mode``,
the ``man_made`` buildings tag) and are NOT expected to pass on a clean HEAD checkout.
"""

from __future__ import annotations

import inspect
import re

import geopandas as gpd
import pytest

from generator.core.osm_bundle_cache import (
    _FEATURE_LAYER_SPECS,
    _build_feature_layer_cache_filename,
    _build_road_graph_cache_filename,
    load_or_build_shared_osm_bundle,
)
from support.overpass_fake import FakeOverpass
from support.synthetic_osm import CENTER_LAT, CENTER_LON, build_features, build_road_network

BUNDLE_KEYS = {
    "edges_raw", "gdf_all_raw", "trees_raw", "waterway_raw", "railway_raw",
    "paths_raw", "water_raw", "green_raw", "coast_raw", "islands_raw",
}
BUILDING_ONLY_KEYS = {"gdf_all_raw", "trees_raw", "waterway_raw", "railway_raw", "paths_raw"}
# Keys read from gdf_all_raw by the Building and Line engines that also exist in the HEAD tag set.
HEAD_STABLE_BUILDING_TAG_KEYS = {"building", "building:part", "landuse", "leisure", "natural", "amenity", "place", "highway"}


def _supports_buildings_only_mode() -> bool:
    return "buildings_only_mode" in inspect.signature(load_or_build_shared_osm_bundle).parameters


def _load(monkeypatch, **kwargs):
    network = build_road_network()
    build_features(network.builder)
    fake = FakeOverpass(network.builder.elements).install(monkeypatch)
    kwargs.setdefault("use_cache", False)
    bundle = load_or_build_shared_osm_bundle(
        center_lat=CENTER_LAT,
        center_lon=CENTER_LON,
        extent_m=560,
        half_width_m=420.0,
        half_height_m=560.0,
        **kwargs,
    )
    return fake, bundle


def _assert_layer(gdf, index_names):
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert gdf.crs.to_epsg() == 4326
    assert list(gdf.index.names) == index_names


def _assert_edges(edges):
    _assert_layer(edges, ["u", "v", "key"])
    assert len(edges) > 0
    assert "highway" in edges.columns
    assert set(edges.geom_type) == {"LineString"}


def test_default_mode_bundle_contract(monkeypatch):
    _, bundle = _load(monkeypatch)

    assert set(bundle) == BUNDLE_KEYS
    _assert_edges(bundle["edges_raw"])
    for key in BUILDING_ONLY_KEYS:
        assert bundle[key] is None
    _assert_layer(bundle["water_raw"], ["element", "id"])
    _assert_layer(bundle["green_raw"], ["element", "id"])
    assert bundle["coast_raw"] is None
    assert isinstance(bundle["islands_raw"], gpd.GeoDataFrame)
    assert len(bundle["islands_raw"]) == 0
    assert bundle["islands_raw"].crs.to_epsg() == 4326


def test_building_features_mode_bundle_contract(monkeypatch):
    fake, bundle = _load(monkeypatch, include_building_features=True)

    assert set(bundle) == BUNDLE_KEYS
    _assert_edges(bundle["edges_raw"])
    for key in BUILDING_ONLY_KEYS | {"water_raw", "green_raw"}:
        _assert_layer(bundle[key], ["element", "id"])
    assert {"building", "natural", "leisure", "landuse"} <= set(bundle["gdf_all_raw"].columns)
    assert bundle["coast_raw"] is None
    assert len(bundle["islands_raw"]) == 0
    assert len(fake.feature_calls) == len(_FEATURE_LAYER_SPECS)


def test_buildings_layer_tags_cover_head_stable_engine_keys():
    assert HEAD_STABLE_BUILDING_TAG_KEYS <= set(_FEATURE_LAYER_SPECS["buildings"]["tags"])


@pytest.mark.working_tree
def test_buildings_layer_tags_include_man_made():
    assert _FEATURE_LAYER_SPECS["buildings"]["tags"]["man_made"] == ["pier", "breakwater"]


@pytest.mark.working_tree
@pytest.mark.skipif(not _supports_buildings_only_mode(), reason="buildings_only_mode is working-tree only")
def test_buildings_only_mode_bundle_contract(monkeypatch):
    fake, bundle = _load(monkeypatch, buildings_only_mode=True)

    assert set(bundle) == BUNDLE_KEYS
    _assert_edges(bundle["edges_raw"])
    _assert_layer(bundle["gdf_all_raw"], ["element", "id"])
    for key in BUNDLE_KEYS - {"edges_raw", "gdf_all_raw"}:
        assert bundle[key] is None
    assert [tags for _, tags in fake.feature_calls] == [_FEATURE_LAYER_SPECS["buildings"]["tags"]]


def test_cache_filename_formats():
    road = _build_road_graph_cache_filename(center_lat=CENTER_LAT, center_lon=CENTER_LON, dist_m=1000, simplify=True)
    assert re.fullmatch(r"osm_road_graph_47\.497912_19\.040235_rf[0-9a-f]{12}_s1_v1_normal_map_v1_d1000\.pkl", road)

    layer = _build_feature_layer_cache_filename(
        layer_name="water",
        center_lat=CENTER_LAT,
        center_lon=CENTER_LON,
        dist_m=1000,
        tags=_FEATURE_LAYER_SPECS["water"]["tags"],
    )
    assert re.fullmatch(r"osm_feature_layer_water_47\.497912_19\.040235_d1000_qh[0-9a-f]{12}_v1_normal_map_v1\.pkl", layer)


def test_cache_writes_stay_in_isolated_dir_and_are_reused(monkeypatch, offline_isolated_env):
    fake, _ = _load(monkeypatch, use_cache=True)
    calls_after_first = (len(fake.network_calls), len(fake.feature_calls))

    written = sorted(p.name for p in offline_isolated_env.iterdir())
    assert any(name.startswith("osm_road_graph_") for name in written)
    assert sum(name.startswith("osm_feature_layer_") for name in written) >= 3

    load_or_build_shared_osm_bundle(
        center_lat=CENTER_LAT, center_lon=CENTER_LON, extent_m=560,
        half_width_m=420.0, half_height_m=560.0, use_cache=True,
    )
    assert (len(fake.network_calls), len(fake.feature_calls)) == calls_after_first
