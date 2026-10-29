"""Bounded, reference-complete PBF extracts for the local geographic-store builder."""

from __future__ import annotations

import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import osmium


class RegionalExtractError(RuntimeError):
	pass


@dataclass(frozen=True)
class RegionalExtractResult:
	output_path: Path
	bbox_wgs84: tuple[float, float, float, float]
	selected_nodes: int
	selected_ways: int
	selected_relations: int
	output_nodes: int
	output_ways: int
	output_relations: int
	unresolved_references: int
	unresolved_reference_sample: tuple[str, ...]
	output_size_bytes: int


class _RegionHandler(osmium.SimpleHandler):
	def __init__(self, writer, tracker, bbox: tuple[float, float, float, float]) -> None:
		super().__init__()
		self.writer = writer
		self.tracker = tracker
		self.west, self.south, self.east, self.north = bbox
		self.selected_nodes = 0
		self.selected_ways = 0
		self.selected_relations = 0

	def node(self, node) -> None:
		if not node.location.valid():
			return
		if self.west <= node.location.lon <= self.east and self.south <= node.location.lat <= self.north:
			self.writer.add_node(node)
			self.tracker.add_node(node.id)
			self.selected_nodes += 1

	def way(self, way) -> None:
		if self.tracker.contains_any_references(way):
			self.writer.add_way(way)
			self.tracker.add_way(way.id)
			self.selected_ways += 1

	def relation(self, relation) -> None:
		if self.tracker.contains_any_references(relation):
			self.writer.add_relation(relation)
			self.tracker.add_relation(relation.id)
			self.selected_relations += 1


def _count_and_validate_references(path: Path) -> tuple[dict[str, int], int, tuple[str, ...]]:
	counts = {"node": 0, "way": 0, "relation": 0}
	ids = {"node": set(), "way": set(), "relation": set()}
	type_names = {"n": "node", "w": "way", "r": "relation"}
	for obj in osmium.FileProcessor(str(path)):
		kind = type_names.get(obj.type_str())
		if kind:
			counts[kind] += 1
			ids[kind].add(obj.id)

	missing_count = 0
	missing_sample: list[str] = []
	for obj in osmium.FileProcessor(str(path)):
		if obj.is_way():
			missing = (("node", node.ref) for node in obj.nodes if node.ref not in ids["node"])
			parent = f"way:{obj.id}"
		elif obj.is_relation():
			missing = ((type_names[member.type], member.ref) for member in obj.members if member.ref not in ids[type_names[member.type]])
			parent = f"relation:{obj.id}"
		else:
			continue
		for kind, ref in missing:
			missing_count += 1
			if len(missing_sample) < 20:
				missing_sample.append(f"{parent}->{kind}:{ref}")
	return counts, missing_count, tuple(missing_sample)


def extract_region_pbf(
	source_path: Path | str,
	output_path: Path | str,
	bbox_wgs84: tuple[float, float, float, float],
	*,
	relation_depth: int = 2,
) -> RegionalExtractResult:
	"""Select objects by nodes in a coarse WGS84 bbox and complete their OSM references."""
	source = Path(source_path).expanduser().resolve()
	output = Path(output_path).expanduser().resolve()
	if not source.is_file() or source.suffix.casefold() != ".pbf":
		raise RegionalExtractError(f"Source must be an existing .pbf file: {source}")
	if source == output:
		raise RegionalExtractError("Regional output cannot overwrite the source PBF")
	if output.exists():
		raise RegionalExtractError(f"Refusing to overwrite an existing regional extract: {output}")
	if relation_depth < 0:
		raise RegionalExtractError("relation_depth must not be negative")
	if len(bbox_wgs84) != 4 or not all(math.isfinite(value) for value in bbox_wgs84):
		raise RegionalExtractError(f"Invalid WGS84 bbox: {bbox_wgs84!r}")
	west, south, east, north = bbox_wgs84
	if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
		raise RegionalExtractError(f"Invalid WGS84 bbox: {bbox_wgs84!r}")
	output.parent.mkdir(parents=True, exist_ok=True)

	with tempfile.TemporaryDirectory(prefix="order-region-extract-", dir=output.parent) as temp_dir:
		staged = Path(temp_dir) / output.name
		tracker = osmium.IdTracker()
		writer = osmium.BackReferenceWriter(
			str(staged), str(source), overwrite=True, remove_tags=False, relation_depth=relation_depth,
		)
		try:
			handler = _RegionHandler(writer, tracker, bbox_wgs84)
			handler.apply_file(str(source))
		finally:
			writer.close()
		if handler.selected_nodes == 0:
			raise RegionalExtractError(f"No OSM nodes found in extraction bbox {bbox_wgs84!r}")
		counts, missing_count, missing_sample = _count_and_validate_references(staged)
		if counts["node"] == 0 or counts["way"] == 0:
			raise RegionalExtractError(f"Regional extract lacks nodes or ways: {counts}")
		os.replace(staged, output)

	return RegionalExtractResult(
		output_path=output,
		bbox_wgs84=bbox_wgs84,
		selected_nodes=handler.selected_nodes,
		selected_ways=handler.selected_ways,
		selected_relations=handler.selected_relations,
		output_nodes=counts["node"],
		output_ways=counts["way"],
		output_relations=counts["relation"],
		unresolved_references=missing_count,
		unresolved_reference_sample=missing_sample,
		output_size_bytes=output.stat().st_size,
	)
