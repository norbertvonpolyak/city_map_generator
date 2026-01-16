from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import matplotlib.patheffects as pe
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle


@dataclass(frozen=True)
class FontSet:
    city_font: Path
    country_font: Path
    coords_font: Path


def load_fonts(font_dir: Path) -> FontSet:
    """
    A megadott mappából betölti a fontokat.
    Elvárt fájlnevek:
      - six-hands-black.ttf
      - Jingleberry.otf
      - SwungNote.otf
    """
    font_dir = Path(font_dir)

    city = font_dir / "six-hands-black.ttf"
    country = font_dir / "Jingleberry.otf"
    coords = font_dir / "SwungNote.otf"

    missing = [str(p) for p in (city, country, coords) if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Hiányzó fontfájl(ok): {missing}")

    return FontSet(city_font=city, country_font=country, coords_font=coords)


def to_dms(lat: float, lon: float) -> str:
    """
    Decimal degree -> DMS formátum, a mintához hasonlóan:
    51°29′33″N 0°19′03″W
    """
    def _one(value: float, is_lat: bool) -> str:
        hemi = ("N" if value >= 0 else "S") if is_lat else ("E" if value >= 0 else "W")
        v = abs(value)
        deg = int(v)
        rem = (v - deg) * 60
        minutes = int(rem)
        seconds = int(round((rem - minutes) * 60))

        # kerekítésből lehet 60 mp -> carry
        if seconds == 60:
            seconds = 0
            minutes += 1
        if minutes == 60:
            minutes = 0
            deg += 1

        return f"{deg}°{minutes:02d}′{seconds:02d}″{hemi}"

    return f"{_one(lat, True)} {_one(lon, False)}"


def add_poster_layout(
    *,
    fig,
    city: str,
    country: str,
    coord_text: str,
    fonts: FontSet,
    # Layout paraméterek (később preseteljük méret szerint)
    frame_margin: float = 0.03,
    frame_lw: float = 2.0,
    # Szöveg pozíciók figure koordinátában (0..1)
    city_y: float = 0.105,
    country_y: float = 0.075,
    coords_y: float = 0.045,
    # Színek
    text_color: str = "#f2f2f2",
    # Méretezés (később spec alapján skálázzuk)
    city_size: float = 44,
    country_size: float = 18,
    coords_size: float = 16,
) -> None:
    """
    Keret + alsó címblokk a megadott stílusban és pozícióban.
    """
    # Keret
    rect = Rectangle(
        (frame_margin, frame_margin),
        1 - 2 * frame_margin,
        1 - 2 * frame_margin,
        transform=fig.transFigure,
        fill=False,
        linewidth=frame_lw,
        edgecolor=text_color,
    )
    fig.add_artist(rect)

    # FontProperties
    fp_city = FontProperties(fname=str(fonts.city_font))
    fp_country = FontProperties(fname=str(fonts.country_font))
    fp_coords = FontProperties(fname=str(fonts.coords_font))

    # Finom “kontraszt”: halvány sötét körvonal (nyomtatásban is szép)
    stroke = [pe.withStroke(linewidth=3, foreground="black", alpha=0.18)]

    fig.text(
        0.5, city_y, city.upper(),
        ha="center", va="center",
        color=text_color,
        fontsize=city_size,
        fontproperties=fp_city,
        path_effects=stroke,
    )
    fig.text(
        0.5, country_y, country.upper(),
        ha="center", va="center",
        color=text_color,
        fontsize=country_size,
        fontproperties=fp_country,
        path_effects=stroke,
    )
    fig.text(
        0.5, coords_y, coord_text,
        ha="center", va="center",
        color=text_color,
        fontsize=coords_size,
        fontproperties=fp_coords,
        path_effects=stroke,
    )
