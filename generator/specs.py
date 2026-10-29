from __future__ import annotations

import math
import numbers
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Tuple, List


# --- webshop termékméretek (cm) ---
# FONTOS: itt minden termékvonal közös "univerzális" listája lehet,
# a termékvonal-specifikus szűrést a get_allowed_size_keys() csinálja.
SIZES_CM = {
    "40x50": (40, 50),
    "50x40": (50, 40),  # <-- FIX: eddig hibásan 40x50 volt

    "50x70": (50, 70),
    "70x50": (70, 50),

    "50x50": (50, 50),

    "60x90": (60, 90),
    "90x60": (90, 60),
}

DEFAULT_EXTENT_M = 5000  # félmagasság méterben (default)


class ProductLine(str, Enum):
    CITYMAP = "citymap"


def get_allowed_size_keys(product_line: ProductLine) -> List[str]:
    """
    Termékvonal-specifikus méretkínálat.

    DÖNTÉSEID:
    - minden termékvonal ugyanazt a hét poster formátumot használja
    """
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


def _positive_finite(name: str, value) -> float | int:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(f"{name} must be a positive finite number, got {value!r}")
    as_float = float(value)
    if not math.isfinite(as_float) or as_float <= 0:
        raise ValueError(f"{name} must be a positive finite number, got {value!r}")
    # Integral values stay ints so size labels remain e.g. "50x70", not "50.0x70.0".
    return int(as_float) if as_float.is_integer() else as_float


def format_size_label(width_cm: float, height_cm: float) -> str:
    return f"{width_cm:g}x{height_cm:g}"


@dataclass(frozen=True)
class ProductSpec:
    width_cm: float
    height_cm: float
    extent_m: float = DEFAULT_EXTENT_M
    dpi: int = 300  # PNG-hez releváns, PDF-nél metadata

    def __post_init__(self) -> None:
        object.__setattr__(self, "width_cm", _positive_finite("width_cm", self.width_cm))
        object.__setattr__(self, "height_cm", _positive_finite("height_cm", self.height_cm))
        object.__setattr__(self, "extent_m", _positive_finite("extent_m", self.extent_m))
        object.__setattr__(self, "dpi", _positive_finite("dpi", self.dpi))

    @property
    def size_label(self) -> str:
        return format_size_label(self.width_cm, self.height_cm)

    @property
    def orientation(self) -> str:
        if self.width_cm > self.height_cm:
            return "landscape"
        if self.width_cm < self.height_cm:
            return "portrait"
        return "square"

    @property
    def aspect_ratio(self) -> Tuple[int, int]:
        ratio = Fraction(str(self.width_cm)) / Fraction(str(self.height_cm))
        return (ratio.numerator, ratio.denominator)

    @property
    def fig_size_inches(self) -> Tuple[float, float]:
        return (self.width_cm / 2.54, self.height_cm / 2.54)

    @property
    def frame_half_sizes_m(self) -> Tuple[float, float]:
        half_h = float(self.extent_m)
        half_w = half_h * self.width_cm / self.height_cm
        return half_w, half_h


def spec_from_size_key(size_key: str, extent_m: int = DEFAULT_EXTENT_M, dpi: int = 300) -> ProductSpec:
    if size_key not in SIZES_CM:
        raise ValueError(f"Ismeretlen méret kulcs: {size_key}. Választható: {list(SIZES_CM.keys())}")
    w, h = SIZES_CM[size_key]
    return ProductSpec(width_cm=w, height_cm=h, extent_m=extent_m, dpi=dpi)


def spec_from_dimensions(
    width_cm: float,
    height_cm: float,
    extent_m: float = DEFAULT_EXTENT_M,
    dpi: int = 300,
) -> ProductSpec:
    """Internal generation entry point: any positive finite physical size, not limited to SIZES_CM."""
    return ProductSpec(width_cm=width_cm, height_cm=height_cm, extent_m=extent_m, dpi=dpi)


def resolve_size_request(size) -> tuple[str, float, float]:
    """Resolve a catalog key (webshop) or an explicit (width_cm, height_cm) pair (internal requests)."""
    if isinstance(size, str):
        if size not in SIZES_CM:
            raise ValueError(f"Unsupported catalog size {size!r}; catalog: {', '.join(SIZES_CM)}")
        width_cm, height_cm = SIZES_CM[size]
        return size, width_cm, height_cm
    if isinstance(size, (tuple, list)) and len(size) == 2:
        width_cm = _positive_finite("print_width_cm", size[0])
        height_cm = _positive_finite("print_height_cm", size[1])
        return format_size_label(width_cm, height_cm), width_cm, height_cm
    raise ValueError(f"Size must be a catalog key or a (print_width_cm, print_height_cm) pair, got {size!r}")
