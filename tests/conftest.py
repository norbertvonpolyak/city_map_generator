from __future__ import annotations

import osmnx as ox
import pytest
import requests

from generator.core import cache as core_cache
from generator.core import osm_bundle_cache


@pytest.fixture(autouse=True)
def offline_isolated_env(monkeypatch, tmp_path):
    def _blocked(*args, **kwargs):
        raise RuntimeError("Network access is disabled during tests.")

    monkeypatch.setattr(requests.sessions.Session, "request", _blocked)

    monkeypatch.setattr(ox.settings, "use_cache", False)
    monkeypatch.setattr(ox.settings, "cache_folder", str(tmp_path / "osmnx_http_cache"))
    # _run_with_overpass_fallback mutates overpass_url; registering it restores the original afterwards.
    monkeypatch.setattr(ox.settings, "overpass_url", ox.settings.overpass_url)

    bundle_cache_dir = tmp_path / "bundle_cache"
    bundle_cache_dir.mkdir()
    monkeypatch.setattr(core_cache, "CACHE_DIR", bundle_cache_dir)
    monkeypatch.setattr(osm_bundle_cache, "_cache_dir", lambda: bundle_cache_dir)

    monkeypatch.delenv("OVERPASS_DEBUG", raising=False)
    monkeypatch.delenv("OSM_OVERPASS_ENDPOINTS", raising=False)
    return bundle_cache_dir
