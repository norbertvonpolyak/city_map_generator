import pickle
from pathlib import Path
from typing import Callable, Any

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)


def load_or_build_geometry(
    *,
    cache_prefix: str,
    center_lat: float,
    center_lon: float,
    extent_m: int,
    builder_func: Callable[[], Any],
):
    """
    Generic geometry cache loader.

    - Only caches heavy geometry generation
    - Never caches matplotlib objects
    - Deterministic key based on lat/lon/extent
    """

    cache_key = (
        f"{cache_prefix}_"
        f"{center_lat:.6f}_"
        f"{center_lon:.6f}_"
        f"{extent_m}.pkl"
    )

    cache_path = CACHE_DIR / cache_key

    if cache_path.exists():
        print(f"[CACHE] Loading geometry: {cache_key}")
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    print(f"[CACHE] Building geometry: {cache_key}")
    geometry_data = builder_func()

    with open(cache_path, "wb") as f:
        pickle.dump(geometry_data, f)

    return geometry_data