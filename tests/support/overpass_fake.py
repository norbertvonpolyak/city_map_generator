"""Offline stand-in for OSMnx's Overpass download functions.

This is a TEST FIXTURE for exercising OSMnx's client-side processing. It is NOT proof of how the real
Overpass server selects elements. Its selection rule is an explicit assumption (migration plan §7.1):

- road ways: the custom filter regex is applied with ``re.search`` (unanchored, case-sensitive);
- ways: selected when their node line intersects the query polygon;
- relations: selected when a member way is selected or a member node lies inside the polygon;
- recursion returns all nodes of selected ways and all members (and their nodes) of selected relations.

``selection="all"`` ignores geometry and returns every tag-matching element.
"""

from __future__ import annotations

import copy
import re

from osmnx import _overpass
from shapely.geometry import LineString, Point

_FILTER_RE = re.compile(r'^\["(?P<key>[^"]+)"~"(?P<pattern>[^"]+)"\]$')


def _tags_match(element_tags: dict, query_tags: dict) -> bool:
    for key, value in query_tags.items():
        if key not in element_tags:
            continue
        if value is True:
            return True
        if isinstance(value, str) and element_tags[key] == value:
            return True
        if isinstance(value, list) and element_tags[key] in value:
            return True
    return False


class FakeOverpass:
    def __init__(self, elements: list[dict], selection: str = "assumed") -> None:
        if selection not in {"assumed", "all"}:
            raise ValueError(selection)
        self.selection = selection
        self._nodes = {e["id"]: e for e in elements if e["type"] == "node"}
        self._ways = {e["id"]: e for e in elements if e["type"] == "way"}
        self._relations = {e["id"]: e for e in elements if e["type"] == "relation"}
        self.network_calls: list[tuple] = []
        self.feature_calls: list[tuple] = []

    def install(self, monkeypatch) -> "FakeOverpass":
        monkeypatch.setattr(_overpass, "_download_overpass_network", self.download_network)
        monkeypatch.setattr(_overpass, "_download_overpass_features", self.download_features)
        return self

    def _way_line(self, way: dict):
        coords = [(self._nodes[n]["lon"], self._nodes[n]["lat"]) for n in way["nodes"] if n in self._nodes]
        return LineString(coords) if len(coords) > 1 else Point(coords[0])

    def _way_hits(self, way: dict, polygon) -> bool:
        return self.selection == "all" or self._way_line(way).intersects(polygon)

    def _node_hits(self, node: dict, polygon) -> bool:
        return self.selection == "all" or Point(node["lon"], node["lat"]).intersects(polygon)

    def _response(self, node_ids: set, way_ids: set, relation_ids: set) -> list[dict]:
        for way_id in way_ids:
            node_ids.update(n for n in self._ways[way_id]["nodes"] if n in self._nodes)
        elements = (
            [self._nodes[i] for i in sorted(node_ids)]
            + [self._ways[i] for i in sorted(way_ids)]
            + [self._relations[i] for i in sorted(relation_ids)]
        )
        # OSMnx mutates response elements in place, so every call gets fresh copies.
        return [{"elements": copy.deepcopy(elements)}]

    def select_network(self, polygon, custom_filter: str) -> list[dict]:
        match = _FILTER_RE.match(custom_filter)
        if match is None:
            raise ValueError(f"Unsupported custom_filter: {custom_filter!r}")
        key, pattern = match.group("key"), re.compile(match.group("pattern"))
        way_ids = {
            way_id for way_id, way in self._ways.items()
            if key in way.get("tags", {}) and pattern.search(way["tags"][key]) and self._way_hits(way, polygon)
        }
        return self._response(set(), way_ids, set())

    def select_features(self, polygon, tags: dict) -> list[dict]:
        node_ids = {
            i for i, n in self._nodes.items()
            if _tags_match(n.get("tags", {}), tags) and self._node_hits(n, polygon)
        }
        way_ids = {
            i for i, w in self._ways.items()
            if _tags_match(w.get("tags", {}), tags) and self._way_hits(w, polygon)
        }
        relation_ids = set()
        for relation_id, relation in self._relations.items():
            if not _tags_match(relation.get("tags", {}), tags):
                continue
            members = relation["members"]
            if self.selection == "all" or any(
                (m["type"] == "way" and m["ref"] in self._ways and self._way_hits(self._ways[m["ref"]], polygon))
                or (m["type"] == "node" and m["ref"] in self._nodes and self._node_hits(self._nodes[m["ref"]], polygon))
                for m in members
            ):
                relation_ids.add(relation_id)
                way_ids.update(m["ref"] for m in members if m["type"] == "way" and m["ref"] in self._ways)
                node_ids.update(m["ref"] for m in members if m["type"] == "node" and m["ref"] in self._nodes)
        return self._response(node_ids, way_ids, relation_ids)

    def download_network(self, polygon, network_type, custom_filter):
        self.network_calls.append((polygon, network_type, custom_filter))
        return self.select_network(polygon, custom_filter)

    def download_features(self, polygon, tags):
        self.feature_calls.append((polygon, tags))
        return self.select_features(polygon, tags)
