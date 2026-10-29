from pathlib import Path

import pytest

from generator import batch


EUROPE_BOUNDS = (-32.6, 29.6, 46.7, 81.4)
HUNGARY_BOUNDS = (16.1, 45.7, 22.9, 48.6)


def test_discovery_uses_geographic_coverage_not_filename(tmp_path, monkeypatch):
    directory = tmp_path / "GEOFABRIK"
    directory.mkdir()
    europe = directory / "regional-latest.osm.pbf"
    hungary = directory / "hungary.osm.pbf"
    europe.write_bytes(b"not-empty")
    hungary.write_bytes(b"not-empty")
    monkeypatch.setattr(batch, "read_pbf_header", lambda path: {"bbox": list(EUROPE_BOUNDS if path == europe.resolve() else HUNGARY_BOUNDS)})

    assert batch.discover_europe_pbf([directory]) == europe.resolve()


def test_discovery_rejects_multiple_covering_inputs(tmp_path, monkeypatch):
    directory = tmp_path / "geofabrik"
    directory.mkdir()
    first, second = directory / "first.pbf", directory / "second.pbf"
    first.write_bytes(b"1")
    second.write_bytes(b"2")
    monkeypatch.setattr(batch, "read_pbf_header", lambda _path: {"bbox": list(EUROPE_BOUNDS)})

    with pytest.raises(batch.PbfSelectionError, match="Multiple Europe PBF"):
        batch.discover_europe_pbf([directory])


def test_discovery_reports_hungary_when_no_europe_source(tmp_path, monkeypatch):
    directory = tmp_path / "geofabrik"
    directory.mkdir()
    hungary = directory / "hungary.osm.pbf"
    hungary.write_bytes(b"1")
    monkeypatch.setattr(batch, "read_pbf_header", lambda _path: {"bbox": list(HUNGARY_BOUNDS)})

    with pytest.raises(batch.PbfSelectionError, match="hungary.osm.pbf"):
        batch.discover_europe_pbf([directory])


def test_override_accepts_valid_local_pbf_without_europe_coverage(tmp_path, monkeypatch):
    alternative = tmp_path / "alternative.pbf"
    alternative.write_bytes(b"1")
    monkeypatch.setattr(batch, "read_pbf_header", lambda _path: {"bbox": list(HUNGARY_BOUNDS)})

    assert batch.validate_pbf_input(alternative)["bbox"] == list(HUNGARY_BOUNDS)