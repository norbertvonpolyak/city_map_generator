from __future__ import annotations

from typing import Literal

from generator.specs import ProductLine, ProductSpec


LayoutPreset = Literal["default"]


# -----------------------------------------------------------------------------
# Preset kiválasztás
# -----------------------------------------------------------------------------

def choose_layout_preset(
    *,
    product_line: ProductLine,
    spec: ProductSpec,
) -> LayoutPreset:
    return "default"
