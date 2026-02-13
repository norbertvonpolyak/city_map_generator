from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from osmnx._errors import InsufficientResponseError

import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import osmnx as ox
import random

from shapely.geometry import Point, box, LineString
from shapely.ops import unary_union, polygonize

from generator.specs import ProductSpec
from generator.styles import Style, DEFAULT_STYLE, get_palette


@dataclass(frozen=True)
class RenderResult:
    output_pdf: Path


def _safe_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _fetch_water_union(
    *,
    center_lat: float,
    center_lon: float,
    dist_m: int,
    clip_rect,
) -> Optional[object]:
    """
    Belvizek union (Polygon/MultiPolygon) projekcióban, a frame-re vágva.
    OSMnx 2.x: features_from_point.
    """
    tags = {
        "natural": ["water"],
        "water": True,
        "waterway": ["river", "canal"],
        "landuse": ["reservoir"],
    }

    try:
        gdf_water = ox.features_from_point((center_lat, center_lon), tags=tags, dist=dist_m)
    except InsufficientResponseError:
        return None

    gdf_water = gdf_water[gdf_water.geometry.notnull()].copy()
    if len(gdf_water) == 0:
        return None

    gdf_water_p = ox.projection.project_gdf(gdf_water)
    water_polys = gdf_water_p[gdf_water_p.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    if len(water_polys) == 0:
        return None

    # frame-re vágás
    water_polys["geometry"] = water_polys.geometry.intersection(clip_rect)
    water_polys = water_polys[~water_polys.is_empty]
    if len(water_polys) == 0:
        return None

    return water_polys.unary_union


def _fetch_harbour_areas_union(
    *,
    center_lat: float,
    center_lon: float,
    dist_m: int,
    clip_rect,
) -> Optional[object]:
    """
    Kikötő / ipari / kereskedelmi területek unionja (Polygon/MultiPolygon) projekcióban,
    frame-re vágva. Cél: legyen kitölthető felület road-loop nélkül is.
    """
    tags = {
        "landuse": ["harbour", "port", "industrial", "commercial"],
        "harbour": True,
    }

    try:
        gdf = ox.features_from_point((center_lat, center_lon), tags=tags, dist=dist_m)
    except InsufficientResponseError:
        return None

    gdf = gdf[gdf.geometry.notnull()].copy()
    if len(gdf) == 0:
        return None

    gdf_p = ox.projection.project_gdf(gdf)
    polys = gdf_p[gdf_p.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    if len(polys) == 0:
        return None

    polys["geometry"] = polys.geometry.intersection(clip_rect)
    polys = polys[~polys.is_empty]
    if len(polys) == 0:
        return None

    return polys.unary_union


def _fetch_sea_polygon(
    *,
    center_point_proj,   # <-- új: a projekciós középpont (Shapely Point)
    center_lat: float,
    center_lon: float,
    dist_m: int,
    clip_rect,
) -> Optional[object]:
    """
    Tenger polygon becslése coastline (natural=coastline) alapján.

    Bulletproof heurisztika:
    - polygonize(frame_boundary + coastline)
    - LAND = az a poligon, amelyik tartalmazza a center_point_proj pontot
    - SEA = frame - LAND
    - fallback: boundary-touch (4 oldal) guard-rail küszöbökkel
    """
    tags = {"natural": ["coastline"]}
    try:
        gdf_coast = ox.features_from_point((center_lat, center_lon), tags=tags, dist=dist_m)
    except InsufficientResponseError:
        return None
    gdf_coast = gdf_coast[gdf_coast.geometry.notnull()].copy()
    if len(gdf_coast) == 0:
        return None

    gdf_coast_p = ox.projection.project_gdf(gdf_coast)
    coast_lines = gdf_coast_p[gdf_coast_p.geom_type.isin(["LineString", "MultiLineString"])].copy()
    if len(coast_lines) == 0:
        return None

    clip_buf = clip_rect.buffer(50.0)
    coast_lines["geometry"] = coast_lines.geometry.intersection(clip_buf)
    coast_lines = coast_lines[~coast_lines.is_empty]
    if len(coast_lines) == 0:
        return None

    rect_boundary = clip_rect.boundary

    line_geoms = list(coast_lines.geometry.values)
    line_geoms.append(rect_boundary)

    merged_lines = unary_union(line_geoms)
    polys = list(polygonize(merged_lines))
    if len(polys) == 0:
        return None

    polys_in = []
    for p in polys:
        inter = p.intersection(clip_rect)
        if inter.is_empty:
            continue
        if inter.geom_type in ["Polygon", "MultiPolygon"]:
            polys_in.append(inter)

    if len(polys_in) < 2:
        return None

    # 1) PRIMARY: center-in-poly -> LAND
    land_poly = None
    for p in polys_in:
        try:
            if p.contains(center_point_proj):
                land_poly = p
                break
        except Exception:
            continue

    if land_poly is not None:
        sea_poly = clip_rect.difference(land_poly)
        if sea_poly.is_empty:
            return None
        return sea_poly

    # 2) FALLBACK: boundary-touch (4 oldal) + guard-rail
    minx, miny, maxx, maxy = clip_rect.bounds
    west_boundary = LineString([(minx, miny), (minx, maxy)])
    east_boundary = LineString([(maxx, miny), (maxx, maxy)])
    south_boundary = LineString([(minx, miny), (maxx, miny)])
    north_boundary = LineString([(minx, maxy), (maxx, maxy)])
    boundaries = (west_boundary, east_boundary, south_boundary, north_boundary)

    frame_area = float(clip_rect.area)
    MIN_TOUCH_LEN = 20.0
    MIN_AREA_FRAC = 0.02

    best_poly = None
    best_score = 0.0

    for p in polys_in:
        try:
            area_frac = float(p.area) / frame_area if frame_area > 0 else 0.0
        except Exception:
            area_frac = 0.0
        if area_frac < MIN_AREA_FRAC:
            continue

        touch = 0.0
        for b in boundaries:
            try:
                touch = max(touch, p.boundary.intersection(b).length)
            except Exception:
                continue

        if touch > best_score:
            best_score = touch
            best_poly = p

    if best_poly is None or best_score < MIN_TOUCH_LEN:
        return None

    return best_poly.intersection(clip_rect)

def _scaled_linewidth(
    *,
    half_height_m: float,
    base_linewidth: float,
    reference_half_height_m: float = 5000.0,
    min_lw: float = 0.3,
    max_lw: float = 1.8,
) -> float:
    """
    Útvonalvastagság skálázása a kiterjedéshez (félmagassághoz) képest.
    5000 m félmagasságnál a base_linewidth az “igazi” arány, ettől eltérve skálázunk.

    A clamp (min_lw/max_lw) nyomdai/preview stabilitás miatt kell.
    """
    if half_height_m <= 0:
        return base_linewidth

    scale = reference_half_height_m / float(half_height_m)
    lw = base_linewidth * scale
    return float(max(min_lw, min(lw, max_lw)))


def render_city_map(
    *,
    center_lat: float,
    center_lon: float,
    spec: ProductSpec,
    output_dir: Path,
    palette_name: str = "warm",
    style: Style = DEFAULT_STYLE,
    seed: Optional[int] = 42,
    filename_prefix: str = "city_map",
    network_type: str = "drive",
    min_poly_area: float = 300.0,
    road_width: float = 0.8,
) -> RenderResult:

    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    palette: List[str] = get_palette(palette_name)

    half_width_m, half_height_m = spec.frame_half_sizes_m
    fig_w_in, fig_h_in = spec.fig_size_inches

    scaled_road_width = _scaled_linewidth(
        half_height_m=half_height_m,
        base_linewidth=road_width,
        reference_half_height_m=5000.0,
        min_lw=0.35,
        max_lw=2.2,
    )

    # HIERARCHY WIDTHS
    lw_major = scaled_road_width * 1.5
    lw_medium = scaled_road_width * 1.15
    lw_minor = scaled_road_width * 0.80
    lw_bridge = scaled_road_width * 1.6

    dist_m = int(np.ceil((half_width_m**2 + half_height_m**2) ** 0.5)) + 300

    ts = _safe_timestamp()
    output_pdf = output_dir / f"{filename_prefix}_{spec.width_cm}x{spec.height_cm}cm_{ts}.pdf"

    # ------------------------
    # ROAD NETWORK
    # ------------------------
    G = ox.graph_from_point(
        (center_lat, center_lon),
        dist=dist_m,
        network_type="all",
        simplify=True
    )

    gdf_edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
    gdf_edges_p = ox.projection.project_gdf(gdf_edges)

    # ------------------------
    # FRAME
    # ------------------------
    center = gpd.GeoDataFrame(geometry=[Point(center_lon, center_lat)], crs="EPSG:4326")
    center_p = ox.projection.project_gdf(center).geometry.iloc[0]

    minx = center_p.x - half_width_m
    maxx = center_p.x + half_width_m
    miny = center_p.y - half_height_m
    maxy = center_p.y + half_height_m

    clip_rect = box(minx, miny, maxx, maxy)
    rect_boundary = clip_rect.boundary

    # ------------------------
    # WATER (BELVÍZ + TENGER)
    # ------------------------
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
        water_union = unary_union(parts).intersection(clip_rect)

    # ------------------------
    # POLYGONIZE
    # ------------------------
    edges_clip = gpd.clip(gdf_edges_p, gpd.GeoSeries([clip_rect], crs=gdf_edges_p.crs))

    line_geoms = list(edges_clip.geometry.values)
    line_geoms.append(rect_boundary)

    merged_lines = unary_union(line_geoms)
    polys = list(polygonize(merged_lines))

    gdf_blocks_p = gpd.GeoDataFrame(geometry=polys, crs=gdf_edges_p.crs)
    gdf_blocks_p = gdf_blocks_p[gdf_blocks_p.geometry.within(clip_rect)]
    gdf_blocks_p = gdf_blocks_p[gdf_blocks_p.geometry.area > float(min_poly_area)]

    # ------------------------
    # WATER KIVONÁS A BLOKKOKBÓL
    # ------------------------
    if water_union is not None and len(gdf_blocks_p) > 0:
        gdf_blocks_p["geometry"] = gdf_blocks_p.geometry.difference(water_union)
        gdf_blocks_p = gdf_blocks_p[~gdf_blocks_p.is_empty]

    # ------------------------
    # COLORING
    # ------------------------
    if palette_name == "warm":
        hole_color = np.random.choice(palette)
        block_colors = np.random.choice(palette, size=len(gdf_blocks_p), replace=True)
    else:
        weights = np.array([1.5, 2.0, 3.5, 5.0, 4.5, 3.0, 1.8], dtype=float)
        p = weights / weights.sum()
        hole_color = np.random.choice(palette, p=p)
        block_colors = np.random.choice(palette, size=len(gdf_blocks_p), replace=True, p=p)

    # ------------------------
    # PLOT
    # ------------------------
    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
    fig.patch.set_facecolor(style.background)
    ax.set_facecolor(style.background)

    if len(gdf_blocks_p) > 0:
        gdf_blocks_p.plot(ax=ax, color=block_colors, linewidth=0)

    # ------------------------
    # ROAD CLASSIFICATION
    # ------------------------
    def _classify_highway(hw):
        if isinstance(hw, list):
            hw = hw[0]
        if hw in ["motorway", "trunk", "primary"]:
            return "major"
        elif hw in ["secondary", "tertiary"]:
            return "medium"
        else:
            return "minor"

    gdf_edges_p["road_class"] = gdf_edges_p["highway"].apply(_classify_highway)

    major = gdf_edges_p[gdf_edges_p["road_class"] == "major"]
    medium = gdf_edges_p[gdf_edges_p["road_class"] == "medium"]
    minor = gdf_edges_p[gdf_edges_p["road_class"] == "minor"]

    # Rajzolási sorrend: kicsi → nagy
    if len(minor) > 0:
        minor.plot(ax=ax, color=style.road, linewidth=lw_minor, alpha=1.0)

    if len(medium) > 0:
        medium.plot(ax=ax, color=style.road, linewidth=lw_medium, alpha=1.0)

    if len(major) > 0:
        major.plot(ax=ax, color=style.road, linewidth=lw_major, alpha=1.0)

    # ------------------------
    # BRIDGES
    # ------------------------
    if "bridge" in gdf_edges.columns:
        bridges = gdf_edges[gdf_edges["bridge"].notna()].copy()
        if len(bridges) > 0:
            ox.projection.project_gdf(bridges).plot(
                ax=ax,
                color=style.bridge,
                linewidth=lw_bridge,
                alpha=1.0,
            )

    # Frame boundary
    gpd.GeoSeries([rect_boundary], crs=gdf_edges_p.crs).plot(
        ax=ax,
        color=style.road,
        linewidth=lw_medium,
        alpha=1.0,
    )

    # ------------------------
    # WATER – LEGELÜL
    # ------------------------
    if water_union is not None and not water_union.is_empty:
        gpd.GeoSeries([water_union], crs=gdf_edges_p.crs).plot(
            ax=ax,
            color=style.water,
            edgecolor=style.water,
            linewidth=0,
        )

    # ------------------------
    # CLEAN COMPOSITION CROP
    # ------------------------

    bottom_cut_frac = 0.07  # mostani kb fele (korábban 0.12 volt)

    frame_height = maxy - miny
    new_miny = miny + frame_height * bottom_cut_frac
    plt.subplots_adjust (left=0.02, right=0.98, top=0.98, bottom=0.02)

    bottom_cut_frac = 0.05  # finom alsó levágás (5%)

    frame_height = maxy - miny
    new_miny = miny + frame_height * bottom_cut_frac

    ax.set_xlim (minx, maxx)
    ax.set_ylim (new_miny, maxy)
    outer_margin = 0.02
    ax.set_axis_off ()

    # ---------------------------------
    # MANUAL AXES POSITIONING
    # ---------------------------------

    left_margin = 0.02
    right_margin = 0.02
    top_margin = 0.025
    bottom_margin = 0.08  # nagyobb alsó sáv

    ax.set_position ([
        left_margin,
        bottom_margin,
        1 - left_margin - right_margin,
        1 - top_margin - bottom_margin
    ])

    fig.savefig (output_pdf, format="pdf", dpi=spec.dpi)

    plt.close(fig)

    return RenderResult(output_pdf=output_pdf)


def weighted_palette_choice(palette: List[str]) -> str:
    """
    (Jelenleg nem használod, de meghagyható.)
    Világos színek dominálnak, sötétek ritkák.
    """
    weights = [6, 5, 4, 3, 2, 1, 0.5]
    return random.choices(palette, weights=weights, k=1)[0]
