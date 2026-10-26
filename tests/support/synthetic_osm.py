"""Synthetic OSM elements in Overpass JSON shape, positioned by metre offsets around a centre."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Same spherical radius OSMnx uses in utils_geo.bbox_from_point, so offsets line up with its query box.
EARTH_RADIUS_M = 6_371_009

CENTER_LAT = 47.497912345
CENTER_LON = 19.040234567


@dataclass
class OsmBuilder:
    lat0: float = CENTER_LAT
    lon0: float = CENTER_LON
    nodes: list[dict] = field(default_factory=list)
    ways: list[dict] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)
    _next_node: int = 1000
    _next_way: int = 2000
    _next_relation: int = 3000

    def lonlat(self, x_m: float, y_m: float) -> tuple[float, float]:
        lat = self.lat0 + math.degrees(y_m / EARTH_RADIUS_M)
        lon = self.lon0 + math.degrees(x_m / EARTH_RADIUS_M) / math.cos(math.radians(self.lat0))
        return lon, lat

    def node(self, x_m: float, y_m: float, tags: dict | None = None) -> int:
        lon, lat = self.lonlat(x_m, y_m)
        node_id = self._next_node
        self._next_node += 1
        element = {"type": "node", "id": node_id, "lat": lat, "lon": lon}
        if tags:
            element["tags"] = dict(tags)
        self.nodes.append(element)
        return node_id

    def way(self, node_ids: list[int], tags: dict | None = None) -> int:
        way_id = self._next_way
        self._next_way += 1
        element = {"type": "way", "id": way_id, "nodes": list(node_ids)}
        if tags:
            element["tags"] = dict(tags)
        self.ways.append(element)
        return way_id

    def line(self, coords_m: list[tuple[float, float]], tags: dict | None = None) -> int:
        return self.way([self.node(x, y) for x, y in coords_m], tags)

    def closed_way(self, coords_m: list[tuple[float, float]], tags: dict | None = None) -> int:
        node_ids = [self.node(x, y) for x, y in coords_m]
        return self.way([*node_ids, node_ids[0]], tags)

    def rect(self, minx: float, miny: float, maxx: float, maxy: float, tags: dict | None = None) -> int:
        return self.closed_way([(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)], tags)

    def relation(self, members: list[tuple[str, int, str]], tags: dict) -> int:
        relation_id = self._next_relation
        self._next_relation += 1
        self.relations.append({
            "type": "relation",
            "id": relation_id,
            "members": [{"type": t, "ref": ref, "role": role} for t, ref, role in members],
            "tags": dict(tags),
        })
        return relation_id

    @property
    def elements(self) -> list[dict]:
        return [*self.nodes, *self.ways, *self.relations]


@dataclass
class RoadNetwork:
    builder: OsmBuilder
    nodes: dict[str, int]
    ways: dict[str, int]


def build_road_network(builder: OsmBuilder | None = None) -> RoadNetwork:
    """Road graph fixture designed for a 1000 m OSMnx query box around the centre.

    East branch ends at x=1200 m (inside the 500 m topology buffer, outside the box).
    """
    b = builder or OsmBuilder()
    n = {
        "a": b.node(-600, 0), "b": b.node(-300, 0), "c": b.node(0, 0),
        "d": b.node(300, 0), "e": b.node(600, 0), "f": b.node(900, 0), "g": b.node(1200, 0),
        "n1": b.node(0, 600), "s1": b.node(0, -600),
        "p1": b.node(-300, 600), "p2": b.node(-600, 600),
        "q1": b.node(400, -500), "q2": b.node(700, -500),
    }
    w = {
        "west_inner": b.way([n["c"], n["b"]], {"highway": "residential", "name": "West"}),
        "west_bridge": b.way([n["b"], n["a"]], {"highway": "residential", "bridge": "yes"}),
        "east": b.way([n["c"], n["d"], n["e"]], {"highway": "residential"}),
        "east_out": b.way([n["e"], n["f"], n["g"]], {"highway": "residential"}),
        "north_south_oneway": b.way([n["n1"], n["c"], n["s1"]], {"highway": "secondary", "oneway": "yes"}),
        "north_tertiary": b.way([n["n1"], n["p1"]], {"highway": "tertiary"}),
        "north_residential": b.way([n["p1"], n["p2"]], {"highway": "residential"}),
        "fragment": b.way([n["q1"], n["q2"]], {"highway": "residential"}),
    }
    return RoadNetwork(builder=b, nodes=n, ways=w)


@dataclass
class FeatureSet:
    builder: OsmBuilder
    ids: dict[str, tuple[str, int]]


def build_features(builder: OsmBuilder | None = None) -> FeatureSet:
    """Feature fixture designed for a 1000 m OSMnx query box around the centre."""
    b = builder or OsmBuilder()
    ids: dict[str, tuple[str, int]] = {}

    ids["building_east"] = ("way", b.rect(950, -20, 1050, 20, {"building": "yes"}))
    ids["building_west"] = ("way", b.rect(-1050, -20, -950, 20, {"building": "yes"}))
    ids["building_north"] = ("way", b.rect(-20, 950, 20, 1050, {"building": "yes"}))
    ids["building_south"] = ("way", b.rect(-20, -1050, 20, -950, {"building": "yes"}))
    ids["building_inside"] = ("way", b.rect(100, 100, 120, 120, {"building": "yes"}))

    outer = b.rect(-400, -400, -100, -100)
    inner = b.rect(-300, -300, -200, -200)
    ids["water_with_hole"] = ("relation", b.relation(
        [("way", outer, "outer"), ("way", inner, "inner")],
        {"type": "multipolygon", "natural": "water"},
    ))
    partial_outer = b.rect(100, -400, 200, -300)
    ids["water_missing_member"] = ("relation", b.relation(
        [("way", partial_outer, "outer"), ("way", 2999, "outer")],
        {"type": "multipolygon", "natural": "water"},
    ))

    ids["park_area_no"] = ("way", b.rect(300, 300, 400, 400, {"leisure": "park", "area": "no"}))
    ids["park"] = ("way", b.rect(500, 500, 600, 600, {"leisure": "park"}))
    ids["pond"] = ("way", b.rect(-600, 500, -500, 600, {"natural": "water"}))
    ids["grass"] = ("way", b.rect(-800, -200, -700, -100, {"landuse": "grass"}))
    ids["enclosing_forest"] = ("way", b.rect(-1500, -1500, 1500, 1500, {"landuse": "forest"}))

    ids["tree"] = ("node", b.node(50, 50, {"natural": "tree"}))
    ids["river"] = ("way", b.line([(-800, -800), (800, -800)], {"waterway": "river"}))
    ids["rail"] = ("way", b.line([(-800, 800), (800, 800)], {"railway": "rail"}))
    ids["footway"] = ("way", b.line([(200, -200), (400, -200)], {"highway": "footway"}))
    ids["pier"] = ("way", b.line([(600, -600), (700, -600)], {"man_made": "pier"}))
    return FeatureSet(builder=b, ids=ids)
