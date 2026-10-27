"""Synthetic datasets for the M3 PBF bundle-source tests.

Every dataset is written to a PBF and loaded into a store in pytest tmp dirs. Parity tests feed
FakeOverpass the elements read back from that same PBF, so both paths see identical coordinates
(PBF stores 1e-7 degree fixed-point locations).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import osmium
from osmium.osm import mutable

from generator.core import pbf_store
from support.synthetic_osm import OsmBuilder, build_features, build_road_network

HEADER_BBOX = (18.9, 47.4, 19.2, 47.6)
# Bundle viewport giving dist_m = 1000, the size the M1 road/feature fixtures are designed for.
HALF_WIDTH_M = 420.0
HALF_HEIGHT_M = 560.0
EXTENT_M = 560
# Beyond the HEADER_BBOX east edge (~12 km east of the centre).
OUTSIDE_EXTRACT_X_M = 16_000

_MEMBER_CODE = {"node": "n", "way": "w", "relation": "r"}
_OVERPASS_TYPE = {"n": "node", "w": "way", "r": "relation"}


@dataclass
class Dataset:
    builder: OsmBuilder
    ids: dict[str, tuple[str, int]]
    # Elements present only in the PBF, deliberately incomplete; absent from the parity reference.
    truncated: set[tuple[str, int]] = field(default_factory=set)


def write_pbf(path: Path, builder: OsmBuilder, header_bbox=HEADER_BBOX) -> Path:
    header = osmium.io.Header()
    west, south, east, north = header_bbox
    header.add_box(osmium.osm.Box(osmium.osm.Location(west, south), osmium.osm.Location(east, north)))
    writer = osmium.SimpleWriter(str(path), header=header)
    try:
        for node in sorted(builder.nodes, key=lambda e: e["id"]):
            writer.add_node(mutable.Node(
                id=node["id"], location=osmium.osm.Location(node["lon"], node["lat"]), tags=node.get("tags", {}),
            ))
        for way in sorted(builder.ways, key=lambda e: e["id"]):
            writer.add_way(mutable.Way(id=way["id"], nodes=way["nodes"], tags=way.get("tags", {})))
        for relation in sorted(builder.relations, key=lambda e: e["id"]):
            members = [(_MEMBER_CODE[m["type"]], m["ref"], m["role"]) for m in relation["members"]]
            writer.add_relation(mutable.Relation(id=relation["id"], members=members, tags=relation.get("tags", {})))
    finally:
        writer.close()
    return path


def pbf_elements(path: Path, exclude: set[tuple[str, int]] = frozenset()) -> list[dict]:
    """Overpass-JSON-shaped elements read back from a PBF."""
    elements = []
    for obj in osmium.FileProcessor(str(path)):
        if obj.is_node():
            key, element = ("node", obj.id), {"type": "node", "id": obj.id, "lon": obj.location.lon, "lat": obj.location.lat}
        elif obj.is_way():
            key, element = ("way", obj.id), {"type": "way", "id": obj.id, "nodes": [n.ref for n in obj.nodes]}
        else:
            key, element = ("relation", obj.id), {
                "type": "relation", "id": obj.id,
                "members": [{"type": _OVERPASS_TYPE[m.type], "ref": m.ref, "role": m.role} for m in obj.members],
            }
        tags = dict(obj.tags)
        if tags or key[0] == "relation":
            element["tags"] = tags
        if key not in exclude:
            elements.append(element)
    return elements


def build_store(root: Path, dataset: Dataset) -> tuple[Path, pbf_store.PbfStoreReader]:
    root.mkdir(parents=True, exist_ok=True)
    pbf = write_pbf(root / "data.osm.pbf", dataset.builder)
    pbf_store.build_store(pbf, root / "store")
    return pbf, pbf_store.PbfStoreReader(root / "store", pbf_path=pbf)


def engine_dataset(*, with_coast: bool) -> Dataset:
    """M1 fixtures plus every tag family the Block, Building and Line engines read, and relation edge cases."""
    b = OsmBuilder()
    build_road_network(b)
    ids = dict(build_features(b).ids)

    # Buildings layer (gdf_all_raw) tag families used by the Building and Line engines.
    ids["building_part"] = ("way", b.rect(130, 130, 140, 140, {"building:part": "yes"}))
    ids["industrial"] = ("way", b.rect(-500, 100, -400, 200, {"landuse": "industrial"}))
    ids["parking"] = ("way", b.rect(-380, 100, -340, 140, {"amenity": "parking"}))
    ids["cemetery"] = ("way", b.rect(-300, 100, -250, 150, {"landuse": "cemetery"}))
    ids["square"] = ("way", b.rect(-200, 100, -150, 150, {"place": "square"}))
    ids["pedestrian_area"] = ("way", b.rect(-140, 100, -100, 150, {"highway": "pedestrian", "area": "yes"}))
    ids["beach"] = ("way", b.rect(800, -900, 900, -850, {"natural": "beach"}))
    ids["harbour"] = ("way", b.rect(650, -900, 750, -850, {"landuse": "harbour"}))
    ids["marina"] = ("way", b.rect(660, -840, 700, -820, {"amenity": "marina"}))
    ids["breakwater"] = ("way", b.line([(600, -700), (700, -700)], {"man_made": "breakwater"}))

    # Node-only and line features.
    ids["tree_outside"] = ("node", b.node(1300, 0, {"natural": "tree"}))
    ids["level_crossing"] = ("node", b.node(0, 800, {"railway": "level_crossing"}))
    ids["path"] = ("way", b.line([(-400, -600), (-200, -600)], {"highway": "path"}))
    ids["steps"] = ("way", b.line([(-150, -600), (-100, -600)], {"highway": "steps"}))
    ids["track"] = ("way", b.line([(-900, 400), (-700, 400)], {"highway": "track"}))
    ids["canal"] = ("way", b.line([(-800, -700), (800, -700)], {"waterway": "canal"}))
    ids["basin"] = ("way", b.rect(-600, -500, -550, -450, {"landuse": "basin"}))

    # Relation selected only through an untagged label node; its outer ring encloses the query box.
    reserve_outer = b.rect(-2000, -2000, 2000, 2000)
    label = b.node(0, 200)
    ids["reserve_by_label"] = ("relation", b.relation(
        [("way", reserve_outer, "outer"), ("node", label, "label")],
        {"type": "boundary", "leisure": "nature_reserve"},
    ))
    # Nested relation member (never expanded by Overpass recursion or by the store).
    sub_outer = b.rect(300, -150, 380, -100)
    sub_rel = b.relation([("way", sub_outer, "outer")], {"type": "multipolygon", "leisure": "garden"})
    garden_outer = b.rect(250, -200, 450, -50)
    ids["garden_nested"] = ("relation", b.relation(
        [("way", garden_outer, "outer"), ("relation", sub_rel, "subarea")],
        {"type": "multipolygon", "leisure": "garden"},
    ))
    # Relation whose label node is absent from the extract (geometry needs only member ways).
    park_outer = b.rect(-950, 700, -850, 800)
    ids["park_missing_label_node"] = ("relation", b.relation(
        [("way", park_outer, "outer"), ("node", 999_990, "label")],
        {"type": "multipolygon", "leisure": "park"},
    ))
    # Complete way crossing the extract boundary (Geofabrik keeps complete ways).
    ids["rail_cross_border"] = ("way", b.line([(-200, 850), (OUTSIDE_EXTRACT_X_M, 850)], {"railway": "rail"}))

    if with_coast:
        ids["coastline"] = ("way", b.line([(-1600, -950), (1600, -950)], {"natural": "coastline"}))
        ids["island_way"] = ("way", b.rect(-100, -900, 0, -860, {"place": "island"}))
        island_outer = b.rect(100, -900, 200, -860)
        ids["island_relation"] = ("relation", b.relation(
            [("way", island_outer, "outer")], {"type": "multipolygon", "natural": "island"},
        ))
    return Dataset(builder=b, ids=ids)


def truncated_dataset() -> Dataset:
    """``engine_dataset`` plus elements whose node locations are missing (extract-border truncation)."""
    data = engine_dataset(with_coast=False)
    b, ids = data.builder, data.ids

    ids["truncated_road"] = ("way", b.way([b.node(-700, 300), 999_001, b.node(-700, 500)], {"highway": "residential"}))
    n1, n2, n3 = b.node(50, 300), b.node(80, 300), b.node(80, 330)
    ids["truncated_building"] = ("way", b.way([n1, n2, n3, 999_002, n1], {"building": "yes"}))
    m1, m2, m3 = b.node(-100, 400), b.node(0, 400), b.node(0, 500)
    truncated_outer = b.way([m1, m2, m3, 999_003, m1])
    ids["truncated_outer"] = ("way", truncated_outer)
    ids["water_with_truncated_member"] = ("relation", b.relation(
        [("way", truncated_outer, "outer")], {"type": "multipolygon", "natural": "water"},
    ))
    # Road cut at the extract boundary: its outside node was not exported.
    ids["border_cut_road"] = ("way", b.way([b.node(500, 900), b.node(900, 900), 999_004], {"highway": "primary"}))

    data.truncated = {
        ids["truncated_road"], ids["truncated_building"], ids["truncated_outer"],
        ids["water_with_truncated_member"], ids["border_cut_road"],
    }
    return data
