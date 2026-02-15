from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import gcd
from typing import Tuple, List


# --- webshop termékméretek (cm) ---
# FONTOS: itt minden termékvonal közös "univerzális" listája lehet,
# a termékvonal-specifikus szűrést a get_allowed_size_keys() csinálja.
SIZES_CM = {

    "30x40": (30, 40),
    "40x30": (40, 30),

    "40x50": (40, 50),
    "50x40": (50, 40),  # <-- FIX: eddig hibásan 40x50 volt

    "50x70": (50, 70),
    "70x50": (70, 50),

    "61x91": (61, 91),
    "91x61": (91, 61),

    "32x32": (32, 32),
    "50x50": (50, 50),
}

DEFAULT_EXTENT_M = 5000  # félmagasság méterben (default)


class ProductLine(str, Enum):
    CITYMAP = "citymap"
    STARMAP = "starmap"


def get_allowed_size_keys(product_line: ProductLine) -> List[str]:
    """
    Termékvonal-specifikus méretkínálat.

    DÖNTÉSEID:
    - STARMAP: csak álló méretek (21x30, 30x40, 40x50) + speciális 50x50
    - CITYMAP: nem érinti, maradhat a teljes választék
    """
    if product_line == ProductLine.STARMAP:
        return ["21x30", "30x40", "40x50", "50x50"]
    return list(SIZES_CM.keys())


def validate_size_key_for_product_line(size_key: str, product_line: ProductLine) -> None:
    """
    A main.py ezt hívja indításkor.

    - Ha a size_key nem létezik a globális listában -> ValueError
    - Ha létezik, de az adott termékvonalnál nem engedett -> ValueError
    """
    if size_key not in SIZES_CM:
        raise ValueError(
            f"Ismeretlen méret kulcs: {size_key}. Választható: {list(SIZES_CM.keys())}"
        )

    allowed = get_allowed_size_keys(product_line)
    if size_key not in allowed:
        raise ValueError(
            f"A(z) {size_key} méret nem engedélyezett ehhez a termékvonalhoz: {product_line.value}. "
            f"Engedélyezett méretek: {allowed}"
        )


@dataclass(frozen=True)
class ProductSpec:
    width_cm: int
    height_cm: int
    extent_m: int = DEFAULT_EXTENT_M
    dpi: int = 300  # PNG-hez releváns, PDF-nél metadata

    @property
    def aspect_ratio(self) -> Tuple[int, int]:
        g = gcd(self.width_cm, self.height_cm)
        return (self.width_cm // g, self.height_cm // g)

    @property
    def fig_size_inches(self) -> Tuple[float, float]:
        return (self.width_cm / 2.54, self.height_cm / 2.54)

    @property
    def frame_half_sizes_m(self) -> Tuple[float, float]:
        ar_w, ar_h = self.aspect_ratio
        half_h = float(self.extent_m)
        half_w = half_h * (ar_w / ar_h)
        return half_w, half_h


def spec_from_size_key(size_key: str, extent_m: int = DEFAULT_EXTENT_M, dpi: int = 300) -> ProductSpec:
    if size_key not in SIZES_CM:
        raise ValueError(f"Ismeretlen méret kulcs: {size_key}. Választható: {list(SIZES_CM.keys())}")
    w, h = SIZES_CM[size_key]
    return ProductSpec(width_cm=w, height_cm=h, extent_m=extent_m, dpi=dpi)
