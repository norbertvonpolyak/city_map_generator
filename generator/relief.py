# generator/relief.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

import numpy as np

try:
    import rasterio
    from rasterio.merge import merge as rio_merge
    from rasterio.mask import mask as rio_mask
    from rasterio.warp import transform_bounds
    from rasterio.io import MemoryFile
except ImportError:
    rasterio = None


@dataclass(frozen=True)
class ReliefConfig:
    enabled: bool = True
    cache_dir: str = "data/dem"     # ide kerülnek a DEM GeoTIFF-ek
    azimuth_deg: float = 315.0
    altitude_deg: float = 45.0
    z_factor: float = 1.0
    alpha: float = 0.40
    out_min: float = 0.82
    out_max: float = 0.94
    fail_silently: bool = True


def _list_dem_tifs(cache_dir: Path) -> List[Path]:
    if not cache_dir.exists():
        return []
    return sorted([p for p in cache_dir.rglob("*.tif")] + [p for p in cache_dir.rglob("*.tiff")])


def load_dem_wgs84_crop(
    bbox_wgs84: Tuple[float, float, float, float],
    cache_dir: str,
) -> Optional[Tuple[np.ndarray, "rasterio.Affine", "rasterio.crs.CRS"]]:
    """
    bbox_wgs84: (minlon, minlat, maxlon, maxlat)
    Returns: (dem, transform, crs)
    dem: float32 with nodata as nan
    """
    if rasterio is None:
        return None

    tifs = _list_dem_tifs(Path(cache_dir))
    if not tifs:
        return None

    datasets = []
    for p in tifs:
        try:
            ds = rasterio.open(p)
            datasets.append(ds)
        except Exception:
            continue

    if not datasets:
        return None

    try:
        mosaic, mosaic_transform = rio_merge(datasets)  # (bands, h, w)
        dem = mosaic[0].astype(np.float32)

        mosaic_crs = datasets[0].crs
        if mosaic_crs is None:
            return None

        bbox_in_crs = transform_bounds("EPSG:4326", mosaic_crs, *bbox_wgs84, densify_pts=21)
        minx, miny, maxx, maxy = bbox_in_crs

        geom_crs = {
            "type": "Polygon",
            "coordinates": [[
                (minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy), (minx, miny)
            ]]
        }

        profile = {
            "driver": "GTiff",
            "height": dem.shape[0],
            "width": dem.shape[1],
            "count": 1,
            "dtype": "float32",
            "crs": mosaic_crs,
            "transform": mosaic_transform,
            "nodata": None,
        }

        with MemoryFile() as memfile:
            with memfile.open(**profile) as tmp:
                tmp.write(dem, 1)
                cropped, cropped_transform = rio_mask(tmp, [geom_crs], crop=True, filled=False)

        cropped_dem = cropped[0].astype(np.float32)
        if np.ma.isMaskedArray(cropped_dem):
            cropped_dem = cropped_dem.filled(np.nan)

        return cropped_dem, cropped_transform, mosaic_crs
    finally:
        for ds in datasets:
            try:
                ds.close()
            except Exception:
                pass


def hillshade(
    dem: np.ndarray,
    transform: "rasterio.Affine",
    azimuth_deg: float = 315.0,
    altitude_deg: float = 45.0,
    z_factor: float = 1.0,
) -> np.ndarray:
    """
    Hillshade in [0,1]. nan preserved.
    (Legjobb, ha a DEM projektált méter-alapú CRS-ben van.)
    """
    xres = transform.a
    yres = -transform.e

    dem2 = dem.copy()
    nanmask = np.isnan(dem2)
    if nanmask.any():
        med = np.nanmedian(dem2)
        if np.isnan(med):
            return np.full_like(dem2, np.nan, dtype=np.float32)
        dem2[nanmask] = med

    dzdx = np.gradient(dem2, axis=1) / (xres if xres != 0 else 1.0)
    dzdy = np.gradient(dem2, axis=0) / (yres if yres != 0 else 1.0)
    dzdx *= z_factor
    dzdy *= z_factor

    slope = np.pi / 2.0 - np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(dzdy, -dzdx)

    az = np.deg2rad(azimuth_deg)
    alt = np.deg2rad(altitude_deg)

    shaded = (
        np.sin(alt) * np.sin(slope) +
        np.cos(alt) * np.cos(slope) * np.cos(az - aspect)
    )

    shaded = (shaded - shaded.min()) / (shaded.max() - shaded.min() + 1e-9)
    shaded = shaded.astype(np.float32)
    shaded[nanmask] = np.nan
    return shaded


def normalize_grayscale(shade01: np.ndarray, out_min: float, out_max: float) -> np.ndarray:
    out = out_min + (out_max - out_min) * shade01
    return out.astype(np.float32)
