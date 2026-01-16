from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict


@dataclass(frozen=True)
class Style:
    background: str
    road: str
    bridge: str
    water: str


# Alap (nem palettafüggő) stílus elemek
DEFAULT_STYLE = Style(
    background="#e0dbc8",
    road="#ffffff",
    bridge="#d0d0d0",
    water="#ffffff",
)


# Webshop-paletták
# Ezeket használod a polygonize-alapú tömbszínezéshez
# A sorrend FONTOS: világostól sötétebb felé haladjon
PALETTES: Dict[str, List[str]] = {

    # Meglévő meleg paletta
    "warm": [
        "#e28c41",
        "#cd6d40",
        "#e7b573",
        "#e39f55",
        "#9dc6b4",
        "#6f6b5e",
        "#e2bf98",
    ],

    "vivid_city": [
        "#FFFD82",  # Canary – világos alap
        "#969765",  # Palm Leaf
        "#1B998B",  # Verdigris
        "#246569",  # Stormy Sea
        "#FF9B71",  # Tangerine – akcentus
        "#E84855",  # Watermelon – akcentus
        "#2D3047",  # Space Cadet – mély horgony
    ],

    "amber_dusk": [
        "#EBC775",  # Jasmine – világos, levegős alap
        "#FFA630",  # Amber – meleg akcentus
        "#9CB48F",  # Muted Green
        "#6D9790",  # Muted Teal
        "#3E7990",  # Cerulean
        "#2E5077",  # Dusk Blue
        "#483656",  # Vintage Plum – sötét horgony
    ],


    "sunset_noir": [
        "#FFBA49",  # Sunflower – világos, meleg alap
        "#A4A9AD",  # Cool Silver – neutrális levegő
        "#887F7D",  # Rosy Grey
        "#20A39E",  # Light Sea – friss kontraszt
        "#EF5B5B",  # Vibrant Coral – akcentus
        "#892E3D",  # Burnt Rose – mély meleg
        "#23001E",  # Midnight Plum – sötét horgony
    ],

    "coastal_modern": [
        "#EDE6E3",  # Parchment – nagyon világos alap
        "#DADAD9",  # Alabaster Grey
        "#EFA596",  # Powder Blush
        "#5BC3EB",  # Sky Aqua
        "#497E8D",  # Air Force Blue
        "#F06449",  # Tomato – akcentus
        "#36382E",  # Charcoal Brown – mély kontraszt
    ],

    "urban_gold": [
        "#DFD5BB",  # Sand Dune – világos alap
        "#D9C590",  # Soft Fawn
        "#D3B566",  # Metallic Gold
        "#CCA43B",  # Golden Bronze
        "#786A3E",  # Olive Bark
        "#534F3D",  # Dark Khaki
        "#2D333B",  # Jet Black – mély kontraszt
    ],

}


def get_palette(name: str) -> List[str]:
    if name not in PALETTES:
        raise ValueError(
            f"Ismeretlen paletta: {name}. "
            f"Választható: {list(PALETTES.keys())}"
        )
    return PALETTES[name]
