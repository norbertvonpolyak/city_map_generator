"""OSMnx 2.0.7 private-function contract (migration plan §6.2, binding constraint 2).

The PBF source will call ``osmnx.graph._create_graph`` and ``osmnx.features._create_gdf`` directly.
These tests pin the version and signatures, and prove that driving those private functions with the
same Overpass-shaped elements reproduces ``ox.graph_from_point`` / ``ox.features_from_point`` exactly.
Clean-HEAD compatible: no dependency on uncommitted working-tree behavior.
"""

from __future__ import annotations

import inspect

import osmnx as ox
import pandas as pd
import pytest
from osmnx import features as ox_features
from osmnx import graph as ox_graph
from osmnx._errors import InsufficientResponseError

from generator.core.osm_bundle_cache import _FEATURE_LAYER_SPECS, _ROAD_CUSTOM_FILTER
from support.overpass_fake import FakeOverpass
from support.synthetic_osm import CENTER_LAT, CENTER_LON, build_features, build_road_network

CENTER = (CENTER_LAT, CENTER_LON)
DIST_M = 1000


def _query_polygon():
    return ox.utils_geo.bbox_to_poly(ox.utils_geo.bbox_from_point(CENTER, DIST_M))


def _topology_buffer(polygon):
    # Mirrors osmnx.graph.graph_from_polygon: 500 m buffer in the polygon's UTM CRS.
    poly_proj, crs_utm = ox.projection.project_geometry(polygon)
    poly_buff, _ = ox.projection.project_geometry(poly_proj.buffer(500), crs=crs_utm, to_latlong=True)
    return poly_buff


def _private_graph(fake: FakeOverpass, polygon):
    poly_buff = _topology_buffer(polygon)
    graph = ox_graph._create_graph(fake.select_network(poly_buff, _ROAD_CUSTOM_FILTER), bidirectional=False)
    graph = ox.truncate.truncate_graph_polygon(graph, poly_buff)
    graph = ox.truncate.largest_component(graph, strongly=False)
    graph = ox.simplification.simplify_graph(graph)
    graph = ox.truncate.truncate_graph_polygon(graph, polygon)
    return ox.truncate.largest_component(graph, strongly=False)


def _normalize(value):
    if isinstance(value, list):
        return frozenset(value)
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return value


def _edge_records(graph) -> dict:
    edges = ox.graph_to_gdfs(graph, nodes=False)
    return {
        index: {
            "geometry": row.geometry.wkb,
            **{attr: _normalize(row.get(attr)) for attr in ("highway", "bridge", "oneway", "osmid", "name")},
        }
        for index, row in edges.iterrows()
    }


def _outcome(func):
    try:
        return "gdf", func()
    except InsufficientResponseError as error:
        return "error", type(error).__name__


def test_osmnx_version_is_pinned():
    assert ox.__version__ == "2.0.7"


def test_private_create_graph_signature():
    assert list(inspect.signature(ox_graph._create_graph).parameters) == ["response_jsons", "bidirectional"]


def test_private_create_gdf_signature():
    assert list(inspect.signature(ox_features._create_gdf).parameters) == ["response_jsons", "polygon", "tags"]


def test_private_graph_pipeline_matches_graph_from_point(monkeypatch):
    network = build_road_network()
    fake = FakeOverpass(network.builder.elements).install(monkeypatch)
    polygon = _query_polygon()

    reference = ox.graph_from_point(CENTER, dist=DIST_M, custom_filter=_ROAD_CUSTOM_FILTER, simplify=True)
    private = _private_graph(fake, polygon)

    assert fake.network_calls[0][0].equals_exact(_topology_buffer(polygon), 0)
    reference_edges = _edge_records(reference)
    assert len(reference_edges) >= 4
    assert _edge_records(private) == reference_edges
    assert set(private.nodes) == set(reference.nodes)


@pytest.mark.parametrize("layer_name", sorted(_FEATURE_LAYER_SPECS))
def test_private_create_gdf_matches_features_from_point(monkeypatch, layer_name):
    tags = _FEATURE_LAYER_SPECS[layer_name]["tags"]
    fake = FakeOverpass(build_features().builder.elements).install(monkeypatch)
    polygon = _query_polygon()

    reference = _outcome(lambda: ox.features_from_point(CENTER, tags=tags, dist=DIST_M))
    private = _outcome(lambda: ox_features._create_gdf(fake.select_features(polygon, tags), polygon, tags))

    assert fake.feature_calls[0][0].equals_exact(polygon, 0)
    assert reference[0] == private[0]
    if reference[0] == "error":
        assert reference[1] == private[1]
        return

    ref_gdf, priv_gdf = reference[1].sort_index(), private[1].sort_index()
    assert list(ref_gdf.index) == list(priv_gdf.index)
    assert set(ref_gdf.columns) == set(priv_gdf.columns)
    pd.testing.assert_frame_equal(
        pd.DataFrame(ref_gdf.drop(columns="geometry")),
        pd.DataFrame(priv_gdf.drop(columns="geometry")),
        check_like=True,
    )
    assert ref_gdf.geometry.geom_equals_exact(priv_gdf.geometry, tolerance=0).all()
    assert ref_gdf.crs == priv_gdf.crs
