from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import osmnx as ox
import random

from shapely.geometry import Point, box, LineString
from shapely.ops import unary_union, polygonize

from osmnx._errors import InsufficientResponseError

from generator.specs import ProductSpec
from generator.styles import Style, DEFAULT_STYLE, get_palette


@dataclass(frozen=True)
class RenderResult:
    output_pdf: Path


# --- Non-vehicular highway types that often cause clutter / parallels ---
EXCLUDE_NON_VEHICULAR_HIGHWAYS: set[str] = {
    "pedestrian",
    "cycleway",
    "footway",
    "path",
    "steps",
    "bridleway",
}

# --- Road classification sets (same intent as monochrome) ---
HIGHWAY_HIGHWAY = {"motorway", "trunk"}
HIGHWAY_ARTERIAL = {"primary", "secondary", "tertiary"}
HIGHWAY_LOCAL = {"residential", "unclassified", "living_street"}
HIGHWAY_MINOR = {"service"}  # minor legyen jármű-út jellegű


def _safe_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _scaled_linewidth(
    *,
    half_height_m: float,
    base_linewidth: float,
    reference_half_height_m: float = 2000.0,
    min_lw: float = 0.18,
    max_lw: float = 1.2,
) -> float:
    """
    Pretty módban finomabb, részletesebb vonalvastagság.
    A reference_half_height_m itt kisebb (közelebbi zoomhoz igazítva).
    """
    if half_height_m <= 0:
        return base_linewidth

    scale = reference_half_height_m / float(half_height_m)
    lw = base_linewidth * scale
    return float(max(min_lw, min(lw, max_lw)))


def _normalize_highway_value(v):
    # OSMnx-ben a highway gyakran listás (pl. több tag)
    return v[0] if isinstance(v, (list, tuple)) and v else v


def _highway_has_any(v, banned: set[str]) -> bool:
    """
    highway attribútum lehet str vagy lista/tuple. True, ha bármelyik eleme tiltott.
    """
    if isinstance(v, (list, tuple, set)):
        return any(str(x) in banned for x in v)
    return str(v) in banned


def _classify_road(hw: str) -> str:
    hw = str(hw)
    if hw in HIGHWAY_HIGHWAY:
        return "highway"
    if hw in HIGHWAY_ARTERIAL:
        return "arterial"
    if hw in HIGHWAY_LOCAL:
        return "local"
    if hw in HIGHWAY_MINOR:
        return "minor"
    return "local"


def _fetch_water_union(
    *,
    center_lat: float,
    center_lon: float,
    dist_m: int,
    clip_rect,
) -> Optional[object]:
    """
    Belvizek union (Polygon/MultiPolygon) projekcióban, frame-re vágva.
    """
    tags = {
        "natural": ["water", "bay"],
        "water": True,
        "waterway": ["river", "canal", "dock", "basin"],
        "landuse": ["reservoir", "basin"],
        "man_made": ["dock"],
        "harbour": True,
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

    water_polys["geometry"] = water_polys.geometry.intersection(clip_rect)
    water_polys = water_polys[~water_polys.is_empty]
    if len(water_polys) == 0:
        return None

    return water_polys.unary_union


def _fetch_sea_polygon(
    *,
    center_point_proj,   # shapely Point projekcióban
    center_lat: float,
    center_lon: float,
    dist_m: int,
    clip_rect,
) -> Optional[object]:
    """
    Tenger polygon becslése coastline (natural=coastline) alapján.

    - polygonize(frame_boundary + coastline)
    - LAND = poligon, ami tartalmazza a center_point_proj pontot
    - SEA = frame - LAND
    - fallback: boundary-touch guard-rail küszöbökkel
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

    # PRIMARY: center-in-poly -> LAND
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

    # FALLBACK: boundary-touch (4 oldal)
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


def _relative_luminance(hex_color: str) -> float:
    """
    Approx relative luminance in [0,1] from #RRGGBB.
    Ordering is what we need.
    """
    s = hex_color.strip().lstrip("#")
    if len(s) != 6:
        return 0.0
    r = int(s[0:2], 16) / 255.0
    g = int(s[2:4], 16) / 255.0
    b = int(s[4:6], 16) / 255.0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _pick_lightest(palette: List[str]) -> str:
    return max(palette, key=_relative_luminance)


def _exclude_color(palette: List[str], avoid: str) -> List[str]:
    return [c for c in palette if c != avoid]


def render_city_map_pretty(
    *,
    center_lat: float,
    center_lon: float,
    spec: ProductSpec,
    output_dir: Path,
    palette_name: str = "warm",
    style: Style = DEFAULT_STYLE,
    seed: Optional[int] = 42,
    filename_prefix: str = "city_pretty",
    network_type_draw: str = "all",
    zoom: float = 0.6,

    # base control (skálázódik extent alapján)
    road_width: float = 1.15,

    # NEW: rang szerinti vastagság (monochrome jelleggel)
    road_boost: float = 1.1,
    lw_highway_mult: float = 3.8,
    lw_arterial_mult: float = 2.8,
    lw_local_mult: float = 1.8,
    lw_minor_mult: float = 1.2,

    min_building_area: float = 12.0,

    draw_non_vehicular: bool = False,

    road_color: str = "#404040",
) -> RenderResult:
    """
    Prettymaps-szerű (réteges) render:
    - palette: background = legvilágosabb; buildings = többi szín random
    - roads: sötétszürke + rang szerinti vastagítás (highway>arterial>local>minor)
    - non-vehicular highway réteg (footway/cycleway/path/...) szűrhető
    - víz: belvíz + tenger fehér
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

    palette: List[str] = get_palette(palette_name)

    # Export méret
    fig_w_in, fig_h_in = spec.fig_size_inches

    # Frame (méterben) – zoomolva
    half_width_m, half_height_m = spec.frame_half_sizes_m
    half_width_m = float(half_width_m) * float(zoom)
    half_height_m = float(half_height_m) * float(zoom)

    # base linewidth (extent skálázás)
    base_lw = _scaled_linewidth(
        half_height_m=half_height_m,
        base_linewidth=float(road_width),
        reference_half_height_m=2000.0,
        min_lw=0.20,
        max_lw=4.0,
    ) * float(road_boost)

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

    # kevesebb duplázás
    try:
        G_draw_u = ox.convert.to_undirected(G_draw)
    except AttributeError:
        G_draw_u = ox.utils_graph.get_undirected(G_draw)

    gdf_edges_draw = ox.graph_to_gdfs(G_draw_u, nodes=False, edges=True)
    gdf_edges_draw_p = ox.projection.project_gdf(gdf_edges_draw)
    gdf_edges_draw_p = gpd.clip(
        gdf_edges_draw_p,
        gpd.GeoSeries([clip_rect], crs=gdf_edges_draw_p.crs),
    )
    gdf_edges_draw_p = gdf_edges_draw_p[~gdf_edges_draw_p.is_empty]

    # Szűrés: nem-jármű utak eltüntetése
    if "highway" in gdf_edges_draw_p.columns and not draw_non_vehicular:
        mask = gdf_edges_draw_p["highway"].apply(
            lambda v: not _highway_has_any(v, EXCLUDE_NON_VEHICULAR_HIGHWAYS)
        )
        gdf_edges_draw_p = gdf_edges_draw_p.loc[mask].copy()

        if "footway" in gdf_edges_draw_p.columns:
            gdf_edges_draw_p = gdf_edges_draw_p.loc[
                gdf_edges_draw_p["footway"].astype(str) != "sidewalk"
            ].copy()

    # Klasszifikáció
    if "highway" in gdf_edges_draw_p.columns:
        gdf_edges_draw_p = gdf_edges_draw_p.copy()
        gdf_edges_draw_p["highway"] = gdf_edges_draw_p["highway"].apply(_normalize_highway_value)
        gdf_edges_draw_p["road_class"] = gdf_edges_draw_p["highway"].apply(_classify_road)
    else:
        gdf_edges_draw_p = gdf_edges_draw_p.copy()
        gdf_edges_draw_p["road_class"] = "local"

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

    water_union = None
    if inland_water_union is not None or sea_poly is not None:
        parts = []
        if inland_water_union is not None:
            parts.append(inland_water_union)
        if sea_poly is not None:
            parts.append(sea_poly)
        water_union = unary_union(parts).intersection(clip_rect)

    # --- Buildings ---
    tags_buildings = {"building": True}
    try:
        gdf_bld = ox.features_from_point((center_lat, center_lon), tags=tags_buildings, dist=dist_m)
    except InsufficientResponseError:
        gdf_bld = None

    gdf_bld_p = None
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

    # --- Parks / green (egyelőre marad) ---
    tags_parks = {
        "leisure": ["park", "garden", "nature_reserve"],
        "landuse": ["grass", "meadow", "forest", "recreation_ground"],
        "natural": ["wood"],
    }
    try:
        gdf_parks = ox.features_from_point((center_lat, center_lon), tags=tags_parks, dist=dist_m)
    except InsufficientResponseError:
        gdf_parks = None

    gdf_parks_p = None
    if gdf_parks is not None and len(gdf_parks) > 0:
        gdf_parks = gdf_parks[gdf_parks.geometry.notnull()].copy()
        if len(gdf_parks) > 0:
            gdf_parks_p = ox.projection.project_gdf(gdf_parks)
            gdf_parks_p = gdf_parks_p[gdf_parks_p.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
            if len(gdf_parks_p) > 0:
                gdf_parks_p = gpd.clip(
                    gdf_parks_p,
                    gpd.GeoSeries([clip_rect], crs=gdf_parks_p.crs),
                )
                gdf_parks_p = gdf_parks_p[~gdf_parks_p.is_empty]
                if len(gdf_parks_p) == 0:
                    gdf_parks_p = None

    # víz alól vegyük ki a parkot/épületet
    if water_union is not None and not water_union.is_empty:
        if gdf_parks_p is not None and len(gdf_parks_p) > 0:
            gdf_parks_p = gdf_parks_p.copy()
            gdf_parks_p["geometry"] = gdf_parks_p.geometry.difference(water_union)
            gdf_parks_p = gdf_parks_p[~gdf_parks_p.is_empty]
            if len(gdf_parks_p) == 0:
                gdf_parks_p = None

        if gdf_bld_p is not None and len(gdf_bld_p) > 0:
            gdf_bld_p = gdf_bld_p.copy()
            gdf_bld_p["geometry"] = gdf_bld_p.geometry.difference(water_union)
            gdf_bld_p = gdf_bld_p[~gdf_bld_p.is_empty]
            if len(gdf_bld_p) == 0:
                gdf_bld_p = None

    # --- Color assignment ---
    background_color = _pick_lightest(palette)
    building_palette = _exclude_color(palette, background_color)
    if not building_palette:
        building_palette = palette[:]

    parks_color = _pick_lightest(building_palette) if building_palette else background_color

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
    fig.patch.set_facecolor(style.background)
    ax.set_facecolor(style.background)

    # land background
    gpd.GeoSeries([clip_rect], crs=gdf_edges_draw_p.crs).plot(
        ax=ax,
        color=background_color,
        linewidth=0,
        zorder=1,
    )

    # parks
    if gdf_parks_p is not None and len(gdf_parks_p) > 0:
        gdf_parks_p.plot(
            ax=ax,
            color=parks_color,
            linewidth=0,
            alpha=1.0,
            zorder=2,
        )

    # buildings
    if gdf_bld_p is not None and len(gdf_bld_p) > 0:
        building_colors = np.random.choice(building_palette, size=len(gdf_bld_p), replace=True)
        gdf_bld_p.plot(
            ax=ax,
            color=building_colors,
            linewidth=0,
            alpha=1.0,
            zorder=3,
        )

    # water (white)
    if water_union is not None and not water_union.is_empty:
        gpd.GeoSeries([water_union], crs=gdf_edges_draw_p.crs).plot(
            ax=ax,
            color="white",
            edgecolor="white",
            linewidth=0,
            zorder=4,
        )

    # --- Roads: plot by class, thin -> thick (thick on top) ---
    if gdf_edges_draw_p is not None and len(gdf_edges_draw_p) > 0:
        # draw order: minor, local, arterial, highway
        class_order = [
            ("minor", float(lw_minor_mult), 60),
            ("local", float(lw_local_mult), 70),
            ("arterial", float(lw_arterial_mult), 80),
            ("highway", float(lw_highway_mult), 90),
        ]

        for cls, mult, z in class_order:
            grp = gdf_edges_draw_p.loc[gdf_edges_draw_p["road_class"] == cls]
            if grp is None or len(grp) == 0:
                continue
            grp.plot(
                ax=ax,
                color=road_color,
                linewidth=base_lw * mult,
                alpha=1.0,
                capstyle="round",
                joinstyle="round",
                zorder=z,
            )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    print("Saving PDF to:", output_pdf)
    fig.savefig(output_pdf, format="pdf", dpi=spec.dpi, bbox_inches="tight")
    plt.close(fig)

    return RenderResult(output_pdf=output_pdf)
