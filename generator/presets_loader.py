from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from generator.styles import MonoStyle  # ha máshol van, igazítsd


DEFAULT_MONO_JSON_PATH = Path(__file__).resolve().parent / "presets" / "monochrome_default.json"


def load_monochrome_defaults(
    *,
    fallback_style: MonoStyle,
    fallback_zoom: float = 0.6,
    fallback_extent_m: int = 2000,
    fallback_network_type: str = "all",
    path: Path = DEFAULT_MONO_JSON_PATH,
) -> Tuple[MonoStyle, float, int, str]:
    """
    Loads monochrome default parameters from JSON.
    Returns: (MonoStyle, zoom, extent_m, network_type)
    """
    if not path.exists():
        return fallback_style, float(fallback_zoom), int(fallback_extent_m), str(fallback_network_type)

    data: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    mono_style_data = data.get("mono_style") or {}
    defaults = data.get("defaults") or {}

    # Build style by overriding fallback_style fields with values from JSON
    style = fallback_style
    for k, v in mono_style_data.items():
        if hasattr(style, k):
            style = replace(style, **{k: v})

    zoom = float(defaults.get("zoom", fallback_zoom))
    extent_m = int(defaults.get("extent_m", fallback_extent_m))
    network_type = str(defaults.get("network_type", fallback_network_type))

    return style, zoom, extent_m, network_type
