"""Isolated PBF-store bundle source (Geofabrik migration plan, M3; opt-in production entry point since M4).

Only ``osm_bundle_cache.load_or_build_shared_osm_bundle`` imports this module, lazily, when
``MAPCANVAS_OSM_SOURCE=pbf``; Overpass stays the default. Configuration: ``MAPCANVAS_PBF_STORE_DIR``
(required) and ``MAPCANVAS_PBF_PATH`` (optional; validates source size and mtime against the store).

``PbfBundleSource.load_bundle`` has the keyword signature of
``osm_bundle_cache.load_or_build_shared_osm_bundle`` and returns the same bundle dict, built from a
validated ``PbfStoreReader`` through OSMnx 2.0.7's own client-side processing:

- roads: ``osmnx.graph._create_graph`` followed by the exact ``graph_from_polygon`` steps
  (500 m buffer, truncate, largest component, simplify, truncate, largest component, street_count);
- features: ``osmnx.features._create_gdf`` per layer of ``_FEATURE_LAYER_SPECS``, with the same
  ``InsufficientResponseError`` handling as ``_load_or_build_feature_layer``.

Element selection emulates Overpass ``(poly:...)`` under the assumption documented in plan §7.1 (the
same rule as ``tests/support/overpass_fake.py``): a way is selected when its node line intersects the
query polygon; a relation when a member way is selected or a member node lies in the polygon; recursion
returns all nodes of selected ways and all members of selected relations (no nested relations).

Extract-border truncation is never repaired: ways with missing node locations are dropped and counted;
a relation that thereby loses a member way gets a null geometry from OSMnx and is removed by OSMnx.
"""

from __future__ import annotations

import inspect
import math
import os
import time

import geopandas as gpd
import networkx as nx
import osmnx as ox
import shapely
from osmnx import features as ox_features
from osmnx import graph as ox_graph
from osmnx._errors import InsufficientResponseError
from shapely.geometry import LineString, Point

from generator.core import osm_bundle_cache
from generator.core.pbf_store import Bbox, PbfStoreError, PbfStoreReader

SUPPORTED_OSMNX_VERSION = "2.0.7"
EXPECTED_PRIVATE_SIGNATURES = {
    "_create_graph": ["response_jsons", "bidirectional"],
    "_create_gdf": ["response_jsons", "polygon", "tags"],
}
# osmnx.graph.graph_from_polygon buffers the query polygon by this many metres before truncating.
ROAD_BUFFER_M = 500
# graph_from_point's default network_type; decides bidirectional edges via ox.settings.
ROAD_NETWORK_TYPE = "all"
STORE_DIR_ENV = "MAPCANVAS_PBF_STORE_DIR"
PBF_PATH_ENV = "MAPCANVAS_PBF_PATH"
_OVERPASS_MEMBER_TYPES = {"n": "node", "w": "way", "r": "relation"}


class OsmnxContractError(RuntimeError):
    pass


class CoverageError(PbfStoreError):
    pass


def check_osmnx_contract() -> None:
    if ox.__version__ != SUPPORTED_OSMNX_VERSION:
        raise OsmnxContractError(f"pbf_source requires osmnx=={SUPPORTED_OSMNX_VERSION}, found {ox.__version__}")
    for name, func in (("_create_graph", ox_graph._create_graph), ("_create_gdf", ox_features._create_gdf)):
        params = inspect.signature(func).parameters.values()
        # Both are called positionally, as OSMnx itself does.
        if [p.name for p in params] != EXPECTED_PRIVATE_SIGNATURES[name] or any(
            p.kind is not inspect.Parameter.POSITIONAL_OR_KEYWORD for p in params
        ):
            raise OsmnxContractError(f"osmnx private {name} signature changed: {[str(p) for p in params]}")


check_osmnx_contract()


def bundle_dist_m(half_width_m: float, half_height_m: float) -> int:
    """Same formula as osm_bundle_cache._build_shared_osm_bundle."""
    return int(math.ceil(math.sqrt(half_width_m**2 + half_height_m**2))) + 300


def query_polygon(center_lat: float, center_lon: float, dist_m: int):
    """The polygon features_from_point / graph_from_point query for ``dist=dist_m``."""
    return ox.utils_geo.bbox_to_poly(ox.utils_geo.bbox_from_point((center_lat, center_lon), dist_m))


def road_query_polygon(polygon):
    poly_proj, crs_utm = ox.projection.project_geometry(polygon)
    poly_buff, _ = ox.projection.project_geometry(poly_proj.buffer(ROAD_BUFFER_M), crs=crs_utm, to_latlong=True)
    return poly_buff


def _bbox(geometry) -> Bbox:
    west, south, east, north = geometry.bounds
    return (west, south, east, north)


def _node_element(node: dict) -> dict:
    element = {"type": "node", "id": node["id"], "lat": node["lat"], "lon": node["lon"]}
    if node["tags"]:
        element["tags"] = dict(node["tags"])
    return element


def _way_element(way: dict) -> dict:
    element = {"type": "way", "id": way["id"], "nodes": list(way["node_refs"])}
    if way["tags"]:
        element["tags"] = dict(way["tags"])
    return element


def _relation_element(relation: dict) -> dict:
    return {
        "type": "relation",
        "id": relation["id"],
        "tags": dict(relation["tags"]),
        "members": [
            {"type": _OVERPASS_MEMBER_TYPES[m["type"]], "ref": m["ref"], "role": m["role"]}
            for m in relation["members"]
        ],
    }


def _way_hits(ways: dict[int, dict], nodes: dict[int, dict], polygon) -> set[int]:
    """Way ids whose (present) node line intersects ``polygon``."""
    ids, geoms = [], []
    for way_id, way in ways.items():
        coords = [(nodes[r]["lon"], nodes[r]["lat"]) for r in way["node_refs"] if r in nodes]
        if not coords:
            continue
        ids.append(way_id)
        geoms.append(LineString(coords) if len(coords) > 1 else Point(coords[0]))
    if not ids:
        return set()
    shapely.prepare(polygon)
    mask = shapely.intersects(polygon, geoms)
    return {way_id for way_id, hit in zip(ids, mask) if hit}


def _node_hits(nodes: dict[int, dict], polygon) -> set[int]:
    if not nodes:
        return set()
    ids = list(nodes)
    points = shapely.points([nodes[i]["lon"] for i in ids], [nodes[i]["lat"] for i in ids])
    shapely.prepare(polygon)
    mask = shapely.intersects(polygon, points)
    return {node_id for node_id, hit in zip(ids, mask) if hit}


class _QueryArea:
    """All stored ways around the query polygon, fetched once and shared by every feature layer."""

    def __init__(self, reader: PbfStoreReader, polygon) -> None:
        self.polygon = polygon
        self.bbox = _bbox(polygon)
        self.ways = reader.get_ways(reader.candidate_way_ids(self.bbox))
        self.nodes = reader.get_nodes({r for w in self.ways.values() for r in w["node_refs"]})
        self.hits = _way_hits(self.ways, self.nodes, polygon)


class PbfBundleSource:
    """Builds runtime bundles from a validated local PBF store (no network, no pickle cache)."""

    def __init__(self, reader: PbfStoreReader) -> None:
        self.reader = reader
        self.last_stats: dict = {}

    # -- public -----------------------------------------------------------------

    def load_bundle(
        self,
        *,
        center_lat: float,
        center_lon: float,
        extent_m: int,
        half_width_m: float,
        half_height_m: float,
        use_cache: bool = True,
        include_building_features: bool = False,
        buildings_only_mode: bool = False,
    ) -> dict[str, object]:
        # extent_m and use_cache are accepted for signature parity only; the store is the cache.
        _ = (extent_m, use_cache)
        dist_m = bundle_dist_m(half_width_m, half_height_m)
        polygon = query_polygon(center_lat, center_lon, dist_m)
        road_polygon = road_query_polygon(polygon)
        if not self.reader.covers(_bbox(road_polygon)):
            raise CoverageError(
                f"Query box {_bbox(road_polygon)} (incl. {ROAD_BUFFER_M} m road buffer) is not inside the "
                f"PBF header bbox {self.reader.header_bbox}."
            )

        layer_names = osm_bundle_cache._select_required_feature_layers(include_building_features, buildings_only_mode)
        stats: dict = {
            "center": [center_lat, center_lon],
            "bundle_half_width_m": half_width_m,
            "bundle_half_height_m": half_height_m,
            "dist_m": dist_m,
            "query_bbox": list(_bbox(polygon)),
            "road_query_bbox": list(_bbox(road_polygon)),
            "include_building_features": include_building_features,
            "buildings_only_mode": buildings_only_mode,
            "layers_requested": list(layer_names),
            "timing_s": {},
            "layers": {},
        }
        self.last_stats = stats

        started = time.perf_counter()
        edges_raw = self._road_edges(polygon, road_polygon, stats)
        stats["timing_s"]["roads"] = round(time.perf_counter() - started, 3)

        started = time.perf_counter()
        area = _QueryArea(self.reader, polygon)
        stats["timing_s"]["area_selection"] = round(time.perf_counter() - started, 3)
        stats["area"] = {"candidate_ways": len(area.ways), "ways_intersecting": len(area.hits), "nodes": len(area.nodes)}

        feature_layers: dict[str, object] = {}
        for name in layer_names:
            started = time.perf_counter()
            feature_layers[name] = self._feature_layer(area, name, stats["layers"].setdefault(name, {}))
            stats["timing_s"][f"layer_{name}"] = round(time.perf_counter() - started, 3)

        return osm_bundle_cache._assemble_runtime_bundle(
            edges_raw=edges_raw,
            feature_layers=feature_layers,
            include_building_features=include_building_features,
            buildings_only_mode=buildings_only_mode,
        )

    # -- roads ------------------------------------------------------------------

    def _road_edges(self, polygon, road_polygon, stats: dict) -> gpd.GeoDataFrame:
        ways = self.reader.get_ways(self.reader.candidate_way_ids(_bbox(road_polygon), roads=True))
        nodes = self.reader.get_nodes({r for w in ways.values() for r in w["node_refs"]})
        hits = _way_hits(ways, nodes, road_polygon)
        incomplete = sorted(i for i in hits if ways[i]["missing_nodes"])
        selected = [ways[i] for i in sorted(hits) if not ways[i]["missing_nodes"]]
        node_ids = {r for w in selected for r in w["node_refs"]}
        elements = [_node_element(nodes[i]) for i in sorted(node_ids)] + [_way_element(w) for w in selected]

        bidirectional = ROAD_NETWORK_TYPE in ox.settings.bidirectional_network_types
        g_buff = ox_graph._create_graph([{"elements": elements}], bidirectional)
        g_buff = ox.truncate.truncate_graph_polygon(g_buff, road_polygon, truncate_by_edge=False)
        g_buff = ox.truncate.largest_component(g_buff, strongly=False)
        g_buff = ox.simplification.simplify_graph(g_buff)
        graph = ox.truncate.truncate_graph_polygon(g_buff, polygon, truncate_by_edge=False)
        graph = ox.truncate.largest_component(graph, strongly=False)
        nx.set_node_attributes(graph, values=ox.stats.count_streets_per_node(g_buff, nodes=graph.nodes), name="street_count")
        edges = ox.graph_to_gdfs(graph, nodes=False, edges=True)

        stats["roads"] = {
            "candidate_ways": len(ways),
            "selected_ways": len(selected),
            "incomplete_ways_dropped": len(incomplete),
            "incomplete_way_ids_sample": incomplete[:20],
            "nodes": len(node_ids),
            "graph_nodes": graph.number_of_nodes(),
            "edges": len(edges),
        }
        return edges

    # -- features ---------------------------------------------------------------

    def _feature_layer(self, area: _QueryArea, layer_name: str, stats: dict):
        spec = osm_bundle_cache._FEATURE_LAYER_SPECS[layer_name]
        tags = spec["tags"]
        bit = self.reader.layer_bits[layer_name]
        reader, polygon = self.reader, area.polygon

        selected_ways = {i for i in area.hits if area.ways[i]["layers"] & bit}
        selected_nodes = _node_hits(reader.get_nodes(reader.candidate_node_ids(area.bbox, layer_mask=bit)), polygon)

        candidates = reader.get_relations(reader.candidate_relation_ids(area.bbox, layer_mask=bit))
        member_nodes = reader.get_nodes({m["ref"] for r in candidates.values() for m in r["members"] if m["type"] == "n"})
        member_node_hits = _node_hits(member_nodes, polygon)
        relations = {
            rel_id: rel for rel_id, rel in candidates.items()
            if any(
                (m["type"] == "w" and m["ref"] in area.hits) or (m["type"] == "n" and m["ref"] in member_node_hits)
                for m in rel["members"]
            )
        }

        way_ids = selected_ways | {m["ref"] for r in relations.values() for m in r["members"] if m["type"] == "w"}
        ways = {i: area.ways[i] for i in way_ids if i in area.ways}
        ways.update(reader.get_ways(way_ids - ways.keys()))
        incomplete = sorted(i for i, w in ways.items() if w["missing_nodes"])
        for way_id in incomplete:
            ways.pop(way_id)

        node_ids = (
            {r for w in ways.values() for r in w["node_refs"]}
            | selected_nodes
            | {m["ref"] for r in relations.values() for m in r["members"] if m["type"] == "n"}
        )
        nodes = {i: area.nodes[i] for i in node_ids if i in area.nodes}
        nodes.update(reader.get_nodes(node_ids - nodes.keys()))

        elements = (
            [_node_element(nodes[i]) for i in sorted(nodes)]
            + [_way_element(ways[i]) for i in sorted(ways)]
            + [_relation_element(relations[i]) for i in sorted(relations)]
        )
        stats.update({
            "selected_ways": len(selected_ways),
            "selected_nodes": len(selected_nodes),
            "relations": len(relations),
            "relations_with_missing_members": sum(1 for r in relations.values() if r["missing_members"]),
            "relations_with_nested_members": sum(1 for r in relations.values() if r["nested_relation_members"]),
            "incomplete_ways_dropped": len(incomplete),
            "incomplete_way_ids_sample": incomplete[:20],
        })

        try:
            gdf = ox_features._create_gdf([{"elements": elements}], polygon, tags)
        except InsufficientResponseError:
            # Same outcomes as osm_bundle_cache._load_or_build_feature_layer.
            stats.update({"features": 0, "relations_in_result": 0, "empty": True})
            if layer_name == "islands":
                print("[PBF] Layer EMPTY [islands]")
                return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
            if spec["missing_message"]:
                print(spec["missing_message"])
                return None
            raise
        element_types = gdf.index.get_level_values("element")
        stats.update({
            "features": len(gdf),
            "relations_in_result": int((element_types == "relation").sum()),
            "relations_not_in_result": len(relations) - int((element_types == "relation").sum()),
            "empty": False,
        })
        return gdf


def load_bundle_from_env(**kwargs) -> dict[str, object]:
    """``MAPCANVAS_OSM_SOURCE=pbf`` entry point; no pickle cache is read or written."""
    store_dir = os.getenv(STORE_DIR_ENV, "").strip()
    if not store_dir:
        raise PbfStoreError(f"{STORE_DIR_ENV} must point to a built PBF store when MAPCANVAS_OSM_SOURCE=pbf.")
    pbf_path = os.getenv(PBF_PATH_ENV, "").strip() or None
    with PbfStoreReader(store_dir, pbf_path=pbf_path) as reader:
        bundle = PbfBundleSource(reader).load_bundle(**kwargs)
        print(f"[OSM] Source: PBF store {reader.store_path} (snapshot {reader.meta.get('pbf_replication_timestamp') or 'unknown'})")
    return bundle
