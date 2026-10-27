"""M4: MAPCANVAS_OSM_SOURCE switch in the production loader (Overpass default, PBF opt-in)."""

from __future__ import annotations

import pytest

from generator.core import osm_bundle_cache, pbf_source
from generator.core.pbf_source import CoverageError, PbfBundleSource
from generator.core.pbf_store import PbfStoreError
from generator.core.style_registry import STYLE_REGISTRY
from generator.engines import render_block, render_building, render_line
from generator.specs import ProductSpec
from pbf_source_data import EXTENT_M, HALF_HEIGHT_M, HALF_WIDTH_M, build_store, engine_dataset, pbf_elements
from support.overpass_fake import FakeOverpass
from support.synthetic_osm import CENTER_LAT, CENTER_LON
from test_pbf_source_parity import assert_bundles_equal

PARAMS = dict(
    center_lat=CENTER_LAT, center_lon=CENTER_LON, extent_m=EXTENT_M,
    half_width_m=HALF_WIDTH_M, half_height_m=HALF_HEIGHT_M, include_building_features=True,
)


@pytest.fixture
def store(tmp_path):
    pbf, reader = build_store(tmp_path / "data", engine_dataset(with_coast=True))
    reader.close()
    return {"pbf": pbf, "store_dir": tmp_path / "data" / "store"}


def _forbid_pbf(monkeypatch):
    def fail(**_kwargs):
        raise AssertionError("PBF path must not run when the Overpass source is selected")

    monkeypatch.setattr(pbf_source, "load_bundle_from_env", fail)


@pytest.mark.parametrize("value", [None, "", "overpass", " OVERPASS "])
def test_overpass_is_default_and_unchanged(monkeypatch, store, value):
    if value is not None:
        monkeypatch.setenv("MAPCANVAS_OSM_SOURCE", value)
    _forbid_pbf(monkeypatch)
    fake = FakeOverpass(pbf_elements(store["pbf"])).install(monkeypatch)
    osm_bundle_cache.load_or_build_shared_osm_bundle(use_cache=False, **PARAMS)
    assert len(fake.network_calls) == 1
    assert len(fake.feature_calls) == len(osm_bundle_cache._FEATURE_LAYER_SPECS)


def test_pbf_source_equals_overpass_bundle_without_network(monkeypatch, store, offline_isolated_env):
    fake = FakeOverpass(pbf_elements(store["pbf"])).install(monkeypatch)
    expected = osm_bundle_cache.load_or_build_shared_osm_bundle(use_cache=False, **PARAMS)
    calls = (len(fake.network_calls), len(fake.feature_calls))

    monkeypatch.setenv("MAPCANVAS_OSM_SOURCE", "pbf")
    monkeypatch.setenv("MAPCANVAS_PBF_STORE_DIR", str(store["store_dir"]))
    monkeypatch.setenv("MAPCANVAS_PBF_PATH", str(store["pbf"]))
    actual = osm_bundle_cache.load_or_build_shared_osm_bundle(use_cache=True, **PARAMS)

    assert_bundles_equal(actual, expected)
    assert (len(fake.network_calls), len(fake.feature_calls)) == calls
    # No pickle cache for PBF bundles, even with use_cache=True.
    assert list(offline_isolated_env.iterdir()) == []


def test_pbf_source_requires_store_dir(monkeypatch):
    monkeypatch.setenv("MAPCANVAS_OSM_SOURCE", "pbf")
    monkeypatch.delenv("MAPCANVAS_PBF_STORE_DIR", raising=False)
    with pytest.raises(PbfStoreError, match="MAPCANVAS_PBF_STORE_DIR"):
        osm_bundle_cache.load_or_build_shared_osm_bundle(**PARAMS)


def test_pbf_path_mismatch_is_rejected(monkeypatch, store, tmp_path):
    other = tmp_path / "other.osm.pbf"
    other.write_bytes(b"not the indexed extract")
    monkeypatch.setenv("MAPCANVAS_OSM_SOURCE", "pbf")
    monkeypatch.setenv("MAPCANVAS_PBF_STORE_DIR", str(store["store_dir"]))
    monkeypatch.setenv("MAPCANVAS_PBF_PATH", str(other))
    with pytest.raises(PbfStoreError, match="size or modification time"):
        osm_bundle_cache.load_or_build_shared_osm_bundle(**PARAMS)


def test_out_of_coverage_raises_without_fallback(monkeypatch, store):
    _forbid_overpass = FakeOverpass([]).install(monkeypatch)
    monkeypatch.setenv("MAPCANVAS_OSM_SOURCE", "pbf")
    monkeypatch.setenv("MAPCANVAS_PBF_STORE_DIR", str(store["store_dir"]))
    with pytest.raises(CoverageError):
        osm_bundle_cache.load_or_build_shared_osm_bundle(**{**PARAMS, "center_lon": 19.19})
    assert _forbid_overpass.network_calls == [] and _forbid_overpass.feature_calls == []


def test_unknown_source_value_is_rejected(monkeypatch):
    monkeypatch.setenv("MAPCANVAS_OSM_SOURCE", "geofabrik")
    with pytest.raises(ValueError, match="MAPCANVAS_OSM_SOURCE"):
        osm_bundle_cache.load_or_build_shared_osm_bundle(**PARAMS)


def test_overpass_cache_filenames_unchanged():
    assert osm_bundle_cache._build_road_graph_cache_filename(
        center_lat=CENTER_LAT, center_lon=CENTER_LON, dist_m=1000, simplify=True,
    ) == "osm_road_graph_47.497912_19.040235_rfa3a91803c061_s1_v1_normal_map_v1_d1000.pkl"


@pytest.mark.parametrize("style", ["urban_modern", "midnight_blue", "mp_noir_gold"])
def test_engines_use_switch_through_their_imported_loader(monkeypatch, store, tmp_path, style):
    FakeOverpass([]).install(monkeypatch)
    monkeypatch.setenv("MAPCANVAS_OSM_SOURCE", "pbf")
    monkeypatch.setenv("MAPCANVAS_PBF_STORE_DIR", str(store["store_dir"]))
    seen = []
    original = PbfBundleSource.load_bundle

    def spy(self, **kwargs):
        seen.append(kwargs)
        return original(self, **kwargs)

    monkeypatch.setattr(PbfBundleSource, "load_bundle", spy)
    render = {
        "block": render_block.render_map_block,
        "building": render_building.render_map_building,
        "line": render_line.render_map_line,
    }[STYLE_REGISTRY[style].engine.value]
    result = render(
        center_lat=CENTER_LAT, center_lon=CENTER_LON,
        spec=ProductSpec(width_cm=6, height_cm=8, extent_m=EXTENT_M, dpi=40),
        map_width_cm=6.0, map_height_cm=8.0,
        viewport_half_width_m=HALF_WIDTH_M, viewport_half_height_m=HALF_HEIGHT_M,
        bundle_half_width_m=HALF_WIDTH_M, bundle_half_height_m=HALF_HEIGHT_M,
        output_dir=tmp_path / "out", palette_name=style, preview_mode=True, use_cache=False,
    )
    assert len(seen) == 1
    assert result.output_svg.stat().st_size > 0
