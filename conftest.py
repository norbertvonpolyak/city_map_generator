import pytest


@pytest.fixture(autouse=True)
def _default_osm_source(monkeypatch):
    # A shell with MAPCANVAS_OSM_SOURCE=pbf must not reroute the offline tests; tests opt in explicitly.
    monkeypatch.delenv("MAPCANVAS_OSM_SOURCE", raising=False)
