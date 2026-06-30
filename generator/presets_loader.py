from __future__ import annotations

from enum import Enum
from typing import Literal

from generator.specs import ProductLine, ProductSpec


# -----------------------------------------------------------------------------
# Layout preset kulcsok
# -----------------------------------------------------------------------------

LayoutPreset = Literal[
    "default",              # citymap / fallback
    "starmap_skyfield",     # rebuilt starmap engine preset
]


# -----------------------------------------------------------------------------
# Preset kiválasztás
# -----------------------------------------------------------------------------

def choose_layout_preset(
    *,
    product_line: ProductLine,
    spec: ProductSpec,
) -> LayoutPreset:
    """
    Központi hely a layout döntésekhez.

    JELENLEGI SZABÁLYOK:

        STARMAP:
            - all sizes -> starmap_skyfield

    CITYMAP:
      - default (render mód dönti el a részleteket)
    """

    # -----------------
    # STARMAP
    # -----------------
    if product_line == ProductLine.STARMAP:
        return "starmap_skyfield"

    # -----------------
    # CITYMAP (blocks / pretty / mono)
    # -----------------
    return "default"
