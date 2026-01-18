# generator/render_monochrome.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

import math
import random

import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import osmnx as ox

from shapely.geometry import Point, box
from shapely.ops import unary_union

from osmnx._errors import InsufficientResponseError
from pyproj import Transformer

from generator.specs import ProductSpec
from generator.relief import ReliefConfig, load_dem_wgs84_crop, hillshade, normalize_grayscale

# reuse "pretty" helpers
from generator.render_pretty import _fetch_water_union, _fetch_sea_polygon, _scaled_linewidth


@dataclass(frozen=True)
class RenderResult:
    output_pdf: Path


def _safe_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


# ----------------------------
# Snazzy-like style (mapping)
# ----------------------------
@dataclass(frozen=True)
class MonoSnazzyStyle:
    background: str = "#ffffff"

    # landuse/parks (ha rajzolod őket)
    land_fill: str = "#ffffff"
    park_fill: str = "#ffffff"
    industrial_fill: str = "#ffffff"

    # water: fekete
    water_fill: str = "#000000"
    water_edge: str = "#000000"

    # buildings: nagyon halvány vagy akár off
    buildings_fill: str = "#f4f4f4"

    # highways + arterial: fekete (stroke off-hoz is igazítjuk mindjárt)
    highway_fill: str = "#000000"
    highway_stroke: str = "#000000"

    arterial_fill: str = "#000000"
    arterial_stroke: str = "#000000"

    # local: szürke
    local_fill: str = "#808080"
    local_stroke: str = "#808080"

    # minor: még halványabb szürke (ha szeretnéd)
    minor_fill: str = "#9a9a9a"
    minor_stroke: str = "#9a9a9a"

    # rail: opcionális, halvány
    rail_color: str = "#808080"

    # ordering
    z_land: int = 5
    z_buildings: int = 10
    z_water: int = 15
    z_roads_stroke: int = 50
    z_roads_fill: int = 50
    z_rail: int = 35


STYLE = MonoSnazzyStyle()


# Highway grouping similar to Google categories
HIGHWAY_HIGHWAY = {"motorway", "trunk"}
HIGHWAY_ARTERIAL = {"primary", "secondary", "tertiary"}
HIGHWAY_LOCAL = {"residential", "unclassified", "living_street"}
HIGHWAY_MINOR = {"service", "pedestrian", "cycleway", "footway", "path", "steps"}


# For optional "no parallel lines" collapse
HIGHWAY_RANK = {
    "motorway": 10,
    "trunk": 9,
    "primary": 8,
    "secondary": 7,
    "tertiary": 6,
    "residential": 5,
    "unclassified": 4,
    "living_street": 4,
    "service": 3,
    "pedestrian": 3,
    "cycleway": 2,
    "footway": 2,
    "path": 2,
    "steps": 1,
}


def _to_bbox_wgs84_from_proj_bounds(bounds_proj: Tuple[float, float, float, float], crs_proj) -> Tuple[float, float, float, float]:
    minx, miny, maxx, maxy = bounds_proj
    transformer = Transformer.from_crs(crs_proj, "EPSG:4326", always_xy=True)
    lon1, lat1 = transformer.transform(minx, miny)
    lon2, lat2 = transformer.transform(maxx, maxy)
    return (min(lon1, lon2), min(lat1, lat2), max(lon1, lon2), max(lat1, lat2))


def _normalize_highway_value(v):
    return v[0] if isinstance(v, (list, tuple)) and v else v


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


def _line_bearing_deg(geom) -> float:
    if geom is None or geom.is_empty:
        return 0.0
    if geom.geom_type == "MultiLineString":
        geom = max(list(geom.geoms), key=lambda g: g.length, default=None)
        if geom is None:
            return 0.0
    if geom.geom_type != "LineString":
        return 0.0
    coords = list(geom.coords)
    if len(coords) < 2:
        return 0.0
    (x1, y1), (x2, y2) = coords[0], coords[-1]
    ang = math.degrees(math.atan2((y2 - y1), (x2 - x1)))
    return abs(ang) % 180.0


def _angle_diff_deg(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def collapse_parallel_roads(
    gdf_edges_p: gpd.GeoDataFrame,
    *,
    tol_m: float = 7.0,
    angle_tol_deg: float = 12.0,
    prefer_higher_rank: bool = True,
) -> gpd.GeoDataFrame:
    if gdf_edges_p is None or len(gdf_edges_p) == 0:
        return gdf_edges_p

    gdf = gdf_edges_p.copy()
    if "highway" in gdf.columns:
        gdf["highway"] = gdf["highway"].apply(_normalize_highway_value)
    else:
        gdf["highway"] = "road"

    gdf["bearing"] = gdf.geometry.apply(_line_bearing_deg)
    gdf["rank"] = gdf["highway"].map(lambda h: HIGHWAY_RANK.get(str(h), 0)).astype(int)

    sidx = gdf.sindex

    keep = np.ones(len(gdf), dtype=bool)
    visited = np.zeros(len(gdf), dtype=bool)

    geoms = gdf.geometry.values
    bearings = gdf["bearing"].values
    ranks = gdf["rank"].values

    for i in range(len(gdf)):
        if visited[i] or not keep[i]:
            continue
        visited[i] = True

        gi = geoms[i]
        if gi is None or gi.is_empty:
            continue

        cand_idx = list(sidx.intersection(gi.buffer(tol_m).bounds))
        if not cand_idx:
            continue

        cluster = [i]
        for j in cand_idx:
            if j == i or visited[j] or not keep[j]:
                continue
            gj = geoms[j]
            if gj is None or gj.is_empty:
                continue

            if _angle_diff_deg(bearings[i], bearings[j]) <= angle_tol_deg:
                if gi.distance(gj) <= tol_m:
                    cluster.append(j)

        if len(cluster) == 1:
            continue

        if prefer_higher_rank:
            best = max(cluster, key=lambda k: (ranks[k], geoms[k].length))
        else:
            best = max(cluster, key=lambda k: geoms[k].length)

        for k in cluster:
            if k != best:
                keep[k] = False
                visited[k] = True

    return gdf.loc[keep].drop(columns=["bearing", "rank"], errors="ignore")


def _plot_two_pass(ax, gdf: gpd.GeoDataFrame, lw: float, fill: str, stroke: str,
                   z_stroke: int, z_fill: int, *, stroke_enabled: bool = True):
    if gdf is None or len(gdf) == 0:
        return

    if stroke_enabled:
        gdf.plot(
            ax=ax,
            color=stroke,
            linewidth=lw * 1.45,
            alpha=1.0,
            capstyle="round",
            joinstyle="round",
            zorder=z_stroke,
        )

    gdf.plot(
        ax=ax,
        color=fill,
        linewidth=lw,
        alpha=1.0,
        capstyle="round",
        joinstyle="round",
        zorder=z_fill,
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
    network_type_draw: str = "all",

    # content layers
    show_buildings: bool = True,
    min_building_area: float = 12.0,
    show_landuse: bool = True,
    show_parks: bool = True,
    show_rail: bool = True,

    # relief (optional)
    relief: ReliefConfig = ReliefConfig(),

    # controls
    road_width: float = 1.25,
    road_boost: float = 1.0,  # global multiplier
    collapse_parallels: bool = False,
    parallel_tol_m: float = 7.0,
    parallel_angle_tol_deg: float = 12.0,
) -> RenderResult:
    """
    SnazzyMaps-like monochrome:
      - water is gray
      - land is light gray
      - roads have stroke + fill (two-pass) and hierarchy
      - labels are not drawn
    """

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    fig_w_in, fig_h_in = spec.fig_size_inches

    half_width_m, half_height_m = spec.frame_half_sizes_m
    half_width_m = float(half_width_m) * float(zoom)
    half_height_m = float(half_height_m) * float(zoom)

    dist_m = int(np.ceil((half_width_m**2 + half_height_m**2) ** 0.5)) + 300

    ts = _safe_timestamp()
    output_pdf = output_dir / f"{filename_prefix}_{spec.width_cm}x{spec.height_cm}cm_z{zoom:.2f}_{ts}.pdf"

    center = gpd.GeoDataFrame(geometry=[Point(center_lon, center_lat)], crs="EPSG:4326")
    center_p = ox.projection.project_gdf(center).geometry.iloc[0]

    minx = center_p.x - half_width_m
    maxx = center_p.x + half_width_m
    miny = center_p.y - half_height_m
    maxy = center_p.y + half_height_m
    clip_rect = box(minx, miny, maxx, maxy)

    # --- Roads (fetch directed, draw undirected) ---
    G = ox.graph_from_point(
        (center_lat, center_lon),
        dist=dist_m,
        network_type=network_type_draw,
        simplify=True,
    )
    try:
        G_u = ox.convert.to_undirected(G)
    except AttributeError:
        G_u = ox.utils_graph.get_undirected(G)

    edges = ox.graph_to_gdfs(G_u, nodes=False, edges=True)
    edges_p = ox.projection.project_gdf(edges)
    edges_p = gpd.clip(edges_p, gpd.GeoSeries([clip_rect], crs=edges_p.crs))

    if "highway" in edges_p.columns:
        edges_p["highway"] = edges_p["highway"].apply(_normalize_highway_value)
        edges_p["road_class"] = edges_p["highway"].apply(_classify_road)
    else:
        edges_p["road_class"] = "local"

    if collapse_parallels:
        edges_p = collapse_parallel_roads(
            edges_p,
            tol_m=parallel_tol_m,
            angle_tol_deg=parallel_angle_tol_deg,
            prefer_higher_rank=True,
        )

    # --- Water/Sea (same as pretty) ---
    inland_water_union = _fetch_water_union(center_lat=center_lat, center_lon=center_lon, dist_m=dist_m, clip_rect=clip_rect)
    sea_poly = _fetch_sea_polygon(center_point_proj=center_p, center_lat=center_lat, center_lon=center_lon, dist_m=dist_m, clip_rect=clip_rect)

    water_union = None
    if inland_water_union is not None or sea_poly is not None:
        parts = []
        if inland_water_union is not None:
            parts.append(inland_water_union)
        if sea_poly is not None:
            parts.append(sea_poly)
        water_union = unary_union(parts).intersection(clip_rect)

    # --- Landuse / parks ---
    landuse_gdf_p = None
    parks_gdf_p = None
    if show_landuse or show_parks:
        tags = {}
        if show_landuse:
            tags.update({"landuse": True})
        if show_parks:
            tags.update({"leisure": "park"})
        try:
            gdf_lu = ox.features_from_point((center_lat, center_lon), tags=tags, dist=dist_m) if tags else None
        except InsufficientResponseError:
            gdf_lu = None

        if gdf_lu is not None and len(gdf_lu) > 0:
            gdf_lu = gdf_lu[gdf_lu.geometry.notnull()].copy()
            gdf_lu_p = ox.projection.project_gdf(gdf_lu)
            gdf_lu_p = gdf_lu_p[gdf_lu_p.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
            gdf_lu_p = gpd.clip(gdf_lu_p, gpd.GeoSeries([clip_rect], crs=gdf_lu_p.crs))
            gdf_lu_p = gdf_lu_p[~gdf_lu_p.is_empty]
            if len(gdf_lu_p) > 0:
                # split parks (leisure=park) and generic landuse
                if "leisure" in gdf_lu_p.columns:
                    parks = gdf_lu_p[gdf_lu_p["leisure"].astype(str) == "park"].copy()
                    if len(parks) > 0:
                        parks_gdf_p = parks
                if "landuse" in gdf_lu_p.columns:
                    landuse = gdf_lu_p[gdf_lu_p["landuse"].notna()].copy()
                    if len(landuse) > 0:
                        landuse_gdf_p = landuse

    # --- Buildings ---
    bld_p = None
    if show_buildings:
        try:
            gdf_bld = ox.features_from_point((center_lat, center_lon), tags={"building": True}, dist=dist_m)
        except InsufficientResponseError:
            gdf_bld = None
        if gdf_bld is not None and len(gdf_bld) > 0:
            gdf_bld = gdf_bld[gdf_bld.geometry.notnull()].copy()
            bld_p = ox.projection.project_gdf(gdf_bld)
            bld_p = bld_p[bld_p.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
            bld_p = gpd.clip(bld_p, gpd.GeoSeries([clip_rect], crs=bld_p.crs))
            bld_p = bld_p[~bld_p.is_empty]
            if len(bld_p) > 0:
                bld_p = bld_p[bld_p.geometry.area > float(min_building_area)]
            if len(bld_p) == 0:
                bld_p = None

    # Cut buildings out of water
    if water_union is not None and not water_union.is_empty and bld_p is not None and len(bld_p) > 0:
        bld_p = bld_p.copy()
        bld_p["geometry"] = bld_p.geometry.difference(water_union)
        bld_p = bld_p[~bld_p.is_empty]
        if len(bld_p) == 0:
            bld_p = None

    # --- Rail (optional) ---
    rail_p = None
    if show_rail:
        try:
            gdf_rail = ox.features_from_point((center_lat, center_lon), tags={"railway": True}, dist=dist_m)
        except InsufficientResponseError:
            gdf_rail = None
        if gdf_rail is not None and len(gdf_rail) > 0:
            gdf_rail = gdf_rail[gdf_rail.geometry.notnull()].copy()
            rail_p = ox.projection.project_gdf(gdf_rail)
            rail_p = rail_p[rail_p.geom_type.isin(["LineString", "MultiLineString"])].copy()
            rail_p = gpd.clip(rail_p, gpd.GeoSeries([clip_rect], crs=rail_p.crs))
            rail_p = rail_p[~rail_p.is_empty]
            if len(rail_p) == 0:
                rail_p = None

    # --- Linewidth scaling ---
    lw = _scaled_linewidth(
        half_height_m=half_height_m,
        base_linewidth=road_width,
        reference_half_height_m=2000.0,
        min_lw=0.25,
        max_lw=3.0,
    ) * float(road_boost)

    # --- Relief bbox in WGS84 (optional) ---
    bbox_wgs84 = _to_bbox_wgs84_from_proj_bounds((minx, miny, maxx, maxy), edges_p.crs)

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
    fig.patch.set_facecolor(STYLE.background)
    ax.set_facecolor(STYLE.background)

    # Relief first (very subtle) - but snazzy style usually doesn't need it
    if relief.enabled:
        try:
            dem_pack = load_dem_wgs84_crop(bbox_wgs84, relief.cache_dir)
            if dem_pack is not None:
                dem, dem_transform, _ = dem_pack
                shade01 = hillshade(
                    dem, dem_transform,
                    azimuth_deg=relief.azimuth_deg,
                    altitude_deg=relief.altitude_deg,
                    z_factor=relief.z_factor,
                )
                gray = normalize_grayscale(shade01, relief.out_min, relief.out_max)
                rgba = np.dstack([gray, gray, gray, np.full_like(gray, relief.alpha, dtype=np.float32)])
                ax.imshow(rgba, extent=(minx, maxx, miny, maxy), origin="upper", zorder=0)
        except Exception:
            if not relief.fail_silently:
                raise

    # Landuse / parks
    if landuse_gdf_p is not None and len(landuse_gdf_p) > 0:
        # industrial a bit different if present
        if "landuse" in landuse_gdf_p.columns:
            ind = landuse_gdf_p[landuse_gdf_p["landuse"].astype(str) == "industrial"]
            rest = landuse_gdf_p[landuse_gdf_p["landuse"].astype(str) != "industrial"]
            if len(rest) > 0:
                rest.plot(ax=ax, color=STYLE.land_fill, linewidth=0, zorder=STYLE.z_land)
            if len(ind) > 0:
                ind.plot(ax=ax, color=STYLE.industrial_fill, linewidth=0, zorder=STYLE.z_land)
        else:
            landuse_gdf_p.plot(ax=ax, color=STYLE.land_fill, linewidth=0, zorder=STYLE.z_land)

    if parks_gdf_p is not None and len(parks_gdf_p) > 0:
        parks_gdf_p.plot(ax=ax, color=STYLE.park_fill, linewidth=0, zorder=STYLE.z_land + 1)

    # Buildings
    if bld_p is not None and len(bld_p) > 0:
        bld_p.plot(ax=ax, color=STYLE.buildings_fill, linewidth=0, zorder=STYLE.z_buildings)

    # Water mask (mid gray)
    if water_union is not None and not water_union.is_empty:
        gpd.GeoSeries([water_union], crs=edges_p.crs).plot(
            ax=ax,
            color=STYLE.water_fill,
            edgecolor=STYLE.water_edge,
            linewidth=0,
            zorder=STYLE.z_water,
        )

    # Rail (very subtle)
    if rail_p is not None and len(rail_p) > 0:
        rail_p.plot(ax=ax, color=STYLE.rail_color, linewidth=max(0.1, lw * 0.4), zorder=STYLE.z_rail)

    # Roads split by class, two-pass
    roads_by_class: Dict[str, gpd.GeoDataFrame] = {}
    for cls in ["highway", "arterial", "local", "minor"]:
        roads_by_class[cls] = edges_p[edges_p["road_class"] == cls].copy()

    _plot_two_pass(ax, roads_by_class["minor"], lw * 0.60, STYLE.minor_fill, STYLE.minor_stroke,
                   STYLE.z_roads_stroke, STYLE.z_roads_fill, stroke_enabled=True)

    _plot_two_pass(ax, roads_by_class["local"], lw * 0.85, STYLE.local_fill, STYLE.local_stroke,
                   STYLE.z_roads_stroke, STYLE.z_roads_fill, stroke_enabled=True)

    # arterial: stroke OFF (Snazzy szerint)
    _plot_two_pass(ax, roads_by_class["arterial"], lw * 1.10, STYLE.arterial_fill, STYLE.arterial_stroke,
                   STYLE.z_roads_stroke, STYLE.z_roads_fill, stroke_enabled=False)

    # highway: stroke OFF (Snazzy szerint)
    _plot_two_pass(ax, roads_by_class["highway"], lw * 1.35, STYLE.highway_fill, STYLE.highway_stroke,
                   STYLE.z_roads_stroke, STYLE.z_roads_fill, stroke_enabled=False)

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    print("Saving PDF to:", output_pdf)
    fig.savefig(output_pdf, format="pdf", dpi=spec.dpi, bbox_inches="tight")
    plt.close(fig)

    return RenderResult(output_pdf=output_pdf)
