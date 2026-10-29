import json

import fitz
import osmium
import pytest
from PIL import Image

from generator.batch_pipeline import _cache_only_environment
from generator.order_cache import (
    _required_cache_bbox,
    _source_identity,
    _validate_store,
    build_cache_identity,
    cache_identity_id,
    prepare_order_cache,
)
from generator.order_renderer import _validate_pdf, _slug, _validate_order_config
from generator.core.style_registry import STYLE_REGISTRY
from generator.specs import DEFAULT_EXTENT_M, SIZES_CM


def _write_source(path, longitude=19.0):
    header = osmium.io.Header()
    header.add_box(osmium.osm.Box(osmium.osm.Location(18.5, 47.0), osmium.osm.Location(19.5, 48.0)))
    writer = osmium.SimpleWriter(str(path), header=header, overwrite=True)
    writer.add_node(osmium.osm.mutable.Node(id=1, location=osmium.osm.Location(longitude, 47.5)))
    writer.add_node(osmium.osm.mutable.Node(id=2, location=osmium.osm.Location(longitude + 0.001, 47.5)))
    writer.add_way(osmium.osm.mutable.Way(id=10, nodes=[1, 2], tags={"highway": "residential"}))
    writer.close()
    return path


def _write_vector_pdf(path, width_cm=10, height_cm=14):
    document = fitz.open()
    page = document.new_page(width=width_cm / 2.54 * 72, height=height_cm / 2.54 * 72)
    page.draw_line((20, 20), (page.rect.width - 20, page.rect.height - 20), color=(0, 0, 0), width=0.5)
    page.insert_text((30, 60), "Local order map", fontsize=12)
    document.save(path)
    document.close()
    return path


def test_source_provenance_includes_path_size_mtime_and_content_fingerprint(tmp_path):
    pbf = _write_source(tmp_path / "city.osm.pbf")
    first = _source_identity(pbf)
    assert first["path"] == str(pbf.resolve())
    assert first["size_bytes"] == pbf.stat().st_size
    assert first["mtime_ns"] == pbf.stat().st_mtime_ns
    assert len(first["sha256"]) == 64

    _write_source(pbf, longitude=19.1)
    second = _source_identity(pbf)
    assert first["sha256"] != second["sha256"]


def test_cache_identity_is_independent_of_size_and_style_but_invalidates_source_or_schema():
    source = {"path": "city.osm.pbf", "size_bytes": 100, "mtime_ns": 1, "sha256": "a" * 64}
    args = (source, 47.5, 19.0, (18.8, 47.3, 19.2, 47.7))
    first = build_cache_identity(*args, schema_version=1, preprocess_version=1, tag_rules_hash="rules")
    repeated = build_cache_identity(*args, schema_version=1, preprocess_version=1, tag_rules_hash="rules")
    changed_source = dict(source, sha256="b" * 64)
    changed_schema = build_cache_identity(*args, schema_version=2, preprocess_version=1, tag_rules_hash="rules")

    assert cache_identity_id(first) == cache_identity_id(repeated)
    assert cache_identity_id(first) != cache_identity_id(build_cache_identity(changed_source, 47.5, 19.0, args[3], schema_version=1, preprocess_version=1, tag_rules_hash="rules"))
    assert cache_identity_id(first) != cache_identity_id(changed_schema)


def test_required_city_cache_bounds_are_independent_of_selected_size_and_style():
    small_extent_bounds = _required_cache_bbox(47.4979, 19.0402, 3000)
    default_extent_bounds = _required_cache_bbox(47.4979, 19.0402, DEFAULT_EXTENT_M)

    assert small_extent_bounds == default_extent_bounds


def test_existing_store_is_reused_across_size_extents_without_rebuild(tmp_path, monkeypatch):
    from generator.core import pbf_store
    from generator import order_cache

    pbf = _write_source(tmp_path / "city.osm.pbf")
    store_dir = tmp_path / "existing-store"
    pbf_store.build_store(pbf, store_dir)
    expected_bbox = (18.6, 47.1, 19.4, 47.9)
    monkeypatch.setattr(order_cache, "_required_cache_bbox", lambda *_args: expected_bbox)
    monkeypatch.setattr(order_cache, "_validate_render_features", lambda *_args: {"roads": {"edges": 1}})
    monkeypatch.setattr(pbf_store, "build_store", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("store rebuilt")))

    first = prepare_order_cache(
        pbf_path=pbf,
        center_lat=47.5,
        center_lon=19.0,
        extent_m=3000,
        cache_root=tmp_path / "cache",
        preferred_store_dir=store_dir,
    )
    second = prepare_order_cache(
        pbf_path=pbf,
        center_lat=47.5,
        center_lon=19.0,
        extent_m=4500,
        cache_root=tmp_path / "cache",
        preferred_store_dir=store_dir,
    )

    assert first["reused"] and second["reused"]
    assert first["cache_id"] == second["cache_id"]
    assert first["store_dir"] == second["store_dir"] == str(store_dir.resolve())


def test_existing_store_rejects_out_of_coverage_request(tmp_path):
    from generator.core import pbf_store

    pbf = _write_source(tmp_path / "city.osm.pbf")
    store_dir = tmp_path / "store"
    pbf_store.build_store(pbf, store_dir)

    with pytest.raises(Exception, match="does not contain required bounds"):
        _validate_store(store_dir, pbf, (19.8, 47.8, 20.0, 48.0), explicit_coverage=None)


def test_local_pbf_order_configuration_rejects_bad_inputs_before_cache_build(tmp_path):
    pbf = _write_source(tmp_path / "source.osm.pbf")
    base = {
        "pbf_path": pbf,
        "city_name": "Budapest",
        "center_lat": 47.5,
        "center_lon": 19.0,
        "style": "urban_modern",
        "sizes": tuple(SIZES_CM),
        "extent_m": DEFAULT_EXTENT_M,
    }
    _validate_order_config(**base)
    with pytest.raises(ValueError, match="not registered"):
        _validate_order_config(**{**base, "style": "not_a_style"})
    with pytest.raises(ValueError, match="Unsupported catalog size"):
        _validate_order_config(**{**base, "sizes": ("poster-xl",)})
    with pytest.raises(ValueError, match="CENTER_LAT"):
        _validate_order_config(**{**base, "center_lat": 95})


def test_pbf_only_environment_unsets_direct_pbf_and_restores_caller_state(monkeypatch, tmp_path):
    monkeypatch.setenv("MAPCANVAS_OSM_SOURCE", "overpass")
    monkeypatch.setenv("MAPCANVAS_PBF_PATH", "raw-source-must-not-be-read.pbf")
    with _cache_only_environment(tmp_path / "store"):
        assert __import__("os").environ["MAPCANVAS_OSM_SOURCE"] == "pbf"
        assert __import__("os").environ["MAPCANVAS_PBF_STORE_DIR"] == str(tmp_path / "store")
        assert "MAPCANVAS_PBF_PATH" not in __import__("os").environ
    assert __import__("os").environ["MAPCANVAS_OSM_SOURCE"] == "overpass"
    assert __import__("os").environ["MAPCANVAS_PBF_PATH"] == "raw-source-must-not-be-read.pbf"


def test_pdf_export_keeps_vector_content(tmp_path):
    pdf = _write_vector_pdf(tmp_path / "map.pdf")

    pdf_info = _validate_pdf(pdf, 10, 14)

    assert pdf_info["vector_drawings"] > 0
    assert pdf_info["embedded_images"] == 0


def test_city_output_slug_is_stable():
    assert _slug("Turin / Torino") == "turin-torino"