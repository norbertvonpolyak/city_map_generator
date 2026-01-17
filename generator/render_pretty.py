# from __future__ import annotations
#
# from dataclasses import dataclass
# from datetime import datetime
# from pathlib import Path
# from typing import Optional, List
#
# import numpy as np
# import geopandas as gpd
# import matplotlib.pyplot as plt
# import osmnx as ox
# import random
#
# from shapely.geometry import Point, box
# from shapely.ops import unary_union
#
# from osmnx._errors import InsufficientResponseError
#
# from generator.specs import ProductSpec
# from generator.styles import Style, DEFAULT_STYLE, get_palette
#
#
# @dataclass(frozen=True)
# class RenderResult:
#     output_pdf: Path
#
#
# def _safe_timestamp() -> str:
#     return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
#
#
# def render_city_map_pretty(
#     *,
#     center_lat: float,
#     center_lon: float,
#     spec: ProductSpec,
#     output_dir: Path,
#     palette_name: str = "warm",
#     style: Style = DEFAULT_STYLE,
#     seed: Optional[int] = 42,
#     filename_prefix: str = "city_pretty",
#     network_type_draw: str = "drive",
#     zoom: float = 0.6,
#     road_width: float = 0.75,
# ) -> RenderResult:
#     """
#     Prettymaps-szerű (réteges) render alap váz:
#     - ugyanaz a termékméret (spec), ugyanaz a PDF export
#     - kisebb kiterjedés zoom szorzóval (épület részletekhez)
#     - jelenleg: háttér + utak (water/sea később)
#     """
#     if not (-90.0 <= center_lat <= 90.0):
#         raise ValueError("center_lat érvénytelen (−90..90).")
#     if not (-180.0 <= center_lon <= 180.0):
#         raise ValueError("center_lon érvénytelen (−180..180).")
#     if zoom <= 0:
#         raise ValueError("zoom > 0 kell legyen.")
#
#     output_dir = Path(output_dir)
#     output_dir.mkdir(parents=True, exist_ok=True)
#
#     if seed is not None:
#         np.random.seed(seed)
#         random.seed(seed)
#
#     palette: List[str] = get_palette(palette_name)
#
#     # Export méret
#     fig_w_in, fig_h_in = spec.fig_size_inches
#
#     # Frame (méterben) – zoomolva
#     half_width_m, half_height_m = spec.frame_half_sizes_m
#     half_width_m = float(half_width_m) * float(zoom)
#     half_height_m = float(half_height_m) * float(zoom)
#
#     # Letöltési távolság: félátló + tartalék
#     dist_m = int(np.ceil((half_width_m**2 + half_height_m**2) ** 0.5)) + 300
#
#     # Timestampes fájlnév
#     ts = _safe_timestamp()
#     output_pdf = output_dir / f"{filename_prefix}_{spec.width_cm}x{spec.height_cm}cm_z{zoom:.2f}_{ts}.pdf"
#
#     # Középpont projekcióban
#     center = gpd.GeoDataFrame(geometry=[Point(center_lon, center_lat)], crs="EPSG:4326")
#     center_p = ox.projection.project_gdf(center).geometry.iloc[0]
#
#     minx = center_p.x - half_width_m
#     maxx = center_p.x + half_width_m
#     miny = center_p.y - half_height_m
#     maxy = center_p.y + half_height_m
#     clip_rect = box(minx, miny, maxx, maxy)
#
#     # Utak (rajz) – most még csak ennyi
#     G_draw = ox.graph_from_point(
#         (center_lat, center_lon),
#         dist=dist_m,
#         network_type=network_type_draw,
#         simplify=True,
#     )
#     gdf_edges_draw = ox.graph_to_gdfs(G_draw, nodes=False, edges=True)
#     gdf_edges_draw_p = ox.projection.project_gdf(gdf_edges_draw)
#     gdf_edges_draw_p = gpd.clip(
#         gdf_edges_draw_p,
#         gpd.GeoSeries([clip_rect], crs=gdf_edges_draw_p.crs),
#     )
#
#     # Buildings (épületek) – polygon layer
#     tags_buildings = {"building": True}
#     try:
#         gdf_bld = ox.features_from_point((center_lat, center_lon), tags=tags_buildings, dist=dist_m)
#     except InsufficientResponseError:
#         gdf_bld = None
#
#     gdf_bld_p = None
#     if gdf_bld is not None and len(gdf_bld) > 0:
#         gdf_bld = gdf_bld[gdf_bld.geometry.notnull()].copy()
#         if len(gdf_bld) > 0:
#             gdf_bld_p = ox.projection.project_gdf(gdf_bld)
#             gdf_bld_p = gdf_bld_p[gdf_bld_p.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
#             if len(gdf_bld_p) > 0:
#                 gdf_bld_p = gpd.clip(
#                     gdf_bld_p,
#                     gpd.GeoSeries([clip_rect], crs=gdf_bld_p.crs),
#                 )
#                 gdf_bld_p = gdf_bld_p[~gdf_bld_p.is_empty]
#                 if len(gdf_bld_p) == 0:
#                     gdf_bld_p = None
#
#
#     # Parks / green – polygon layer
#     tags_parks = {
#         "leisure": ["park", "garden", "nature_reserve"],
#         "landuse": ["grass", "meadow", "forest", "recreation_ground"],
#         "natural": ["wood"],
#     }
#     try:
#         gdf_parks = ox.features_from_point((center_lat, center_lon), tags=tags_parks, dist=dist_m)
#     except InsufficientResponseError:
#         gdf_parks = None
#
#     gdf_parks_p = None
#     if gdf_parks is not None and len(gdf_parks) > 0:
#         gdf_parks = gdf_parks[gdf_parks.geometry.notnull()].copy()
#         if len(gdf_parks) > 0:
#             gdf_parks_p = ox.projection.project_gdf(gdf_parks)
#             gdf_parks_p = gdf_parks_p[gdf_parks_p.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
#             if len(gdf_parks_p) > 0:
#                 gdf_parks_p = gpd.clip(
#                     gdf_parks_p,
#                     gpd.GeoSeries([clip_rect], crs=gdf_parks_p.crs),
#                 )
#                 gdf_parks_p = gdf_parks_p[~gdf_parks_p.is_empty]
#                 if len(gdf_parks_p) == 0:
#                     gdf_parks_p = None
#
#
#     # Háttérszín: palette-ből (egységes)
#     background_color = np.random.choice(palette)
#
#     fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
#     fig.patch.set_facecolor(style.background)
#     ax.set_facecolor(style.background)
#
#     # háttér “land” (egyszerű téglalapként)
#     gpd.GeoSeries([clip_rect], crs=gdf_edges_draw_p.crs).plot(
#         ax=ax,
#         color=background_color,
#         linewidth=0,
#     )
#
#     # parkok/green: külön színnel, hogy felismerhető legyen a zöldfelület
#     if gdf_parks_p is not None and len(gdf_parks_p) > 0:
#         parks_color = np.random.choice(palette)
#         gdf_parks_p.plot(
#             ax=ax,
#             color=parks_color,
#             linewidth=0,
#             alpha=1.0,
#         )
#
#
#     # épületek: kapjanak egy visszafogott, világos tónust (palette-ből), vékony kontúrral
#     if gdf_bld_p is not None and len(gdf_bld_p) > 0:
#         building_color = np.random.choice(palette)
#         gdf_bld_p.plot(
#             ax=ax,
#             color=building_color,
#             linewidth=0.15,
#             edgecolor=building_color,
#             alpha=1.0,
#         )
#
#     # utak
#     if len(gdf_edges_draw_p) > 0:
#         gdf_edges_draw_p.plot(
#             ax=ax,
#             color=style.road,
#             linewidth=road_width,
#             alpha=1.0,
#         )
#
#     ax.set_xlim(minx, maxx)
#     ax.set_ylim(miny, maxy)
#     ax.set_axis_off()
#
#     print("Saving PDF to:", output_pdf)
#     fig.savefig(output_pdf, format="pdf", dpi=spec.dpi, bbox_inches="tight")
#     plt.close(fig)
#
#     return RenderResult(output_pdf=output_pdf)

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
        # klasszikus vízpoligonok
        "natural": ["water", "bay"],
        "water": True,

        # vízfolyások (vonalakból néha poligon is lehet a gdf-ben)
        "waterway": ["river", "canal", "dock", "basin"],

        # mesterséges / kikötői vízterek
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

    Bulletproof heurisztika:
    - polygonize(frame_boundary + coastline)
    - LAND = az a poligon, amelyik tartalmazza a center_point_proj pontot
    - SEA = frame - LAND
    - fallback: boundary-touch (4 oldal) guard-rail küszöbökkel

    Inland városnál nincs coastline -> None (és NEM dob hibát).
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


def _pick_distinct_color(palette: List[str], avoid: Optional[str]) -> str:
    if avoid is None:
        return str(np.random.choice(palette))
    choices = [c for c in palette if c != avoid]
    if not choices:
        return str(np.random.choice(palette))
    return str(np.random.choice(choices))


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
    network_type_draw: str = "all",   # <-- fontos: így jönnek a kisebb utcák is
    zoom: float = 0.6,
    road_width: float = 0.75,
    min_building_area: float = 12.0,  # m^2 – nagyon apró building sliverek szűrése
) -> RenderResult:
    """
    Prettymaps-szerű (réteges) render:
    - ugyanaz a termékméret (spec), ugyanaz a PDF export
    - zoom: kisebb kiterjedés (épület részletekhez)
    - rétegek: background/land, parks, buildings, water (white), roads (white), bridges (gray)
    - víz: belvíz + tenger (coastline), mind fehér
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

    # pretty road width skálázás
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
    rect_boundary = clip_rect.boundary

    # --- Roads (draw) ---
    G_draw = ox.graph_from_point(
        (center_lat, center_lon),
        dist=dist_m,
        network_type=network_type_draw,
        simplify=True,
    )
    gdf_edges_draw = ox.graph_to_gdfs(G_draw, nodes=False, edges=True)
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
                    # nagyon apró polygonok szűrése
                    gdf_bld_p = gdf_bld_p[gdf_bld_p.geometry.area > float(min_building_area)]
                if len(gdf_bld_p) == 0:
                    gdf_bld_p = None

    # --- Parks / green (opcionális, de jól áll pretty módnak) ---
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

    # Biztonság: ha van water_union, vegyük ki a víz alól a parkot/épületet
    if water_union is not None and not water_union.is_empty:
        if gdf_parks_p is not None and len(gdf_parks_p) > 0:
            gdf_parks_p["geometry"] = gdf_parks_p.geometry.difference(water_union)
            gdf_parks_p = gdf_parks_p[~gdf_parks_p.is_empty]
            if len(gdf_parks_p) == 0:
                gdf_parks_p = None
        if gdf_bld_p is not None and len(gdf_bld_p) > 0:
            gdf_bld_p["geometry"] = gdf_bld_p.geometry.difference(water_union)
            gdf_bld_p = gdf_bld_p[~gdf_bld_p.is_empty]
            if len(gdf_bld_p) == 0:
                gdf_bld_p = None

    # --- Color assignment (nem homogén épületek) ---
    background_color = str(np.random.choice(palette))
    parks_color = _pick_distinct_color(palette, avoid=background_color)

    # épület-színek: warm -> egyenletes; egyéb -> súlyozott
    if palette_name == "warm":
        bld_p = None
        if gdf_bld_p is not None:
            bld_p = None  # uniform
        # nem kell p
    else:
        weights = np.array([1.5, 2.0, 3.5, 5.0, 4.5, 3.0, 1.8], dtype=float)
        bld_p = weights / weights.sum()

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
    fig.patch.set_facecolor(style.background)
    ax.set_facecolor(style.background)

    # background land (téglalap)
    gpd.GeoSeries([clip_rect], crs=gdf_edges_draw_p.crs).plot(
        ax=ax,
        color=background_color,
        linewidth=0,
    )

    # parks (alap foltok)
    if gdf_parks_p is not None and len(gdf_parks_p) > 0:
        gdf_parks_p.plot(
            ax=ax,
            color=parks_color,
            linewidth=0,
            alpha=1.0,
        )

    # buildings (nem homogén)
    if gdf_bld_p is not None and len(gdf_bld_p) > 0:
        if palette_name == "warm":
            building_colors = np.random.choice(palette, size=len(gdf_bld_p), replace=True)
        else:
            building_colors = np.random.choice(palette, size=len(gdf_bld_p), replace=True, p=bld_p)

        gdf_bld_p.plot(
            ax=ax,
            color=building_colors,
            linewidth=0,      # kontúrt most nem erőltetjük, hogy ne "szőnyeg" legyen
            alpha=1.0,
        )

    # víz (mindig fehér) – a buildings/parks fölé, hogy biztosan kijöjjön
    if water_union is not None and not water_union.is_empty:
        gpd.GeoSeries([water_union], crs=gdf_edges_draw_p.crs).plot(
            ax=ax,
            color="white",
            edgecolor="white",
            linewidth=0,
        )

    # utak (fehér)
    if len(gdf_edges_draw_p) > 0:
        gdf_edges_draw_p.plot(
            ax=ax,
            color=style.road,  # nálad jellemzően fehér
            linewidth=scaled_road_width,
            alpha=1.0,
        )

    # hidak: halványabb (ha van bridge attribútum)
    if "bridge" in gdf_edges_draw.columns:
        bridges = gdf_edges_draw[gdf_edges_draw["bridge"].notna()].copy()
        if len(bridges) > 0:
            ox.projection.project_gdf(bridges).plot(
                ax=ax,
                color=style.bridge,
                linewidth=max(0.12, scaled_road_width * 0.75),
                alpha=1.0,
            )

    # frame border finom fehérrel (opcionális, de szép)
    gpd.GeoSeries([rect_boundary], crs=gdf_edges_draw_p.crs).plot(
        ax=ax,
        color=style.road,
        linewidth=max(0.12, scaled_road_width * 0.75),
        alpha=1.0,
    )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    print("Saving PDF to:", output_pdf)
    fig.savefig(output_pdf, format="pdf", dpi=spec.dpi, bbox_inches="tight")
    plt.close(fig)

    return RenderResult(output_pdf=output_pdf)
