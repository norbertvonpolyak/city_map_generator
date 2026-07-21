import pickle
from pathlib import Path
from time import perf_counter
from typing import Callable, Any

CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def load_or_build_geometry(
    *,
    cache_prefix: str,
    center_lat: float,
    center_lon: float,
    extent_m: int,
    cache_variant: str = "",
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
        f"{extent_m}_"
        f"{cache_variant}.pkl"
    )

    cache_path = CACHE_DIR / cache_key

    if cache_path.exists():
        started = perf_counter()
        with open(cache_path, "rb") as f:
            data = pickle.load(f)
        elapsed = perf_counter() - started
        print(f"[CACHE] Loading geometry: {cache_key} ({elapsed:.2f}s)")
        return data

    print(f"[CACHE] Building geometry: {cache_key}")
    started = perf_counter()
    geometry_data = builder_func()
    elapsed = perf_counter() - started

    with open(cache_path, "wb") as f:
        pickle.dump(geometry_data, f)

    print(f"[CACHE] Built geometry: {cache_key} ({elapsed:.2f}s)")

    return geometry_data