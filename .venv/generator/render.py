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

from shapely.geometry import Point, box
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
    Vízfelület union (Polygon/MultiPolygon) projekcióban, a frame-re vágva.
    OSMnx 2.x: features_from_point.
    """
    tags = {
        "natural": ["water"],
        "water": True,
        "waterway": ["river", "canal"],
        "landuse": ["reservoir"],
    }

    gdf_water = ox.features_from_point((center_lat, center_lon), tags=tags, dist=dist_m)
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


def _scaled_linewidth(
    *,
    half_height_m: float,
    base_linewidth: float,
    reference_half_height_m: float = 5000.0,
    min_lw: float = 0.35,
    max_lw: float = 2.2,
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
    road_width: float = 1.1,
) -> RenderResult:
    """
    Webshop-kompatibilis render:
    - frame (téglalap) a spec képarányával
    - tömbök színezése palettából
    - lyuk kitöltése 1 palettaszínnel (nem darabolva)
    - utak fehérek, hidak halvány szürkék, víz fehér
    - PDF mentés timestamp névvel
    """
    if not (-90.0 <= center_lat <= 90.0):
        raise ValueError("center_lat érvénytelen (−90..90).")
    if not (-180.0 <= center_lon <= 180.0):
        raise ValueError("center_lon érvénytelen (−180..180).")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # determinisztikus random (ha seed=None, minden futás más)
    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    palette: List[str] = get_palette(palette_name)

    # Frame méretek (méterben) és fizikai export méretek (inch)
    half_width_m, half_height_m = spec.frame_half_sizes_m
    fig_w_in, fig_h_in = spec.fig_size_inches

    # Útvastagság skálázása a kiterjedéshez (5000 m félmagasság volt a “jó” referencia)
    scaled_road_width = _scaled_linewidth(
        half_height_m=half_height_m,
        base_linewidth=road_width,
        reference_half_height_m=5000.0,
        min_lw=0.35,
        max_lw=2.2,
    )

    # Letöltési távolság: félátló + tartalék
    dist_m = int(np.ceil((half_width_m**2 + half_height_m**2) ** 0.5)) + 300

    # Timestampes fájlnév (nem ír felül)
    ts = _safe_timestamp()
    output_pdf = output_dir / f"{filename_prefix}_{spec.width_cm}x{spec.height_cm}cm_{ts}.pdf"

    # 1) Úthálózat letöltés + edges gdf
    G = ox.graph_from_point((center_lat, center_lon), dist=dist_m, network_type=network_type, simplify=True)
    gdf_edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
    gdf_edges_p = ox.projection.project_gdf(gdf_edges)

    # 2) Frame téglalap projekcióban
    center = gpd.GeoDataFrame(geometry=[Point(center_lon, center_lat)], crs="EPSG:4326")
    center_p = ox.projection.project_gdf(center).geometry.iloc[0]

    minx = center_p.x - half_width_m
    maxx = center_p.x + half_width_m
    miny = center_p.y - half_height_m
    maxy = center_p.y + half_height_m

    clip_rect = box(minx, miny, maxx, maxy)
    rect_boundary = clip_rect.boundary

    # 3) Víz union (projekcióban, frame-re vágva)
    water_union = _fetch_water_union(
        center_lat=center_lat,
        center_lon=center_lon,
        dist_m=dist_m,
        clip_rect=clip_rect,
    )

    # 4) “Frame = utca”: polygonize a frame-en belül + frame boundary
    edges_clip = gpd.clip(gdf_edges_p, gpd.GeoSeries([clip_rect], crs=gdf_edges_p.crs))

    line_geoms = list(edges_clip.geometry.values)
    line_geoms.append(rect_boundary)

    merged_lines = unary_union(line_geoms)
    polys = list(polygonize(merged_lines))

    gdf_blocks_p = gpd.GeoDataFrame(geometry=polys, crs=gdf_edges_p.crs)
    gdf_blocks_p = gdf_blocks_p[gdf_blocks_p.geometry.within(clip_rect)]
    gdf_blocks_p = gdf_blocks_p[gdf_blocks_p.geometry.area > float(min_poly_area)]

    # 5) Víz kivonása a blokkokból (hogy a folyó/tó ne legyen színes)
    if water_union is not None and len(gdf_blocks_p) > 0:
        gdf_blocks_p["geometry"] = gdf_blocks_p.geometry.difference(water_union)
        gdf_blocks_p = gdf_blocks_p[~gdf_blocks_p.is_empty]

    # 6) “Lyuk” = frame - víz - blokkok_unió (1 db színnel töltjük)
    blocks_union = gdf_blocks_p.unary_union if len(gdf_blocks_p) > 0 else None

    hole = clip_rect
    if water_union is not None:
        hole = hole.difference(water_union)
    if blocks_union is not None:
        hole = hole.difference(blocks_union)

    # Színkiosztás:
    # - warm: marad az eredeti (egyenletes) elosztás
    # - minden más: súlyozott elosztás a jobb kontraszthoz és kevésbé homogén mintához
    if palette_name == "warm":
        hole_color = np.random.choice(palette)
        block_colors = np.random.choice(palette, size=len(gdf_blocks_p), replace=True)
    else:
        weights = np.array([1.5, 2.0, 3.5, 5.0, 4.5, 3.0, 1.8], dtype=float)
        p = weights / weights.sum()

        hole_color = np.random.choice(palette, p=p)
        block_colors = np.random.choice(palette, size=len(gdf_blocks_p), replace=True, p=p)

    # 7) Plot
    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
    fig.patch.set_facecolor(style.background)
    ax.set_facecolor(style.background)

    # Lyuk kitöltése (nem darabolva)
    if not hole.is_empty:
        gpd.GeoSeries([hole], crs=gdf_edges_p.crs).plot(ax=ax, color=hole_color, linewidth=0)

    # Blokkok színezése
    if len(gdf_blocks_p) > 0:
        gdf_blocks_p.plot(ax=ax, color=block_colors, linewidth=0)

    # Utcák
    gdf_edges_p.plot(ax=ax, color=style.road, linewidth=scaled_road_width, alpha=1.0)

    # Hidak (ugyanazzal a skálázott vastagsággal)
    if "bridge" in gdf_edges.columns:
        bridges = gdf_edges[gdf_edges["bridge"].notna()].copy()
        if len(bridges) > 0:
            ox.projection.project_gdf(bridges).plot(
                ax=ax,
                color=style.bridge,
                linewidth=scaled_road_width,
                alpha=1.0,
            )

    # Frame pereme “utca”
    gpd.GeoSeries([rect_boundary], crs=gdf_edges_p.crs).plot(
        ax=ax,
        color=style.road,
        linewidth=scaled_road_width,
        alpha=1.0,
    )

    # Víz – legfelül
    if water_union is not None:
        gpd.GeoSeries([water_union], crs=gdf_edges_p.crs).plot(
            ax=ax,
            color=style.water,
            edgecolor=style.water,
            linewidth=0,
        )

    # Nézet: pontosan a frame
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()

    # 8) Mentés PDF (timestampes név)
    print("Saving PDF to:", output_pdf)
    fig.savefig(output_pdf, format="pdf", dpi=spec.dpi, bbox_inches="tight")
    plt.close(fig)

    return RenderResult(output_pdf=output_pdf)


def weighted_palette_choice(palette: List[str]) -> str:
    """
    (Jelenleg nem használod, de meghagyható.)
    Világos színek dominálnak, sötétek ritkák.
    """
    weights = [6, 5, 4, 3, 2, 1, 0.5]
    return random.choices(palette, weights=weights, k=1)[0]
