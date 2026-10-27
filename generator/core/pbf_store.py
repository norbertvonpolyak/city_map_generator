"""Isolated local OSM element store built from a regional PBF (Geofabrik migration plan, M2).

Not imported by any production module. The store keeps raw, uncut OSM elements (tags, ordered node
references, ordered relation members with roles) plus SQLite R*Tree bounding boxes for candidate
lookup only. Bounding boxes are never proof of complete or valid geometry.

Reference resolution (verified in M2 S1):
- pass A selects nodes/ways/relations by the production tag rules; for each selected
  multipolygon/boundary relation ``IdTracker.add_references`` is called while the object is alive;
- ``complete_backward_references(relation_depth=0)`` adds the nodes of every tracked way;
- pass B stores tracked nodes/ways, but relations only when pass A selected them. Nested relation
  members are kept as unresolved references and never expanded.

CLI: python -m generator.core.pbf_store {build,inspect,bench} --store-dir DIR [...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import statistics
import sys
import time
import uuid
from array import array
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Iterable, Iterator

import osmium
import osmium.filter
import osmium.version

SCHEMA_VERSION = 1
PREPROCESS_VERSION = 1
STORE_FILENAME = "osm_store.sqlite"
LOCK_FILENAME = ".build.lock"
BUILD_FILE_PREFIX = ".build-"
SELECTED_RELATION_TYPES = ("boundary", "multipolygon")
MEMBER_TYPE_CODES = {"n": 0, "w": 1, "r": 2}
STATUS_COMPLETE = "complete"
_SQL_CHUNK = 900
_INSERT_BATCH = 20_000
_ROAD_FILTER_RE = re.compile(r'^\["(?P<key>[^"]+)"~"(?P<pattern>[^"]+)"\]$')

Bbox = tuple[float, float, float, float]  # (west, south, east, north) in EPSG:4326 degrees


class PbfStoreError(RuntimeError):
    pass


class StoreValidationError(PbfStoreError):
    pass


class StoreLockedError(PbfStoreError):
    pass


# ---------------------------------------------------------------------------
# Tag rules
# ---------------------------------------------------------------------------

def parse_road_filter(custom_filter: str) -> tuple[str, str]:
    match = _ROAD_FILTER_RE.match(custom_filter)
    if match is None:
        raise PbfStoreError(f"Unsupported road custom filter: {custom_filter!r}")
    return match.group("key"), match.group("pattern")


@dataclass
class TagRules:
    """Per-layer tag selection with OSMnx `_filter_features` value semantics, plus the road regex."""

    layer_tags: dict[str, dict]
    road_key: str
    road_pattern: str
    _road_re: re.Pattern = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._road_re = re.compile(self.road_pattern)

    @classmethod
    def from_production(cls) -> "TagRules":
        from generator.core.osm_bundle_cache import _FEATURE_LAYER_SPECS, _ROAD_CUSTOM_FILTER

        key, pattern = parse_road_filter(_ROAD_CUSTOM_FILTER)
        return cls({name: spec["tags"] for name, spec in _FEATURE_LAYER_SPECS.items()}, key, pattern)

    @property
    def layer_bits(self) -> dict[str, int]:
        return {name: 1 << index for index, name in enumerate(sorted(self.layer_tags))}

    @property
    def selection_keys(self) -> list[str]:
        keys = {self.road_key}
        for tags in self.layer_tags.values():
            keys.update(tags)
        return sorted(keys)

    def layer_mask(self, tags: dict) -> int:
        if not tags:
            return 0
        mask = 0
        for name, bit in self.layer_bits.items():
            for key, value in self.layer_tags[name].items():
                if key not in tags:
                    continue
                if value is True or (isinstance(value, str) and tags[key] == value) or (
                    isinstance(value, list) and tags[key] in value
                ):
                    mask |= bit
                    break
        return mask

    def is_road(self, tags: dict) -> bool:
        value = tags.get(self.road_key) if tags else None
        # Overpass regex filters are unanchored; re.search mirrors that for this alternation pattern.
        return value is not None and self._road_re.search(value) is not None

    def rules_hash(self) -> str:
        payload = {
            "layers": self.layer_tags,
            "road": [self.road_key, self.road_pattern],
            "relation_types": list(SELECTED_RELATION_TYPES),
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Source identity
# ---------------------------------------------------------------------------

def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_pbf_header(pbf_path: Path) -> dict:
    reader = osmium.io.Reader(str(pbf_path), osmium.osm.osm_entity_bits.NOTHING)
    try:
        header = reader.header()
        box = header.box()
        bbox = None
        if box.valid():
            bbox = [box.bottom_left.lon, box.bottom_left.lat, box.top_right.lon, box.top_right.lat]
        return {
            "bbox": bbox,
            "replication_timestamp": header.get("osmosis_replication_timestamp") or None,
            "replication_sequence": header.get("osmosis_replication_sequence_number") or None,
            "generator": header.get("generator") or None,
            "multiple_object_versions": bool(header.has_multiple_object_versions),
        }
    finally:
        reader.close()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE nodes (
    id INTEGER PRIMARY KEY,
    lon REAL NOT NULL,
    lat REAL NOT NULL,
    tags TEXT,
    layers INTEGER NOT NULL
);
CREATE TABLE ways (
    id INTEGER PRIMARY KEY,
    tags TEXT NOT NULL,
    node_refs BLOB NOT NULL,
    layers INTEGER NOT NULL,
    is_road INTEGER NOT NULL,
    missing_nodes INTEGER NOT NULL,
    minx REAL, miny REAL, maxx REAL, maxy REAL
);
CREATE TABLE relations (
    id INTEGER PRIMARY KEY,
    tags TEXT NOT NULL,
    members TEXT NOT NULL,
    layers INTEGER NOT NULL,
    missing_members INTEGER NOT NULL DEFAULT 0,
    nested_relation_members INTEGER NOT NULL,
    minx REAL, miny REAL, maxx REAL, maxy REAL
);
CREATE TABLE relation_members (
    member_type INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    relation_id INTEGER NOT NULL,
    seq INTEGER NOT NULL
);
"""

_INDEX_SQL = """
CREATE INDEX relation_members_by_member ON relation_members (member_type, member_id);
CREATE VIRTUAL TABLE rtree_nodes USING rtree(id, minx, maxx, miny, maxy);
CREATE VIRTUAL TABLE rtree_ways USING rtree(id, minx, maxx, miny, maxy);
CREATE VIRTUAL TABLE rtree_relations USING rtree(id, minx, maxx, miny, maxy);
INSERT INTO rtree_nodes SELECT id, lon, lon, lat, lat FROM nodes WHERE layers != 0;
INSERT INTO rtree_ways SELECT id, minx, maxx, miny, maxy FROM ways WHERE minx IS NOT NULL;
"""


def _pack_refs(refs: list[int]) -> bytes:
    return array("q", refs).tobytes()


def _unpack_refs(blob: bytes) -> list[int]:
    values = array("q")
    values.frombytes(blob)
    return values.tolist()


def _tags_json(tags: dict) -> str:
    return json.dumps(tags, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

@dataclass
class BuildResult:
    store_path: Path
    counts: dict
    duration_s: float


class _BuildLock:
    def __init__(self, store_dir: Path, force: bool) -> None:
        self.path = store_dir / LOCK_FILENAME
        self.force = force
        self._fd: int | None = None

    def __enter__(self) -> "_BuildLock":
        if self.force and self.path.exists():
            self.path.unlink()
        try:
            self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise StoreLockedError(
                f"Build lock exists: {self.path}. Another build may be running; use force=True only if it is stale."
            ) from error
        os.write(self._fd, json.dumps({"pid": os.getpid(), "started_utc": _utc_now()}).encode("utf-8"))
        return self

    def __exit__(self, *exc) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def _select_pass_a(pbf_path: Path, rules: TagRules) -> tuple[osmium.IdTracker, set[int]]:
    tracker = osmium.IdTracker()
    selected_relations: set[int] = set()
    processor = osmium.FileProcessor(str(pbf_path)).with_filter(osmium.filter.KeyFilter(*rules.selection_keys))
    for obj in processor:
        tags = dict(obj.tags)
        if obj.is_node():
            if rules.layer_mask(tags):
                tracker.add_node(obj.id)
        elif obj.is_way():
            if rules.is_road(tags) or rules.layer_mask(tags):
                tracker.add_way(obj.id)
        elif obj.is_relation():
            if tags.get("type") in SELECTED_RELATION_TYPES and rules.layer_mask(tags):
                tracker.add_relation(obj.id)
                # Must run while pyosmium still owns a valid relation object.
                tracker.add_references(obj)
                selected_relations.add(obj.id)
    tracker.complete_backward_references(str(pbf_path), relation_depth=0)
    return tracker, selected_relations


def _write_pass_b(
    conn: sqlite3.Connection,
    pbf_path: Path,
    rules: TagRules,
    tracker: osmium.IdTracker,
    selected_relations: set[int],
    location_storage: str,
    counts: dict,
) -> None:
    node_rows: list[tuple] = []
    way_rows: list[tuple] = []
    relation_rows: list[tuple] = []
    member_rows: list[tuple] = []

    def flush(force: bool = False) -> None:
        if node_rows and (force or len(node_rows) >= _INSERT_BATCH):
            conn.executemany("INSERT INTO nodes VALUES (?, ?, ?, ?, ?)", node_rows)
            node_rows.clear()
        if way_rows and (force or len(way_rows) >= _INSERT_BATCH):
            conn.executemany("INSERT INTO ways VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", way_rows)
            way_rows.clear()
        if relation_rows and (force or len(relation_rows) >= _INSERT_BATCH):
            conn.executemany(
                "INSERT INTO relations (id, tags, members, layers, nested_relation_members) VALUES (?, ?, ?, ?, ?)",
                relation_rows,
            )
            relation_rows.clear()
        if member_rows and (force or len(member_rows) >= _INSERT_BATCH):
            conn.executemany("INSERT INTO relation_members VALUES (?, ?, ?, ?)", member_rows)
            member_rows.clear()

    processor = (
        osmium.FileProcessor(str(pbf_path))
        .with_locations(location_storage)
        .with_filter(tracker.id_filter())
    )
    for obj in processor:
        if obj.is_node():
            location = obj.location
            if not location.valid():
                counts["invalid_node_locations"] += 1
                continue
            tags = dict(obj.tags)
            node_rows.append((obj.id, location.lon, location.lat, _tags_json(tags) if tags else None, rules.layer_mask(tags)))
        elif obj.is_way():
            tags = dict(obj.tags)
            refs: list[int] = []
            lons: list[float] = []
            lats: list[float] = []
            for node_ref in obj.nodes:
                refs.append(node_ref.ref)
                location = node_ref.location
                if location.valid():
                    lons.append(location.lon)
                    lats.append(location.lat)
            missing = len(refs) - len(lons)
            bbox = (min(lons), min(lats), max(lons), max(lats)) if lons else (None, None, None, None)
            way_rows.append((
                obj.id, _tags_json(tags), _pack_refs(refs), rules.layer_mask(tags),
                int(rules.is_road(tags)), missing, *bbox,
            ))
            if missing:
                counts["ways_with_missing_nodes"] += 1
                counts["missing_node_refs"] += missing
            if not lons:
                counts["ways_without_location"] += 1
        elif obj.is_relation():
            if obj.id not in selected_relations:
                counts["tracked_relations_not_stored"] += 1
                continue
            tags = dict(obj.tags)
            members = [{"type": m.type, "ref": m.ref, "role": m.role} for m in obj.members]
            nested = sum(1 for m in members if m["type"] == "r")
            relation_rows.append((obj.id, _tags_json(tags), json.dumps(members, ensure_ascii=False), rules.layer_mask(tags), nested))
            member_rows.extend((MEMBER_TYPE_CODES[m["type"]], m["ref"], obj.id, seq) for seq, m in enumerate(members))
            counts["nested_relation_refs"] += nested
        flush()
    flush(force=True)


def _finalize_relations(conn: sqlite3.Connection, counts: dict) -> None:
    conn.executescript("""
        CREATE TEMP TABLE relation_stats AS
        SELECT rm.relation_id AS relation_id,
               SUM(CASE WHEN rm.member_type = 1 AND w.id IS NULL THEN 1
                        WHEN rm.member_type = 0 AND n.id IS NULL THEN 1 ELSE 0 END) AS missing,
               MIN(COALESCE(w.minx, n.lon)) AS minx, MIN(COALESCE(w.miny, n.lat)) AS miny,
               MAX(COALESCE(w.maxx, n.lon)) AS maxx, MAX(COALESCE(w.maxy, n.lat)) AS maxy
        FROM relation_members rm
        LEFT JOIN ways w ON rm.member_type = 1 AND w.id = rm.member_id
        LEFT JOIN nodes n ON rm.member_type = 0 AND n.id = rm.member_id
        GROUP BY rm.relation_id;
        UPDATE relations SET
            missing_members = (SELECT missing FROM relation_stats s WHERE s.relation_id = relations.id),
            minx = (SELECT minx FROM relation_stats s WHERE s.relation_id = relations.id),
            miny = (SELECT miny FROM relation_stats s WHERE s.relation_id = relations.id),
            maxx = (SELECT maxx FROM relation_stats s WHERE s.relation_id = relations.id),
            maxy = (SELECT maxy FROM relation_stats s WHERE s.relation_id = relations.id)
        WHERE id IN (SELECT relation_id FROM relation_stats);
        UPDATE relations SET missing_members = 0 WHERE missing_members IS NULL;
        DROP TABLE relation_stats;
    """)
    conn.execute("INSERT INTO rtree_relations SELECT id, minx, maxx, miny, maxy FROM relations WHERE minx IS NOT NULL")
    counts["relations_with_missing_members"] = conn.execute(
        "SELECT COUNT(*) FROM relations WHERE missing_members > 0").fetchone()[0]
    counts["missing_member_refs"] = conn.execute(
        "SELECT COALESCE(SUM(missing_members), 0) FROM relations").fetchone()[0]
    counts["relations_without_bbox"] = conn.execute(
        "SELECT COUNT(*) FROM relations WHERE minx IS NULL").fetchone()[0]


def _collect_counts(conn: sqlite3.Connection, counts: dict) -> None:
    for key, sql in {
        "nodes": "SELECT COUNT(*) FROM nodes",
        "layer_nodes": "SELECT COUNT(*) FROM nodes WHERE layers != 0",
        "ways": "SELECT COUNT(*) FROM ways",
        "road_ways": "SELECT COUNT(*) FROM ways WHERE is_road = 1",
        "layer_ways": "SELECT COUNT(*) FROM ways WHERE layers != 0",
        "member_only_ways": "SELECT COUNT(*) FROM ways WHERE layers = 0 AND is_road = 0",
        "relations": "SELECT COUNT(*) FROM relations",
    }.items():
        counts[key] = conn.execute(sql).fetchone()[0]


def _remove_stale_build_files(store_dir: Path) -> list[str]:
    removed = []
    for path in store_dir.glob(f"{BUILD_FILE_PREFIX}*"):
        path.unlink()
        removed.append(path.name)
    return removed


def build_store(
    pbf_path: Path | str,
    store_dir: Path | str,
    *,
    rules: TagRules | None = None,
    force: bool = False,
    location_storage: str = "flex_mem",
) -> BuildResult:
    """Build a store into ``store_dir`` and publish it atomically; never replaces a valid store on failure."""
    pbf_path = Path(pbf_path)
    store_dir = Path(store_dir)
    if not pbf_path.is_file():
        raise PbfStoreError(f"PBF not found: {pbf_path}")
    rules = rules or TagRules.from_production()
    store_dir.mkdir(parents=True, exist_ok=True)
    final_path = store_dir / STORE_FILENAME

    with _BuildLock(store_dir, force):
        removed = _remove_stale_build_files(store_dir)
        temp_path = store_dir / f"{BUILD_FILE_PREFIX}{uuid.uuid4().hex}.sqlite"
        started = time.perf_counter()
        started_utc = _utc_now()
        counts = {
            "invalid_node_locations": 0, "ways_with_missing_nodes": 0, "missing_node_refs": 0,
            "ways_without_location": 0, "tracked_relations_not_stored": 0, "nested_relation_refs": 0,
            "stale_build_files_removed": len(removed),
        }
        pbf_stat = pbf_path.stat()
        conn = sqlite3.connect(temp_path)
        try:
            conn.execute("PRAGMA journal_mode = OFF")
            conn.execute("PRAGMA synchronous = OFF")
            conn.executescript(_SCHEMA_SQL)

            pass_a_started = time.perf_counter()
            tracker, selected_relations = _select_pass_a(pbf_path, rules)
            counts["pass_a_s"] = round(time.perf_counter() - pass_a_started, 3)
            counts["selected_relations"] = len(selected_relations)

            pass_b_started = time.perf_counter()
            _write_pass_b(conn, pbf_path, rules, tracker, selected_relations, location_storage, counts)
            counts["pass_b_s"] = round(time.perf_counter() - pass_b_started, 3)

            index_started = time.perf_counter()
            conn.executescript(_INDEX_SQL)
            _finalize_relations(conn, counts)
            _collect_counts(conn, counts)
            counts["index_s"] = round(time.perf_counter() - index_started, 3)

            header = read_pbf_header(pbf_path)
            meta = {
                "schema_version": str(SCHEMA_VERSION),
                "preprocess_version": str(PREPROCESS_VERSION),
                "pbf_path": str(pbf_path.resolve()),
                "pbf_size": str(pbf_stat.st_size),
                "pbf_mtime_ns": str(pbf_stat.st_mtime_ns),
                "pbf_sha256": file_sha256(pbf_path),
                "pbf_header_bbox": json.dumps(header["bbox"]),
                "pbf_replication_timestamp": header["replication_timestamp"] or "",
                "pbf_replication_sequence": header["replication_sequence"] or "",
                "pbf_generator": header["generator"] or "",
                "tag_rules_hash": rules.rules_hash(),
                "layer_bits": json.dumps(rules.layer_bits, sort_keys=True),
                "pyosmium_version": osmium.version.pyosmium_release,
                "libosmium_version": osmium.version.libosmium_version,
                "osmnx_version": metadata.version("osmnx"),
                "location_storage": location_storage,
                "build_started_utc": started_utc,
            }
            duration = time.perf_counter() - started
            meta["build_finished_utc"] = _utc_now()
            meta["build_duration_s"] = f"{duration:.3f}"
            meta["counts"] = json.dumps(counts, sort_keys=True)
            conn.executemany("INSERT INTO meta VALUES (?, ?)", sorted(meta.items()))
            # Written last: readers reject any store without this marker.
            conn.execute("INSERT INTO meta VALUES ('status', ?)", (STATUS_COMPLETE,))
            conn.commit()
            conn.execute("ANALYZE")
            conn.commit()
            conn.close()
            with open(temp_path, "rb+") as handle:
                os.fsync(handle.fileno())
            os.replace(temp_path, final_path)
        except BaseException:
            conn.close()
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
            raise
    return BuildResult(store_path=final_path, counts=counts, duration_s=duration)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _chunks(values: list[int]) -> Iterator[list[int]]:
    for start in range(0, len(values), _SQL_CHUNK):
        yield values[start:start + _SQL_CHUNK]


def _bbox_or_none(row: tuple) -> Bbox | None:
    return None if row[0] is None else (row[0], row[1], row[2], row[3])


class PbfStoreReader:
    """Validated read-only access to a published store; lookups return candidates, not geometry."""

    def __init__(
        self,
        store_dir: Path | str,
        *,
        rules: TagRules | None = None,
        pbf_path: Path | str | None = None,
        verify_sha256: bool = False,
    ) -> None:
        self.store_path = Path(store_dir) / STORE_FILENAME
        if not self.store_path.is_file():
            raise StoreValidationError(f"Store not found: {self.store_path}")
        self._conn = sqlite3.connect(f"{self.store_path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            self.meta = self._read_meta()
            self._validate(rules or TagRules.from_production(), pbf_path, verify_sha256)
        except BaseException:
            self._conn.close()
            raise
        self.layer_bits: dict[str, int] = json.loads(self.meta["layer_bits"])
        self.counts: dict = json.loads(self.meta["counts"])

    def __enter__(self) -> "PbfStoreReader":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    def _read_meta(self) -> dict[str, str]:
        try:
            return dict(self._conn.execute("SELECT key, value FROM meta").fetchall())
        except sqlite3.DatabaseError as error:
            raise StoreValidationError(f"Unreadable store metadata: {error}") from error

    def _validate(self, rules: TagRules, pbf_path: Path | str | None, verify_sha256: bool) -> None:
        meta = self.meta
        if meta.get("status") != STATUS_COMPLETE:
            raise StoreValidationError("Store build is not marked complete.")
        expected = {
            "schema_version": str(SCHEMA_VERSION),
            "preprocess_version": str(PREPROCESS_VERSION),
            "tag_rules_hash": rules.rules_hash(),
        }
        for key, value in expected.items():
            if meta.get(key) != value:
                raise StoreValidationError(f"Store {key} mismatch: store={meta.get(key)!r} expected={value!r}")
        if pbf_path is not None:
            stat = Path(pbf_path).stat()
            if str(stat.st_size) != meta["pbf_size"] or str(stat.st_mtime_ns) != meta["pbf_mtime_ns"]:
                raise StoreValidationError("Source PBF size or modification time differs from the store metadata.")
            if verify_sha256 and file_sha256(Path(pbf_path)) != meta["pbf_sha256"]:
                raise StoreValidationError("Source PBF SHA-256 differs from the store metadata.")

    @property
    def header_bbox(self) -> Bbox | None:
        value = json.loads(self.meta["pbf_header_bbox"])
        return tuple(value) if value else None

    def covers(self, bbox: Bbox) -> bool:
        header = self.header_bbox
        if header is None:
            return False
        west, south, east, north = bbox
        return header[0] <= west and header[1] <= south and east <= header[2] and north <= header[3]

    def _layer_clause(self, table: str, layer_mask: int | None, roads: bool) -> tuple[str, list]:
        clauses, params = [], []
        if layer_mask:
            clauses.append(f"({table}.layers & ?) != 0")
            params.append(layer_mask)
        if roads:
            clauses.append(f"{table}.is_road = 1")
        return (" AND (" + " OR ".join(clauses) + ")" if clauses else ""), params

    def candidate_way_ids(self, bbox: Bbox, *, layer_mask: int | None = None, roads: bool = False) -> set[int]:
        west, south, east, north = bbox
        clause, params = self._layer_clause("w", layer_mask, roads)
        sql = (
            "SELECT r.id FROM rtree_ways r JOIN ways w ON w.id = r.id "
            "WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?" + clause
        )
        return {row[0] for row in self._conn.execute(sql, [east, west, north, south, *params])}

    def candidate_node_ids(self, bbox: Bbox, *, layer_mask: int | None = None) -> set[int]:
        west, south, east, north = bbox
        clause, params = self._layer_clause("n", layer_mask, False)
        sql = (
            "SELECT r.id FROM rtree_nodes r JOIN nodes n ON n.id = r.id "
            "WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?" + clause
        )
        return {row[0] for row in self._conn.execute(sql, [east, west, north, south, *params])}

    def candidate_relation_ids(self, bbox: Bbox, *, layer_mask: int | None = None) -> set[int]:
        west, south, east, north = bbox
        clause, params = self._layer_clause("rel", layer_mask, False)
        sql = (
            "SELECT r.id FROM rtree_relations r JOIN relations rel ON rel.id = r.id "
            "WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?" + clause
        )
        return {row[0] for row in self._conn.execute(sql, [east, west, north, south, *params])}

    def relations_for_members(self, *, way_ids: Iterable[int] = (), node_ids: Iterable[int] = ()) -> set[int]:
        found: set[int] = set()
        for type_code, ids in ((MEMBER_TYPE_CODES["w"], sorted(set(way_ids))), (MEMBER_TYPE_CODES["n"], sorted(set(node_ids)))):
            for chunk in _chunks(ids):
                sql = (
                    "SELECT DISTINCT relation_id FROM relation_members "
                    f"WHERE member_type = ? AND member_id IN ({','.join('?' * len(chunk))})"
                )
                found.update(row[0] for row in self._conn.execute(sql, [type_code, *chunk]))
        return found

    def enclosing_way_ids(self, bbox: Bbox) -> set[int]:
        """Closed ways whose bounding box contains ``bbox`` (diagnostic; not a geometric containment test)."""
        west, south, east, north = bbox
        sql = (
            "SELECT w.id, w.node_refs FROM rtree_ways r JOIN ways w ON w.id = r.id "
            "WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?"
        )
        found = set()
        for way_id, blob in self._conn.execute(sql, [west, east, south, north]):
            refs = _unpack_refs(blob)
            if len(refs) > 3 and refs[0] == refs[-1]:
                found.add(way_id)
        return found

    def enclosing_relation_ids(self, bbox: Bbox) -> set[int]:
        """Relations whose member-union bounding box contains ``bbox`` (diagnostic only)."""
        west, south, east, north = bbox
        sql = "SELECT id FROM rtree_relations WHERE minx <= ? AND maxx >= ? AND miny <= ? AND maxy >= ?"
        return {row[0] for row in self._conn.execute(sql, [west, east, south, north])}

    def get_nodes(self, ids: Iterable[int]) -> dict[int, dict]:
        result = {}
        for chunk in _chunks(sorted(set(ids))):
            sql = f"SELECT id, lon, lat, tags, layers FROM nodes WHERE id IN ({','.join('?' * len(chunk))})"
            for node_id, lon, lat, tags, layers in self._conn.execute(sql, chunk):
                result[node_id] = {
                    "id": node_id, "lon": lon, "lat": lat,
                    "tags": json.loads(tags) if tags else {}, "layers": layers,
                }
        return result

    def get_ways(self, ids: Iterable[int]) -> dict[int, dict]:
        result = {}
        for chunk in _chunks(sorted(set(ids))):
            sql = (
                "SELECT id, tags, node_refs, layers, is_road, missing_nodes, minx, miny, maxx, maxy "
                f"FROM ways WHERE id IN ({','.join('?' * len(chunk))})"
            )
            for way_id, tags, refs, layers, is_road, missing, *bbox in self._conn.execute(sql, chunk):
                result[way_id] = {
                    "id": way_id, "tags": json.loads(tags), "node_refs": _unpack_refs(refs),
                    "layers": layers, "is_road": bool(is_road), "missing_nodes": missing,
                    "bbox": _bbox_or_none(bbox),
                }
        return result

    def get_relations(self, ids: Iterable[int]) -> dict[int, dict]:
        result = {}
        for chunk in _chunks(sorted(set(ids))):
            sql = (
                "SELECT id, tags, members, layers, missing_members, nested_relation_members, minx, miny, maxx, maxy "
                f"FROM relations WHERE id IN ({','.join('?' * len(chunk))})"
            )
            for rel_id, tags, members, layers, missing, nested, *bbox in self._conn.execute(sql, chunk):
                result[rel_id] = {
                    "id": rel_id, "tags": json.loads(tags), "members": json.loads(members),
                    "layers": layers, "missing_members": missing, "nested_relation_members": nested,
                    "bbox": _bbox_or_none(bbox),
                }
        return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _bbox_from_center(lat: float, lon: float, dist_m: float) -> Bbox:
    import osmnx as ox

    return ox.utils_geo.bbox_from_point((lat, lon), dist_m)


def _cmd_build(args: argparse.Namespace) -> int:
    result = build_store(args.pbf, args.store_dir, force=args.force, location_storage=args.location_storage)
    print(json.dumps({"store": str(result.store_path), "duration_s": round(result.duration_s, 3), "counts": result.counts}, indent=2))
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    with PbfStoreReader(args.store_dir, pbf_path=args.pbf) as reader:
        meta = dict(reader.meta)
        meta["counts"] = reader.counts
        meta["store_size_bytes"] = reader.store_path.stat().st_size
        print(json.dumps(meta, indent=2, default=str))
    return 0


def _cmd_bench(args: argparse.Namespace) -> int:
    lat, lon = (float(v) for v in args.center.split(","))
    bbox = _bbox_from_center(lat, lon, args.dist)
    lookup_s, fetch_s = [], []
    with PbfStoreReader(args.store_dir, pbf_path=args.pbf) as reader:
        for _ in range(args.repeat):
            started = time.perf_counter()
            way_ids = reader.candidate_way_ids(bbox)
            node_ids = reader.candidate_node_ids(bbox)
            relation_ids = reader.relations_for_members(way_ids=way_ids, node_ids=node_ids)
            lookup_s.append(time.perf_counter() - started)
            started = time.perf_counter()
            ways = reader.get_ways(way_ids)
            relations = reader.get_relations(relation_ids)
            member_ways = {m["ref"] for r in relations.values() for m in r["members"] if m["type"] == "w"}
            ways.update(reader.get_ways(member_ways - set(ways)))
            refs = {ref for w in ways.values() for ref in w["node_refs"]}
            nodes = reader.get_nodes(refs | node_ids)
            fetch_s.append(time.perf_counter() - started)

    def summary(values: list[float]) -> dict:
        ordered = sorted(values)
        return {
            "median_s": round(statistics.median(ordered), 4),
            "p95_s": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 4),
        }

    print(json.dumps({
        "bbox": bbox, "repeat": args.repeat, "candidate_lookup": summary(lookup_s), "element_fetch": summary(fetch_s),
        "ways": len(ways), "relations": len(relations), "nodes": len(nodes),
    }, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m generator.core.pbf_store")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Preprocess a PBF into a new store (atomic publish).")
    build.add_argument("--pbf", type=Path, required=True)
    build.add_argument("--store-dir", type=Path, required=True)
    build.add_argument("--force", action="store_true", help="Break a stale build lock.")
    build.add_argument("--location-storage", default="flex_mem")
    build.set_defaults(func=_cmd_build)

    inspect_cmd = sub.add_parser("inspect", help="Validate a store and print its metadata.")
    inspect_cmd.add_argument("--store-dir", type=Path, required=True)
    inspect_cmd.add_argument("--pbf", type=Path, default=None)
    inspect_cmd.set_defaults(func=_cmd_inspect)

    bench = sub.add_parser("bench", help="Time candidate lookup and element fetch for one query box.")
    bench.add_argument("--store-dir", type=Path, required=True)
    bench.add_argument("--pbf", type=Path, default=None)
    bench.add_argument("--center", required=True, help="lat,lon")
    bench.add_argument("--dist", type=float, required=True, help="OSMnx bbox distance in metres")
    bench.add_argument("--repeat", type=int, default=5)
    bench.set_defaults(func=_cmd_bench)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
