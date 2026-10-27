from __future__ import annotations

import pytest

pytest.importorskip("osmium")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "requires_pbf: needs the external Hungary PBF; opt-in via MAPCANVAS_PBF_INTEGRATION=1",
    )
