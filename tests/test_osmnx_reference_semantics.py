"""Characterization of current OSMnx 2.0.7 road/feature processing (migration plan §6, §7; B4 harness).

These tests describe what the Overpass path does today with given input elements. The input comes
from the synthetic FakeOverpass fixture, whose element selection is an ASSUMPTION, not verified real
Overpass behavior (plan §7.1). Clean-HEAD compatible: only OSMnx and the road filter string are used.
"""

from __future__ import annotations

import re

import osmnx as ox
import pytest
from osmnx._errors import InsufficientResponseError
from shapely.geometry import LineString, Polygon

from generator.core.osm_bundle_cache import _ROAD_CUSTOM_FILTER
from support.overpass_fake import FakeOverpass
from support.synthetic_osm import CENTER_LAT, CENTER_LON, build_features, build_road_network

CENTER = (CENTER_LAT, CENTER_LON)
DIST_M = 1000
FEATURE_TAGS = {"building": True, "natural": ["water"], "leisure": ["park"], "landuse": ["forest"]}


@pytest.fixture
def road_graph(monkeypatch):
    network = build_road_network()
    FakeOverpass(network.builder.elements).install(monkeypatch)
    graph = ox.graph_from_point(CENTER, dist=DIST_M, custom_filter=_ROAD_CUSTOM_FILTER, simplify=True)
    edges = ox.graph_to_gdfs(graph, nodes=False)
    return network, graph, edges


def _query_polygon():
    return ox.utils_geo.bbox_to_poly(ox.utils_geo.bbox_from_point(CENTER, DIST_M))


def _features(monkeypatch, selection="assumed", tags=FEATURE_TAGS):
    feature_set = build_features()
    FakeOverpass(feature_set.builder.elements, selection=selection).install(monkeypatch)
    return feature_set, ox.features_from_point(CENTER, tags=tags, dist=DIST_M)


def _way_polygon(builder, way_id) -> Polygon:
    nodes = {n["id"]: (n["lon"], n["lat"]) for n in builder.nodes}
    way = next(w for w in builder.ways if w["id"] == way_id)
    return Polygon([nodes[n] for n in way["nodes"]])


def test_road_filter_is_unanchored_case_sensitive_regex():
    pattern = re.compile(re.match(r'^\["highway"~"(.+)"\]$', _ROAD_CUSTOM_FILTER).group(1))
    assert pattern.search("services")
    assert pattern.search("footway;steps")
    assert pattern.search("primary_link")
    assert not pattern.search("track")
    assert not pattern.search("cycleway")
    assert not pattern.search("Primary")


def test_two_way_road_produces_both_directions(road_graph):
    network, _, edges = road_graph
    n = network.nodes
    assert (n["c"], n["a"], 0) in edges.index
    assert (n["a"], n["c"], 0) in edges.index
    assert not edges.loc[(n["c"], n["a"], 0), "oneway"]


def test_oneway_road_produces_single_direction(road_graph):
    network, _, edges = road_graph
    n = network.nodes
    assert (n["n1"], n["c"], 0) in edges.index
    assert (n["c"], n["n1"], 0) not in edges.index
    assert (n["c"], n["s1"], 0) in edges.index
    assert (n["s1"], n["c"], 0) not in edges.index


def test_bridge_segment_marks_whole_simplified_edge(road_graph):
    network, graph, edges = road_graph
    n = network.nodes
    edge = edges.loc[(n["c"], n["a"], 0)]
    assert edge["bridge"] == "yes"
    assert edge["highway"] == "residential"
    assert len(edge.geometry.coords) == 3
    assert n["b"] not in graph.nodes


def test_merged_edge_with_differing_highway_gets_list(road_graph):
    network, _, edges = road_graph
    n = network.nodes
    highway = edges.loc[(n["n1"], n["p2"], 0), "highway"]
    assert isinstance(highway, list)
    assert set(highway) == {"tertiary", "residential"}


def test_simplified_edge_reaching_outside_query_box_is_dropped_entirely(road_graph):
    # Simplification merges c-d-e-f-g before the final truncation removes g, so the whole edge goes.
    network, graph, _ = road_graph
    n = network.nodes
    assert n["c"] in graph.nodes
    for name in ("d", "e", "f", "g"):
        assert n[name] not in graph.nodes


def test_disconnected_fragment_is_removed(road_graph):
    network, graph, _ = road_graph
    assert network.nodes["q1"] not in graph.nodes
    assert network.nodes["q2"] not in graph.nodes


@pytest.mark.parametrize("name", ["building_east", "building_west", "building_north", "building_south"])
def test_boundary_crossing_features_are_returned_uncut(monkeypatch, name):
    feature_set, gdf = _features(monkeypatch)
    element, osm_id = feature_set.ids[name]
    geometry = gdf.loc[(element, osm_id)].geometry
    polygon = _query_polygon()
    assert polygon.intersects(geometry) and not polygon.contains(geometry)
    assert geometry.equals(_way_polygon(feature_set.builder, osm_id))


def test_multipolygon_relation_keeps_hole(monkeypatch):
    feature_set, gdf = _features(monkeypatch)
    geometry = gdf.loc[feature_set.ids["water_with_hole"]].geometry
    assert geometry.geom_type == "Polygon"
    assert len(geometry.interiors) == 1


def test_relation_with_missing_member_is_dropped(monkeypatch):
    feature_set, gdf = _features(monkeypatch)
    assert feature_set.ids["water_missing_member"] not in gdf.index


def test_closed_way_area_no_stays_line(monkeypatch):
    feature_set, gdf = _features(monkeypatch)
    assert isinstance(gdf.loc[feature_set.ids["park_area_no"]].geometry, LineString)
    assert gdf.loc[feature_set.ids["park"]].geometry.geom_type == "Polygon"


def test_enclosing_polygon_depends_on_overpass_selection(monkeypatch):
    # Documents the unresolved selection rule (plan §7.1); "assumed" is a fixture assumption, not Overpass truth.
    feature_set, assumed = _features(monkeypatch, selection="assumed")
    assert feature_set.ids["enclosing_forest"] not in assumed.index

    feature_set, everything = _features(monkeypatch, selection="all")
    forest = everything.loc[feature_set.ids["enclosing_forest"]].geometry
    assert forest.contains(_query_polygon())


def test_layer_without_matches_raises_insufficient_response(monkeypatch):
    with pytest.raises(InsufficientResponseError):
        _features(monkeypatch, tags={"natural": ["glacier"]})
