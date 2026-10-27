"""Optional real-PBF checks. Skipped unless explicitly enabled; never part of the default offline suite.

MAPCANVAS_PBF_INTEGRATION=1      read the external Hungary PBF header only.
MAPCANVAS_PBF_FULL_BUILD=1       additionally run a full build (stage S4, requires separate approval)
                                 into MAPCANVAS_PBF_STORE_DIR, which must be set explicitly.
MAPCANVAS_PBF_PATH               overrides the default PBF location outside the repository.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from generator.core import pbf_store

DEFAULT_PBF = Path(__file__).resolve().parents[3] / "GEOFABRIK" / "hungary-260918.osm.pbf"

pytestmark = [
    pytest.mark.requires_pbf,
    pytest.mark.skipif(
        os.environ.get("MAPCANVAS_PBF_INTEGRATION") != "1", reason="real-PBF checks need MAPCANVAS_PBF_INTEGRATION=1",
    ),
]


@pytest.fixture
def real_pbf() -> Path:
    path = Path(os.environ.get("MAPCANVAS_PBF_PATH", DEFAULT_PBF))
    if not path.is_file():
        pytest.skip(f"external PBF not available: {path}")
    return path


def test_real_pbf_header_is_readable(real_pbf):
    header = pbf_store.read_pbf_header(real_pbf)
    assert header["bbox"] is not None
    assert not header["multiple_object_versions"]


@pytest.mark.skipif(os.environ.get("MAPCANVAS_PBF_FULL_BUILD") != "1", reason="full build is stage S4")
def test_real_pbf_full_build(real_pbf):
    store_dir = os.environ.get("MAPCANVAS_PBF_STORE_DIR")
    if not store_dir:
        pytest.skip("MAPCANVAS_PBF_STORE_DIR must be set explicitly for a full build")
    result = pbf_store.build_store(real_pbf, Path(store_dir))
    with pbf_store.PbfStoreReader(store_dir, pbf_path=real_pbf) as reader:
        assert reader.counts == result.counts
