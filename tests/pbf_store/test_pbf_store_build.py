"""M2 store build: raw element preservation, selection rules, reference resolution, missing references."""

from __future__ import annotations

import json

import pytest
from osmnx import features as ox_features
from osmnx._errors import InsufficientResponseError
from shapely.geometry import Polygon

from generator.core import pbf_store
from pbf_synthetic import (
    HEADER_BBOX,
    MISSING_MEMBER_WAY,
    MISSING_RELATION,
    build_store_dataset,
    overpass_elements,
    read_pbf,
    write_pbf,
)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("store_build")
    builder, ids = build_store_dataset()
    pbf = write_pbf(root / "synthetic.osm.pbf", builder, header_options={
        "osmosis_replication_timestamp": "2026-09-18T20:21:10Z",
        "osmosis_replication_sequence_number": "4914",
    })
    result = pbf_store.build_store(pbf, root / "store")
    reader = pbf_store.PbfStoreReader(root / "store", pbf_path=pbf)
    yield {"reader": reader, "ids": ids, "truth": read_pbf(pbf), "pbf": pbf, "result": result, "root": root}
    reader.close()


def _all_ids(reader, table):
    return {row[0] for row in reader._conn.execute(f"SELECT id FROM {table}")}


def test_raw_elements_are_preserved_exactly(built):
    reader, truth = built["reader"], built["truth"]

    ways = reader.get_ways(_all_ids(reader, "ways"))
    assert ways
    for way_id, way in ways.items():
        assert way["tags"] == truth["ways"][way_id]["tags"]
        assert way["node_refs"] == truth["ways"][way_id]["node_refs"]

    nodes = reader.get_nodes(_all_ids(reader, "nodes"))
    for node_id, node in nodes.items():
        assert (node["lon"], node["lat"]) == (truth["nodes"][node_id]["lon"], truth["nodes"][node_id]["lat"])
        assert node["tags"] == truth["nodes"][node_id]["tags"]

    relations = reader.get_relations(_all_ids(reader, "relations"))
    for relation_id, relation in relations.items():
        assert relation["tags"] == truth["relations"][relation_id]["tags"]
        assert relation["members"] == truth["relations"][relation_id]["members"]


def test_duplicate_node_refs_and_utf8_tags(built):
    reader, ids = built["reader"], built["ids"]
    way = reader.get_ways([ids["dup_building"][1]])[ids["dup_building"][1]]
    assert way["tags"]["name"] == "Fő tér ünnep"
    refs = way["node_refs"]
    assert len(refs) == 5 and refs[1] == refs[2] and refs[0] == refs[-1]


def test_road_regex_selection(built):
    reader, ids = built["reader"], built["ids"]
    stored = _all_ids(reader, "ways")
    services = reader.get_ways([ids["services_road"][1]])[ids["services_road"][1]]
    assert services["is_road"]
    assert ids["cycleway"][1] not in stored


def test_unselected_elements_are_not_stored(built):
    reader, ids = built["reader"], built["ids"]
    assert ids["bench_node"][1] not in _all_ids(reader, "nodes")
    assert ids["route_member"][1] not in _all_ids(reader, "ways")
    assert ids["nested_outer"][1] not in _all_ids(reader, "ways")


@pytest.mark.parametrize("layer_name", sorted(pbf_store.TagRules.from_production().layer_tags))
def test_layer_flags_match_osmnx_feature_selection(built, layer_name):
    reader, truth = built["reader"], built["truth"]
    rules = pbf_store.TagRules.from_production()
    tags = rules.layer_tags[layer_name]
    bit = reader.layer_bits[layer_name]

    try:
        gdf = ox_features._create_gdf([{"elements": overpass_elements(truth)}], Polygon(), tags)
        osmnx_ids = set(gdf.index)
    except InsufficientResponseError:
        osmnx_ids = set()

    conn = reader._conn
    store_ids = {("node", r[0]) for r in conn.execute("SELECT id FROM nodes WHERE layers & ? != 0", (bit,))}
    store_ids |= {("way", r[0]) for r in conn.execute("SELECT id FROM ways WHERE layers & ? != 0", (bit,))}
    store_ids |= {("relation", r[0]) for r in conn.execute("SELECT id FROM relations WHERE layers & ? != 0", (bit,))}
    # OSMnx cannot build geometry for elements with missing references; those are recorded, not dropped.
    incomplete = {("way", r[0]) for r in conn.execute("SELECT id FROM ways WHERE missing_nodes > 0")}
    incomplete |= {("relation", r[0]) for r in conn.execute("SELECT id FROM relations WHERE missing_members > 0")}

    assert osmnx_ids == store_ids - incomplete


def test_only_pass_a_selected_relations_are_stored(built):
    reader, ids, counts = built["reader"], built["ids"], built["result"].counts
    assert _all_ids(reader, "relations") == {
        ids["water_with_hole"][1], ids["water_missing_member"][1], ids["boundary"][1],
    }
    assert counts["selected_relations"] == 3
    # The nested multipolygon is tracked via add_references and emitted by the ID filter, but not stored.
    assert counts["tracked_relations_not_stored"] == 1


def test_direct_members_are_stored_and_indexed(built):
    reader, ids = built["reader"], built["ids"]
    boundary_outer = reader.get_ways([ids["boundary_outer"][1]])[ids["boundary_outer"][1]]
    assert boundary_outer["layers"] == 0 and not boundary_outer["is_road"]
    assert ids["boundary_label"][1] in _all_ids(reader, "nodes")
    assert reader.relations_for_members(way_ids=[ids["boundary_outer"][1]]) == {ids["boundary"][1]}
    assert reader.relations_for_members(node_ids=[ids["boundary_label"][1]]) == {ids["boundary"][1]}


def test_nested_relations_stay_unresolved(built):
    reader, ids, counts = built["reader"], built["ids"], built["result"].counts
    boundary = reader.get_relations([ids["boundary"][1]])[ids["boundary"][1]]
    nested = [m for m in boundary["members"] if m["type"] == "r"]
    assert [m["ref"] for m in nested] == [ids["nested_mp"][1], MISSING_RELATION]
    assert boundary["nested_relation_members"] == 2
    assert boundary["missing_members"] == 0
    assert counts["nested_relation_refs"] == 2
    assert ids["nested_mp"][1] not in _all_ids(reader, "relations")


def test_missing_member_way_is_recorded(built):
    reader, ids, counts = built["reader"], built["ids"], built["result"].counts
    relation = reader.get_relations([ids["water_missing_member"][1]])[ids["water_missing_member"][1]]
    assert {"type": "w", "ref": MISSING_MEMBER_WAY, "role": "outer"} in relation["members"]
    assert relation["missing_members"] == 1
    assert relation["bbox"] is not None
    assert counts["relations_with_missing_members"] == 1
    assert counts["missing_member_refs"] == 1


def test_missing_node_locations_are_recorded(built):
    reader, ids, counts = built["reader"], built["ids"], built["result"].counts
    ways = reader.get_ways([ids["partial_way"][1], ids["no_location_way"][1]])
    partial, empty = ways[ids["partial_way"][1]], ways[ids["no_location_way"][1]]
    assert partial["missing_nodes"] == 1 and partial["bbox"] is not None
    assert partial["bbox"][0] == partial["bbox"][2] and partial["bbox"][1] == partial["bbox"][3]
    assert empty["missing_nodes"] == 3 and empty["bbox"] is None
    rtree_ids = {r[0] for r in reader._conn.execute("SELECT id FROM rtree_ways")}
    assert ids["no_location_way"][1] not in rtree_ids
    assert counts["ways_with_missing_nodes"] == 2
    assert counts["missing_node_refs"] == 4
    assert counts["ways_without_location"] == 1


def test_multipolygon_hole_assembles_from_store_via_osmnx(built):
    reader, ids = built["reader"], built["ids"]
    relation_id = ids["water_with_hole"][1]
    relation = reader.get_relations([relation_id])[relation_id]
    way_ids = [m["ref"] for m in relation["members"] if m["type"] == "w"]
    ways = reader.get_ways(way_ids)
    nodes = reader.get_nodes({ref for way in ways.values() for ref in way["node_refs"]})

    elements = [{"type": "node", "id": n["id"], "lon": n["lon"], "lat": n["lat"]} for n in nodes.values()]
    elements += [{"type": "way", "id": w["id"], "nodes": w["node_refs"]} for w in ways.values()]
    elements.append({
        "type": "relation", "id": relation_id, "tags": relation["tags"],
        "members": [{"type": {"n": "node", "w": "way", "r": "relation"}[m["type"]], "ref": m["ref"], "role": m["role"]}
                    for m in relation["members"]],
    })
    gdf = ox_features._create_gdf([{"elements": elements}], Polygon(), {"natural": ["water"]})
    geometry = gdf.loc[("relation", relation_id)].geometry
    assert geometry.geom_type == "Polygon"
    assert len(geometry.interiors) == 1


def test_metadata_records_versions_and_source(built):
    reader, pbf = built["reader"], built["pbf"]
    meta = reader.meta
    assert meta["status"] == "complete"
    assert meta["schema_version"] == str(pbf_store.SCHEMA_VERSION)
    assert meta["preprocess_version"] == str(pbf_store.PREPROCESS_VERSION)
    assert meta["tag_rules_hash"] == pbf_store.TagRules.from_production().rules_hash()
    assert meta["pbf_size"] == str(pbf.stat().st_size)
    assert meta["pbf_sha256"] == pbf_store.file_sha256(pbf)
    assert meta["osmnx_version"] == "2.0.7"
    assert meta["pyosmium_version"] and meta["libosmium_version"]
    header = pbf_store.read_pbf_header(pbf)
    assert json.loads(meta["pbf_header_bbox"]) == pytest.approx(list(HEADER_BBOX))
    assert meta["pbf_replication_timestamp"] == (header["replication_timestamp"] or "")
    assert meta["pbf_replication_sequence"] == (header["replication_sequence"] or "")
    counts = json.loads(meta["counts"])
    assert counts == built["result"].counts
    assert {"pass_a_s", "pass_b_s", "index_s", "nodes", "ways", "relations"} <= set(counts)
