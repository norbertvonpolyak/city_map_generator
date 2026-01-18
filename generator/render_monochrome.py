# generator/render_monochrome.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict

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
from generator.render_pretty import _fetch_water_union, _fetch_sea_polygon, _scaled_linewidth
from generator.styles import MonoStyle, MONO_PRESETS


@dataclass(frozen=True)
class RenderResult:
    output_pdf: Optional[Path] = None
    output_png: Optional[Path] = None


# --- Road classification (OSM highway -> our classes) ---
HIGHWAY_HIGHWAY = {"motorway", "trunk"}
HIGHWAY_ARTERIAL = {"primary", "secondary", "tertiary"}
HIGHWAY_LOCAL = {"residential", "unclassified", "living_street"}

# IMPORTANT:
# "minor" legyen jármű-út jellegű (service), NE a gyalog/bicikli/path réteg.
HIGHWAY_MINOR = {"service"}

# Nem-jármű "highway" típusok, amik nagyon gyakran párhuzamos vonalakat okoznak
# (külön OSM way-ként a főút mellett / felett).
EXCLUDE_NON_VEHICULAR_HIGHWAYS = {
    "pedestrian",
    "cycleway",
    "footway",
    "path",
    "steps",
    "bridleway",
}

# For optional "collapse parallels" (rang a preferált kiválasztáshoz)
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
    # az alábbiak maradnak, mert ha draw_non_vehicular=True, akkor lehet értelme:
    "pedestrian": 3,
    "cycleway": 2,
    "footway": 2,
    "path": 2,
    "steps": 1,
}


def _safe_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


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


def _to_bbox_wgs84_from_proj_bounds(
    bounds_proj: Tuple[float, float, float, float],
    crs_proj,
) -> Tuple[float, float, float, float]:
    minx, miny, maxx, maxy = bounds_proj
    transformer = Transformer.from_crs(crs_proj, "EPSG:4326", always_xy=True)
    lon1, lat1 = transformer.transform(minx, miny)
    lon2, lat2 = transformer.transform(maxx, maxy)
    return (min(lon1, lon2), min(lat1, lat2), max(lon1, lon2), max(lat1, lat2))


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
    """
    Aggressive: within a corridor (near + roughly parallel), keep exactly one line.
    Use only if you explicitly want to eliminate any parallel depiction.
    """
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


def _plot_two_pass(
    ax,
    gdf: gpd.GeoDataFrame,
    lw: float,
    fill: str,
    stroke: str,
    z_stroke: int,
    z_fill: int,
    *,
    stroke_enabled: bool,
    stroke_mult: float,
):
    if gdf is None or len(gdf) == 0:
        return

    if stroke_enabled:
        gdf.plot(
            ax=ax,
            color=stroke,
            linewidth=lw * float(stroke_mult),
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

    # layers
    show_buildings: bool = True,
    min_building_area: float = 12.0,
    show_landuse: bool = True,
    show_parks: bool = True,
    show_rail: bool = True,

    # relief
    relief: ReliefConfig = ReliefConfig(),

    # style
    style: Optional[MonoStyle] = None,
    preset_name: str = "snazzy_bw_blackwater",

    # IMPORTANT: ha False, kiszűrjük a footway/cycleway/path/pedestrian/steps réteget,
    # ami a párhuzamos "dupla" vonalak leggyakoribb oka.
    draw_non_vehicular: bool = False,

    # geometry cleanup (optional)
    collapse_parallels: bool = False,
    parallel_tol_m: float = 7.0,
    parallel_angle_tol_deg: float = 12.0,

    # output
    preview: bool = False,
) -> RenderResult:
    """
    Monochrome renderer controlled by MonoStyle presets.
    preview=True -> saves PNG for fast iteration (Streamlit).
    preview=False -> saves PDF for print.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    if style is None:
        style = MONO_PRESETS.get(preset_name)
        if style is None:
            raise ValueError(
                f"Unknown mono preset '{preset_name}'. Available: {list(MONO_PRESETS.keys())}"
            )

    fig_w_in, fig_h_in = spec.fig_size_inches

    half_width_m, half_height_m = spec.frame_half_sizes_m
    half_width_m = float(half_width_m) * float(zoom)
    half_height_m = float(half_height_m) * float(zoom)

    dist_m = int(np.ceil((half_width_m ** 2 + half_height_m ** 2) ** 0.5)) + 300

    ts = _safe_timestamp()
    out_pdf = output_dir / f"{filename_prefix}_{spec.width_cm}x{spec.height_cm}cm_z{zoom:.2f}_{ts}.pdf"
    out_png = output_dir / f"{filename_prefix}_{spec.width_cm}x{spec.height_cm}cm_z{zoom:.2f}_{ts}.png"

    # center in projected CRS
    center = gpd.GeoDataFrame(geometry=[Point(center_lon, center_lat)], crs="EPSG:4326")
    center_p = ox.projection.project_gdf(center).geometry.iloc[0]

    minx = center_p.x - half_width_m
    maxx = center_p.x + half_width_m
    miny = center_p.y - half_height_m
    maxy = center_p.y + half_height_m
    clip_rect = box(minx, miny, maxx, maxy)

    # --- Roads ---
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

    # --- Filter out non-vehicular highway ways (to avoid parallel clutter) ---
    if "highway" in edges_p.columns and not draw_non_vehicular:
        mask = edges_p["highway"].apply(
            lambda v: not _highway_has_any(v, EXCLUDE_NON_VEHICULAR_HIGHWAYS)
        )
        edges_p = edges_p.loc[mask].copy()

        # Optional: ha járda külön attribútumként jelen van (ritkább graph-edge eset)
        if "footway" in edges_p.columns:
            edges_p = edges_p.loc[edges_p["footway"].astype(str) != "sidewalk"].copy()

    # --- Classification ---
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
        if "highway" in edges_p.columns:
            edges_p["road_class"] = edges_p["highway"].apply(_classify_road)

    # --- Water/Sea ---
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

    # --- Landuse / Parks ---
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

    if water_union is not None and not water_union.is_empty and bld_p is not None and len(bld_p) > 0:
        bld_p = bld_p.copy()
        bld_p["geometry"] = bld_p.geometry.difference(water_union)
        bld_p = bld_p[~bld_p.is_empty]
        if len(bld_p) == 0:
            bld_p = None

    # --- Rail ---
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
        base_linewidth=float(style.road_width),
        reference_half_height_m=2000.0,
        min_lw=0.20,
        max_lw=4.0,
    ) * float(style.road_boost)

    # Relief bbox (optional)
    bbox_wgs84 = _to_bbox_wgs84_from_proj_bounds((minx, miny, maxx, maxy), edges_p.crs)

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
    fig.patch.set_facecolor(style.background)
    ax.set_facecolor(style.background)

    # Relief first (subtle)
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
                rgba = np.dstack([gray, gray, gray, np.full_like(gray, relief.alpha, dtype=np.float32)])
                ax.imshow(rgba, extent=(minx, maxx, miny, maxy), origin="upper", zorder=0)
        except Exception:
            if not relief.fail_silently:
                raise

    # Landuse / parks
    if landuse_gdf_p is not None and len(landuse_gdf_p) > 0:
        if "landuse" in landuse_gdf_p.columns:
            ind = landuse_gdf_p[landuse_gdf_p["landuse"].astype(str) == "industrial"]
            rest = landuse_gdf_p[landuse_gdf_p["landuse"].astype(str) != "industrial"]
            if len(rest) > 0:
                rest.plot(ax=ax, color=style.land_fill, linewidth=0, zorder=5)
            if len(ind) > 0:
                ind.plot(ax=ax, color=style.industrial_fill, linewidth=0, zorder=5)
        else:
            landuse_gdf_p.plot(ax=ax, color=style.land_fill, linewidth=0, zorder=5)

    if parks_gdf_p is not None and len(parks_gdf_p) > 0:
        parks_gdf_p.plot(ax=ax, color=style.park_fill, linewidth=0, zorder=6)

    # Buildings
    if bld_p is not None and len(bld_p) > 0:
        bld_p.plot(ax=ax, color=style.buildings_fill, linewidth=0, zorder=10)

    # Water (víz mindig fehér, edge most nincs kirajzolva külön)
    if water_union is not None and not water_union.is_empty:
        gpd.GeoSeries([water_union], crs=edges_p.crs).plot(
            ax=ax,
            color=style.water_fill,
            edgecolor=style.water_edge,
            linewidth=0,
            zorder=15,
        )

    # Rail
    if rail_p is not None and len(rail_p) > 0:
        rail_p.plot(ax=ax, color=style.rail_color, linewidth=max(0.10, lw * 0.35), zorder=35)

    # Roads by class
    roads_by_class: Dict[str, gpd.GeoDataFrame] = {}
    for cls in ["highway", "arterial", "local", "minor"]:
        roads_by_class[cls] = edges_p[edges_p["road_class"] == cls].copy()

    _plot_two_pass(
        ax,
        roads_by_class["minor"],
        lw * float(style.lw_minor_mult),
        style.minor_fill,
        style.minor_stroke,
        40,
        50,
        stroke_enabled=bool(style.minor_stroke_enabled),
        stroke_mult=float(style.stroke_mult),
    )
    _plot_two_pass(
        ax,
        roads_by_class["local"],
        lw * float(style.lw_local_mult),
        style.local_fill,
        style.local_stroke,
        40,
        50,
        stroke_enabled=bool(style.local_stroke_enabled),
        stroke_mult=float(style.stroke_mult),
    )
    _plot_two_pass(
        ax,
        roads_by_class["arterial"],
        lw * float(style.lw_arterial_mult),
        style.arterial_fill,
        style.arterial_stroke,
        40,
        50,
        stroke_enabled=bool(style.arterial_stroke_enabled),
        stroke_mult=float(style.stroke_mult),
    )
    _plot_two_pass(
        ax,
        roads_by_class["highway"],
        lw * float(style.lw_highway_mult),
        style.highway_fill,
        style.highway_stroke,
        40,
        50,
        stroke_enabled=bool(style.highway_stroke_enabled),
        stroke_mult=float(style.stroke_mult),
    )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    if preview:
        fig.savefig(out_png, format="png", dpi=min(180, spec.dpi), bbox_inches="tight")
        plt.close(fig)
        return RenderResult(output_png=out_png)

    fig.savefig(out_pdf, format="pdf", dpi=spec.dpi, bbox_inches="tight")
    plt.close(fig)
    return RenderResult(output_pdf=out_pdf)
