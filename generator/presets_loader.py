from __future__ import annotations

from enum import Enum
from typing import Literal

from generator.specs import ProductLine, ProductSpec


# -----------------------------------------------------------------------------
# Layout preset kulcsok
# -----------------------------------------------------------------------------

LayoutPreset = Literal[
    "default",              # citymap / fallback
    "legacy_portrait",      # starmap álló (körös, régi arányos)
    "banded_square_50",     # starmap 50x50 speciális keretsávos
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
      - 50x50  -> banded_square_50
      - minden más (álló) -> legacy_portrait

    CITYMAP:
      - default (render mód dönti el a részleteket)
    """

    # -----------------
    # STARMAP
    # -----------------
    if product_line == ProductLine.STARMAP:
        if spec.width_cm == 50 and spec.height_cm == 50:
            return "banded_square_50"
        return "legacy_portrait"

    # -----------------
    # CITYMAP (blocks / pretty / mono)
    # -----------------
    return "default"
