from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Any


# =============================================================================
# SIMPLE STYLE (nem-monochrome, legacy / blocks render)
# =============================================================================

@dataclass(frozen=True)
class Style:
    background: str
    road: str
    bridge: str
    water: str


DEFAULT_STYLE = Style(
    background="#e0dbc8",
    road="#FFFFFF",        # középszürke utak (MÓDOSÍTVA)
    bridge="#FFFFFF",      # sötétebb hidak (MÓDOSÍTVA)
    water="#5BA29D",
)


# =============================================================================
# COLOR PALETTES (polygonize-based city blocks)
# =============================================================================
# FONTOS: világostól sötét felé rendezve

PALETTES: Dict[str, List[str]] = {
    "warm":             ["#e28c41","#cd6d40","#e7b573","#e39f55","#c86a3d","#b55a3a","#9b4d37"], #szuper
    "urban_modern": ["#E8891C","#D26A1E","#C65A2A","#E2C79F","#F0A21A","#7C7368","#2F2F2F"],
    "amber_district": [ "#2f2f33", "#4a4a4a","#8c7a5b", "#b89b5e", "#d4b35f", "#e2cfa4", "#c76a3a"], #szuper
    "slate_harbor": ["#2c333a", "#4f5d6a", "#7a8c99", "#a7b5b8", "#c9cfcb", "#bfae9f", "#9e8c7a"],
    "grayscale":        ["#f2f2f2","#d9d9d9","#bfbfbf","#8c8c8c","#737373","#595959","#535353"], # #92B2C4 vízszínnel megy jól
    "pastel":           ["#ffcb77","#eed3a6","#dddad5","#eea4a4","#fe6d73","#17c3b2","#227c9d"], #nem jó
    "bronze":           ["#bfbdc1","#6d6a75","#524e5a","#37323e","#8b7540","#deb841","#de9e36"]
}

def get_palette(name: str) -> List[str]:
    """
    City map renderhez használt paletta lekérdezés.
    A render.py ezt várja: get_palette(palette_name) -> list of hex colors.

    - Ha nincs ilyen paletta: ValueError (jobb, mint a silent fallback)
    """
    if not name:
        raise ValueError("palette name is empty")

    if name not in PALETTES:
        raise ValueError(f"Unknown palette: {name}. Available: {list(PALETTES.keys())}")

    return PALETTES[name]


# =============================================================================
# MONO STYLE (render_monochrome)
# =============================================================================

@dataclass(frozen=True)
class MonoStyle:
    # általános
    background_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)
    ink_rgb: tuple[float, float, float] = (0.1, 0.1, 0.1)

    # vonalak
    road_alpha: float = 0.85
    bridge_alpha: float = 0.55
    water_alpha: float = 0.0

    # kitöltések
    land_alpha: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

MONO_PRESETS = {
    "default": None,  # sentinel: a render_monochrome fallbackoljon a DEFAULT_MONO_STYLE-ra
}

DEFAULT_MONO_STYLE = MonoStyle()


# =============================================================================
# STARMAP STYLE (render_stars)
# =============================================================================

@dataclass(frozen=True)
class StarMapStyle:
    # page / paper
    page_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)   # fehér lap

    # sky (map area)
    sky_rgb: tuple[float, float, float] = (0.0, 0.0, 0.0)    # fekete ég
    star_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)   # fehér csillag

    # typography
    text_rgb: tuple[float, float, float] = (0.0, 0.0, 0.0)   # fekete szöveg

    # milky way fog
    mw_fog_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)
    mw_fog_alpha: float = 0.05

    # glow
    glow_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)
    glow_alpha_1: float = 0.10
    glow_alpha_2: float = 0.06

    # circle outline
    circle_stroke_rgb: tuple[float, float, float] = (0.70, 0.70, 0.70)
    circle_stroke_alpha: float = 0.65
    circle_stroke_width: float = 0.8

    # subtle drop shadow around circle (VERY gentle)
    shadow_dx_pt: float = 1.8
    shadow_dy_pt: float = -1.8
    shadow_alpha_max: float = 0.10
    shadow_steps: int = 4
    shadow_spread_pt: float = 3.0

    # layout tuning
    portrait_side_clear_frac: float = 0.07
    portrait_radius_scale: float = 0.90
    portrait_min_gap_frac: float = 0.055

    # typography BASE sizes (30x40 baseline; renderben dinamikusan skálázunk)
    portrait_title_size: float = 99.0
    portrait_motto_size: float = 26.0
    portrait_line2_size: float = 16.5
    portrait_line3_size: float = 15.75
    portrait_track1: float = 2.0
    portrait_track2: float = 1.68
    portrait_track3: float = 1.44

    # square 50x50 band
    square50_band_height_frac: float = 0.12   # <-- vékonyabb (kb fele vagy kevesebb)
    square50_band_fill_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)
    square50_band_alpha: float = 0.50         # <-- 50% áttetsző
    square50_text_rgb: tuple[float, float, float] = (0.0, 0.0, 0.0)

    square50_track1: float = 1.9
    square50_track2: float = 1.6
    square50_track3: float = 1.35

    # densities
    portrait_bg_count: int = 2600
    square50_bg_count: int = 3200

    # milky way band model
    band_sigma: float = 0.18
    band_strength_portrait: float = 0.70
    band_strength_square50: float = 0.75

    # star visibility
    star_min_radius_pt: float = 1.15  # biztosan látszik preview-ban is

    # procedural dust (fine star texture)
    dust_count_portrait: int = 1400
    dust_count_square50: int = 2200
    dust_min_size_pt: float = 1.05
    dust_max_size_pt: float = 1.45
    dust_band_bias: float = 0.55
    dust_alpha: float = 0.28
    dust_use_circles: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_STARMAP_STYLE = StarMapStyle()