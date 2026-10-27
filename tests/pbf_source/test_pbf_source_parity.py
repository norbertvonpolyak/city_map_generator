"""M3 parity: PBF-store bundles equal the production Overpass-path bundles on synthetic data.

The reference runs the real ``load_or_build_shared_osm_bundle`` and OSMnx against FakeOverpass fed with
the elements of the same PBF. Equality holds under FakeOverpass's selection rule, which is the plan §7.1
assumption shared with the adapter; it is not proof of real Overpass selection.
"""

from __future__ import annotations

import pytest
from geopandas.testing import assert_geodataframe_equal
from osmnx._errors import InsufficientResponseError

from generator.core import osm_bundle_cache
from generator.core.pbf_source import PbfBundleSource
from pbf_source_data import (
    EXTENT_M,
    HALF_HEIGHT_M,
    HALF_WIDTH_M,
    build_store,
    engine_dataset,
    pbf_elements,
    truncated_dataset,
)
from support.overpass_fake import FakeOverpass
from support.synthetic_osm import CENTER_LAT, CENTER_LON, OsmBuilder, build_road_network

MODES = {
    "block": {"include_building_features": False},
    "building_line": {"include_building_features": True},
    "buildings_only": {"include_building_features": False, "buildings_only_mode": True},
}


def _normalized(gdf):
    # Merged-edge list attributes come from list(set(...)) in OSMnx; their order is not part of the contract.
    gdf = gdf.copy()
    for column in gdf.columns:
        if column != gdf.geometry.name and gdf[column].dtype == object:
            gdf[column] = gdf[column].map(lambda v: tuple(sorted(map(str, v))) if isinstance(v, list) else v)
    return gdf.sort_index()


def assert_bundles_equal(actual: dict, expected: dict) -> None:
    assert actual.keys() == expected.keys()
    for key, reference in expected.items():
        value = actual[key]
        if reference is None:
            assert value is None, key
            continue
        assert value is not None, key
        assert len(value) == len(reference), key
        if len(reference) == 0:
            assert value.crs == reference.crs, key
            continue
        assert_geodataframe_equal(_normalized(value), _normalized(reference), check_like=True)


def _bundles(monkeypatch, tmp_path, dataset, **mode):
    pbf, reader = build_store(tmp_path, dataset)
    FakeOverpass(pbf_elements(pbf, exclude=dataset.truncated)).install(monkeypatch)
    params = dict(
        center_lat=CENTER_LAT, center_lon=CENTER_LON, extent_m=EXTENT_M,
        half_width_m=HALF_WIDTH_M, half_height_m=HALF_HEIGHT_M, use_cache=False, **mode,
    )
    expected = osm_bundle_cache.load_or_build_shared_osm_bundle(**params)
    with reader:
        source = PbfBundleSource(reader)
        actual = source.load_bundle(**params)
    return actual, expected, source.last_stats


@pytest.mark.parametrize("with_coast", [False, True], ids=["inland", "coast"])
@pytest.mark.parametrize("mode", [
    "block",
    "building_line",
    # buildings_only_mode exists only in the uncommitted working tree.
    pytest.param("buildings_only", marks=pytest.mark.working_tree),
])
def test_bundle_parity(monkeypatch, tmp_path, mode, with_coast):
    actual, expected, stats = _bundles(monkeypatch, tmp_path, engine_dataset(with_coast=with_coast), **MODES[mode])
    assert_bundles_equal(actual, expected)
    assert stats["layers_requested"] == osm_bundle_cache._select_required_feature_layers(
        MODES[mode]["include_building_features"], MODES[mode].get("buildings_only_mode", False)
    )


def test_inland_layers_follow_production_empty_handling(monkeypatch, tmp_path):
    actual, _, stats = _bundles(monkeypatch, tmp_path, engine_dataset(with_coast=False), include_building_features=True)
    assert actual["coast_raw"] is None
    assert len(actual["islands_raw"]) == 0 and actual["islands_raw"].crs.to_epsg() == 4326
    assert stats["layers"]["coast"]["empty"] and stats["layers"]["islands"]["empty"]


def test_coast_dataset_layers_present(monkeypatch, tmp_path):
    data = engine_dataset(with_coast=True)
    actual, _, _ = _bundles(monkeypatch, tmp_path, data, include_building_features=True)
    assert ("way", data.ids["coastline"][1]) in actual["coast_raw"].index
    assert {("way", data.ids["island_way"][1]), ("relation", data.ids["island_relation"][1])} <= set(actual["islands_raw"].index)


def test_relation_edge_cases(monkeypatch, tmp_path):
    data = engine_dataset(with_coast=False)
    actual, _, stats = _bundles(monkeypatch, tmp_path, data, include_building_features=True)
    green = actual["green_raw"]
    # Selected through its untagged label node although its outer ring encloses the query box.
    assert ("relation", data.ids["reserve_by_label"][1]) in green.index
    # Nested relation member ignored; geometry from the member way only.
    assert ("relation", data.ids["garden_nested"][1]) in green.index
    # Missing label node does not affect a geometry made of member ways.
    assert ("relation", data.ids["park_missing_label_node"][1]) in green.index
    # Missing member way: OSMnx yields a null geometry and removes the relation.
    assert ("relation", data.ids["water_missing_member"][1]) not in actual["water_raw"].index
    assert stats["layers"]["water"]["relations_with_missing_members"] == 1
    assert stats["layers"]["green"]["relations_with_nested_members"] == 1
    assert stats["layers"]["green"]["relations_with_missing_members"] == 1
    # Enclosing way with no segment in the box is not selected under the assumed rule.
    assert ("way", data.ids["enclosing_forest"][1]) not in green.index


def test_complete_way_crossing_extract_boundary_keeps_full_geometry(monkeypatch, tmp_path):
    data = engine_dataset(with_coast=False)
    actual, _, _ = _bundles(monkeypatch, tmp_path, data, include_building_features=True)
    rail = actual["railway_raw"].loc[("way", data.ids["rail_cross_border"][1])]
    assert rail.geometry.bounds[2] > 19.2  # extends past the header bbox east edge


def test_truncated_elements_are_dropped_without_side_effects(monkeypatch, tmp_path):
    data = truncated_dataset()
    actual, expected, stats = _bundles(monkeypatch, tmp_path, data, include_building_features=True)
    # Equal to the reference built WITHOUT the truncated elements.
    assert_bundles_equal(actual, expected)
    assert stats["roads"]["incomplete_ways_dropped"] == 2
    assert set(stats["roads"]["incomplete_way_ids_sample"]) == {data.ids["truncated_road"][1], data.ids["border_cut_road"][1]}
    # natural=water is also a buildings-layer tag, so the truncated relation member is dropped there too.
    assert set(stats["layers"]["buildings"]["incomplete_way_ids_sample"]) == {
        data.ids["truncated_building"][1], data.ids["truncated_outer"][1],
    }
    water = stats["layers"]["water"]
    assert water["incomplete_ways_dropped"] == 1
    assert water["relations_not_in_result"] == 2  # truncated member + missing member


def test_missing_required_layer_raises_like_production(monkeypatch, tmp_path):
    # No trees in the box: production raises InsufficientResponseError for the trees layer.
    from pbf_source_data import Dataset

    b = OsmBuilder()
    build_road_network(b)
    b.rect(100, 100, 120, 120, {"building": "yes"})
    data = Dataset(builder=b, ids={})
    pbf, reader = build_store(tmp_path, data)
    FakeOverpass(pbf_elements(pbf)).install(monkeypatch)
    params = dict(
        center_lat=CENTER_LAT, center_lon=CENTER_LON, extent_m=EXTENT_M,
        half_width_m=HALF_WIDTH_M, half_height_m=HALF_HEIGHT_M, use_cache=False, include_building_features=True,
    )
    with pytest.raises(InsufficientResponseError):
        osm_bundle_cache.load_or_build_shared_osm_bundle(**params)
    with reader, pytest.raises(InsufficientResponseError):
        PbfBundleSource(reader).load_bundle(**params)
