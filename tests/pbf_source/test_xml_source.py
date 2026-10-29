"""Raw OSM XML source: parsing, bounds/center, reference completeness, clipping, switch and order cleanup."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import fitz
import geopandas as gpd
import osmnx as ox
import pytest
from shapely.geometry import Point, box

from generator import xml_order
from generator.core import osm_bundle_cache, pbf_store
from generator.core.pbf_source import PbfBundleSource
from generator.core.pbf_store import PbfStoreError
from generator.core.render_dispatcher import get_viewport_for_style
from generator.specs import spec_from_dimensions
from pbf_source_data import EXTENT_M, HALF_HEIGHT_M, HALF_WIDTH_M, engine_dataset, write_pbf
from support.synthetic_osm import CENTER_LAT, CENTER_LON, OsmBuilder

HEADER_BBOX = (18.9, 47.4, 19.2, 47.6)
PARAMS = dict(
    center_lat=CENTER_LAT, center_lon=CENTER_LON, extent_m=EXTENT_M,
    half_width_m=HALF_WIDTH_M, half_height_m=HALF_HEIGHT_M, include_building_features=True,
)


def _node_at(builder: OsmBuilder, x_m: float, y_m: float) -> int:
    lon, lat = builder.lonlat(x_m, y_m)
    return next(n["id"] for n in builder.nodes if abs(n["lon"] - lon) < 1e-9 and abs(n["lat"] - lat) < 1e-9)


def _crossing_dataset():
    data = engine_dataset(with_coast=False)
    b = data.builder
    # Connected road crossing the whole map: outer vertices lie far outside every query area, and the
    # intersections that bound the clipped part (x=±700 m) lie outside the visible map (x=±420 m).
    west_x, east_x = b.node(-700, 50), b.node(700, 50)
    data.ids["crossing_road"] = ("way", b.way(
        [b.node(-3000, 50), west_x, _node_at(b, -300, 0), _node_at(b, 300, 0), east_x, b.node(3000, 50)],
        {"highway": "primary"},
    ))
    b.line([(-700, 50), (-700, 150)], {"highway": "residential"})
    b.ways[-1]["nodes"][0] = west_x
    b.line([(700, 50), (700, 150)], {"highway": "residential"})
    b.ways[-1]["nodes"][0] = east_x
    # Multipolygon building whose only outer ring has every vertex outside the query polygon.
    outer = b.rect(-2500, 300, 2500, 380)
    data.ids["crossing_mp_outer"] = ("way", outer)
    data.ids["crossing_mp"] = ("relation", b.relation([("way", outer, "outer")], {"type": "multipolygon", "building": "yes"}))
    return data


@pytest.fixture(scope="module")
def xml_store(tmp_path_factory):
    root = tmp_path_factory.mktemp("xml_store")
    data = _crossing_dataset()
    xml = write_pbf(root / "city.osm", data.builder, header_bbox=HEADER_BBOX)
    pbf_store.build_store(xml, root / "store", reference_tracking="sparse")
    return {"xml": xml, "store_dir": root / "store", "ids": data.ids, "builder": data.builder}


def _table_rows(store_dir: Path) -> dict:
    conn = sqlite3.connect(store_dir / pbf_store.STORE_FILENAME)
    try:
        return {
            "nodes": conn.execute("SELECT id, lon, lat, tags, layers FROM nodes ORDER BY id").fetchall(),
            "ways": conn.execute("SELECT id, tags, node_refs, layers, is_road, missing_nodes FROM ways ORDER BY id").fetchall(),
            "relations": conn.execute("SELECT id, tags, members, missing_members FROM relations ORDER BY id").fetchall(),
        }
    finally:
        conn.close()


def test_xml_header_and_format_are_read(xml_store):
    assert pbf_store.source_format(xml_store["xml"]) == "xml"
    assert pbf_store.read_pbf_header(xml_store["xml"])["bbox"] == pytest.approx(list(HEADER_BBOX))
    with pbf_store.PbfStoreReader(xml_store["store_dir"], pbf_path=xml_store["xml"]) as reader:
        assert reader.meta["source_format"] == "xml"
        assert reader.meta["reference_tracking"] == "sparse"
        assert reader.counts["road_ways"] > 0 and reader.counts["missing_node_refs"] == 0


@pytest.mark.parametrize("location_storage,tracking", [
    ("flex_mem", "dense"),
    ("sparse_mem_array", "sparse"),
])
def test_node_index_and_reference_tracking_variants_build_identical_stores(xml_store, tmp_path, location_storage, tracking):
    pbf_store.build_store(xml_store["xml"], tmp_path / "store", location_storage=location_storage, reference_tracking=tracking)
    assert _table_rows(tmp_path / "store") == _table_rows(xml_store["store_dir"])


def test_file_backed_node_index_is_rejected_for_temporary_orders(xml_store, tmp_path):
    # PyOsmium keeps file-backed index handles open until process exit, so per-order cleanup could not remove them.
    with pytest.raises(ValueError, match="file-backed"):
        xml_order.render_xml_order(
            xml_path=xml_store["xml"], city_name="Testville", style="urban_modern", sizes=[(6, 8)],
            output_dir=tmp_path / "out", location_storage="sparse_file_array,idx",
        )
    assert not (tmp_path / "out").exists()


def test_unknown_reference_tracking_is_rejected(xml_store, tmp_path):
    with pytest.raises(PbfStoreError, match="reference_tracking"):
        pbf_store.build_store(xml_store["xml"], tmp_path / "store", reference_tracking="bitset")


def _project_and_clip(gdf):
    center = ox.projection.project_gdf(gpd.GeoDataFrame(geometry=[Point(CENTER_LON, CENTER_LAT)], crs="EPSG:4326"))
    point = center.geometry.iloc[0]
    rect = box(point.x - HALF_WIDTH_M, point.y - HALF_HEIGHT_M, point.x + HALF_WIDTH_M, point.y + HALF_HEIGHT_M)
    projected = gdf.to_crs(center.crs)
    return projected, gpd.clip(projected, gpd.GeoSeries([rect], crs=center.crs)), rect


def test_crossing_road_and_multipolygon_are_complete_before_clipping(monkeypatch, xml_store):
    monkeypatch.setenv("MAPCANVAS_OSM_SOURCE", "xml")
    monkeypatch.setenv("MAPCANVAS_XML_STORE_DIR", str(xml_store["store_dir"]))
    monkeypatch.setenv("MAPCANVAS_XML_PATH", str(xml_store["xml"]))
    bundle = osm_bundle_cache.load_or_build_shared_osm_bundle(**PARAMS)

    road_id = xml_store["ids"]["crossing_road"][1]
    edges = bundle["edges_raw"].reset_index()
    road = edges[edges["osmid"].apply(lambda v: road_id in (v if isinstance(v, list) else [v]))]
    # Two-way streets appear once per direction; measure one direction only.
    road = road[road["u"] < road["v"]]
    assert len(road) > 0
    _, clipped_road, rect = _project_and_clip(road)
    # The clipped road spans the full map width: nothing is lost at the clip boundary.
    assert clipped_road.geometry.length.sum() == pytest.approx(rect.bounds[2] - rect.bounds[0], rel=0.01)

    mp_id = xml_store["ids"]["crossing_mp"][1]
    features = bundle["gdf_all_raw"]
    assert ("relation", mp_id) in features.index
    building = features.loc[[("relation", mp_id)]]
    full, clipped, _ = _project_and_clip(building)
    assert full.geometry.area.iloc[0] == pytest.approx(5000 * 80, rel=0.02)
    assert clipped.geometry.area.sum() == pytest.approx(2 * HALF_WIDTH_M * 80, rel=0.02)


def test_xml_switch_requires_store_and_rejects_pbf_stores(monkeypatch, tmp_path):
    monkeypatch.setenv("MAPCANVAS_OSM_SOURCE", "xml")
    monkeypatch.delenv("MAPCANVAS_XML_STORE_DIR", raising=False)
    with pytest.raises(PbfStoreError, match="MAPCANVAS_XML_STORE_DIR"):
        osm_bundle_cache.load_or_build_shared_osm_bundle(**PARAMS)

    pbf = write_pbf(tmp_path / "data.osm.pbf", engine_dataset(with_coast=False).builder)
    pbf_store.build_store(pbf, tmp_path / "store")
    monkeypatch.setenv("MAPCANVAS_XML_STORE_DIR", str(tmp_path / "store"))
    with pytest.raises(PbfStoreError, match="not built from an OSM XML"):
        osm_bundle_cache.load_or_build_shared_osm_bundle(**PARAMS)


def test_xml_and_pbf_stores_of_same_data_produce_identical_bundles(xml_store, tmp_path):
    pbf = write_pbf(tmp_path / "same.osm.pbf", xml_store["builder"], header_bbox=HEADER_BBOX)
    pbf_store.build_store(pbf, tmp_path / "pbf_store")
    with pbf_store.PbfStoreReader(xml_store["store_dir"]) as xml_reader, pbf_store.PbfStoreReader(tmp_path / "pbf_store") as pbf_reader:
        xml_bundle = PbfBundleSource(xml_reader).load_bundle(**PARAMS)
        pbf_bundle = PbfBundleSource(pbf_reader).load_bundle(**PARAMS)
    for key, value in pbf_bundle.items():
        other = xml_bundle[key]
        assert (value is None) == (other is None), key
        if value is not None:
            assert sorted(map(str, value.index)) == sorted(map(str, other.index)), key


# ---------------------------------------------------------------------------
# Source bounds and center
# ---------------------------------------------------------------------------

def _write_xml(path: Path, builder: OsmBuilder, bbox=None) -> Path:
    if bbox is not None:
        return write_pbf(path, builder, header_bbox=bbox)
    from osmium.osm import mutable
    import osmium

    writer = osmium.SimpleWriter(str(path))
    try:
        for node in builder.nodes:
            writer.add_node(mutable.Node(id=node["id"], location=osmium.osm.Location(node["lon"], node["lat"]), tags=node.get("tags", {})))
        for way in builder.ways:
            writer.add_way(mutable.Way(id=way["id"], nodes=way["nodes"], tags=way.get("tags", {})))
    finally:
        writer.close()
    return path


def _write_bounds_case(path: Path, *, tails: bool, independent: bool, bounds=True) -> Path:
    b = OsmBuilder()
    b.rect(-500, -500, 500, 500, {"building": "yes"})
    if tails:
        b.line([(0, 0), (9000, 0)], {"highway": "primary"})
    if independent:
        b.rect(20000, 20000, 20100, 20100, {"building": "yes"})
    west, south = b.lonlat(-1000, -1000)
    east, north = b.lonlat(1000, 1000)
    return _write_xml(path, b, (west, south, east, north) if bounds else None)


def test_declared_bounds_verified_when_outside_data_is_only_reference_tails(tmp_path):
    info = xml_order.inspect_osm_xml(_write_bounds_case(tmp_path / "a.osm", tails=True, independent=False))
    assert info["declared_bounds_verified"] is True
    west, south, east, north = info["declared_bounds"]
    assert info["center_lat"] == pytest.approx((south + north) / 2)
    assert info["center_lon"] == pytest.approx((west + east) / 2)
    assert info["observed_node_bounds"][2] > east
    assert info["outside_declared_bounds"]["nodes"] == 1


def test_observed_bounds_used_when_independent_data_lies_outside(tmp_path):
    info = xml_order.inspect_osm_xml(_write_bounds_case(tmp_path / "b.osm", tails=False, independent=True))
    assert info["declared_bounds_verified"] is False
    west, south, east, north = info["observed_node_bounds"]
    assert (info["center_lat"], info["center_lon"]) == pytest.approx(((south + north) / 2, (west + east) / 2))


def test_observed_bounds_used_without_declared_bounds(tmp_path):
    info = xml_order.inspect_osm_xml(_write_bounds_case(tmp_path / "c.osm", tails=True, independent=False, bounds=False))
    assert info["declared_bounds"] is None and info["center_bounds_source"] == "observed"


# ---------------------------------------------------------------------------
# Order flow: products, manifest, temporary cleanup
# ---------------------------------------------------------------------------

def _order(xml, tmp_path, **overrides):
    kwargs = dict(
        xml_path=xml, city_name="Testville", style="urban_modern", sizes=[(6, 8)], extent_m=EXTENT_M,
        output_dir=tmp_path / "out", center=(CENTER_LAT, CENTER_LON), dpi=40, temp_root=tmp_path / "tmp",
    )
    kwargs.update(overrides)
    return xml_order.render_xml_order(**kwargs)


def _leftovers(tmp_path) -> list[str]:
    temp = [p.name for p in (tmp_path / "tmp").iterdir()] if (tmp_path / "tmp").exists() else []
    staging = [p.name for p in (tmp_path / "out" / "testville").glob(".staging-*")]
    return temp + staging


def test_xml_order_publishes_validated_products_and_removes_temporary_store(xml_store, tmp_path):
    source_before = xml_store["xml"].stat()
    result = _order(xml_store["xml"], tmp_path)

    assert result["success"] == 1 and result["failed"] == 0
    assert _leftovers(tmp_path) == []
    assert all(entry["removed"] for entry in result["cleanup"].values())
    product = tmp_path / "out" / "testville" / "testville_urban_modern_6x8_extent560"
    names = {p.name for p in product.iterdir()}
    assert names == {
        "testville_urban_modern_6x8_extent560.pdf",
        "testville_urban_modern_6x8_extent560_preview.webp",
        "manifest.json",
    }
    with fitz.open(product / "testville_urban_modern_6x8_extent560.pdf") as pdf:
        assert pdf[0].rect.width * 25.4 / 72 == pytest.approx(60, abs=0.05)
        assert pdf[0].rect.height * 25.4 / 72 == pytest.approx(80, abs=0.05)
    manifest = json.loads((product / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["print_size"] == {
        "label": "6x8", "catalog_key": None, "width_cm": 6, "height_cm": 8, "width_mm": 60, "height_mm": 80,
        "orientation": "portrait",
    }
    assert set(manifest["files"]) == {"pdf", "preview_webp"}
    assert manifest["source"]["type"] == "osm_xml" and manifest["source"]["identity"]["sha256"]
    assert manifest["viewport"]["renderer_half_width_m"] == pytest.approx(
        get_viewport_for_style("urban_modern", spec_from_dimensions(6, 8, extent_m=EXTENT_M))[0]
    )
    assert manifest["viewport"]["renderer_half_height_m"] == EXTENT_M
    assert manifest["cache_policy"]["persistent_store"] is None
    assert manifest["cache_policy"]["temporary_store_removed"] is True
    assert manifest["files"]["preview_webp"]["bytes"] <= 150_000
    assert max(manifest["files"]["preview_webp"]["width_px"], manifest["files"]["preview_webp"]["height_px"]) <= 1400
    assert manifest["bundle"]["roads"]["edges"] > 0
    assert manifest["resources"]["temporary_disk_peak_bytes"] > 0
    assert xml_store["xml"].stat().st_mtime_ns == source_before.st_mtime_ns


def test_failed_xml_order_cleans_up_and_keeps_source_and_previous_product(xml_store, tmp_path, monkeypatch):
    _order(xml_store["xml"], tmp_path)
    product = tmp_path / "out" / "testville" / "testville_urban_modern_6x8_extent560"
    before = {p.name: p.read_bytes() for p in product.iterdir()}

    def fail(**_kwargs):
        raise RuntimeError("injected render failure")

    monkeypatch.setattr(xml_order, "render_product", fail)
    result = _order(xml_store["xml"], tmp_path)

    assert result["success"] == 0 and result["failed"] == 1
    assert "injected render failure" in result["results"]["6x8"]["error"]
    assert _leftovers(tmp_path) == []
    assert {p.name: p.read_bytes() for p in product.iterdir()} == before
    assert xml_store["xml"].is_file()


def test_rerender_replaces_product_holding_retired_print_webp(xml_store, tmp_path):
    _order(xml_store["xml"], tmp_path)
    product = tmp_path / "out" / "testville" / "testville_urban_modern_6x8_extent560"
    (product / "testville_urban_modern_6x8_extent560.webp").write_bytes(b"legacy print webp")

    result = _order(xml_store["xml"], tmp_path)

    assert result["success"] == 1
    assert not (product / "testville_urban_modern_6x8_extent560.webp").exists()


def test_failed_store_build_cleans_up(xml_store, tmp_path, monkeypatch):
    def fail(*_args, **_kwargs):
        raise PbfStoreError("injected build failure")

    monkeypatch.setattr(pbf_store, "build_store", fail)
    with pytest.raises(PbfStoreError, match="injected build failure"):
        _order(xml_store["xml"], tmp_path)
    assert _leftovers(tmp_path) == []
    assert xml_store["xml"].is_file()


def test_opt_in_persistent_store_is_reused(xml_store, tmp_path):
    persistent = tmp_path / "persistent"
    first = _order(xml_store["xml"], tmp_path, persistent_store_dir=persistent)
    second = _order(xml_store["xml"], tmp_path, persistent_store_dir=persistent)
    first_policy = first["results"]["6x8"]["manifest"]["cache_policy"]
    second_policy = second["results"]["6x8"]["manifest"]["cache_policy"]
    assert first_policy["store_reused"] is False and second_policy["store_reused"] is True
    assert (persistent / pbf_store.STORE_FILENAME).is_file()


def test_effective_coverage_matches_requested_rectangle():
    spec = spec_from_dimensions(50, 70, extent_m=4000)
    coverage = xml_order.effective_coverage(CENTER_LAT, CENTER_LON, *spec.frame_half_sizes_m)
    assert coverage["width_m"] == pytest.approx(2 * 4000 * 50 / 70)
    assert coverage["height_m"] == 8000
    west, south, east, north = coverage["wgs84_bounds"]
    assert west < CENTER_LON < east and south < CENTER_LAT < north
