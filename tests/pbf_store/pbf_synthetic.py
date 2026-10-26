"""Synthetic PBF fixtures for the M2 store tests (written into pytest tmp dirs only)."""

from __future__ import annotations

import copy
import random
from pathlib import Path

import osmium
from osmium.osm import mutable

from support.synthetic_osm import OsmBuilder, build_features, build_road_network

_MEMBER_TYPE = {"node": "n", "way": "w", "relation": "r"}
_OVERPASS_TYPE = {"n": "node", "w": "way", "r": "relation"}
HEADER_BBOX = (18.9, 47.4, 19.2, 47.6)
MISSING_MEMBER_WAY = 2999
MISSING_RELATION = 9999


def write_pbf(path: Path, builder: OsmBuilder, header_bbox=HEADER_BBOX, header_options: dict | None = None) -> Path:
    header = osmium.io.Header()
    if header_bbox is not None:
        west, south, east, north = header_bbox
        header.add_box(osmium.osm.Box(osmium.osm.Location(west, south), osmium.osm.Location(east, north)))
    for key, value in (header_options or {}).items():
        header.set(key, value)
    writer = osmium.SimpleWriter(str(path), header=header)
    try:
        for node in sorted(builder.nodes, key=lambda e: e["id"]):
            writer.add_node(mutable.Node(
                id=node["id"], location=osmium.osm.Location(node["lon"], node["lat"]), tags=node.get("tags", {}),
            ))
        for way in sorted(builder.ways, key=lambda e: e["id"]):
            writer.add_way(mutable.Way(id=way["id"], nodes=way["nodes"], tags=way.get("tags", {})))
        for relation in sorted(builder.relations, key=lambda e: e["id"]):
            members = [(_MEMBER_TYPE[m["type"]], m["ref"], m["role"]) for m in relation["members"]]
            writer.add_relation(mutable.Relation(id=relation["id"], members=members, tags=relation.get("tags", {})))
    finally:
        writer.close()
    return path


def read_pbf(path: Path) -> dict:
    """Unfiltered ground-truth read of every element in a PBF."""
    data = {"nodes": {}, "ways": {}, "relations": {}}
    for obj in osmium.FileProcessor(str(path)):
        if obj.is_node():
            data["nodes"][obj.id] = {"lon": obj.location.lon, "lat": obj.location.lat, "tags": dict(obj.tags)}
        elif obj.is_way():
            data["ways"][obj.id] = {"node_refs": [n.ref for n in obj.nodes], "tags": dict(obj.tags)}
        elif obj.is_relation():
            data["relations"][obj.id] = {
                "members": [{"type": m.type, "ref": m.ref, "role": m.role} for m in obj.members],
                "tags": dict(obj.tags),
            }
    return data


def overpass_elements(data: dict) -> list[dict]:
    """Overpass-JSON-shaped copy of a ``read_pbf`` result."""
    elements = []
    for node_id, node in data["nodes"].items():
        element = {"type": "node", "id": node_id, "lon": node["lon"], "lat": node["lat"]}
        if node["tags"]:
            element["tags"] = dict(node["tags"])
        elements.append(element)
    for way_id, way in data["ways"].items():
        element = {"type": "way", "id": way_id, "nodes": list(way["node_refs"])}
        if way["tags"]:
            element["tags"] = dict(way["tags"])
        elements.append(element)
    for relation_id, relation in data["relations"].items():
        elements.append({
            "type": "relation", "id": relation_id, "tags": dict(relation["tags"]),
            "members": [{"type": _OVERPASS_TYPE[m["type"]], "ref": m["ref"], "role": m["role"]} for m in relation["members"]],
        })
    return copy.deepcopy(elements)


def build_store_dataset() -> tuple[OsmBuilder, dict[str, tuple[str, int]]]:
    """M1 road/feature fixtures plus reference-resolution and extract-boundary edge cases."""
    b = OsmBuilder()
    build_road_network(b)
    ids = dict(build_features(b).ids)

    n1, n2, n3 = b.node(150, -150), b.node(180, -150), b.node(180, -120)
    ids["dup_building"] = ("way", b.way([n1, n2, n2, n3, n1], {"building": "yes", "name": "Fő tér ünnep"}))
    ids["services_road"] = ("way", b.line([(-50, 300), (50, 300)], {"highway": "services"}))
    ids["cycleway"] = ("way", b.line([(-50, 350), (50, 350)], {"highway": "cycleway"}))
    ids["bench_node"] = ("node", b.node(10, 10, {"amenity": "bench"}))

    route_member = b.line([(-200, 700), (200, 700)])
    ids["route_member"] = ("way", route_member)
    ids["route"] = ("relation", b.relation(
        [("way", route_member, ""), ("relation", ids["water_with_hole"][1], "")],
        {"type": "route", "natural": "water"},
    ))

    nested_outer = b.rect(700, 700, 800, 800)
    ids["nested_outer"] = ("way", nested_outer)
    ids["nested_mp"] = ("relation", b.relation([("way", nested_outer, "outer")], {"type": "multipolygon"}))
    boundary_outer = b.rect(600, 600, 900, 900)
    ids["boundary_outer"] = ("way", boundary_outer)
    label = b.node(750, 650)
    ids["boundary_label"] = ("node", label)
    ids["boundary"] = ("relation", b.relation(
        [
            ("way", boundary_outer, "outer"),
            ("node", label, "label"),
            ("relation", ids["nested_mp"][1], "subarea"),
            ("relation", MISSING_RELATION, "subarea"),
        ],
        {"type": "boundary", "natural": "water"},
    ))

    kept = b.node(-900, -900)
    ids["partial_way"] = ("way", b.way([kept, 999998], {"highway": "residential"}))
    ids["no_location_way"] = ("way", b.way([999990, 999991, 999990], {"building": "yes"}))
    assert max(w["id"] for w in b.ways) < MISSING_MEMBER_WAY
    return b, ids


def build_random_dataset(seed: int = 7, n_ways: int = 300, n_nodes: int = 250, n_relations: int = 25) -> OsmBuilder:
    rng = random.Random(seed)
    b = OsmBuilder()
    for index in range(n_ways):
        cx, cy = rng.uniform(-3000, 3000), rng.uniform(-3000, 3000)
        points = [(cx + rng.uniform(-250, 250), cy + rng.uniform(-250, 250)) for _ in range(rng.randint(2, 5))]
        b.line(points, {"building": "yes"} if index % 2 else {"highway": "residential"})
    for _ in range(n_nodes):
        b.node(rng.uniform(-3500, 3500), rng.uniform(-3500, 3500), {"natural": "tree"})
    for _ in range(n_relations):
        cx, cy = rng.uniform(-3000, 3000), rng.uniform(-3000, 3000)
        outer = b.rect(cx - 200, cy - 200, cx + 200, cy + 200)
        inner = b.rect(cx - 50, cy - 50, cx + 50, cy + 50)
        b.relation([("way", outer, "outer"), ("way", inner, "inner")], {"type": "multipolygon", "natural": "water"})
    return b
