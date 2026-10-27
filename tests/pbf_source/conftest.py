from __future__ import annotations

import matplotlib
import pytest

pytest.importorskip("osmium")

# Engine smoke tests render real figures; keep them headless.
matplotlib.use("Agg")
