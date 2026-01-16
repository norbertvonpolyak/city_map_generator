from __future__ import annotations

from dataclasses import dataclass
from math import gcd
from typing import Tuple

# --- webshop termékméretek (cm) ---
SIZES_CM = {
    "21x30": (21, 30),
    "30x21": (31, 21),
    "30x40": (30, 40),
    "40x30": (40, 30),
    "40x50": (40, 50),
    "50x40": (40, 50),
    "50x70": (50, 70),
    "70x50": (70, 50),
    "61x91": (61, 91),
    "91x61": (91, 61),
    "32x32": (32, 32),
    "50x50": (50, 50),
}

DEFAULT_EXTENT_M = 5000  # félmagasság méterben (default)


@dataclass(frozen=True)
class ProductSpec:
    width_cm: int
    height_cm: int
    extent_m: int = DEFAULT_EXTENT_M
    dpi: int = 300  # PNG-hez releváns, PDF-nél metadata

    @property
    def aspect_ratio(self) -> Tuple[int, int]:
        """Egyszerűsített képarány (w:h)."""
        g = gcd(self.width_cm, self.height_cm)
        return (self.width_cm // g, self.height_cm // g)

    @property
    def fig_size_inches(self) -> Tuple[float, float]:
        """Export fizikai mérete inch-ben (PDF/PNG méretezéshez)."""
        return (self.width_cm / 2.54, self.height_cm / 2.54)

    @property
    def frame_half_sizes_m(self) -> Tuple[float, float]:
        """
        (half_width_m, half_height_m) méterben.
        extent_m = félmagasság.
        """
        ar_w, ar_h = self.aspect_ratio
        half_h = float(self.extent_m)
        half_w = half_h * (ar_w / ar_h)
        return half_w, half_h


def spec_from_size_key(size_key: str, extent_m: int = DEFAULT_EXTENT_M, dpi: int = 300) -> ProductSpec:
    if size_key not in SIZES_CM:
        raise ValueError(f"Ismeretlen méret kulcs: {size_key}. Választható: {list(SIZES_CM.keys())}")
    w, h = SIZES_CM[size_key]
    return ProductSpec(width_cm=w, height_cm=h, extent_m=extent_m, dpi=dpi)
