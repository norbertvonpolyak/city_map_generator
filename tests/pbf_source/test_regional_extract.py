from pathlib import Path

import osmium
import pytest
from osmium.osm import mutable
from shapely import Polygon

from generator.core.regional_extract import RegionalExtractError, extract_region_pbf


def _write_boundary_pbf(path: Path) -> Path:
	header = osmium.io.Header()
	header.add_box(osmium.osm.Box(osmium.osm.Location(2.2, 48.7), osmium.osm.Location(2.5, 49.0)))
	writer = osmium.SimpleWriter(str(path), header=header)
	try:
		ring = [(101, 2.30, 48.80), (102, 2.40, 48.80), (103, 2.40, 48.90), (104, 2.30, 48.90)]
		for node_id, lon, lat in [*ring, (105, 2.35, 48.85)]:
			writer.add_node(mutable.Node(id=node_id, location=osmium.osm.Location(lon, lat)))
		writer.add_way(mutable.Way(id=201, nodes=[101, 102, 103, 104, 101]))
		writer.add_relation(mutable.Relation(
			id=301,
			members=[("w", 201, "outer"), ("n", 105, "label")],
			tags={"type": "boundary", "boundary": "administrative", "name": "Testville", "admin_level": "8"},
		))
	finally:
		writer.close()
	return path


def test_extract_completes_boundary_way_and_preserves_out_of_bbox_ring(tmp_path):
	source = _write_boundary_pbf(tmp_path / "source.osm.pbf")
	output = tmp_path / "cache" / "region.osm.pbf"

	result = extract_region_pbf(source, output, (2.349, 48.849, 2.351, 48.851))
	objects = {"nodes": {}, "ways": {}, "relations": {}}
	for obj in osmium.FileProcessor(str(output)):
		if obj.is_node():
			objects["nodes"][obj.id] = (obj.location.lon, obj.location.lat)
		elif obj.is_way():
			objects["ways"][obj.id] = [node.ref for node in obj.nodes]
		elif obj.is_relation():
			objects["relations"][obj.id] = [(member.type, member.ref, member.role) for member in obj.members]

	outer = next(member for member in objects["relations"][301] if member[0] == "w" and member[2] == "outer")
	polygon = Polygon([objects["nodes"][node_id] for node_id in objects["ways"][outer[1]]])
	assert polygon.is_valid and polygon.area > 0
	assert result.selected_nodes == 1
	assert result.output_nodes > result.selected_nodes
	assert result.unresolved_references == 0


@pytest.mark.parametrize("bbox", [(1, 0, 0, 1), (-181, 0, -180, 1), (0, 0, 1, 91)])
def test_extract_rejects_invalid_bbox_without_publishing(tmp_path, bbox):
	source = _write_boundary_pbf(tmp_path / "source.osm.pbf")
	output = tmp_path / "cache" / "region.osm.pbf"

	with pytest.raises(RegionalExtractError, match="Invalid WGS84 bbox"):
		extract_region_pbf(source, output, bbox)
	assert not output.exists()
