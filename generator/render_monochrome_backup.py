# generator/render_monochrome.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import osmnx as ox
import random

from shapely.geometry import Point, box

from osmnx._errors import InsufficientResponseError
from pyproj import Transformer

from generator.specs import ProductSpec
from generator.relief import ReliefConfig, load_dem_wgs84_crop, hillshade, normalize_grayscale

# A "pretty" víz+tenger heurisztikát újrahasznosítjuk.
# (Kód duplázás helyett importáljuk a pretty modulból.)
from generator.render_pretty import _fetch_water_union, _fetch_sea_polygon, _scaled_linewidth  # noqa: F401


@dataclass(frozen=True)
class RenderResult:
    output_pdf: Path


def _safe_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _to_bbox_wgs84_from_proj_bounds(
    bounds_proj: Tuple[float, float, float, float],
    crs_proj,
) -> Tuple[float, float, float, float]:
    """
    bounds_proj: (minx, miny, maxx, maxy) a vektor CRS-ben (jellemzően UTM).
    Visszaalakítjuk WGS84-re DEM crop-hoz.
    """
    minx, miny, maxx, maxy = bounds_proj
    transformer = Transformer.from_crs(crs_proj, "EPSG:4326", always_xy=True)

    lon1, lat1 = transformer.transform(minx, miny)
    lon2, lat2 = transformer.transform(maxx, maxy)

    minlon = min(lon1, lon2)
    maxlon = max(lon1, lon2)
    minlat = min(lat1, lat2)
    maxlat = max(lat1, lat2)
    return (minlon, minlat, maxlon, maxlat)


def _highway_factor(highway: str) -> float:
    hw = str(highway)
    if hw in ("motorway", "trunk"):
        return 1.6
    if hw == "primary":
        return 1.3
    if hw == "secondary":
        return 1.1
    if hw == "tertiary":
        return 1.0
    if hw in ("residential", "living_street", "unclassified"):
        return 0.85
    if hw == "service":
        return 0.70
    if hw in ("pedestrian",):
        return 0.65
    if hw in ("footway", "path", "cycleway", "steps"):
        return 0.50
    return 0.80


def _plot_roads_monochrome(ax, gdf_edges_p: gpd.GeoDataFrame, base_lw: float):
    if len(gdf_edges_p) == 0:
        return

    if "highway" not in gdf_edges_p.columns:
        gdf_edges_p.plot(
            ax=ax,
            color="#000000",
            linewidth=base_lw,
            alpha=1.0,
            capstyle="round",
            joinstyle="round",
            zorder=50,
        )
        return

    r = gdf_edges_p.copy()
    r["highway"] = r["highway"].apply(lambda v: v[0] if isinstance(v, (list, tuple)) and v else v)

    for hw, grp in r.groupby("highway"):
        lw = base_lw * _highway_factor(hw)
        grp.plot(
            ax=ax,
            color="#000000",
            linewidth=lw,
            alpha=1.0,
            capstyle="round",
            joinstyle="round",
            zorder=50,
        )


def render_city_map_monochrome(
    *,
    center_lat: float,
    center_lon: float,
    spec: ProductSpec,
    output_dir: Path,
    zoom: float = 0.6,
    seed: Optional[int] = 42,
    filename_prefix: str = "city_mono",
    network_type_draw: str = "all",       # max detail
    road_width: float = 1.10,             # same base as pretty
    show_buildings: bool = True,
    min_building_area: float = 12.0,
    relief: ReliefConfig = ReliefConfig(),
) -> RenderResult:
    """
    Monochrome (BW) render:
    - white background
    - black streets, max detail, no labels
    - water + sea always white (masking relief too)
    - subtle hillshade relief (optional, DEM cache)
    """
    if not (-90.0 <= center_lat <= 90.0):
        raise ValueError("center_lat érvénytelen (−90..90).")
    if not (-180.0 <= center_lon <= 180.0):
        raise ValueError("center_lon érvénytelen (−180..180).")
    if zoom <= 0:
        raise ValueError("zoom > 0 kell legyen.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    # Export méret
    fig_w_in, fig_h_in = spec.fig_size_inches

    # Frame (méterben) – zoomolva (ugyanaz, mint pretty)
    half_width_m, half_height_m = spec.frame_half_sizes_m
    half_width_m = float(half_width_m) * float(zoom)
    half_height_m = float(half_height_m) * float(zoom)

    # Pretty linewidth skálázás újrahasznosítva (reference_half_height_m=2000 a pretty-ben)
    scaled_road_width = _scaled_linewidth(
        half_height_m=half_height_m,
        base_linewidth=road_width,
        reference_half_height_m=2000.0,
        min_lw=0.18,
        max_lw=1.2,
    )

    # Letöltési távolság: félátló + tartalék
    dist_m = int(np.ceil((half_width_m**2 + half_height_m**2) ** 0.5)) + 300

    # Timestampes fájlnév
    ts = _safe_timestamp()
    output_pdf = output_dir / f"{filename_prefix}_{spec.width_cm}x{spec.height_cm}cm_z{zoom:.2f}_{ts}.pdf"

    # Középpont projekcióban
    center = gpd.GeoDataFrame(geometry=[Point(center_lon, center_lat)], crs="EPSG:4326")
    center_p = ox.projection.project_gdf(center).geometry.iloc[0]

    minx = center_p.x - half_width_m
    maxx = center_p.x + half_width_m
    miny = center_p.y - half_height_m
    maxy = center_p.y + half_height_m
    clip_rect = box(minx, miny, maxx, maxy)

    # --- Roads ---
    G_draw = ox.graph_from_point(
        (center_lat, center_lon),
        dist=dist_m,
        network_type=network_type_draw,
        simplify=True,
    )

    # Rajzoláshoz irányfüggetlenítjük: eltünteti az oda-vissza duplázást
    try:
        G_draw_u = ox.convert.to_undirected(G_draw)
    except AttributeError:
        # OSMnx verziófüggő fallback
        G_draw_u = ox.utils_graph.get_undirected(G_draw)

    gdf_edges_draw = ox.graph_to_gdfs(G_draw_u, nodes=False, edges=True)
    gdf_edges_draw_p = ox.projection.project_gdf(gdf_edges_draw)
    gdf_edges_draw_p = gpd.clip(
        gdf_edges_draw_p,
        gpd.GeoSeries([clip_rect], crs=gdf_edges_draw_p.crs),
    )

    # --- Water (inland + sea) ---
    inland_water_union = _fetch_water_union(
        center_lat=center_lat,
        center_lon=center_lon,
        dist_m=dist_m,
        clip_rect=clip_rect,
    )
    sea_poly = _fetch_sea_polygon(
        center_point_proj=center_p,
        center_lat=center_lat,
        center_lon=center_lon,
        dist_m=dist_m,
        clip_rect=clip_rect,
    )

    if inland_water_union is None and sea_poly is None:
        water_union = None
    else:
        parts = []
        if inland_water_union is not None:
            parts.append(inland_water_union)
        if sea_poly is not None:
            parts.append(sea_poly)
        from shapely.ops import unary_union
        water_union = unary_union(parts).intersection(clip_rect)

    # --- Buildings ---
    gdf_bld_p = None
    if show_buildings:
        tags_buildings = {"building": True}
        try:
            gdf_bld = ox.features_from_point((center_lat, center_lon), tags=tags_buildings, dist=dist_m)
        except InsufficientResponseError:
            gdf_bld = None

        if gdf_bld is not None and len(gdf_bld) > 0:
            gdf_bld = gdf_bld[gdf_bld.geometry.notnull()].copy()
            if len(gdf_bld) > 0:
                gdf_bld_p = ox.projection.project_gdf(gdf_bld)
                gdf_bld_p = gdf_bld_p[gdf_bld_p.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
                if len(gdf_bld_p) > 0:
                    gdf_bld_p = gpd.clip(
                        gdf_bld_p,
                        gpd.GeoSeries([clip_rect], crs=gdf_bld_p.crs),
                    )
                    gdf_bld_p = gdf_bld_p[~gdf_bld_p.is_empty]
                    if len(gdf_bld_p) > 0:
                        gdf_bld_p = gdf_bld_p[gdf_bld_p.geometry.area > float(min_building_area)]
                    if len(gdf_bld_p) == 0:
                        gdf_bld_p = None

    # Víz alól vegyük ki a buildinget (biztonság, mint pretty)
    if water_union is not None and not water_union.is_empty and gdf_bld_p is not None and len(gdf_bld_p) > 0:
        gdf_bld_p["geometry"] = gdf_bld_p.geometry.difference(water_union)
        gdf_bld_p = gdf_bld_p[~gdf_bld_p.is_empty]
        if len(gdf_bld_p) == 0:
            gdf_bld_p = None

    # --- Relief prep: bbox WGS84 a frame bounds alapján ---
    bbox_wgs84 = _to_bbox_wgs84_from_proj_bounds((minx, miny, maxx, maxy), gdf_edges_draw_p.crs)

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # 1) Relief (háttér, ha elérhető)
    if relief.enabled:
        try:
            dem_pack = load_dem_wgs84_crop(bbox_wgs84, relief.cache_dir)
            if dem_pack is not None:
                dem, dem_transform, _ = dem_pack
                shade01 = hillshade(
                    dem,
                    dem_transform,
                    azimuth_deg=relief.azimuth_deg,
                    altitude_deg=relief.altitude_deg,
                    z_factor=relief.z_factor,
                )
                gray = normalize_grayscale(shade01, relief.out_min, relief.out_max)
                rgba = np.dstack([
                    gray, gray, gray,
                    np.full_like(gray, relief.alpha, dtype=np.float32),
                ])
                # Best-effort: ráfeszítjük a frame-re (vizuálisan jó, CRS mismatch esetén is)
                ax.imshow(
                    rgba,
                    extent=(minx, maxx, miny, maxy),
                    origin="upper",
                    zorder=0,
                )
        except Exception:
            if not relief.fail_silently:
                raise

    # 2) Buildings (nagyon világos)
    if gdf_bld_p is not None and len(gdf_bld_p) > 0:
        gdf_bld_p.plot(
            ax=ax,
            color="#F2F2F2",
            linewidth=0,
            alpha=1.0,
            zorder=10,
        )

    # 3) Water mask (mindig fehér, relief fölé is)
    if water_union is not None and not water_union.is_empty:
        gpd.GeoSeries([water_union], crs=gdf_edges_draw_p.crs).plot(
            ax=ax,
            color="white",
            edgecolor="white",
            linewidth=0,
            zorder=20,
        )

    # 4) Roads (fekete, max detail)
    _plot_roads_monochrome(ax, gdf_edges_draw_p, scaled_road_width)

    # 5) Bridges (halvány szürke – külön réteg, ha van)
    if "bridge" in gdf_edges_draw.columns:
        bridges = gdf_edges_draw[gdf_edges_draw["bridge"].notna()].copy()
        if len(bridges) > 0:
            ox.projection.project_gdf(bridges).plot(
                ax=ax,
                color="#CFCFCF",
                linewidth=max(0.12, scaled_road_width * 0.75),
                alpha=1.0,
                zorder=60,
            )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    print("Saving PDF to:", output_pdf)
    fig.savefig(output_pdf, format="pdf", dpi=spec.dpi, bbox_inches="tight")
    plt.close(fig)

    return RenderResult(output_pdf=output_pdf)
