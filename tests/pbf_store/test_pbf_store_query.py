"""M2 store lookups: R*Tree candidates vs brute force, layer filters, enclosing lookup, coverage."""

from __future__ import annotations

import random

import pytest

from generator.core import pbf_store
from pbf_synthetic import build_random_dataset, build_store_dataset, read_pbf, write_pbf

# R*Tree stores float32 bounds rounded outward; extras must lie within this tolerance of the query box.
FLOAT32_TOLERANCE_DEG = 1e-5


def _intersects(a, b, pad=0.0):
    return a[0] <= b[2] + pad and a[2] >= b[0] - pad and a[1] <= b[3] + pad and a[3] >= b[1] - pad


@pytest.fixture(scope="module")
def random_store(tmp_path_factory):
    root = tmp_path_factory.mktemp("store_random")
    builder = build_random_dataset()
    pbf = write_pbf(root / "random.osm.pbf", builder, header_bbox=None)
    pbf_store.build_store(pbf, root / "store")
    reader = pbf_store.PbfStoreReader(root / "store")
    yield {"reader": reader, "truth": read_pbf(pbf), "builder": builder}
    reader.close()


@pytest.fixture(scope="module")
def edge_store(tmp_path_factory):
    root = tmp_path_factory.mktemp("store_edges")
    builder, ids = build_store_dataset()
    pbf = write_pbf(root / "edges.osm.pbf", builder)
    pbf_store.build_store(pbf, root / "store")
    reader = pbf_store.PbfStoreReader(root / "store")
    yield {"reader": reader, "ids": ids, "builder": builder}
    reader.close()


def _query_boxes(builder, count=50, seed=11):
    rng = random.Random(seed)
    boxes = []
    for _ in range(count):
        x, y = rng.uniform(-3500, 3000), rng.uniform(-3500, 3000)
        w, h = rng.uniform(10, 1500), rng.uniform(10, 1500)
        west, south = builder.lonlat(x, y)
        east, north = builder.lonlat(x + w, y + h)
        boxes.append((west, south, east, north))
    return boxes


def _exact_way_bboxes(reader, truth):
    stored = {row[0] for row in reader._conn.execute("SELECT id FROM ways")}
    bboxes = {}
    for way_id in stored:
        coords = [truth["nodes"][ref] for ref in truth["ways"][way_id]["node_refs"] if ref in truth["nodes"]]
        if coords:
            lons, lats = [c["lon"] for c in coords], [c["lat"] for c in coords]
            bboxes[way_id] = (min(lons), min(lats), max(lons), max(lats))
    return bboxes


def test_way_candidates_match_brute_force(random_store):
    reader, truth, builder = random_store["reader"], random_store["truth"], random_store["builder"]
    bboxes = _exact_way_bboxes(reader, truth)
    assert len(bboxes) > 300
    for box in _query_boxes(builder):
        expected = {i for i, b in bboxes.items() if _intersects(b, box)}
        candidates = reader.candidate_way_ids(box)
        assert expected <= candidates, (box, expected - candidates)
        assert all(_intersects(bboxes[i], box, FLOAT32_TOLERANCE_DEG) for i in candidates - expected)


def test_node_candidates_match_brute_force(random_store):
    reader, truth, builder = random_store["reader"], random_store["truth"], random_store["builder"]
    layer_nodes = {i: n for i, n in truth["nodes"].items() if n["tags"].get("natural") == "tree"}
    assert len(layer_nodes) == 250
    for box in _query_boxes(builder):
        expected = {i for i, n in layer_nodes.items() if _intersects((n["lon"], n["lat"], n["lon"], n["lat"]), box)}
        candidates = reader.candidate_node_ids(box)
        assert expected <= candidates
        assert all(
            _intersects((layer_nodes[i]["lon"], layer_nodes[i]["lat"]) * 2, box, FLOAT32_TOLERANCE_DEG)
            for i in candidates - expected
        )


def test_relation_candidates_match_member_union_brute_force(random_store):
    reader, truth, builder = random_store["reader"], random_store["truth"], random_store["builder"]
    way_bboxes = _exact_way_bboxes(reader, truth)
    relation_bboxes = {}
    for relation_id, relation in truth["relations"].items():
        member_boxes = [way_bboxes[m["ref"]] for m in relation["members"] if m["type"] == "w"]
        relation_bboxes[relation_id] = (
            min(b[0] for b in member_boxes), min(b[1] for b in member_boxes),
            max(b[2] for b in member_boxes), max(b[3] for b in member_boxes),
        )
    assert len(relation_bboxes) == 25
    for box in _query_boxes(builder):
        expected = {i for i, b in relation_bboxes.items() if _intersects(b, box)}
        candidates = reader.candidate_relation_ids(box)
        assert expected <= candidates
        assert all(_intersects(relation_bboxes[i], box, FLOAT32_TOLERANCE_DEG) for i in candidates - expected)


def test_get_by_id_handles_more_than_one_sql_chunk(random_store):
    reader = random_store["reader"]
    node_ids = [row[0] for row in reader._conn.execute("SELECT id FROM nodes")]
    assert len(node_ids) > 900
    assert set(reader.get_nodes(node_ids)) == set(node_ids)


def test_layer_and_road_filters(edge_store):
    reader, ids, builder = edge_store["reader"], edge_store["ids"], edge_store["builder"]
    west, south = builder.lonlat(-1100, -1100)
    east, north = builder.lonlat(1100, 1100)
    box = (west, south, east, north)

    roads = reader.candidate_way_ids(box, roads=True)
    buildings = reader.candidate_way_ids(box, layer_mask=reader.layer_bits["buildings"])
    everything = reader.candidate_way_ids(box)

    assert ids["services_road"][1] in roads and ids["building_inside"][1] not in roads
    assert ids["building_inside"][1] in buildings and ids["services_road"][1] not in buildings
    assert ids["boundary_outer"][1] in everything
    assert ids["boundary_outer"][1] not in roads | buildings


def test_enclosing_lookup_is_diagnostic_and_candidate_only(edge_store):
    reader, ids, builder = edge_store["reader"], edge_store["ids"], edge_store["builder"]
    west, south = builder.lonlat(-100, -100)
    east, north = builder.lonlat(100, 100)
    box = (west, south, east, north)
    forest = ids["enclosing_forest"][1]
    assert forest in reader.enclosing_way_ids(box)
    # The R*Tree returns it as a candidate even though no segment lies inside the box (plan §7.1).
    assert forest in reader.candidate_way_ids(box)


def test_covers_uses_header_bbox(edge_store, random_store):
    reader = edge_store["reader"]
    assert reader.header_bbox == pytest.approx((18.9, 47.4, 19.2, 47.6))
    assert reader.covers((19.0, 47.45, 19.1, 47.55))
    assert not reader.covers((18.8, 47.45, 19.1, 47.55))
    assert not reader.covers((19.0, 47.45, 19.3, 47.55))
    assert random_store["reader"].header_bbox is None
    assert not random_store["reader"].covers((19.0, 47.45, 19.1, 47.55))
