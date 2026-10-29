"""M3 guards: OSMnx contract, query geometry parity with the production loader, and isolation."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import osmnx as ox
import pytest
from osmnx import graph as ox_graph

from generator.core import osm_bundle_cache, pbf_source
from generator.core.pbf_source import (
    CoverageError,
    OsmnxContractError,
    PbfBundleSource,
    bundle_dist_m,
    check_osmnx_contract,
    query_polygon,
    road_query_polygon,
)
from pbf_source_data import EXTENT_M, HALF_HEIGHT_M, HALF_WIDTH_M, build_store, engine_dataset, pbf_elements
from support.overpass_fake import FakeOverpass
from support.synthetic_osm import CENTER_LAT, CENTER_LON

REPO = Path(__file__).resolve().parents[2]


def test_osmnx_contract_holds():
    check_osmnx_contract()


def test_osmnx_version_guard(monkeypatch):
    monkeypatch.setattr(ox, "__version__", "2.1.0")
    with pytest.raises(OsmnxContractError, match="2.0.7"):
        check_osmnx_contract()


def test_private_signature_guard(monkeypatch):
    monkeypatch.setattr(ox_graph, "_create_graph", lambda response_jsons, *, bidirectional: None)
    with pytest.raises(OsmnxContractError, match="_create_graph"):
        check_osmnx_contract()


@pytest.mark.parametrize("half_width_m, half_height_m", [(420.0, 560.0), (2262.295081967213, 3000.0), (1.0, 1.0)])
def test_dist_formula_matches_production(monkeypatch, half_width_m, half_height_m):
    seen = {}

    def fake_graph(*args, **kwargs):
        seen["dist"] = kwargs["dist"]
        raise RuntimeError("stop")

    monkeypatch.setattr(osm_bundle_cache.ox, "graph_from_point", fake_graph)
    monkeypatch.setattr(osm_bundle_cache.time, "sleep", lambda _s: None)
    with pytest.raises(RuntimeError, match="stop"):
        osm_bundle_cache.load_or_build_shared_osm_bundle(
            center_lat=CENTER_LAT, center_lon=CENTER_LON, extent_m=EXTENT_M,
            half_width_m=half_width_m, half_height_m=half_height_m, use_cache=False,
        )
    assert seen["dist"] == bundle_dist_m(half_width_m, half_height_m)


def test_query_polygons_equal_production_overpass_polygons(monkeypatch, tmp_path):
    data = engine_dataset(with_coast=False)
    pbf, reader = build_store(tmp_path, data)
    with reader:
        fake = FakeOverpass(pbf_elements(pbf)).install(monkeypatch)
        osm_bundle_cache.load_or_build_shared_osm_bundle(
            center_lat=CENTER_LAT, center_lon=CENTER_LON, extent_m=EXTENT_M,
            half_width_m=HALF_WIDTH_M, half_height_m=HALF_HEIGHT_M, use_cache=False,
        )
        dist_m = bundle_dist_m(HALF_WIDTH_M, HALF_HEIGHT_M)
        polygon = query_polygon(CENTER_LAT, CENTER_LON, dist_m)
        assert fake.network_calls[0][0].equals_exact(road_query_polygon(polygon), 0)
        assert all(call[0].equals_exact(polygon, 0) for call in fake.feature_calls)


def test_coverage_error_outside_header_bbox(tmp_path):
    _, reader = build_store(tmp_path, engine_dataset(with_coast=False))
    with reader:
        source = PbfBundleSource(reader)
        # The 1000 m box plus 500 m road buffer crosses the 19.2 degree east header edge.
        with pytest.raises(CoverageError, match="header bbox"):
            source.load_bundle(
                center_lat=CENTER_LAT, center_lon=19.19, extent_m=EXTENT_M,
                half_width_m=HALF_WIDTH_M, half_height_m=HALF_HEIGHT_M,
            )
        assert source.last_stats == {}


def test_load_bundle_signature_matches_production():
    import inspect

    production = inspect.signature(osm_bundle_cache.load_or_build_shared_osm_bundle)
    adapter = inspect.signature(PbfBundleSource.load_bundle)
    assert list(adapter.parameters)[1:] == list(production.parameters)
    for name, param in production.parameters.items():
        assert adapter.parameters[name].default == param.default
        assert adapter.parameters[name].kind == param.kind


def test_production_imports_pbf_code_only_lazily_from_bundle_loader():
    # M4 contract: the core loader and explicit batch entry point import PBF code lazily.
    any_import = re.compile(r"^\s*(from|import)\s+[\w.]*\bpbf_(source|store)\b|^\s*import\s+.*\bpbf_(source|store)\b", re.M)
    top_level_import = re.compile(r"^(from|import)\s+[\w.]*\bpbf_(source|store)\b|^import\s+.*\bpbf_(source|store)\b", re.M)
    allowed = {Path(pbf_source.__file__).resolve(), (REPO / "generator" / "core" / "pbf_store.py").resolve()}
    loader = (REPO / "generator" / "core" / "osm_bundle_cache.py").resolve()
    batch_modules = {
        (REPO / "generator" / "batch.py").resolve(),
        (REPO / "generator" / "batch_pipeline.py").resolve(),
        (REPO / "generator" / "order_cache.py").resolve(),
        (REPO / "generator" / "order_renderer.py").resolve(),
        (REPO / "generator" / "xml_order.py").resolve(),
    }
    offenders = []
    for path in [*REPO.glob("*.py"), *(REPO / "generator").rglob("*.py")]:
        if path.resolve() in allowed:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.resolve() == loader:
            if top_level_import.search(text):
                offenders.append(f"{path.relative_to(REPO)} (top-level)")
            continue
        if path.resolve() in batch_modules:
            tree = ast.parse(text)
            for statement in tree.body:
                if isinstance(statement, ast.ImportFrom) and statement.module and re.search(
                    r"\bpbf_(source|store)\b", statement.module
                ):
                    offenders.append(f"{path.relative_to(REPO)} (top-level)")
                elif isinstance(statement, ast.Import) and any(
                    re.search(r"\bpbf_(source|store)\b", alias.name) for alias in statement.names
                ):
                    offenders.append(f"{path.relative_to(REPO)} (top-level)")
            continue
        if any_import.search(text):
            offenders.append(str(path.relative_to(REPO)))
    assert offenders == []
    loader_text = loader.read_text(encoding="utf-8")
    assert loader_text.count("from generator.core.pbf_source import load_bundle_from_env") == 1
