"""M3 engine smoke tests: every registered style renders from a PBF-store bundle (synthetic data, offline)."""

from __future__ import annotations

import pytest

from generator.core import osm_bundle_cache
from generator.core.pbf_source import PbfBundleSource
from generator.core.style_registry import STYLE_REGISTRY, EngineType
from generator.engines import render_block, render_building, render_line
from generator.specs import ProductSpec
from pbf_source_data import EXTENT_M, HALF_HEIGHT_M, HALF_WIDTH_M, build_store, engine_dataset
from support.synthetic_osm import CENTER_LAT, CENTER_LON

ENGINES = {
    EngineType.BLOCK: (render_block, render_block.render_map_block),
    EngineType.BUILDING: (render_building, render_building.render_map_building),
    EngineType.LINE: (render_line, render_line.render_map_line),
}
# The keyword the production engine passes (absent for Block, which relies on the default False).
EXPECTED_BUILDING_FEATURES = {EngineType.BLOCK: False, EngineType.BUILDING: True, EngineType.LINE: True}


@pytest.fixture(scope="module", params=[False, True], ids=["inland", "coast"])
def store(request, tmp_path_factory):
    _, reader = build_store(tmp_path_factory.mktemp("engine_store"), engine_dataset(with_coast=request.param))
    yield reader
    reader.close()


def _render(monkeypatch, tmp_path, reader, style, **extra):
    engine = STYLE_REGISTRY[style].engine
    module, render = ENGINES[engine]
    source = PbfBundleSource(reader)
    calls = []

    def loader(**kwargs):
        calls.append(kwargs)
        return source.load_bundle(**kwargs)

    for other, _ in ENGINES.values():
        monkeypatch.setattr(other, "load_or_build_shared_osm_bundle", loader)
    result = render(
        center_lat=CENTER_LAT, center_lon=CENTER_LON,
        spec=ProductSpec(width_cm=6, height_cm=8, extent_m=EXTENT_M, dpi=40),
        map_width_cm=6.0, map_height_cm=8.0,
        viewport_half_width_m=HALF_WIDTH_M, viewport_half_height_m=HALF_HEIGHT_M,
        bundle_half_width_m=HALF_WIDTH_M, bundle_half_height_m=HALF_HEIGHT_M,
        output_dir=tmp_path, palette_name=style, preview_mode=True, use_cache=False, **extra,
    )
    return engine, result, calls, source.last_stats


@pytest.mark.parametrize("style", sorted(STYLE_REGISTRY))
def test_style_renders_from_pbf_bundle(monkeypatch, tmp_path, store, style):
    engine, result, calls, stats = _render(monkeypatch, tmp_path, store, style)
    assert len(calls) == 1
    include = calls[0].get("include_building_features", False)
    assert include is EXPECTED_BUILDING_FEATURES[engine]
    assert stats["layers_requested"] == osm_bundle_cache._select_required_feature_layers(include, False)
    assert result.output_svg is not None and result.output_svg.stat().st_size > 0


@pytest.mark.working_tree
def test_buildings_only_mode_renders_from_pbf_bundle(monkeypatch, tmp_path, store):
    _, result, calls, stats = _render(monkeypatch, tmp_path, store, "midnight_blue", buildings_only=True)
    assert calls[0]["buildings_only_mode"] is True
    assert stats["layers_requested"] == ["buildings"]
    assert result.output_svg.stat().st_size > 0
